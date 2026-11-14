"""
Actividade dos alunos por curso: quem é aluno de que curso e quanto fez num período.

Usado pelas conquistas dos professores (achievement_utils), pelas competições
(competicoes.py) e pelos números da área do professor (professor/).

Aluno de um curso (o mesmo critério da lista de alunos do professor):
- inscrição activa (CourseEnrollment), em qualquer tipo de curso;
- num curso de prática, ter feito exercícios (ChallengeProgress) ou tê-lo como curso activo.

Métricas (`valores`), sempre por aluno e, quando há `cursos`, só a actividade nesses cursos:
- licoes: lições de prática concluídas pela primeira vez (LessonCompletion) + aulas de vídeo
  concluídas (ChapterProgress.completed_at);
- pontos: pontos ganhos nesses cursos (PointsEntry.curso);
- dias_seguidos: maior sequência de dias seguidos (hora de Luanda) com actividade nesses cursos
  (pontos, respostas a exercícios, tempo de vídeo);
- minutos_conversa: minutos com o tutor (todas as conversas do aluno; a conversa não pertence
  a um curso);
- conversas: conversas avaliadas nas situações indicadas em `situacoes` (slugs); sem
  `situacoes`, todas;
- palavras: palavras ditas nas conversas terminadas nessas situações.
"""
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

FUSO = ZoneInfo('Africa/Luanda')
METRICAS = ('licoes', 'pontos', 'dias_seguidos', 'minutos_conversa', 'conversas', 'palavras')


def cursos_do_aluno(user):
    """Ids dos cursos de que a pessoa é aluna."""
    from apps.courses.models import CourseEnrollment
    from apps.practice.models import ChallengeProgress, UserProgress

    ids = set(CourseEnrollment.objects.filter(user=user, is_active=True).values_list('course_id', flat=True))
    ids |= set(ChallengeProgress.objects.filter(user=user)
               .values_list('challenge__lesson__unit__course_id', flat=True).distinct())
    activo = UserProgress.objects.filter(user=user).values_list('active_course_id', flat=True).first()
    if activo:
        ids.add(activo)
    ids.discard(None)
    return ids


def alunos_dos_cursos(cursos):
    """Ids dos alunos dos cursos (sem os donos dos cursos)."""
    from apps.courses.models import Course, CourseEnrollment
    from apps.practice.models import ChallengeProgress, UserProgress

    cursos = list(cursos)
    if not cursos:
        return set()
    ids = set(CourseEnrollment.objects.filter(course_id__in=cursos, is_active=True)
              .values_list('user_id', flat=True))
    ids |= set(ChallengeProgress.objects.filter(challenge__lesson__unit__course_id__in=cursos)
               .values_list('user_id', flat=True).distinct())
    ids |= set(UserProgress.objects.filter(active_course_id__in=cursos).values_list('user_id', flat=True))
    ids -= set(Course.objects.filter(id__in=cursos).values_list('teacher_id', flat=True))
    return ids


def _periodo(qs, campo, inicio, fim):
    if inicio is not None:
        qs = qs.filter(**{f'{campo}__gte': inicio})
    if fim is not None:
        qs = qs.filter(**{f'{campo}__lt': fim})
    return qs


def _dia(dt):
    return timezone.localtime(dt, FUSO).date()


def maior_sequencia(dias):
    """Maior número de dias seguidos num conjunto de datas."""
    melhor = actual = 0
    anterior = None
    for d in sorted(dias):
        actual = actual + 1 if anterior is not None and d == anterior + timedelta(days=1) else 1
        melhor = max(melhor, actual)
        anterior = d
    return melhor


def dias_activos(user_ids, cursos=None, inicio=None, fim=None):
    """{user_id: set(datas)} com actividade nos cursos (None = qualquer curso)."""
    from apps.courses.models import VideoWatchLog
    from apps.practice.models import ChallengeAttempt, PointsEntry

    dias = defaultdict(set)
    user_ids = list(user_ids)
    if not user_ids:
        return dias
    pontos = PointsEntry.objects.filter(user_id__in=user_ids)
    respostas = ChallengeAttempt.objects.filter(user_id__in=user_ids)
    video = VideoWatchLog.objects.filter(user_id__in=user_ids)
    if cursos is not None:
        cursos = list(cursos)
        pontos = pontos.filter(curso_id__in=cursos)
        respostas = respostas.filter(challenge__lesson__unit__course_id__in=cursos)
        video = video.filter(chapter__section__course_id__in=cursos)
    for uid, quando in _periodo(pontos, 'created_at', inicio, fim).values_list('user_id', 'created_at'):
        dias[uid].add(_dia(quando))
    for uid, quando in _periodo(respostas, 'created_at', inicio, fim).values_list('user_id', 'created_at'):
        dias[uid].add(_dia(quando))
    if inicio is not None:
        video = video.filter(date__gte=_dia(inicio))
    if fim is not None:  # fim é exclusivo: o último dia é o do instante anterior
        video = video.filter(date__lte=_dia(fim - timedelta(microseconds=1)))
    for uid, d in video.values_list('user_id', 'date'):
        dias[uid].add(d)
    return dias


def valores(metrica, user_ids, cursos=None, inicio=None, fim=None, situacoes=None):
    """{user_id: int} da métrica para cada aluno (0 quando não fez nada)."""
    from apps.courses.models import ChapterProgress
    from apps.practice.models import LessonCompletion, PointsEntry, VapiSession

    user_ids = list(user_ids)
    out = {uid: 0 for uid in user_ids}
    if not user_ids:
        return out
    cursos = list(cursos) if cursos is not None else None

    if metrica == 'licoes':
        qs = LessonCompletion.objects.filter(user_id__in=user_ids)
        cap = ChapterProgress.objects.filter(user_progress__user_id__in=user_ids, completed=True,
                                             completed_at__isnull=False)
        if cursos is not None:
            qs = qs.filter(lesson__unit__course_id__in=cursos)
            cap = cap.filter(user_progress__course_id__in=cursos)
        for r in _periodo(qs, 'first_completed_at', inicio, fim).values('user_id').annotate(n=Count('id')):
            out[r['user_id']] += r['n']
        for r in (_periodo(cap, 'completed_at', inicio, fim).values('user_progress__user_id')
                  .annotate(n=Count('id'))):
            out[r['user_progress__user_id']] += r['n']
    elif metrica == 'pontos':
        qs = PointsEntry.objects.filter(user_id__in=user_ids)
        if cursos is not None:
            qs = qs.filter(curso_id__in=cursos)
        for r in _periodo(qs, 'created_at', inicio, fim).values('user_id').annotate(n=Sum('points')):
            out[r['user_id']] = r['n'] or 0
    elif metrica == 'dias_seguidos':
        for uid, dias in dias_activos(user_ids, cursos, inicio, fim).items():
            out[uid] = maior_sequencia(dias)
    elif metrica in ('minutos_conversa', 'conversas', 'palavras'):
        if metrica == 'conversas':  # só as avaliadas (com conteúdo suficiente para avaliar)
            qs = VapiSession.objects.filter(user_id__in=user_ids, status=VapiSession.STATUS_AVALIADA)
        else:
            qs = VapiSession.objects.filter(user_id__in=user_ids, status__in=VapiSession.STATUS_TERMINADAS)
        if metrica != 'minutos_conversa' and situacoes is not None:
            qs = qs.filter(situation__in=list(situacoes))
        qs = _periodo(qs, 'created_at', inicio, fim)
        agregado = {'minutos_conversa': Sum('duration_minutes'), 'conversas': Count('session_id'),
                    'palavras': Sum('total_words')}[metrica]
        for r in qs.values('user_id').annotate(n=agregado):
            out[r['user_id']] = r['n'] or 0
    else:
        raise ValueError(f'Métrica desconhecida: {metrica}')
    return out
