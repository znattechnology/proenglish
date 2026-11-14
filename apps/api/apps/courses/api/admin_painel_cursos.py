"""
Cursos na área de administração (lista, análise, detalhe para revisão e arquivo).

  GET  /api/v1/admin/cursos/?tipo=&estado=&q=&professor=&pagina=   lista (25 por página) + números
  GET  /api/v1/admin/cursos/analise/?periodo=7|30|90                actividade e inscrições (cache 10 min)
  GET  /api/v1/admin/cursos/analise/exportar/?periodo=               a mesma análise em CSV
  GET  /api/v1/admin/cursos/<id>/                                    detalhe para revisão (estrutura completa)
  POST /api/v1/admin/cursos/<id>/arquivar/  {modo, motivo}           arquiva qualquer curso (+ aviso)

Só administradores (apps.core.permissions.EAdministrador). Os números por curso vêm dos mesmos
cálculos da área do professor (apps/courses/api/teacher/cursos.py: metricas), para baterem certo.

Definições usadas na análise (dias contados no fuso de Luanda):
- activo num dia: aluno (role student) com alguma actividade de aprendizagem nesse dia: minutos de
  vídeo, resposta a um exercício, progresso numa aula/lição, lição concluída ou conversa com o tutor;
- lições concluídas: lições de prática concluídas pela primeira vez + aulas de vídeo concluídas no período;
- alunos: contas com papel student e activas (base da % de activos na semana);
- inscrições: matrículas activas de alunos (role student) em cursos de vídeo + primeira participação
  (primeiro exercício) de um aluno num curso de prática; "este mês" conta as criadas desde o dia 1;
- desistência: entre os alunos que ainda não acabaram o curso, a janela de 3 aulas/lições seguidas
  onde mais pararam (a aula onde um aluno parou = aulas concluídas + 1). Devolve
  {texto, alunos, pct} (pct = parte dos que pararam que o fizeram nessa janela) ou null quando a
  janela tem menos de 3 alunos ou menos de 30% dos que pararam (não há um ponto claro).
"""
import csv
import io
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Min, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador
from apps.courses import ciclo
from apps.courses.models import Chapter, ChapterProgress, Course, CourseEnrollment, CourseSection

logger = logging.getLogger(__name__)

PERMISSOES = [EAdministrador]
LUANDA = ZoneInfo('Africa/Luanda')
POR_PAGINA = 25
PERIODOS = (7, 30, 90)
CACHE_ANALISE = 'admin_cursos_analise:v2:{periodo}'
CACHE_SEGUNDOS = 600
DESISTENCIA_MIN_ALUNOS = 3
DESISTENCIA_MIN_PCT = 30
TIPOS = {'video': 'video', 'pratica': 'practice'}
LIGACAO_PROFESSOR = '/teacher/courses'


def _erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details, **extra), status=status_http)


def _hoje():
    return timezone.localtime(timezone.now(), LUANDA).date()


def _inicio_dia(dia):
    return datetime.combine(dia, time.min, tzinfo=LUANDA)


def _nome_professor(c):
    return c.teacherName or getattr(c.teacher, 'name', '') or ''


# ---------------------------------------------------------------------------
# Inscrições (vídeo: matrículas; prática: primeira participação)
# ---------------------------------------------------------------------------

def _inscricoes_desde(desde):
    """[(quando, categoria_do_curso)] das inscrições a partir de `desde`."""
    from apps.practice.models import ChallengeProgress

    linhas = [(r['enrollment_date'], r['course__category']) for r in
              CourseEnrollment.objects.filter(enrollment_date__gte=desde, course__course_type='video',
                                              is_active=True, user__role='student')
              .values('enrollment_date', 'course__category')]
    pratica = ChallengeProgress.objects.filter(challenge__lesson__unit__course__course_type='practice',
                                               user__role='student')
    # Pré-filtro por data: só os alunos com exercícios feitos desde `desde` podem ter a primeira
    # participação nesse intervalo (o mínimo continua a ser calculado sobre todo o histórico deles).
    recentes = pratica.filter(completed_at__gte=desde).values('user_id')
    linhas += [(r['primeiro'], r['challenge__lesson__unit__course__category']) for r in
               pratica.filter(user_id__in=recentes)
               .values('user_id', 'challenge__lesson__unit__course_id', 'challenge__lesson__unit__course__category')
               .annotate(primeiro=Min('completed_at')).filter(primeiro__gte=desde)]
    return linhas


# ---------------------------------------------------------------------------
# GET /admin/cursos/
# ---------------------------------------------------------------------------

def _numeros(cursos, m):
    from apps.courses.api.teacher.cursos import _conclusao_media

    agora = timezone.now()
    publicados = [c for c in cursos if c.status == ciclo.PUBLICADO]
    rascunhos = [c for c in cursos if c.status == ciclo.RASCUNHO]
    inicio_mes = _inicio_dia(_hoje().replace(day=1))
    return {
        'publicados': len(publicados),
        'publicados_video': sum(1 for c in publicados if c.course_type != 'practice'),
        'publicados_pratica': sum(1 for c in publicados if c.course_type == 'practice'),
        'rascunhos': len(rascunhos),
        'rascunhos_parados_30d': sum(1 for c in rascunhos if c.updated_at and c.updated_at < agora - timedelta(days=30)),
        'em_revisao': sum(1 for c in cursos if c.status == ciclo.EM_REVISAO),
        'arquivados': sum(1 for c in cursos if c.status == ciclo.ARQUIVADO),
        'inscricoes': sum(m[c.id]['alunos'] for c in cursos),
        'inscricoes_mes': len(_inscricoes_desde(inicio_mes)),
        'conclusao_media': _conclusao_media(cursos, m),
    }


def _item_lista(c, mc):
    conclusao = mc['conclusao'] if mc['alunos'] else None
    return {
        'id': str(c.id),
        'titulo': c.title,
        'tipo': ciclo.tipo_api(c),
        'professor': {'id': str(c.teacher_id), 'nome': _nome_professor(c)},
        'area': ciclo.area_pt(c.category),
        'nivel': ciclo.nivel_pt(c.level),
        'estado': ciclo.estado(c),
        'alunos': mc['alunos'],
        'conclusao': None if conclusao is None else int(round(conclusao)),
        'actualizado_em': c.updated_at.isoformat() if c.updated_at else None,
        'submetido_em': c.submetido_em.isoformat() if c.submetido_em else None,
    }


@api_view(['GET'])
@permission_classes(PERMISSOES)
def lista(request):
    from apps.courses.api.teacher.cursos import metricas

    p = request.query_params
    erros = {}
    tipo = p.get('tipo') or None
    if tipo and tipo not in TIPOS:
        erros['tipo'] = ['Use "video" ou "pratica".']
    estado = p.get('estado') or None
    if estado and estado not in ciclo.API_ESTADO:
        erros['estado'] = ['Use rascunho, em_revisao, publicado ou arquivado.']
    professor = (p.get('professor') or '').strip() or None
    if professor:
        import uuid
        try:
            professor = uuid.UUID(professor)
        except ValueError:
            erros['professor'] = ['Professor inválido.']
    try:
        pagina = int(p.get('pagina') or 1)
        if pagina < 1:
            raise ValueError
    except ValueError:
        erros['pagina'] = ['Indique um número de página válido.']
        pagina = 1
    if erros:
        return _erro(next(iter(erros.values()))[0], 'validation_error', details=erros)

    todos = list(Course.objects.select_related('teacher').order_by('-updated_at'))
    m = metricas(todos)
    numeros = _numeros(todos, m)

    cursos = todos
    if tipo:
        cursos = [c for c in cursos if (c.course_type == 'practice') == (tipo == 'pratica')]
    if estado:
        cursos = [c for c in cursos if c.status == ciclo.API_ESTADO[estado]]
    if professor:
        cursos = [c for c in cursos if c.teacher_id == professor]
    q = (p.get('q') or '').strip().lower()
    if q:
        cursos = [c for c in cursos if q in (c.title or '').lower() or q in _nome_professor(c).lower()
                  or q in (getattr(c.teacher, 'email', '') or '').lower()]
    if estado == 'em_revisao':
        # A fila de revisão: os mais antigos primeiro.
        cursos.sort(key=lambda c: (c.submetido_em or c.updated_at))

    total = len(cursos)
    inicio = (pagina - 1) * POR_PAGINA
    return Response({
        'numeros': numeros,
        'total': total,
        'paginas': max(1, math.ceil(total / POR_PAGINA)),
        'pagina': pagina,
        'resultados': [_item_lista(c, m[c.id]) for c in cursos[inicio:inicio + POR_PAGINA]],
    })


# ---------------------------------------------------------------------------
# GET /admin/cursos/analise/
# ---------------------------------------------------------------------------

def _pares_activos(desde):
    """{(user_id, dia em Luanda)} dos alunos (role student, conta activa) com actividade desde `desde`."""
    from apps.courses.models import VideoWatchLog
    from apps.practice.models import ChallengeAttempt, ChallengeProgress, LessonCompletion, VapiSession

    fontes = [
        (VideoWatchLog.objects.filter(updated_at__gte=desde, seconds__gt=0, user__role='student', user__is_active=True),
         'user_id', 'updated_at'),
        (ChallengeAttempt.objects.filter(created_at__gte=desde, user__role='student', user__is_active=True), 'user_id', 'created_at'),
        (ChallengeProgress.objects.filter(updated_at__gte=desde, user__role='student', user__is_active=True), 'user_id', 'updated_at'),
        (LessonCompletion.objects.filter(last_completed_at__gte=desde, user__role='student', user__is_active=True),
         'user_id', 'last_completed_at'),
        (LessonCompletion.objects.filter(first_completed_at__gte=desde, user__role='student', user__is_active=True),
         'user_id', 'first_completed_at'),
        (ChapterProgress.objects.filter(updated_at__gte=desde, user_progress__user__role='student',
                                       user_progress__user__is_active=True),
         'user_progress__user_id', 'updated_at'),
        (VapiSession.objects.filter(created_at__gte=desde, user__role='student', user__is_active=True)
         .exclude(status=VapiSession.STATUS_NAO_LIGOU), 'user_id', 'created_at'),
    ]
    pares = set()
    for qs, campo_user, campo_data in fontes:
        for r in qs.annotate(_dia=TruncDate(campo_data, tzinfo=LUANDA)).values_list(campo_user, '_dia').distinct():
            pares.add(r)
    return pares


def _licoes_concluidas(desde):
    from apps.practice.models import LessonCompletion

    pratica = LessonCompletion.objects.filter(first_completed_at__gte=desde, user__role='student').count()
    video = ChapterProgress.objects.filter(completed=True, completed_at__gte=desde,
                                           user_progress__user__role='student').count()
    return pratica + video


def _janela(paragens, n, rotulo):
    """
    paragens: [posição onde cada aluno parou]. Devolve {texto: 'entre a aula X e a Y', alunos, pct}
    (pct = % dos que pararam que o fizeram nessa janela) ou None se não houver um ponto claro.
    """
    if len(paragens) < DESISTENCIA_MIN_ALUNOS or n < 2:
        return None
    contagem = Counter(paragens)
    largura = min(3, n)
    melhor, melhor_k = -1, 1
    for k in range(1, n - largura + 2):
        soma = sum(contagem[i] for i in range(k, k + largura))
        if soma > melhor:
            melhor, melhor_k = soma, k
    fim = melhor_k + largura - 1
    pct = melhor * 100.0 / len(paragens)
    if melhor < DESISTENCIA_MIN_ALUNOS or pct < DESISTENCIA_MIN_PCT:
        return None
    texto = f'entre a {rotulo} {melhor_k} e a {fim}' if fim > melhor_k else f'na {rotulo} {melhor_k}'
    return {'texto': texto, 'alunos': melhor, 'pct': int(round(pct))}


def _desistencia_video(curso):
    from apps.courses.models import UserCourseProgress

    aulas = list(Chapter.objects.filter(ciclo.q_aula_visivel(), section__course=curso).values_list('id', flat=True))
    n = len(aulas)
    if n < 2:
        return None
    inscritos = set(CourseEnrollment.objects.filter(course=curso, is_active=True, user__role='student')
                    .values_list('user_id', flat=True))
    feitas = dict(ChapterProgress.objects.filter(user_progress__course=curso, completed=True, chapter_id__in=aulas,
                                                  user_progress__user_id__in=inscritos)
                  .values('user_progress__user_id').annotate(n=Count('chapter_id', distinct=True))
                  .values_list('user_progress__user_id', 'n'))
    acabaram = set(UserCourseProgress.objects.filter(course=curso, overallProgress__gte=100)
                   .values_list('user_id', flat=True))
    paragens = [min(n, feitas.get(u, 0) + 1) for u in inscritos if u not in acabaram and feitas.get(u, 0) < n]
    return _janela(paragens, n, 'aula')


def _desistencia_pratica(curso):
    from apps.practice.models import ChallengeProgress, PracticeChallenge

    por_licao = dict(PracticeChallenge.objects.filter(lesson__unit__course=curso).values('lesson_id')
                     .annotate(n=Count('id')).values_list('lesson_id', 'n'))
    n = len(por_licao)
    if n < 2:
        return None
    feitas = defaultdict(int)
    alunos = set()
    for r in (ChallengeProgress.objects.filter(challenge__lesson__unit__course=curso, user__role='student')
              .values('user_id', 'challenge__lesson_id')
              .annotate(c=Count('challenge_id', distinct=True, filter=Q(completed=True)))):
        alunos.add(r['user_id'])
        total = por_licao.get(r['challenge__lesson_id'], 0)
        if total and r['c'] >= total:
            feitas[r['user_id']] += 1
    paragens = [feitas[u] + 1 for u in alunos if feitas[u] < n]
    return _janela(paragens, n, 'lição')


def _conclusao_baixa(limite=5):
    from apps.courses.api.teacher.cursos import metricas

    publicados = list(Course.objects.filter(status=ciclo.PUBLICADO))
    m = metricas(publicados)
    candidatos = [c for c in publicados if m[c.id]['alunos'] >= 5 and m[c.id]['conclusao'] is not None]
    candidatos.sort(key=lambda c: (m[c.id]['conclusao'], -m[c.id]['alunos']))
    saida = []
    for c in candidatos[:limite]:
        try:
            desistencia = _desistencia_pratica(c) if c.course_type == 'practice' else _desistencia_video(c)
        except Exception:  # um cálculo auxiliar não deita abaixo a análise
            logger.exception('Falha ao calcular a desistência do curso %s', c.pk)
            desistencia = None
        saida.append({
            'id': str(c.id), 'titulo': c.title, 'tipo': ciclo.tipo_api(c),
            'alunos': m[c.id]['alunos'], 'conclusao': int(round(m[c.id]['conclusao'])),
            'desistencia': desistencia,
        })
    return saida


def calcular_analise(periodo):
    from apps.users.models import User

    hoje = _hoje()
    dias = [hoje - timedelta(days=i) for i in range(periodo - 1, -1, -1)]
    inicio = _inicio_dia(dias[0])
    inicio_anterior = inicio - timedelta(days=periodo)
    inicio_semana = hoje - timedelta(days=6)

    pares = _pares_activos(_inicio_dia(min(dias[0], inicio_semana)))
    por_dia = Counter(dia for _, dia in pares)
    activos_dia = [{'dia': d.isoformat(), 'n': por_dia.get(d, 0)} for d in dias]
    activos_semana = len({u for u, d in pares if d >= inicio_semana})
    alunos = User.objects.filter(role='student', is_active=True).count()

    inscricoes = _inscricoes_desde(inicio_anterior)
    novas = [cat for quando, cat in inscricoes if quando >= inicio]
    anteriores = sum(1 for quando, _ in inscricoes if inicio_anterior <= quando < inicio)
    variacao = round((len(novas) - anteriores) * 100.0 / anteriores, 1) if anteriores else None
    areas = Counter(ciclo.area_pt(cat) or 'Sem área' for cat in novas)

    licoes = _licoes_concluidas(inicio)
    return {
        'periodo': periodo,
        'activos_dia_media': round(sum(x['n'] for x in activos_dia) / periodo, 1),
        'activos_dia': activos_dia,
        'activos_semana': activos_semana,
        'pct_activos_semana': round(activos_semana * 100.0 / alunos, 1) if alunos else None,
        'alunos': alunos,
        'inscricoes_novas': len(novas),
        'inscricoes_anteriores': anteriores,
        'inscricoes_variacao_pct': variacao,
        'licoes_concluidas': licoes,
        'licoes_por_dia': round(licoes / periodo, 1),
        'por_area': [{'area': a, 'inscricoes': n} for a, n in sorted(areas.items(), key=lambda x: (-x[1], x[0]))],
        'conclusao_baixa': _conclusao_baixa(),
        'gerado_em': timezone.now().isoformat(),
        'cache_segundos': CACHE_SEGUNDOS,
    }


def _periodo(request):
    valor = request.query_params.get('periodo') or '30'
    try:
        periodo = int(valor)
    except ValueError:
        periodo = None
    return periodo if periodo in PERIODOS else None


def analise_em_cache(periodo):
    chave = CACHE_ANALISE.format(periodo=periodo)
    dados = cache.get(chave)
    if dados is None:
        dados = calcular_analise(periodo)
        cache.set(chave, dados, CACHE_SEGUNDOS)
    return dados


def _erro_periodo():
    return _erro('Período inválido. Use 7, 30 ou 90 dias.', 'periodo_invalido',
                 details={'periodo': ['Use 7, 30 ou 90.']})


def _erro_interno():
    return _erro('Não foi possível calcular a análise. Tente de novo dentro de momentos.', 'erro_interno', 500)


@api_view(['GET'])
@permission_classes(PERMISSOES)
def analise(request):
    periodo = _periodo(request)
    if periodo is None:
        return _erro_periodo()
    try:
        return Response(analise_em_cache(periodo))
    except Exception:
        logger.exception('Falha ao calcular a análise dos cursos')
        return _erro_interno()


def celula(valor):
    """Evita fórmulas no Excel em texto (=, +, -, @, tab, CR); os números passam como estão."""
    if valor is None:
        return ''
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor).replace('.', ',')
    texto = str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exportar_analise(request):
    periodo = _periodo(request)
    if periodo is None:
        return _erro_periodo()
    try:
        d = analise_em_cache(periodo)
    except Exception:
        logger.exception('Falha ao exportar a análise dos cursos')
        return _erro_interno()

    linhas = [
        ['Análise de cursos', f'Últimos {periodo} dias'],
        ['Indicador', 'Valor'],
        ['Média de alunos activos por dia', d['activos_dia_media']],
        ['Alunos activos nos últimos 7 dias', d['activos_semana']],
        ['% de alunos activos nos últimos 7 dias', d['pct_activos_semana']],
        ['Inscrições novas', d['inscricoes_novas']],
        ['Variação face ao período anterior (%)', d['inscricoes_variacao_pct']],
        ['Lições concluídas', d['licoes_concluidas']],
        ['Lições concluídas por dia', d['licoes_por_dia']],
        [],
        ['Dia', 'Alunos activos'],
        *[[x['dia'], x['n']] for x in d['activos_dia']],
        [],
        ['Área', 'Inscrições'],
        *[[x['area'], x['inscricoes']] for x in d['por_area']],
        [],
        ['Curso', 'Tipo', 'Alunos', 'Conclusão (%)', 'Onde desistem'],
        *[[x['titulo'], 'Prática' if x['tipo'] == 'pratica' else 'Vídeo', x['alunos'], x['conclusao'],
           (x['desistencia'] or {}).get('texto', '')] for x in d['conclusao_baixa']],
    ]
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';', lineterminator='\r\n')
    for linha in linhas:
        escritor.writerow([celula(v) for v in linha])
    resposta = HttpResponse('﻿' + saida.getvalue(), content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="analise-cursos-{periodo}d-{_hoje().isoformat()}.csv"'
    return resposta


# ---------------------------------------------------------------------------
# GET /admin/cursos/<id>/
# ---------------------------------------------------------------------------

def _estrutura_video(curso):
    from apps.courses.api.teacher.editor_video import _aulas_com_materiais, seccao_dict

    seccoes = list(CourseSection.objects.filter(course=curso).order_by('order', 'created_at'))
    aulas = _aulas_com_materiais(Chapter.objects.filter(section__course=curso))
    por_seccao = defaultdict(list)
    for a in aulas:
        por_seccao[a.section_id].append(a)
    return {'tipo': 'video', 'seccoes': [seccao_dict(s, por_seccao.get(s.id, [])) for s in seccoes]}


def _estrutura_pratica(curso):
    from django.db.models import Prefetch
    from apps.courses.api.teacher.pratica import _licoes_dicts, _tentativas_por_exercicio, exercicio_dict
    from apps.practice.models import ChallengeOption, PracticeChallenge, PracticeLesson, PracticeUnit

    unidades = list(PracticeUnit.objects.filter(course=curso).order_by('order'))
    licoes = list(PracticeLesson.objects.filter(unit__course=curso).order_by('order'))
    dicts = _licoes_dicts(licoes)
    chs = list(PracticeChallenge.objects.filter(lesson__unit__course=curso).order_by('order')
               .prefetch_related(Prefetch('options', queryset=ChallengeOption.objects.order_by('order'))))
    stats = _tentativas_por_exercicio({'challenge__lesson__unit__course': curso})
    por_licao = defaultdict(list)
    for ch in chs:
        por_licao[ch.lesson_id].append(exercicio_dict(ch, stats))
    por_unidade = defaultdict(list)
    for l in licoes:
        d = dict(dicts[l.id])
        d['n_exercicios'] = d['exercicios']
        d['exercicios'] = por_licao.get(l.id, [])
        por_unidade[l.unit_id].append(d)
    return {'tipo': 'pratica', 'unidades': [
        {'id': str(u.id), 'titulo': u.title, 'descricao': u.description or '', 'ordem': u.order,
         'licoes': por_unidade.get(u.id, [])} for u in unidades]}


def professor_publica_sem_revisao(teacher_id):
    """PerfilProfessor.publica_sem_revisao, lido com cuidado (o campo pode ainda não existir)."""
    try:
        from apps.users.models import PerfilProfessor
        if not any(f.name == 'publica_sem_revisao' for f in PerfilProfessor._meta.get_fields()):
            return False
        with transaction.atomic():  # ponto de gravação: um erro de BD não estraga a transacção de fora
            return bool(PerfilProfessor.objects.filter(user_id=teacher_id)
                        .values_list('publica_sem_revisao', flat=True).first())
    except Exception:
        logger.exception('Não foi possível ler publica_sem_revisao do professor %s', teacher_id)
        return False


@api_view(['GET'])
@permission_classes(PERMISSOES)
def detalhe(request, curso_id):
    from apps.courses.api.teacher.cursos import detalhe_curso

    curso = Course.objects.filter(id=curso_id).select_related('teacher').first()
    if curso is None:
        return _erro('Curso não encontrado.', 'not_found', 404)
    prof = curso.teacher
    estrutura = _estrutura_pratica(curso) if curso.course_type == 'practice' else _estrutura_video(curso)
    return Response({
        'curso': detalhe_curso(curso),
        'professor': {
            'id': str(prof.id),
            'nome': getattr(prof, 'name', '') or _nome_professor(curso),
            'email': prof.email,
            'cursos_publicados': Course.objects.filter(teacher_id=prof.id, status=ciclo.PUBLICADO).count(),
            'publica_sem_revisao': professor_publica_sem_revisao(prof.id),
        },
        'verificacao': ciclo.verificar(curso),
        'estrutura': estrutura,
    })


# ---------------------------------------------------------------------------
# POST /admin/cursos/<id>/arquivar/
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes(PERMISSOES)
def arquivar(request, curso_id):
    from apps.courses.api.admin_cursos import _avisar, chave_aviso
    from apps.courses.api.teacher.cursos import detalhe_curso

    dados = request.data if isinstance(request.data, dict) else {}
    modo = dados.get('modo')
    motivo = dados.get('motivo')
    motivo = motivo.strip() if isinstance(motivo, str) else ''
    erros = {}
    if modo not in ciclo.MODOS_ARQUIVO:
        erros['modo'] = ['Use "manter" (os inscritos continuam a ter acesso) ou "fechar".']
    if len(motivo) < 5:
        erros['motivo'] = ['Explique ao professor porque o curso foi arquivado (pelo menos 5 caracteres).']
    if erros:
        return _erro(next(iter(erros.values()))[0], 'validation_error', details=erros)

    with transaction.atomic():
        curso = Course.objects.select_for_update().filter(id=curso_id).first()
        if curso is None:
            return _erro('Curso não encontrado.', 'not_found', 404)
        if curso.status == ciclo.ARQUIVADO and curso.modo_arquivo == modo:
            return _erro('Este curso já está arquivado neste modo.', 'ja_arquivado')
        agora = timezone.now()
        curso.status = ciclo.ARQUIVADO
        curso.modo_arquivo = modo
        curso.arquivado_em = agora
        curso.submetido_em = None
        curso.estado_antes_revisao = ''
        # O motivo de uma recusa antiga já não se aplica: o que conta agora é o do arquivamento.
        motivo = motivo[:2000]
        curso.motivo_recusa = ''
        curso.motivo_moderacao = motivo
        curso.moderacao_accao = 'arquivar'
        curso.moderado_por = request.user
        curso.moderado_em = agora
        curso.save(update_fields=['status', 'modo_arquivo', 'arquivado_em', 'submetido_em',
                                  'estado_antes_revisao', 'motivo_recusa', 'motivo_moderacao',
                                  'moderacao_accao', 'moderado_por', 'moderado_em', 'updated_at'])
    if modo == ciclo.MANTER:
        efeito = 'Os alunos inscritos continuam a ter acesso; não há inscrições novas.'
    else:
        efeito = 'Os inscritos deixam de ver as aulas; os certificados emitidos continuam válidos.'
    _avisar(curso, 'Curso arquivado pela administração',
            f'O seu curso "{curso.title}" foi arquivado pela administração. {efeito} Motivo: {motivo}',
            chave_aviso('curso-arquivado-admin', curso))
    return Response({'message': f'Curso arquivado. {efeito} O professor foi avisado.',
                     'motivo': motivo, 'curso': detalhe_curso(curso)})
