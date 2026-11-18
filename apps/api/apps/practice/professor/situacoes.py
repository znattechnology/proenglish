"""
Área do professor: situações da conversa com o tutor e resultados da fala.

  GET    /api/v1/teacher/situacoes/?tipo=conversa|todas
  POST   /api/v1/teacher/situacoes/
  GET    /api/v1/teacher/situacoes/opcoes/
  GET    /api/v1/teacher/situacoes/<id>/
  PATCH  /api/v1/teacher/situacoes/<id>/
  DELETE /api/v1/teacher/situacoes/<id>/       (só sem conversas; senão 409: desligue-a)
  GET    /api/v1/teacher/resultados/fala/?periodo=7|30|90|365

A lista mostra as situações do professor e as da plataforma (só leitura, minha=false).
As de outros professores não existem (404). Alterar uma da plataforma: 403 (só o administrador).
Uma situação sem curso é "Geral": a da plataforma vê-se por todos os alunos; a de um professor,
pelos alunos de qualquer curso dele (ver conversa/situacoes.situacoes_visiveis).
"""
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.practice.actividade import alunos_dos_cursos
from apps.practice.conversa.situacoes import AREA_IDS
from apps.practice.models import Situacao, VapiSession

from .comum import (
    PERMISSOES, _erro, corpo, curso_api, cursos_do_professor, e_minha, erro_sem_permissao,
    erro_validacao, ler_curso, obter_visivel, texto,
)

NOMES_NIVEIS = {
    'A1': 'A1 · Iniciante', 'A2': 'A2 · Elementar', 'B1': 'B1 · Intermédio',
    'B2': 'B2 · Intermédio superior', 'C1': 'C1 · Avançado', 'C2': 'C2 · Proficiente',
}
AREA_POR_CATEGORIA = {
    'Industry English': 'petroleum', 'Oil & Gas': 'petroleum',
    'Technical English': 'IT', 'Technology English': 'IT', 'Technology': 'IT',
    'Business English': 'business', 'Financial English': 'business', 'Banking': 'business',
    'Executive': 'business',
}
PERIODOS = (7, 30, 90, 365)
COMPETENCIAS = [
    ('Fluência', 'fluency_score'),
    ('Gramática', 'grammar_score'),
    ('Vocabulário', 'vocabulary_score'),
]  # a pronúncia não é medida nas conversas (só há texto): fica de fora
MAX_FRASES = 10


def _r(v):
    return None if v is None else round(v)


def _visiveis(request):
    return Situacao.objects.filter(Q(criado_por__isnull=True) | Q(criado_por=request.user))


def _numeros(slugs):
    """{slug: (sessoes terminadas, media das avaliadas)}"""
    out = {}
    for r in (VapiSession.objects.filter(situation__in=list(slugs), status__in=VapiSession.STATUS_TERMINADAS)
              .values('situation')
              .annotate(n=Count('session_id'),
                        media=Avg('overall_score', filter=Q(status=VapiSession.STATUS_AVALIADA)))):
        out[r['situation']] = (r['n'], _r(r['media']))
    return out


def _item(request, s, numeros):
    n, media = numeros.get(s.slug, (0, None))
    return {
        'id': s.pk,
        'nome': s.nome,
        'tipo': 'conversa',
        'curso': curso_api(s.curso),
        'nivel': s.nivel,
        'estado': s.estado,
        'sessoes': n,
        'pontuacao_media': media,
        'minha': e_minha(request, s),
    }


def _detalhe(request, s):
    item = _item(request, s, _numeros([s.slug]))
    item.update({
        'descricao': s.descricao,
        'papel_tutor': s.papel_tutor,
        'frases': [f if isinstance(f, str) else str(f) for f in (s.frases or [])],
        'area': s.area,
        'duracao_min': s.duracao_min,
        'correccao': s.correccao,
        'aula': ({'id': str(s.aula_id), 'titulo': s.aula.title} if s.aula_id else None),
        'tipo_conversa': s.tipo_conversa or None,
        'criada_em': s.created_at.isoformat(),
        'actualizada_em': s.updated_at.isoformat(),
    })
    return item


def _validar(request, dados, parcial, erros):
    """Campos validados (só os enviados, em PATCH)."""
    limpos = {}

    def quer(campo):
        return not parcial or campo in dados

    if quer('nome'):
        limpos['nome'] = texto(dados, 'nome', erros, 3, 80, 'o nome da situação')
    if quer('descricao'):
        limpos['descricao'] = texto(dados, 'descricao', erros, 10, 600, 'o que acontece na situação')
    if quer('papel_tutor'):
        limpos['papel_tutor'] = texto(dados, 'papel_tutor', erros, 3, 200, 'o papel do tutor')
    if quer('frases'):
        # Frases-alvo opcionais (0 a MAX_FRASES); as vazias são ignoradas.
        frases = dados.get('frases', [])
        if frases is None:
            frases = []
        if not isinstance(frases, list) or any(f is not None and not isinstance(f, str) for f in frases):
            erros['frases'] = 'As frases-alvo têm de ser uma lista de textos.'
        else:
            frases = [' '.join(f.split()) for f in frases if f and f.strip()]
            if len(frases) > MAX_FRASES:
                erros['frases'] = f'Pode indicar no máximo {MAX_FRASES} frases-alvo.'
            elif any(len(f) > 160 for f in frases):
                erros['frases'] = 'Cada frase-alvo pode ter no máximo 160 caracteres.'
            else:
                limpos['frases'] = frases
    if quer('curso'):
        limpos['curso'] = ler_curso(request, dados.get('curso'), erros)
    if quer('nivel'):
        if dados.get('nivel') not in Situacao.NIVEIS:
            erros['nivel'] = 'Escolha um nível de A1 a C2.'
        else:
            limpos['nivel'] = dados['nivel']
    if quer('duracao_min'):
        if dados.get('duracao_min') not in Situacao.DURACOES or isinstance(dados.get('duracao_min'), bool):
            erros['duracao_min'] = 'Escolha uma duração de 3, 5 ou 10 minutos.'
        else:
            limpos['duracao_min'] = dados['duracao_min']
    if 'correccao' in dados or not parcial:
        valor = dados.get('correccao', 'suave' if not parcial else None)
        if valor not in Situacao.CORRECCOES:
            erros['correccao'] = 'Escolha a correcção «suave» ou «directa».'
        else:
            limpos['correccao'] = valor
    if 'estado' in dados or not parcial:
        valor = dados.get('estado', Situacao.RASCUNHO if not parcial else None)
        if valor not in Situacao.ESTADOS:
            erros['estado'] = 'O estado tem de ser «rascunho» ou «activo».'
        else:
            limpos['estado'] = valor
    if 'tipo_conversa' in dados:
        valor = dados.get('tipo_conversa') or ''
        if valor not in ('', *Situacao.TIPOS_CONVERSA):
            erros['tipo_conversa'] = 'O tipo de conversa tem de ser «guiada» ou «livre».'
        else:
            limpos['tipo_conversa'] = valor
    if 'aula' in dados:
        # A aula depois da qual o aluno faz a conversa: tem de ser de um curso do professor
        # (e do curso da situação: verificado em _aula_do_curso, depois de se saber o curso).
        valor = dados.get('aula')
        if valor in (None, ''):
            limpos['aula'] = None
        else:
            from apps.courses.models import Chapter
            try:
                limpos['aula'] = Chapter.objects.select_related('section').get(
                    pk=valor, section__course__in=cursos_do_professor(request.user))
            except (Chapter.DoesNotExist, ValueError, TypeError, DjangoValidationError):
                erros['aula'] = 'Aula não encontrada nos seus cursos.'
    if 'area' in dados:
        if dados.get('area') not in AREA_IDS:
            erros['area'] = 'Área inválida.'
        else:
            limpos['area'] = dados['area']
    return {k: v for k, v in limpos.items() if k not in erros}


def _aula_do_curso(aula, curso):
    """Mensagem de erro se a aula não é do curso da situação (None se está bem)."""
    if aula is None:
        return None
    if curso is None or aula.section.course_id != curso.id:
        return 'A aula tem de ser do curso desta situação.'
    return None


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def lista(request):
    if request.method == 'POST':
        return _criar(request)
    tipo = request.query_params.get('tipo') or 'todas'
    if tipo not in ('todas', 'conversa'):
        return _erro('Tipo inválido. Use "conversa" ou "todas".', 'tipo_invalido', details={'tipo': tipo})
    situacoes = list(_visiveis(request).select_related('curso').order_by('-criado_por_id', 'ordem', '-created_at'))
    numeros = _numeros([s.slug for s in situacoes])
    # As do professor primeiro (mais recentes no topo); depois as da plataforma.
    situacoes.sort(key=lambda s: (s.criado_por_id is None, s.ordem if s.criado_por_id is None else 0,
                                  -s.created_at.timestamp()))
    return Response({'resultados': [_item(request, s, numeros) for s in situacoes]})


def _criar(request):
    dados = corpo(request)
    erros = {}
    limpos = _validar(request, dados, False, erros)
    if erros:
        return erro_validacao(erros)
    curso = limpos.get('curso')
    erro_aula = _aula_do_curso(limpos.get('aula'), curso)
    if erro_aula:
        return erro_validacao({'aula': erro_aula})
    if 'area' not in limpos:
        limpos['area'] = AREA_POR_CATEGORIA.get(getattr(curso, 'category', ''), 'general')
    s = Situacao.objects.create(slug=f'p-{uuid.uuid4().hex[:16]}', criado_por=request.user, **limpos)
    return Response(_detalhe(request, s), status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def detalhe(request, situacao_id):
    s = obter_visivel(request, Situacao.objects.select_related('curso'), situacao_id, 'Situação não encontrada.')
    if request.method == 'GET':
        return Response(_detalhe(request, s))
    proibido = erro_sem_permissao(request, s)
    if proibido:
        return proibido
    if request.method == 'DELETE':
        if VapiSession.objects.filter(situation=s.slug).exists():
            return _erro('Esta situação já tem conversas e não pode ser apagada. Para a retirar aos alunos, '
                         'desligue-a (passe-a a rascunho).', 'tem_sessoes', 409)
        s.delete()
        return Response(status=204)
    dados = corpo(request)
    erros = {}
    limpos = _validar(request, dados, True, erros)
    if erros:
        return erro_validacao(erros)
    erro_aula = _aula_do_curso(limpos.get('aula', s.aula), limpos.get('curso', s.curso))
    if erro_aula:
        return erro_validacao({'aula': erro_aula})
    for campo, valor in limpos.items():
        setattr(s, campo, valor)
    s.save()
    return Response(_detalhe(request, s))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def opcoes(request):
    from apps.courses.models import Chapter
    from apps.practice.conversa.situacoes import AREAS

    cursos = cursos_do_professor(request.user)
    # As aulas de cada curso em vídeo, pela ordem do curso: para ligar a conversa a uma aula
    # (o aluno faz a conversa depois dessa aula, no percurso do curso).
    aulas = {}
    for a in (Chapter.objects.filter(section__course__in=cursos, section__course__course_type='video')
              .exclude(type='Quiz').select_related('section')
              .order_by('section__order', 'section__created_at', 'order', 'created_at')):
        aulas.setdefault(str(a.section.course_id), []).append(
            {'id': str(a.id), 'titulo': a.title, 'unidade': a.section.sectionTitle})
    return Response({
        'cursos': [curso_api(c) for c in cursos],
        'aulas': aulas,
        'niveis': [{'valor': n, 'nome': NOMES_NIVEIS[n]} for n in Situacao.NIVEIS],
        'duracoes': list(Situacao.DURACOES),
        'correccoes': [{'valor': 'suave', 'nome': 'Suave'}, {'valor': 'directa', 'nome': 'Directa'}],
        'areas': [{'valor': a['id'], 'nome': a['nome']} for a in AREAS],
    })


# ---------------------------------------------------------------------------
# GET /teacher/resultados/fala/
# ---------------------------------------------------------------------------

def sessoes_do_professor(user):
    """
    Conversas que contam para os resultados da fala do professor:
    - todas as conversas nas situações criadas por ele (de qualquer aluno que as possa ver);
    - as conversas dos alunos dos cursos dele nas situações da plataforma.
    Conversas noutras situações (de outros professores) não contam.
    """
    from apps.courses.models import Course

    minhas = list(Situacao.objects.filter(criado_por=user).values_list('slug', flat=True))
    plataforma = list(Situacao.objects.filter(criado_por__isnull=True).values_list('slug', flat=True))
    alunos = alunos_dos_cursos(Course.objects.filter(teacher=user).values_list('id', flat=True))
    return VapiSession.objects.filter(
        Q(situation__in=minhas) | Q(situation__in=plataforma, user_id__in=list(alunos)))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def resultados_fala(request):
    """
    Números da conversa com o tutor no período (dias, até agora), sobre sessoes_do_professor:
    - minutos / sessoes: conversas terminadas (avaliadas, sem avaliação ou a avaliar);
    - minutos_variacao_pct: contra o período anterior com a mesma duração (null se antes era 0);
    - pontuacao_media e competencias: médias das conversas avaliadas (Fluência, Gramática e
      Vocabulário; media null quando não há conversas avaliadas). A pronúncia não é medida nas
      conversas, por isso não aparece;
    - terminam_pct: das conversas que ligaram (sem as que ainda estão em curso), quantas chegaram
      à avaliação com conteúdo suficiente.
    """
    try:
        periodo = int(request.query_params.get('periodo') or 30)
    except ValueError:
        periodo = None
    if periodo not in PERIODOS:
        return _erro('Período inválido. Use 7, 30, 90 ou 365 dias.', 'periodo_invalido',
                     details={'periodo': request.query_params.get('periodo')})
    agora = timezone.now()
    desde = agora - timedelta(days=periodo)
    base = sessoes_do_professor(request.user)
    no_periodo = base.filter(created_at__gte=desde, created_at__lt=agora)
    terminadas = no_periodo.filter(status__in=VapiSession.STATUS_TERMINADAS)
    avaliadas = no_periodo.filter(status=VapiSession.STATUS_AVALIADA)

    agg = terminadas.aggregate(n=Count('session_id'), minutos=Sum('duration_minutes'))
    minutos = agg['minutos'] or 0
    anteriores = (base.filter(created_at__gte=desde - timedelta(days=periodo), created_at__lt=desde,
                              status__in=VapiSession.STATUS_TERMINADAS)
                  .aggregate(m=Sum('duration_minutes'))['m'] or 0)
    variacao = round((minutos - anteriores) * 100.0 / anteriores) if anteriores else None

    medias = avaliadas.aggregate(geral=Avg('overall_score'), **{c: Avg(c) for _, c in COMPETENCIAS})
    ligaram = no_periodo.exclude(status__in=[VapiSession.STATUS_EM_CURSO, VapiSession.STATUS_NAO_LIGOU]).count()
    terminam = round(avaliadas.count() * 100.0 / ligaram) if ligaram else None

    por_slug = {r['situation']: r for r in terminadas.values('situation').annotate(
        n=Count('session_id'), media=Avg('overall_score', filter=Q(status=VapiSession.STATUS_AVALIADA)))}
    situacoes = []
    for s in Situacao.objects.filter(slug__in=list(por_slug)):
        r = por_slug[s.slug]
        situacoes.append({'id': s.pk, 'nome': s.nome, 'sessoes': r['n'], 'media': _r(r['media'])})
    situacoes.sort(key=lambda x: (-x['sessoes'], x['nome']))

    n = agg['n'] or 0
    return Response({
        'periodo': periodo,
        'minutos': minutos,
        'minutos_variacao_pct': variacao,
        'sessoes': n,
        'sessoes_por_dia': round(n / periodo, 1),
        'pontuacao_media': _r(medias['geral']),
        'terminam_pct': terminam,
        'competencias': [{'nome': nome, 'media': _r(medias[campo])} for nome, campo in COMPETENCIAS],
        'situacoes': situacoes,
    })
