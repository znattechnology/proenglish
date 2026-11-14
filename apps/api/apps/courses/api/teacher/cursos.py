"""
Área do professor (base nova): painel, lista de cursos, definições e ciclo de vida.

  GET   /api/v1/teacher/painel/
  GET   /api/v1/teacher/cursos/?tipo=video|pratica&estado=rascunho|em_revisao|publicado|arquivado
  POST  /api/v1/teacher/cursos/                      (criar; ver editor_video.py)
  GET   /api/v1/teacher/cursos/<id>/                 (item + descrição + definições)
  PATCH /api/v1/teacher/cursos/<id>/                 (dados e definições; lista fechada de campos)
  GET   /api/v1/teacher/cursos/<id>/verificacao/     (lista de verificação, sem mudar o estado)
  POST  /api/v1/teacher/cursos/<id>/submeter/        (-> em_revisao, ou 400 com a lista)
  POST  /api/v1/teacher/cursos/<id>/cancelar-revisao/ (em_revisao -> rascunho)
  POST  /api/v1/teacher/cursos/<id>/arquivar/        {modo: manter|fechar}

Só o professor dono do curso (ou um administrador, ver apps.core.permissions.e_administrador) vê e mexe;
os outros recebem 404. Um professor marcado com PerfilProfessor.publica_sem_revisao publica ao submeter.
Os números são calculados com poucas consultas agregadas (sem N+1).
"""
from collections import defaultdict
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Exists, Max, Min, OuterRef, Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.courses import ciclo, niveis
from apps.courses.models import (
    Chapter, Course, CourseEnrollment, CourseSection, UserCourseProgress,
)

logger = logging.getLogger(__name__)


class EProfessorOuStaff(permissions.BasePermission):
    message = 'Apenas professores podem aceder a esta área.'

    def has_permission(self, request, view):
        return ciclo.e_professor(request.user) or ciclo.e_staff(request.user)


PERMISSOES = [permissions.IsAuthenticated, EProfessorOuStaff]


def _erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details, **extra), status=status_http)


def _curso_do_professor(request, curso_id):
    """O curso, se for do professor (ou se quem pede for administrador); senão 404."""
    curso = Course.objects.filter(id=curso_id).select_related('teacher').first()
    if curso is None or not ciclo.e_dono_ou_staff(request.user, curso):
        raise NotFound('Curso não encontrado.')
    return curso


class _QuebraCurso(Exception):
    def __init__(self, resposta):
        super().__init__('quebra_curso')
        self.resposta = resposta


def _lista_guarda(curso):
    # Num curso publicado as aulas escondidas (sem vídeo) não contam: os alunos não as vêem.
    return ciclo.verificar(curso, so_visiveis=curso.status == ciclo.PUBLICADO, com_avisos=False)


def guardar_publicado(curso, alterar):
    """
    Corre alterar() numa transacção. Num curso publicado ou em revisão, se a alteração deixar por
    cumprir um item da lista de verificação que estava cumprido, desfaz tudo e devolve 409
    (code "quebra_curso"). As alterações a um curso publicado ficam logo visíveis aos alunos,
    por isso não se aceitam as que o deixariam incompleto.
    """
    protegido = curso.status in (ciclo.PUBLICADO, ciclo.EM_REVISAO)
    # "Antes" lido da base de dados: o objecto pode já trazer as alterações do pedido em memória.
    antes = ({i['chave']: i['ok'] for i in _lista_guarda(Course.objects.get(pk=curso.pk))['itens']}
             if protegido else {})
    try:
        with transaction.atomic():
            resultado = alterar()
            if protegido:
                depois = _lista_guarda(curso)
                quebrados = [i for i in depois['itens'] if not i['ok'] and antes.get(i['chave'])]
                if quebrados:
                    raise _QuebraCurso(_resposta_quebra(curso, quebrados, depois))
    except _QuebraCurso as e:
        return e.resposta
    return resultado


def _resposta_quebra(curso, quebrados, verificacao):
    onde = 'publicado' if curso.status == ciclo.PUBLICADO else 'em revisão'
    motivo = quebrados[0]['detalhe'] if quebrados[0].get('detalhe') else quebrados[0]['titulo']
    mensagem = (f'Este curso está {onde} e esta alteração deixava-o incompleto ({quebrados[0]["titulo"].lower()}): '
                f'{motivo} Corrija primeiro ou arquive o curso.')
    return _erro(mensagem, 'quebra_curso', 409,
                 details={'itens': quebrados, 'verificacao': verificacao})


def _pct(v):
    return None if v is None else round(float(v), 1)


# ---------------------------------------------------------------------------
# Números por curso (consultas agregadas)
# ---------------------------------------------------------------------------

def metricas(cursos):
    """
    {course_id: {...}} com alunos, conclusao, aulas, seccoes, unidades, licoes, exercicios,
    acerto e a última actividade. Também devolve, em '_alunos_por_tipo', os ids dos alunos.
    Alunos = contas com papel student: vídeo, inscrições activas; prática, quem respondeu a exercícios.
    """
    from apps.practice.models import (
        ChallengeAttempt, ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit,
    )

    video = [c.id for c in cursos if c.course_type != 'practice']
    pratica = [c.id for c in cursos if c.course_type == 'practice']
    m = {c.id: {
        'alunos': 0, 'conclusao': None, 'aulas': None, 'aulas_sem_video': None, 'seccoes': None,
        'unidades': None, 'licoes': None, 'exercicios': None, 'acerto': None,
        'certas': 0, 'tentativas': 0, 'ultima': c.updated_at,
    } for c in cursos}

    def _ultima(cid, quando):
        if quando and (m[cid]['ultima'] is None or quando > m[cid]['ultima']):
            m[cid]['ultima'] = quando

    if video:
        for cid in video:
            m[cid].update({'aulas': 0, 'aulas_sem_video': 0, 'seccoes': 0})
        for r in CourseSection.objects.filter(course_id__in=video).values('course_id').annotate(n=Count('id')):
            m[r['course_id']]['seccoes'] = r['n']
        for r in (Chapter.objects.filter(section__course_id__in=video).values('section__course_id')
                  .annotate(n=Count('id'), sem=Count('id', filter=Q(type='Video', video='')))):
            m[r['section__course_id']]['aulas'] = r['n']
            m[r['section__course_id']]['aulas_sem_video'] = r['sem']
        for r in (CourseEnrollment.objects.filter(course_id__in=video, is_active=True, user__role='student')
                  .values('course_id').annotate(n=Count('user_id', distinct=True))):
            m[r['course_id']]['alunos'] = r['n']
        activa = CourseEnrollment.objects.filter(
            user_id=OuterRef('user_id'), course_id=OuterRef('course_id'), is_active=True, user__role='student')
        for r in (UserCourseProgress.objects.filter(course_id__in=video).filter(Exists(activa))
                  .values('course_id').annotate(media=Avg('overallProgress'), ult=Max('lastAccessedTimestamp'))):
            if m[r['course_id']]['alunos']:
                m[r['course_id']]['conclusao'] = _pct(r['media'])
            _ultima(r['course_id'], r['ult'])

    if pratica:
        for cid in pratica:
            m[cid].update({'unidades': 0, 'licoes': 0, 'exercicios': 0})
        for r in PracticeUnit.objects.filter(course_id__in=pratica).values('course_id').annotate(n=Count('id')):
            m[r['course_id']]['unidades'] = r['n']
        for r in (PracticeLesson.objects.filter(unit__course_id__in=pratica)
                  .values('unit__course_id').annotate(n=Count('id'))):
            m[r['unit__course_id']]['licoes'] = r['n']
        por_licao = {}
        for r in (PracticeChallenge.objects.filter(lesson__unit__course_id__in=pratica)
                  .values('lesson_id', 'lesson__unit__course_id').annotate(n=Count('id'))):
            por_licao[r['lesson_id']] = r['n']
            m[r['lesson__unit__course_id']]['exercicios'] += r['n']
        for r in (ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=pratica, user__role='student')
                  .values('challenge__lesson__unit__course_id')
                  .annotate(n=Count('user_id', distinct=True), ult=Max('updated_at'))):
            m[r['challenge__lesson__unit__course_id']]['alunos'] = r['n']
            _ultima(r['challenge__lesson__unit__course_id'], r['ult'])
        # Conclusão: lições com todos os exercícios feitos / lições do curso, por aluno.
        feitas = defaultdict(lambda: defaultdict(int))  # curso -> aluno -> lições feitas
        alunos_curso = defaultdict(set)
        for r in (ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=pratica, user__role='student')
                  .values('user_id', 'challenge__lesson_id', 'challenge__lesson__unit__course_id')
                  .annotate(c=Count('challenge_id', distinct=True, filter=Q(completed=True)))):
            cid = r['challenge__lesson__unit__course_id']
            alunos_curso[cid].add(r['user_id'])
            total = por_licao.get(r['challenge__lesson_id'], 0)
            if total and r['c'] >= total:
                feitas[cid][r['user_id']] += 1
        for cid, alunos in alunos_curso.items():
            licoes = m[cid]['licoes'] or 0
            if alunos and licoes:
                m[cid]['conclusao'] = _pct(sum(feitas[cid][u] for u in alunos) * 100.0 / (licoes * len(alunos)))
        for r in (ChallengeAttempt.objects.filter(challenge__lesson__unit__course_id__in=pratica)
                  .values('challenge__lesson__unit__course_id')
                  .annotate(t=Count('id'), certas=Count('id', filter=Q(is_correct=True)), ult=Max('created_at'))):
            cid = r['challenge__lesson__unit__course_id']
            m[cid]['tentativas'] = r['t']
            m[cid]['certas'] = r['certas']
            m[cid]['acerto'] = _pct(r['certas'] * 100.0 / r['t']) if r['t'] else None
            _ultima(cid, r['ult'])
    return m


def item_curso(c, mc):
    return {
        'id': str(c.id),
        'tipo': ciclo.tipo_api(c),
        'titulo': c.title,
        'area': ciclo.area_pt(c.category),
        'nivel': ciclo.nivel_pt(c.level),
        'estado': ciclo.estado(c),
        'motivo_recusa': c.motivo_recusa or None,
        # Última decisão do administrador (recusa ou arquivamento), mesmo com o curso arquivado.
        'motivo_moderacao': c.motivo_moderacao or None,
        'moderacao': ({'accao': c.moderacao_accao or None, 'motivo': c.motivo_moderacao,
                       'em': c.moderado_em.isoformat() if c.moderado_em else None}
                      if c.motivo_moderacao else None),
        'imagem': c.image or None,
        'alunos': mc['alunos'],
        'conclusao': mc['conclusao'] if mc['alunos'] else None,
        'aulas': mc['aulas'],
        'aulas_sem_video': mc['aulas_sem_video'],
        'seccoes': mc['seccoes'],
        'unidades': mc['unidades'],
        'licoes': mc['licoes'],
        'exercicios': mc['exercicios'],
        'acerto': mc['acerto'],
        'actualizado_em': c.updated_at.isoformat() if c.updated_at else None,
    }


def _contagem_estados(cursos):
    contagem = defaultdict(int)
    for c in cursos:
        contagem[c.status] += 1
    return {
        'publicados': contagem[ciclo.PUBLICADO],
        'rascunhos': contagem[ciclo.RASCUNHO],
        'em_revisao': contagem[ciclo.EM_REVISAO],
        'arquivados': contagem[ciclo.ARQUIVADO],
    }


def _ids_alunos(video, pratica, desde=None):
    """Conjunto de ids de alunos dos cursos (opcionalmente só os activos desde `desde`)."""
    from apps.courses.models import VideoWatchLog
    from apps.practice.models import ChallengeAttempt, ChallengeProgress

    ids = set()
    if video:
        if desde is None:
            ids |= set(CourseEnrollment.objects.filter(course_id__in=video, is_active=True)
                       .values_list('user_id', flat=True).distinct())
        else:
            ids |= set(UserCourseProgress.objects.filter(course_id__in=video, lastAccessedTimestamp__gte=desde)
                       .values_list('user_id', flat=True).distinct())
            ids |= set(VideoWatchLog.objects.filter(chapter__section__course_id__in=video, date__gte=desde.date())
                       .values_list('user_id', flat=True).distinct())
    if pratica:
        qs = ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=pratica)
        if desde is not None:
            qs = qs.filter(updated_at__gte=desde)
            ids |= set(ChallengeAttempt.objects.filter(challenge__lesson__unit__course_id__in=pratica,
                                                       created_at__gte=desde)
                       .values_list('user_id', flat=True).distinct())
        ids |= set(qs.values_list('user_id', flat=True).distinct())
    return ids


def _alunos_novos_mes(video, pratica):
    from apps.practice.models import ChallengeProgress

    agora = timezone.localtime()
    inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ids = set()
    if video:
        ids |= set(CourseEnrollment.objects.filter(course_id__in=video, enrollment_date__gte=inicio)
                   .values_list('user_id', flat=True).distinct())
    if pratica:
        ids |= set(ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=pratica)
                   .values('user_id').annotate(primeiro=Min('completed_at'))
                   .filter(primeiro__gte=inicio).values_list('user_id', flat=True))
    return len(ids)


def _conclusao_media(cursos, m):
    soma = n = 0
    for c in cursos:
        mc = m[c.id]
        if mc['alunos'] and mc['conclusao'] is not None:
            soma += mc['conclusao'] * mc['alunos']
            n += mc['alunos']
    return _pct(soma / n) if n else None


def numeros_cursos(cursos, m, tipo):
    video = [c.id for c in cursos if c.course_type != 'practice']
    pratica = [c.id for c in cursos if c.course_type == 'practice']
    numeros = _contagem_estados(cursos)
    numeros.update({
        'alunos': len(_ids_alunos(video, pratica)),
        'alunos_novos_mes': _alunos_novos_mes(video, pratica),
        'conclusao_media': _conclusao_media(cursos, m),
    })
    if tipo in (None, 'video'):
        # "Aulas publicadas": aulas que os alunos vêem (com vídeo) nos cursos publicados.
        publicados = {c.id for c in cursos if c.status == ciclo.PUBLICADO and c.course_type != 'practice'}
        numeros['aulas'] = sum((m[c]['aulas'] or 0) - (m[c]['aulas_sem_video'] or 0) for c in publicados)
        numeros['aulas_total'] = sum(m[c]['aulas'] or 0 for c in video)
        numeros['seccoes'] = sum(m[c]['seccoes'] or 0 for c in video)
    if tipo in (None, 'pratica'):
        numeros['licoes'] = sum(m[c]['licoes'] or 0 for c in pratica)
        numeros['exercicios'] = sum(m[c]['exercicios'] or 0 for c in pratica)
        tentativas = sum(m[c]['tentativas'] for c in pratica)
        certas = sum(m[c]['certas'] for c in pratica)
        numeros['acerto_medio'] = _pct(certas * 100.0 / tentativas) if tentativas else None
    return numeros


def _cursos_do_pedido(request):
    return list(Course.objects.filter(teacher=request.user).order_by('-updated_at'))


# ---------------------------------------------------------------------------
# GET /teacher/cursos/
# ---------------------------------------------------------------------------

TIPOS = {'video': 'video', 'pratica': 'practice'}


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def lista_cursos(request):
    if request.method == 'POST':
        from .editor_video import criar_curso
        return criar_curso(request)
    tipo = request.query_params.get('tipo') or None
    if tipo and tipo not in TIPOS:
        return _erro('Tipo inválido. Use "video" ou "pratica".', 'tipo_invalido', details={'tipo': ['Use "video" ou "pratica".']})
    estado = request.query_params.get('estado') or None
    if estado and estado not in ciclo.API_ESTADO:
        return _erro('Estado inválido. Use rascunho, em_revisao, publicado ou arquivado.', 'estado_invalido',
                     details={'estado': ['Use rascunho, em_revisao, publicado ou arquivado.']})

    cursos = _cursos_do_pedido(request)
    if tipo:
        cursos = [c for c in cursos if (c.course_type == 'practice') == (tipo == 'pratica')]
    m = metricas(cursos)
    numeros = numeros_cursos(cursos, m, tipo)
    if estado:
        cursos = [c for c in cursos if c.status == ciclo.API_ESTADO[estado]]
    return Response({'numeros': numeros, 'resultados': [item_curso(c, m[c.id]) for c in cursos]})


# ---------------------------------------------------------------------------
# GET /teacher/painel/
# ---------------------------------------------------------------------------

def tropecos(user, desde, limite=5):
    from apps.practice.models import ChallengeAttempt, PracticeChallenge, PracticeLesson, PracticeUnit

    linhas = list(
        ChallengeAttempt.objects.filter(challenge__lesson__unit__course__teacher=user, created_at__gte=desde)
        .values('challenge_id')
        .annotate(total=Count('id'), erros=Count('id', filter=Q(is_correct=False)))
        .filter(erros__gt=0)
        .order_by('-erros', '-total')[:limite]
    )
    if not linhas:
        return []
    exercicios = {ch.id: ch for ch in PracticeChallenge.objects.filter(id__in=[l['challenge_id'] for l in linhas])
                  .select_related('lesson__unit__course')}
    cursos = {ch.lesson.unit.course_id for ch in exercicios.values()}
    unidades = defaultdict(list)
    for u in PracticeUnit.objects.filter(course_id__in=cursos).order_by('order', 'id').values('id', 'course_id'):
        unidades[u['course_id']].append(u['id'])
    unidades_ids = {ch.lesson.unit_id for ch in exercicios.values()}
    licoes = defaultdict(list)
    for l in PracticeLesson.objects.filter(unit_id__in=unidades_ids).order_by('order', 'id').values('id', 'unit_id'):
        licoes[l['unit_id']].append(l['id'])

    resultado = []
    for linha in linhas:
        ch = exercicios.get(linha['challenge_id'])
        if ch is None:
            continue
        licao, unidade = ch.lesson, ch.lesson.unit
        n_unidade = unidades[unidade.course_id].index(unidade.id) + 1 if unidade.id in unidades[unidade.course_id] else unidade.order
        n_licao = licoes[unidade.id].index(licao.id) + 1 if licao.id in licoes[unidade.id] else licao.order
        resultado.append({
            'challenge_id': str(ch.id),
            'frase': (ch.question or '').strip() or ciclo.TIPOS_EXERCICIO.get(ch.type, ch.type),
            'tipo': ciclo.TIPOS_EXERCICIO.get(ch.type, ch.type),
            'curso_id': str(unidade.course_id),
            'curso': unidade.course.title,
            'unidade_id': str(unidade.id),
            'licao_id': str(licao.id),
            'onde': f'Unidade {n_unidade}, lição {n_licao}',
            'erros': linha['erros'],
            'acerto': round((linha['total'] - linha['erros']) * 100 / linha['total']),
        })
    return resultado


@api_view(['GET'])
@permission_classes(PERMISSOES)
def painel(request):
    cursos = _cursos_do_pedido(request)
    m = metricas(cursos)
    video = [c.id for c in cursos if c.course_type != 'practice']
    pratica = [c.id for c in cursos if c.course_type == 'practice']
    agora = timezone.now()
    numeros = _contagem_estados(cursos)
    numeros.update({
        'alunos': len(_ids_alunos(video, pratica)),
        'alunos_activos_7d': len(_ids_alunos(video, pratica, desde=agora - timedelta(days=7))),
        'conclusao_media': _conclusao_media(cursos, m),
    })
    recentes = sorted(cursos, key=lambda c: m[c.id]['ultima'] or c.updated_at, reverse=True)[:8]
    return Response({
        'numeros': numeros,
        'cursos': [item_curso(c, m[c.id]) for c in recentes],
        'tropecos': tropecos(request.user, agora - timedelta(days=7)),
    })


# ---------------------------------------------------------------------------
# GET/PATCH /teacher/cursos/<id>/
# ---------------------------------------------------------------------------

CAMPOS_PROIBIDOS = {'status', 'estado', 'is_featured', 'course_type', 'tipo', 'teacher', 'teacher_id',
                    'teacherName', 'access_level', 'aprovado_em', 'aprovado_por', 'motivo_recusa'}
BOOLEANOS = ('visivel_catalogo', 'inscricao_livre', 'pode_repetir', 'mostrar_progresso',
             'resumo_semanal', 'certificado_automatico')
SINONIMOS = {
    'title': 'titulo', 'description': 'descricao', 'category': 'area', 'categoria': 'area',
    'level': 'nivel', 'image': 'imagem',
}


ACESSO_API = {'free': 'todos', 'premium': 'premium', 'premium_plus': 'premium'}


def _definicoes_exame(c):
    """Exame oral do curso (fase 6): obrigatório para o certificado e nota mínima para passar."""
    from apps.courses.models import CourseGradingConfig
    config = CourseGradingConfig.objects.filter(course=c).first()
    if config is None:
        config = CourseGradingConfig(course=c)  # valores por omissão, não gravado
    pesos = ((config.exam_weight or 0) + (config.phrases_weight or 0) + (config.conversation_weight or 0)
             + (config.study_weight or 0))
    return {
        'exame_oral': config.exam_enabled,
        'nota_minima_exame': int(round(config.min_exam_score)),
        # Só leitura: quanto vale o exame na nota (peso configurado sobre o total dos pesos).
        'peso_exame': round((config.exam_weight or 0) * 100 / pesos) if pesos else 0,
    }


def detalhe_curso(c, mc=None):
    from apps.courses.certificados import nota_minima
    mc = mc or metricas([c])[c.id]
    dados = item_curso(c, mc)
    dados.update({
        'descricao': c.description,
        'categoria': c.category,
        'nivel_codigo': niveis.normalizar(c.level) or c.level,
        'submetido_em': c.submetido_em.isoformat() if c.submetido_em else None,
        'aprovado_em': c.aprovado_em.isoformat() if c.aprovado_em else None,
        'acesso': ACESSO_API.get(c.access_level, 'todos'),
        'modo_arquivo': c.modo_arquivo or None,
        'estado_antes_revisao': ciclo.ESTADO_API.get(c.estado_antes_revisao) if c.status == ciclo.EM_REVISAO else None,
        'arquivado_em': c.arquivado_em.isoformat() if c.arquivado_em else None,
        'definicoes': {
            'visivel_catalogo': c.visivel_catalogo,
            'inscricao_livre': c.inscricao_livre,
            'maximo_alunos': c.maximo_alunos,
            'nota_minima': int(round(nota_minima(c))),
            **_definicoes_exame(c),
            **ciclo.definicoes(c),
        },
    })
    return dados


def _inteiro_ou_nulo(valor, minimo, maximo, campo, erros):
    if valor in (None, ''):
        return None
    if isinstance(valor, bool):
        erros[campo] = ['Indique um número inteiro.']
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        erros[campo] = ['Indique um número inteiro.']
        return None
    if n < minimo or n > maximo:
        erros[campo] = [f'Indique um valor entre {minimo} e {maximo}.']
        return None
    return n


@api_view(['GET', 'PATCH'])
@permission_classes(PERMISSOES)
def curso_detalhe(request, curso_id):
    curso = _curso_do_professor(request, curso_id)
    if request.method == 'GET':
        return Response(detalhe_curso(curso))

    dados = request.data if isinstance(request.data, dict) else {}
    entrada = {}
    for chave, valor in dados.items():
        if chave == 'definicoes' and isinstance(valor, dict):
            entrada.update(valor)
        else:
            entrada[SINONIMOS.get(chave, chave)] = valor

    proibidos = sorted(set(entrada) & CAMPOS_PROIBIDOS)
    if proibidos:
        return _erro('O estado e o destaque do curso não se mudam aqui: use submeter, arquivar ou peça ao administrador.',
                     'campo_nao_editavel', details={c: ['Campo não editável.'] for c in proibidos})

    erros, campos, defs = {}, [], {}
    if 'titulo' in entrada:
        titulo = (entrada['titulo'] or '').strip() if isinstance(entrada['titulo'], str) else ''
        if len(titulo) < 3 or len(titulo) > 200:
            erros['titulo'] = ['O título deve ter entre 3 e 200 caracteres.']
        else:
            curso.title = titulo
            campos.append('title')
    if 'acesso' in entrada:
        # "todos" = qualquer plano (free); "premium" = Premium e Premium Plus.
        mapa = {'todos': 'free', 'premium': 'premium'}
        if entrada['acesso'] not in mapa:
            erros['acesso'] = ['Escolha "todos" ou "premium".']
        else:
            curso.access_level = mapa[entrada['acesso']]
            campos.append('access_level')
    if 'descricao' in entrada:
        curso.description = str(entrada['descricao'] or '').strip()
        campos.append('description')
    if 'area' in entrada:
        area = ciclo.categoria_de_entrada(entrada['area'] if isinstance(entrada['area'], str) else '',
                                          curso.course_type)
        if not area or len(area) > 100:
            erros['area'] = ['Escolha a área do curso.']
        else:
            curso.category = area
            campos.append('category')
    if 'nivel' in entrada:
        nivel = ciclo.nivel_de_entrada(entrada['nivel'] if isinstance(entrada['nivel'], str) else '')
        if not nivel:
            erros['nivel'] = ['Nível inválido. Escolha um nível de A1 a C2.']
        else:
            curso.level = nivel
            campos.append('level')
    if 'imagem' in entrada:
        if curso.course_type == 'practice':
            erros['imagem'] = ['Os cursos de prática não têm imagem de capa.']
        else:
            from django.core.validators import URLValidator
            from django.core.exceptions import ValidationError as DjangoValidationError
            imagem = (entrada['imagem'] or '').strip() if isinstance(entrada['imagem'], str) else ''
            try:
                if imagem:
                    URLValidator()(imagem)
                curso.image = imagem
                campos.append('image')
            except DjangoValidationError:
                erros['imagem'] = ['Indique um endereço (URL) válido para a imagem.']
    for chave in BOOLEANOS:
        if chave in entrada:
            if not isinstance(entrada[chave], bool):
                erros[chave] = ['Indique verdadeiro ou falso.']
            elif chave in ('visivel_catalogo', 'inscricao_livre'):
                setattr(curso, chave, entrada[chave])
                campos.append(chave)
            else:
                defs[chave] = entrada[chave]
    if 'maximo_alunos' in entrada:
        n = _inteiro_ou_nulo(entrada['maximo_alunos'], 1, 100000, 'maximo_alunos', erros)
        if 'maximo_alunos' not in erros:
            curso.maximo_alunos = n
            campos.append('maximo_alunos')
    if 'tempo_limite_questionario_min' in entrada:
        n = _inteiro_ou_nulo(entrada['tempo_limite_questionario_min'], 1, 300, 'tempo_limite_questionario_min', erros)
        if 'tempo_limite_questionario_min' not in erros:
            defs['tempo_limite_questionario_min'] = n
    nota = None
    if 'nota_minima' in entrada:
        nota = _inteiro_ou_nulo(entrada['nota_minima'], 50, 100, 'nota_minima', erros)
        if nota is None and 'nota_minima' not in erros:
            erros['nota_minima'] = ['Indique um valor entre 50 e 100.']

    exame = {}
    if 'exame_oral' in entrada:
        if isinstance(entrada['exame_oral'], bool):
            exame['exam_enabled'] = entrada['exame_oral']
        else:
            erros['exame_oral'] = ['Use verdadeiro ou falso.']
    if 'nota_minima_exame' in entrada:
        n = _inteiro_ou_nulo(entrada['nota_minima_exame'], 40, 100, 'nota_minima_exame', erros)
        if n is None and 'nota_minima_exame' not in erros:
            erros['nota_minima_exame'] = ['Indique um valor entre 40 e 100.']
        elif n is not None:
            exame['min_exam_score'] = float(n)

    if erros:
        primeiro = next(iter(erros.values()))[0]
        return _erro(primeiro, 'validation_error', details=erros)

    imagem_anterior = Course.objects.filter(pk=curso.pk).values_list('image', flat=True).first()

    def _gravar():
        if defs:
            curso.definicoes = {**(curso.definicoes if isinstance(curso.definicoes, dict) else {}), **defs}
            campos.append('definicoes')
        if campos:
            curso.save(update_fields=list(dict.fromkeys(campos)) + ['updated_at'])
        if nota is not None:
            from apps.courses.models import CourseGradingConfig
            config, _ = CourseGradingConfig.objects.get_or_create(course=curso)
            if config.min_final_grade != nota:
                config.min_final_grade = nota
                config.save(update_fields=['min_final_grade'])
        if exame:
            from apps.courses.models import CourseGradingConfig
            config, _ = CourseGradingConfig.objects.get_or_create(course=curso)
            mudou = [k for k, v in exame.items() if getattr(config, k) != v]
            if mudou:
                for k in mudou:
                    setattr(config, k, exame[k])
                config.save(update_fields=mudou)
                # As notas dos alunos mudam com estas regras: recalcula depois de gravar.
                transaction.on_commit(lambda: _recalcular_notas(curso.pk))
        if 'image' in campos and imagem_anterior and imagem_anterior != curso.image:
            from .envios import apagar_depois_do_commit
            apagar_depois_do_commit([imagem_anterior])
        return Response(detalhe_curso(curso))

    return guardar_publicado(curso, _gravar)


def _recalcular_notas(curso_id):
    """Recalcula as notas dos inscritos numa thread à parte (fora do pedido; ver apps.courses.recalculo)."""
    from apps.courses.recalculo import recalcular_notas_em_fundo
    from apps.practice.conversa.exame import sincronizar_aprovacao
    sincronizar_aprovacao(Course.objects.get(pk=curso_id))  # passou/não passou segue a nota mínima de agora
    recalcular_notas_em_fundo(curso_id)


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def verificacao(request, curso_id):
    curso = _curso_do_professor(request, curso_id)
    return Response(ciclo.verificar(curso))


def _resposta_estado(curso, mensagem):
    return Response({'message': mensagem, 'curso': detalhe_curso(curso)})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def submeter(request, curso_id):
    with transaction.atomic():
        curso = _curso_do_professor(request, curso_id)
        curso = Course.objects.select_for_update().get(pk=curso.pk)
        if curso.status == ciclo.EM_REVISAO:
            return _erro('Este curso já está em revisão.', 'ja_em_revisao')
        if curso.status == ciclo.PUBLICADO:
            return _erro('Este curso já está publicado.', 'ja_publicado')
        resultado = ciclo.verificar(curso)
        if not resultado['pode_submeter']:
            return _erro('O curso ainda não está pronto para revisão. Veja o que falta na lista.',
                         'verificacao_incompleta', details=resultado, **resultado)
        from apps.courses.api.admin_painel_cursos import professor_publica_sem_revisao
        if professor_publica_sem_revisao(curso.teacher_id):
            # Professor de confiança (marcado pelo administrador): publica sem passar pela revisão.
            # Como no aprovar: sai de qualquer arquivo e limpa o estado anterior à revisão.
            agora = timezone.now()
            curso.status = ciclo.PUBLICADO
            curso.submetido_em = agora
            curso.aprovado_em = agora
            curso.aprovado_por = None
            curso.motivo_recusa = ''
            curso.motivo_moderacao = ''
            curso.moderacao_accao = ''
            curso.modo_arquivo = ''
            curso.arquivado_em = None
            curso.estado_antes_revisao = ''
            curso.save(update_fields=['status', 'submetido_em', 'aprovado_em', 'aprovado_por', 'motivo_recusa',
                                      'motivo_moderacao', 'moderacao_accao',
                                      'modo_arquivo', 'arquivado_em', 'estado_antes_revisao', 'updated_at'])
            publicado = True
        else:
            publicado = False
            # Guarda de onde veio: cancelar/recusar volta a esse estado e, se estava arquivado a
            # manter, os inscritos continuam a ter acesso enquanto o curso espera pela revisão.
            curso.estado_antes_revisao = ciclo.ARQUIVADO if curso.status == ciclo.ARQUIVADO else ciclo.RASCUNHO
            curso.status = ciclo.EM_REVISAO
            curso.submetido_em = timezone.now()
            curso.motivo_recusa = ''
            curso.save(update_fields=['status', 'estado_antes_revisao', 'submetido_em', 'motivo_recusa', 'updated_at'])
    if publicado:
        from apps.courses.api.admin_cursos import _avisar, chave_aviso
        _avisar(curso, 'Curso publicado',
                f'O seu curso "{curso.title}" foi publicado e já está no catálogo.',
                chave_aviso('curso-publicado', curso))
        return _resposta_estado(curso, 'Curso publicado. Já está no catálogo.')
    return _resposta_estado(curso, 'Curso enviado para revisão. Vai receber um aviso quando for aprovado.')


@api_view(['POST'])
@permission_classes(PERMISSOES)
def cancelar_revisao(request, curso_id):
    with transaction.atomic():
        curso = _curso_do_professor(request, curso_id)
        curso = Course.objects.select_for_update().get(pk=curso.pk)
        if curso.status != ciclo.EM_REVISAO:
            return _erro('Este curso não está em revisão.', 'nao_em_revisao')
        voltou = sair_da_revisao(curso)
    if voltou == ciclo.ARQUIVADO:
        return _resposta_estado(curso, 'Revisão cancelada. O curso voltou a arquivado.')
    return _resposta_estado(curso, 'Revisão cancelada. O curso voltou a rascunho.')


def sair_da_revisao(curso, motivo=None):
    """
    em_revisao -> estado anterior (cancelar ou recusar): arquivado, no mesmo modo, se o curso
    estava arquivado quando foi submetido; senão rascunho. Devolve o estado novo.
    """
    if curso.estado_antes_revisao == ciclo.ARQUIVADO and curso.modo_arquivo in ciclo.MODOS_ARQUIVO:
        curso.status = ciclo.ARQUIVADO
    else:
        curso.status = ciclo.RASCUNHO
    curso.estado_antes_revisao = ''
    curso.submetido_em = None
    campos = ['status', 'estado_antes_revisao', 'submetido_em', 'updated_at']
    if motivo is not None:
        curso.motivo_recusa = motivo
        campos.append('motivo_recusa')
    curso.save(update_fields=campos)
    return curso.status


@api_view(['POST'])
@permission_classes(PERMISSOES)
def arquivar(request, curso_id):
    modo = (request.data or {}).get('modo') if isinstance(request.data, dict) else None
    if modo not in ciclo.MODOS_ARQUIVO:
        return _erro('Escolha como arquivar: "manter" (os inscritos continuam a ter acesso) ou "fechar".',
                     'modo_invalido', details={'modo': ['Use "manter" ou "fechar".']})
    with transaction.atomic():
        curso = _curso_do_professor(request, curso_id)
        curso = Course.objects.select_for_update().get(pk=curso.pk)
        if curso.status == ciclo.ARQUIVADO and curso.modo_arquivo == modo:
            return _erro('Este curso já está arquivado neste modo.', 'ja_arquivado')
        curso.status = ciclo.ARQUIVADO
        curso.modo_arquivo = modo
        curso.arquivado_em = timezone.now()
        curso.submetido_em = None
        curso.estado_antes_revisao = ''
        curso.save(update_fields=['status', 'modo_arquivo', 'arquivado_em', 'submetido_em',
                                  'estado_antes_revisao', 'updated_at'])
    if modo == ciclo.MANTER:
        mensagem = 'Curso arquivado. Os alunos inscritos continuam a ter acesso; não há inscrições novas.'
    else:
        mensagem = 'Curso arquivado e fechado. Os inscritos deixam de ver as aulas; os certificados emitidos continuam válidos.'
    return _resposta_estado(curso, mensagem)
