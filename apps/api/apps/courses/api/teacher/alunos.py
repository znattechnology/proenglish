"""
Área do professor: alunos e resultados (só leitura).

  GET /api/v1/teacher/alunos/?filtro=todos|activos|em_risco&curso=<id>&q=<nome>&pagina=1
  GET /api/v1/teacher/alunos/exportar/?filtro=&curso=&q=          (CSV)
  GET /api/v1/teacher/alunos/<id>/
  GET /api/v1/teacher/resultados/?periodo=7|30|90
  GET /api/v1/teacher/resultados/exportar/?periodo=                (CSV)

Quem é aluno do professor: inscrição activa (CourseEnrollment) num curso dele, ou progresso
de prática (respostas, exercícios feitos, curso activo) num curso de prática dele.
O administrador vê todos os cursos. Os outros alunos não existem (404).

Actividade de um aluno num curso (a mais recente de):
- vídeo: capítulo concluído, tempo de vídeo registado (VideoWatchLog), progresso guardado
  depois da inscrição (lastAccessedTimestamp, ignorando o momento em que foi criado);
- prática: respostas (ChallengeAttempt), exercícios feitos (ChallengeProgress), lições
  concluídas (LessonCompletion).

Estado do aluno (sobre todos os cursos do professor, ou só o `curso` pedido):
- activo: alguma actividade há menos de 7 dias (é o mesmo número que "activos_7d" e que o
  filtro "activos");
- pouco_activo: a última actividade foi há 7 a 9 dias (só aparece em "todos");
- em_risco: teve actividade e nenhuma há 10 dias ou mais, ou nunca teve actividade e
  inscreveu-se há 10 dias ou mais;
- novo: inscreveu-se há menos de 10 dias e ainda não teve actividade.

Nota de um curso em vídeo (ficha do aluno): null enquanto o aluno não começou o curso
(progresso 0, sem quizzes nem exercícios do curso feitos). A nota guardada inclui a
conversação, que é do nível e não do curso: sem isto, um aluno que nunca abriu o curso
aparecia com a nota das conversas (p. ex. 68 %).

Privacidade: só o nome; nunca e-mail, telefone, pagamentos nem transcrições das conversas.
Os números saem de consultas agregadas por (aluno, curso), sem N+1.
"""
import csv
import io
import math
import uuid
from apps.courses.ciclo import q_aula_visivel
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Max, Min, Q, Sum
from django.db.models.functions import ExtractHour
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo
from apps.courses.api.teacher.cursos import PERMISSOES, _erro, metricas
from apps.courses.api.teacher.posse import exigir_dono_curso
from apps.courses.models import (
    Chapter, ChapterProgress, Course, CourseEnrollment, StudentCourseGrade, UserCourseProgress,
    VideoWatchLog,
)

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')
POR_PAGINA = 25
DIAS_ACTIVO = 7
DIAS_RISCO = 10
FILTROS = ('todos', 'activos', 'em_risco')
PERIODOS = (7, 30, 90)
MINIMO_RESPOSTAS = 5
LIMITE_TEMA = 80
ESTADOS_PT = {'activo': 'Activo', 'pouco_activo': 'Pouco activo', 'em_risco': 'Em risco', 'novo': 'Novo'}
PLANOS_PT = {'FREE': 'Gratuito', 'PREMIUM': 'Premium', 'PREMIUM_PLUS': 'Premium Plus'}
FAIXAS = (('90% ou mais', 90, 101), ('70% a 89%', 70, 90), ('50% a 69%', 50, 70), ('Menos de 50%', 0, 50))
# O progresso guardado é criado na inscrição (lastAccessedTimestamp = agora); só conta como
# actividade quando foi gravado outra vez depois disso.
FOLGA_CRIACAO = timedelta(minutes=2)


# ---------------------------------------------------------------------------
# Dados por (aluno, curso)
# ---------------------------------------------------------------------------

@dataclass
class Par:
    inscrito: datetime | None = None
    ultima: datetime | None = None
    feitos: int = 0          # capítulos (vídeo) ou lições (prática) concluídos
    certas: int = 0
    tentativas: int = 0
    total: int = 0           # capítulos ou lições do curso

    def ver_inscrito(self, quando):
        if quando and (self.inscrito is None or quando < self.inscrito):
            self.inscrito = quando

    def ver_actividade(self, quando):
        if quando and (self.ultima is None or quando > self.ultima):
            self.ultima = quando

    @property
    def progresso(self):
        return min(100, round(self.feitos * 100 / self.total)) if self.total else 0


def _cursos_visiveis(request):
    qs = Course.objects.all() if ciclo.e_staff(request.user) else Course.objects.filter(teacher=request.user)
    return list(qs.only('id', 'title', 'course_type', 'teacher_id', 'status'))


def _pares(cursos, user_ids=None):
    """{(user_id, course_id): Par} dos alunos dos cursos (sem o próprio dono do curso)."""
    from apps.practice.models import (
        ChallengeAttempt, ChallengeProgress, LessonCompletion, PracticeChallenge, PracticeLesson, UserProgress,
    )

    por_id = {c.id: c for c in cursos}
    video = [c.id for c in cursos if c.course_type != 'practice']
    pratica = [c.id for c in cursos if c.course_type == 'practice']
    pares = {}
    totais = {}
    alunos = set()  # pares que contam como aluno (inscrição ou participação na prática)

    def _u(qs, campo='user_id'):
        return qs.filter(**{f'{campo}__in': user_ids}) if user_ids is not None else qs

    def par(uid, cid):
        p = pares.get((uid, cid))
        if p is None:
            p = pares[(uid, cid)] = Par()
        return p

    # Inscrições activas (qualquer tipo de curso).
    for r in _u(CourseEnrollment.objects.filter(course_id__in=list(por_id), is_active=True)).values(
            'user_id', 'course_id', 'enrollment_date'):
        par(r['user_id'], r['course_id']).ver_inscrito(r['enrollment_date'])
        alunos.add((r['user_id'], r['course_id']))

    if video:
        for r in (Chapter.objects.filter(q_aula_visivel(), section__course_id__in=video).values('section__course_id')
                  .annotate(n=Count('id'))):
            totais[r['section__course_id']] = r['n']
        for r in (_u(ChapterProgress.objects.filter(
                q_aula_visivel('chapter__'), user_progress__course_id__in=video, completed=True,
                chapter__section__course_id=F('user_progress__course_id')), 'user_progress__user_id')
                .values('user_progress__user_id', 'user_progress__course_id')
                .annotate(n=Count('chapter_id', distinct=True), ult=Max('completed_at'))):
            p = par(r['user_progress__user_id'], r['user_progress__course_id'])
            p.feitos = r['n']
            p.ver_actividade(r['ult'])
        for r in (_u(UserCourseProgress.objects.filter(
                course_id__in=video, lastAccessedTimestamp__gt=F('created_at') + FOLGA_CRIACAO))
                .values('user_id', 'course_id', 'lastAccessedTimestamp')):
            par(r['user_id'], r['course_id']).ver_actividade(r['lastAccessedTimestamp'])
        for r in (_u(VideoWatchLog.objects.filter(chapter__section__course_id__in=video))
                  .values('user_id', 'chapter__section__course_id').annotate(ult=Max('updated_at'))):
            par(r['user_id'], r['chapter__section__course_id']).ver_actividade(r['ult'])

    # Exercícios de prática (cursos de prática, e os que um curso em vídeo também tenha).
    # Nos cursos de prática responder conta como participar; nos de vídeo só a inscrição conta.
    e_pratica = set(pratica)
    for r in (_u(ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=list(por_id)))
              .values('user_id', 'challenge__lesson__unit__course_id')
              .annotate(primeiro=Min('completed_at'), ult=Max('updated_at'))):
        chave = (r['user_id'], r['challenge__lesson__unit__course_id'])
        p = par(*chave)
        p.ver_actividade(r['ult'])
        if chave[1] in e_pratica:
            p.ver_inscrito(r['primeiro'])
            alunos.add(chave)
    for r in (_u(ChallengeAttempt.objects.filter(challenge__lesson__unit__course_id__in=list(por_id)))
              .values('user_id', 'challenge__lesson__unit__course_id')
              .annotate(t=Count('id'), certas=Count('id', filter=Q(is_correct=True)),
                        primeiro=Min('created_at'), ult=Max('created_at'))):
        chave = (r['user_id'], r['challenge__lesson__unit__course_id'])
        p = par(*chave)
        p.tentativas, p.certas = r['t'], r['certas']
        p.ver_actividade(r['ult'])
        if chave[1] in e_pratica:
            p.ver_inscrito(r['primeiro'])
            alunos.add(chave)
    for r in (_u(LessonCompletion.objects.filter(lesson__unit__course_id__in=list(por_id)))
              .values('user_id', 'lesson__unit__course_id').annotate(ult=Max('last_completed_at'))):
        par(r['user_id'], r['lesson__unit__course_id']).ver_actividade(r['ult'])

    if pratica:
        for r in (PracticeLesson.objects.filter(unit__course_id__in=pratica).values('unit__course_id')
                  .annotate(n=Count('id'))):
            totais[r['unit__course_id']] = r['n']
        # Curso escolhido como activo, ainda sem respostas: conta como inscrito desde então.
        for r in _u(UserProgress.objects.filter(active_course_id__in=pratica)).values(
                'user_id', 'active_course_id', 'updated_at'):
            chave = (r['user_id'], r['active_course_id'])
            p = par(*chave)
            if p.inscrito is None:
                p.ver_inscrito(r['updated_at'])
            alunos.add(chave)
        # Lições concluídas = lições com todos os exercícios feitos (como nos números dos cursos).
        por_licao = dict(PracticeChallenge.objects.filter(lesson__unit__course_id__in=pratica)
                         .values('lesson_id').annotate(n=Count('id')).values_list('lesson_id', 'n'))
        for r in (_u(ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=pratica,
                                                      completed=True))
                  .values('user_id', 'challenge__lesson_id', 'challenge__lesson__unit__course_id')
                  .annotate(c=Count('challenge_id', distinct=True))):
            total = por_licao.get(r['challenge__lesson_id'], 0)
            if total and r['c'] >= total:
                par(r['user_id'], r['challenge__lesson__unit__course_id']).feitos += 1

    resultado = {}
    for chave in alunos:
        uid, cid = chave
        curso = por_id[cid]
        if uid == curso.teacher_id:
            continue
        p = pares[chave]
        p.total = totais.get(cid, 0)
        resultado[chave] = p
    return resultado


def _estado(inscrito, ultima, agora):
    if ultima is not None:
        if ultima > agora - timedelta(days=DIAS_ACTIVO):
            return 'activo'
        return 'pouco_activo' if ultima > agora - timedelta(days=DIAS_RISCO) else 'em_risco'
    if inscrito is not None and inscrito <= agora - timedelta(days=DIAS_RISCO):
        return 'em_risco'
    return 'novo'


def _iniciais(nome):
    partes = [p for p in (nome or '').split() if p[:1].isalpha()]
    if not partes:
        return 'A'
    if len(partes) == 1:
        return partes[0][0].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _nome(nome):
    return (nome or '').strip() or 'Aluno'


def _pct(certas, total):
    return round(certas * 100 / total) if total else None


def _iso(d):
    return d.isoformat() if d else None


def _curso_api(c):
    return {'id': str(c.id), 'titulo': c.title, 'tipo': ciclo.tipo_api(c)}


# ---------------------------------------------------------------------------
# Lista de alunos
# ---------------------------------------------------------------------------

def _ler_curso(request, cursos):
    valor = (request.query_params.get('curso') or '').strip()
    if not valor:
        return None
    try:
        uuid.UUID(valor)
    except ValueError:
        raise NotFound('Curso não encontrado.')
    curso = exigir_dono_curso(request, valor)
    return next((c for c in cursos if c.id == curso.id), curso)


def _linhas_alunos(request):
    """(numeros, linhas ordenadas e filtradas) ou Response de erro."""
    filtro = (request.query_params.get('filtro') or 'todos').strip()
    if filtro not in FILTROS:
        return _erro('Filtro inválido. Use todos, activos ou em_risco.', 'filtro_invalido',
                     details={'filtro': ['Use todos, activos ou em_risco.']}), None
    cursos = _cursos_visiveis(request)
    curso_filtro = _ler_curso(request, cursos)
    por_id = {c.id: c for c in cursos}
    pares = _pares(cursos)

    por_aluno = defaultdict(dict)
    for (uid, cid), p in pares.items():
        por_aluno[uid][cid] = p
    if curso_filtro is not None:
        por_aluno = {uid: cs for uid, cs in por_aluno.items() if curso_filtro.id in cs}

    nomes = dict(get_user_model().objects.filter(id__in=list(por_aluno)).values_list('id', 'name'))
    agora = timezone.now()

    linhas = []
    cursos_com_alunos = set()
    certas_total = tentativas_total = activos_7d = 0
    for uid, cs in por_aluno.items():
        ambito = {curso_filtro.id: cs[curso_filtro.id]} if curso_filtro is not None else cs
        cursos_com_alunos.update(ambito)
        ultima = max((p.ultima for p in ambito.values() if p.ultima), default=None)
        inscrito = min((p.inscrito for p in ambito.values() if p.inscrito), default=None)
        certas = sum(p.certas for p in ambito.values())
        tentativas = sum(p.tentativas for p in ambito.values())
        certas_total += certas
        tentativas_total += tentativas
        if curso_filtro is not None:
            cid = curso_filtro.id
        else:
            # O curso com a actividade mais recente; sem actividade, a inscrição mais recente.
            cid = max(ambito, key=lambda c: (ambito[c].ultima or datetime.min.replace(tzinfo=FUSO_ANGOLA),
                                             ambito[c].inscrito or datetime.min.replace(tzinfo=FUSO_ANGOLA),
                                             str(c)))
        linhas.append({
            'id': str(uid),
            'nome': _nome(nomes.get(uid)),
            'iniciais': _iniciais(nomes.get(uid)),
            'curso': _curso_api(por_id[cid]),
            'outros_cursos': len(cs) - 1,
            'progresso': ambito[cid].progresso,
            'acerto': _pct(certas, tentativas),
            'ultima_actividade': _iso(ultima),
            'estado': _estado(inscrito, ultima, agora),
            '_ultima': ultima,
        })
        if linhas[-1]['estado'] == 'activo':
            activos_7d += 1

    total_alunos = len(linhas)
    em_risco = sum(1 for l in linhas if l['estado'] == 'em_risco')
    numeros = {
        'alunos': total_alunos,
        'cursos': len(cursos_com_alunos),
        'activos_7d': activos_7d,
        'pct_activos': round(activos_7d * 100 / total_alunos) if total_alunos else 0,
        'em_risco': em_risco,
        'acerto_medio': _pct(certas_total, tentativas_total),
    }

    q = (request.query_params.get('q') or '').strip().lower()
    if q:
        linhas = [l for l in linhas if q in l['nome'].lower()]
    if filtro == 'activos':
        linhas = [l for l in linhas if l['estado'] == 'activo']
    elif filtro == 'em_risco':
        linhas = [l for l in linhas if l['estado'] == 'em_risco']

    linhas.sort(key=lambda l: l['nome'].lower())
    if filtro == 'em_risco':
        # Há mais tempo sem actividade primeiro (nunca activos à cabeça).
        linhas.sort(key=lambda l: (l['_ultima'] is not None, l['_ultima'] or agora))
    else:
        linhas.sort(key=lambda l: l['_ultima'] or datetime.min.replace(tzinfo=FUSO_ANGOLA), reverse=True)
    for l in linhas:
        l.pop('_ultima')
    return numeros, linhas


@api_view(['GET'])
@permission_classes(PERMISSOES)
def lista_alunos(request):
    numeros, linhas = _linhas_alunos(request)
    if linhas is None:
        return numeros
    try:
        pagina = max(1, int(request.query_params.get('pagina') or 1))
    except ValueError:
        pagina = 1
    total = len(linhas)
    inicio = (pagina - 1) * POR_PAGINA
    return Response({
        'numeros': numeros,
        'total': total,
        'paginas': max(1, math.ceil(total / POR_PAGINA)),
        'resultados': linhas[inicio:inicio + POR_PAGINA],
    })


def _celula(valor):
    """Evita fórmulas no Excel (=, +, -, @) em texto vindo de pessoas."""
    texto = '' if valor is None else str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


def _data_pt(d):
    return timezone.localtime(d, FUSO_ANGOLA).strftime('%d/%m/%Y %H:%M') if d else ''


def _csv(nome_ficheiro, linhas):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';', lineterminator='\r\n')
    for linha in linhas:
        escritor.writerow([_celula(v) for v in linha])
    resposta = HttpResponse('﻿' + saida.getvalue(), content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_ficheiro}"'
    return resposta


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exportar_alunos(request):
    _, linhas = _linhas_alunos(request)
    if linhas is None:
        return _
    tabela = [['Aluno', 'Curso', 'Progresso', 'Acerto', 'Última actividade', 'Estado']]
    for l in linhas:
        ultima = datetime.fromisoformat(l['ultima_actividade']) if l['ultima_actividade'] else None
        tabela.append([
            l['nome'], l['curso']['titulo'], f"{l['progresso']}%",
            f"{l['acerto']}%" if l['acerto'] is not None else '',
            _data_pt(ultima), ESTADOS_PT[l['estado']],
        ])
    return _csv('alunos.csv', tabela)


# ---------------------------------------------------------------------------
# Ficha de um aluno
# ---------------------------------------------------------------------------

def _numeracao(exercicios):
    """{challenge_id: (curso, n_unidade, n_licao)} com a numeração pela ordem (1, 2, ...)."""
    from apps.practice.models import PracticeLesson, PracticeUnit

    cursos = {ch.lesson.unit.course_id for ch in exercicios}
    unidades = defaultdict(list)
    for u in PracticeUnit.objects.filter(course_id__in=cursos).order_by('order', 'id').values('id', 'course_id'):
        unidades[u['course_id']].append(u['id'])
    licoes = defaultdict(list)
    for l in (PracticeLesson.objects.filter(unit_id__in={ch.lesson.unit_id for ch in exercicios})
              .order_by('order', 'id').values('id', 'unit_id')):
        licoes[l['unit_id']].append(l['id'])
    resultado = {}
    for ch in exercicios:
        licao, unidade = ch.lesson, ch.lesson.unit
        lista_u, lista_l = unidades[unidade.course_id], licoes[unidade.id]
        n_u = lista_u.index(unidade.id) + 1 if unidade.id in lista_u else unidade.order
        n_l = lista_l.index(licao.id) + 1 if licao.id in lista_l else licao.order
        resultado[ch.id] = (unidade.course, n_u, n_l)
    return resultado


def _tema(ch):
    texto = ' '.join((ch.question or '').split()) or ciclo.TIPOS_EXERCICIO.get(ch.type, ch.type)
    return texto if len(texto) <= LIMITE_TEMA else texto[:LIMITE_TEMA - 1].rstrip() + '…'


def _pratica_de(user):
    """Período do dia (hora de Angola) em que o aluno mais estuda, ou None."""
    from apps.practice.models import ChallengeAttempt, VapiSession

    horas = Counter()
    fontes = (
        (ChallengeAttempt.objects.filter(user=user), 'created_at', 'id'),
        (VideoWatchLog.objects.filter(user=user), 'updated_at', 'id'),
        (VapiSession.objects.filter(user=user, status__in=VapiSession.STATUS_TERMINADAS), 'created_at', 'session_id'),
    )
    for qs, campo, pk in fontes:
        for r in (qs.annotate(h=ExtractHour(campo, tzinfo=FUSO_ANGOLA)).values('h')
                  .annotate(n=Count(pk)).order_by()):
            h = r['h']
            if h is None:
                continue
            horas['manhã' if 5 <= h < 12 else 'tarde' if 12 <= h < 18 else 'noite'] += r['n']
    if not horas:
        return None
    return max(('manhã', 'tarde', 'noite'), key=lambda p: horas[p])


def _plano(user):
    from apps.subscriptions.models import UserSubscription

    sub = UserSubscription.objects.select_related('plan').filter(user=user).first()
    if sub and sub.plan and sub.is_active():
        return PLANOS_PT.get(sub.plan.plan_type, 'Gratuito')
    return 'Gratuito'


def _liga(user):
    from apps.practice.liga import construir_liga_semanal
    from apps.practice.models import UserProgress

    if not UserProgress.objects.filter(user=user).exists():
        return None
    dados = construir_liga_semanal(user)
    return {'nome': dados['liga']['nome'], 'posicao': dados['eu']['posicao']}


@api_view(['GET'])
@permission_classes(PERMISSOES)
def detalhe_aluno(request, aluno_id):
    from apps.courses.certificados import nota_minima
    from apps.practice.models import ChallengeAttempt, PracticeChallenge, UserProgress, UserStreak, VapiSession

    cursos = _cursos_visiveis(request)
    pares = {cid: p for (uid, cid), p in _pares(cursos, user_ids=[aluno_id]).items() if uid == aluno_id}
    if not pares:
        raise NotFound('Aluno não encontrado.')
    aluno = get_user_model().objects.filter(id=aluno_id).only('id', 'name', 'preferences').first()
    if aluno is None:
        raise NotFound('Aluno não encontrado.')

    meus = (Course.objects.filter(id__in=list(pares)).select_related('grading_config')
            .order_by('title'))
    prefs = aluno.preferences if isinstance(aluno.preferences, dict) else {}
    cidade = (prefs.get('cidade') or '').strip() or None

    # Acerto nos cursos do professor: total e variação (últimos 30 dias vs. os 30 anteriores).
    agora = timezone.now()
    tentativas = ChallengeAttempt.objects.filter(user=aluno, challenge__lesson__unit__course_id__in=list(pares))
    a = tentativas.aggregate(
        t=Count('id'), c=Count('id', filter=Q(is_correct=True)),
        t30=Count('id', filter=Q(created_at__gte=agora - timedelta(days=30))),
        c30=Count('id', filter=Q(created_at__gte=agora - timedelta(days=30), is_correct=True)),
        t60=Count('id', filter=Q(created_at__gte=agora - timedelta(days=60),
                                 created_at__lt=agora - timedelta(days=30))),
        c60=Count('id', filter=Q(created_at__gte=agora - timedelta(days=60),
                                 created_at__lt=agora - timedelta(days=30), is_correct=True)),
    )
    variacao = None
    if a['t30'] and a['t60']:
        variacao = round(a['c30'] * 100 / a['t30'] - a['c60'] * 100 / a['t60'])

    streak = UserStreak.objects.filter(user=aluno).first()
    progresso = UserProgress.objects.filter(user=aluno).only('points').first()
    conversas = VapiSession.objects.filter(user=aluno, status__in=VapiSession.STATUS_TERMINADAS).aggregate(
        n=Count('session_id'), minutos=Sum('duration_minutes'))

    notas = {g.course_id: g for g in StudentCourseGrade.objects.filter(user=aluno, course_id__in=list(pares))}
    lista_cursos = []
    for c in meus:
        g = notas.get(c.id)
        comecou = pares[c.id].feitos > 0 or (g is not None and (g.quiz_completed or g.practice_completed))
        nota = None
        if (g is not None and c.course_type != 'practice' and comecou
                and g.final_grade_letter != 'N/A'):
            nota = g.final_grade_percentage
        lista_cursos.append({
            **_curso_api(c),
            'progresso': pares[c.id].progresso,
            'nota': round(nota) if nota is not None else None,
            'abaixo_minimo': nota is not None and nota < nota_minima(c),
        })

    # Onde erra: exercícios com mais respostas erradas nos últimos 60 dias.
    erros = list(tentativas.filter(is_correct=False, created_at__gte=agora - timedelta(days=60))
                 .values('challenge_id').annotate(n=Count('id')).order_by('-n', 'challenge_id')[:5])
    exercicios = {ch.id: ch for ch in PracticeChallenge.objects.filter(id__in=[e['challenge_id'] for e in erros])
                  .select_related('lesson__unit__course')}
    numeracao = _numeracao(list(exercicios.values()))
    onde_erra = []
    for e in erros:
        ch = exercicios.get(e['challenge_id'])
        if ch is None:
            continue
        curso, n_u, n_l = numeracao[ch.id]
        onde_erra.append({'tema': _tema(ch), 'onde': f'{curso.title}, unidade {n_u}, lição {n_l}',
                          'erros': e['n']})

    inscrito = min((p.inscrito for p in pares.values() if p.inscrito), default=None)
    return Response({
        'aluno': {
            'id': str(aluno.id),
            'nome': _nome(aluno.name),
            'iniciais': _iniciais(aluno.name),
            'profissao': ciclo.area_pt(prefs.get('area')),
            'cidade': cidade,
            'inscrito_em': _iso(inscrito),
            'plano': _plano(aluno),
        },
        'numeros': {
            'dias_seguidos': streak.get_effective_streak() if streak else 0,
            'pratica_de': _pratica_de(aluno),
            'pontos': progresso.points if progresso else 0,
            'liga': _liga(aluno),
            'acerto': _pct(a['c'], a['t']),
            'acerto_variacao_30d': variacao,
            'conversa_min': round(conversas['minutos'] or 0),
            'conversas': conversas['n'] or 0,
        },
        'cursos': lista_cursos,
        'onde_erra': onde_erra,
    })


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

def _resultados(request):
    from apps.practice.models import ChallengeAttempt, PracticeChallenge

    valor = (request.query_params.get('periodo') or '30').strip()
    if not valor.isdigit() or int(valor) not in PERIODOS:
        return _erro('Período inválido. Use 7, 30 ou 90 dias.', 'periodo_invalido',
                     details={'periodo': ['Use 7, 30 ou 90 dias.']})
    periodo = int(valor)
    desde = timezone.now() - timedelta(days=periodo)

    cursos = _cursos_visiveis(request)
    m = metricas(cursos)
    # Rascunhos sem alunos não têm resultados para mostrar.
    visiveis = [c for c in cursos if m[c.id]['alunos'] or c.status != ciclo.RASCUNHO]
    conclusao = sorted((
        {**_curso_api(c),
         'conclusao': round(m[c.id]['conclusao']) if m[c.id]['alunos'] and m[c.id]['conclusao'] is not None
         else None,
         'alunos': m[c.id]['alunos']}
        for c in visiveis), key=lambda x: (-x['alunos'], x['titulo'].lower()))

    respostas = ChallengeAttempt.objects.filter(
        challenge__lesson__unit__course_id__in=[c.id for c in cursos], created_at__gte=desde)

    contagem = dict.fromkeys((f[0] for f in FAIXAS), 0)
    # Por aluno (somando os cursos), sem contar o próprio professor a experimentar o curso.
    respostas = respostas.exclude(user_id=F('challenge__lesson__unit__course__teacher_id'))
    for r in respostas.values('user_id').annotate(t=Count('id'), c=Count('id', filter=Q(is_correct=True))):
        certas, total = r['c'], r['t']
        if total < MINIMO_RESPOSTAS:
            continue
        pct = certas * 100 / total
        for nome, minimo, maximo in FAIXAS:
            if minimo <= pct < maximo:
                contagem[nome] += 1
                break
    faixas = [{'nome': nome, 'alunos': contagem[nome]} for nome, _, _ in FAIXAS]

    linhas = list(
        respostas.values('challenge_id')
        .annotate(t=Count('id'), c=Count('id', filter=Q(is_correct=True)))
        .filter(t__gte=MINIMO_RESPOSTAS)
    )
    linhas.sort(key=lambda r: (r['c'] / r['t'], -r['t'], str(r['challenge_id'])))
    linhas = linhas[:8]
    exercicios = {ch.id: ch for ch in PracticeChallenge.objects.filter(id__in=[r['challenge_id'] for r in linhas])
                  .select_related('lesson__unit__course')}
    numeracao = _numeracao(list(exercicios.values()))
    dificeis = []
    for r in linhas:
        ch = exercicios.get(r['challenge_id'])
        if ch is None:
            continue
        curso, n_u, n_l = numeracao[ch.id]
        dificeis.append({
            'challenge_id': str(ch.id),
            'frase': _tema(ch),
            'tipo': ciclo.TIPOS_EXERCICIO.get(ch.type, ch.type),
            'curso_id': str(curso.id),
            'curso': curso.title,
            'unidade_id': str(ch.lesson.unit_id),
            'licao_id': str(ch.lesson_id),
            'onde': f'Unidade {n_u}, lição {n_l}',
            'acerto': round(r['c'] * 100 / r['t']),
            'respostas': r['t'],
        })
    return {'periodo': periodo, 'conclusao_por_curso': conclusao, 'faixas': faixas,
            'perguntas_dificeis': dificeis}


@api_view(['GET'])
@permission_classes(PERMISSOES)
def resultados(request):
    dados = _resultados(request)
    return dados if isinstance(dados, Response) else Response(dados)


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exportar_resultados(request):
    dados = _resultados(request)
    if isinstance(dados, Response):
        return dados
    tabela = [[f"Resultados dos últimos {dados['periodo']} dias"], [],
              ['Conclusão por curso'], ['Curso', 'Tipo', 'Alunos', 'Conclusão']]
    for c in dados['conclusao_por_curso']:
        tabela.append([c['titulo'], 'Prática' if c['tipo'] == 'pratica' else 'Vídeo', c['alunos'],
                       f"{c['conclusao']}%" if c['conclusao'] is not None else ''])
    tabela += [[], ['Perguntas mais difíceis'], ['Pergunta', 'Tipo', 'Curso', 'Onde', 'Acerto', 'Respostas']]
    for p in dados['perguntas_dificeis']:
        tabela.append([p['frase'], p['tipo'], p['curso'], p['onde'], f"{p['acerto']}%", p['respostas']])
    return _csv('resultados.csv', tabela)
