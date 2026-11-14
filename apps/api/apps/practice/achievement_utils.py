"""
Achievement utility functions.

Extracted from views.py to reduce coupling and file size.
"""

import logging

from .models import Achievement, UserAchievement, AchievementNotification

logger = logging.getLogger(__name__)


def notify_achievement_unlocked(user, achievement):
    """Publish an in-app Notification for a newly unlocked achievement."""
    try:
        from apps.users.models import Notification
        Notification.notify(
            user,
            Notification.KIND_ACHIEVEMENT,
            title=f'Conquista desbloqueada: {achievement.title}',
            body=achievement.description or '',
            link='/user/laboratory/achievements',
            dedupe_key=f'conquista:{achievement.pk}',
        )
    except Exception:
        logger.exception("Failed to create achievement notification for user %s", user.pk)


def check_achievement_progress(user, achievement_type, current_value):
    """
    Helper function to check and update achievement progress.

    Called from other parts of the system when user actions occur.

    Args:
        user: The user whose achievement progress to check
        achievement_type: The type of achievement to check
        current_value: The current progress value

    Returns:
        List of newly unlocked achievements
    """
    # Get achievements of the specified type
    # Só as conquistas da plataforma: as dos professores contam apenas a actividade nos
    # cursos deles (verificar_conquistas_professor).
    achievements = Achievement.objects.filter(
        requirement_type=achievement_type,
        is_active=True,
        criado_por__isnull=True,
    )

    newly_unlocked = []

    for achievement in achievements:
        if _actualizar(user, achievement, current_value):
            newly_unlocked.append(achievement)

    return newly_unlocked


def _actualizar(user, achievement, valor):
    """
    Guarda o progresso; True se a conquista foi desbloqueada agora.

    A linha UserAchievement (única por aluno e conquista) é bloqueada (select_for_update) antes
    de ver se já estava desbloqueada: dois pedidos ao mesmo tempo não dão os pontos duas vezes.
    """
    from django.db import transaction

    with transaction.atomic():
        UserAchievement.objects.get_or_create(user=user, achievement=achievement,
                                              defaults={'current_progress': 0})
        user_achievement = (UserAchievement.objects.select_for_update()
                            .select_related('achievement').get(user=user, achievement=achievement))
        if user_achievement.is_unlocked:
            return False
        if not user_achievement.update_progress(valor):
            return False
    _, criada = AchievementNotification.objects.get_or_create(user=user, achievement=achievement)
    if criada:
        notify_achievement_unlocked(user, achievement)
    return True


# ---------------------------------------------------------------------------
# Conquistas dos professores (âmbito: cursos do professor)
# ---------------------------------------------------------------------------

# tipo da regra (API do professor) -> (nome, unidade, categoria)
TIPOS_PROFESSOR = {
    'conversas': ('Conversas com o tutor', 'conversas', 'learning'),
    'licoes': ('Lições concluídas', 'lições', 'learning'),
    'dias_seguidos': ('Dias seguidos de prática', 'dias', 'streak'),
    'pontos': ('Pontos ganhos', 'pontos', 'milestone'),
    'palavras': ('Palavras ditas nas conversas', 'palavras', 'learning'),
}


def ambito_conquista(achievement):
    """
    (cursos, situacoes) que contam para uma conquista de professor:
    - cursos: o curso da conquista, ou todos os cursos do professor;
    - situacoes (conversas e palavras): slugs das situações da plataforma (Geral, para todos)
      mais as do professor (com curso: as desse curso e as Gerais dele). As conversas não
      pertencem a um curso; contam as do aluno nessas situações. Situações de outros
      professores não contam.
    """
    from django.db.models import Q
    from apps.courses.models import Course
    from .models import Situacao

    plataforma = Q(criado_por__isnull=True)
    if achievement.curso_id:
        cursos = [achievement.curso_id]
        do_professor = Q(criado_por_id=achievement.criado_por_id) & (
            Q(curso_id=achievement.curso_id) | Q(curso__isnull=True))
    else:
        cursos = list(Course.objects.filter(teacher_id=achievement.criado_por_id).values_list('id', flat=True))
        do_professor = Q(criado_por_id=achievement.criado_por_id)
    situacoes = Situacao.objects.filter(plataforma | do_professor)
    return cursos, list(situacoes.values_list('slug', flat=True))


def valor_conquista_professor(user_ids, achievement):
    """{user_id: valor} da regra de uma conquista de professor, só nos cursos dela."""
    from . import actividade

    cursos, situacoes = ambito_conquista(achievement)
    return actividade.valores(achievement.requirement_type, user_ids, cursos=cursos, situacoes=situacoes)


def conquistas_professor_do_aluno(user, apenas_activas=True):
    """
    Conquistas de professores que se aplicam ao aluno (é aluno de um curso do âmbito).
    Com apenas_activas: as activas e também as desligadas que o aluno já ganhou (desligar uma
    conquista não a tira a quem já a tem); as desligadas por ganhar não aparecem.
    """
    from django.db.models import Q
    from . import actividade

    cursos = actividade.cursos_do_aluno(user)
    if not cursos:
        return Achievement.objects.none()
    from apps.courses.models import Course
    professores = Course.objects.filter(id__in=cursos).values_list('teacher_id', flat=True)
    qs = Achievement.objects.filter(criado_por__isnull=False).filter(
        Q(curso_id__in=cursos) | Q(curso__isnull=True, criado_por_id__in=professores)
    ).exclude(criado_por=user)
    if apenas_activas:
        qs = qs.filter(Q(is_active=True) | Q(id__in=_ganhas(user)))
    return qs


def conquistas_plataforma_do_aluno(user):
    """Conquistas da plataforma a mostrar ao aluno: as activas e as desligadas que já ganhou."""
    from django.db.models import Q
    return (Achievement.objects.filter(criado_por__isnull=True)
            .filter(Q(is_active=True) | Q(id__in=_ganhas(user))))


def _ganhas(user):
    return UserAchievement.objects.filter(user=user, is_unlocked=True).values('achievement_id')


def verificar_conquistas_professor(user):
    """
    Actualiza o progresso do aluno nas conquistas dos professores dele (valor lido das
    tabelas, só nos cursos de cada conquista). Nunca levanta excepções.

    Corre em cada atribuição de pontos, por isso sai cedo (1-2 consultas) quando não há
    conquistas de professores activas, ou nenhuma por ganhar no âmbito do aluno.
    """
    try:
        if not Achievement.objects.filter(criado_por__isnull=False, is_active=True,
                                          requirement_type__in=list(TIPOS_PROFESSOR)).exists():
            return []
        pendentes = list(
            conquistas_professor_do_aluno(user, apenas_activas=False)
            .filter(is_active=True, requirement_type__in=list(TIPOS_PROFESSOR))
            .exclude(id__in=UserAchievement.objects.filter(user=user, is_unlocked=True)
                     .values('achievement_id')))
        desbloqueadas = []
        for conquista in pendentes:
            valor = valor_conquista_professor([user.id], conquista)[user.id]
            if _actualizar(user, conquista, valor):
                desbloqueadas.append(conquista)
        return desbloqueadas
    except Exception:
        logger.exception('Falha ao verificar as conquistas dos professores do utilizador %s', user.pk)
        return []


def live_achievement_values(user, requirement_types):
    """
    Valor actual, lido das tabelas reais, para os tipos de requisito conhecidos
    (os mesmos que check_achievement_progress recebe noutros pontos do sistema).
    Tipos desconhecidos ficam de fora (usa-se o current_progress guardado).
    """
    from django.db.models import Count, F, Q
    from .models import ChallengeProgress, PracticeLesson, UserProgress, UserStreak

    values = {}
    if 'challenges_completed' in requirement_types:
        values['challenges_completed'] = ChallengeProgress.objects.filter(user=user, completed=True).count()
    if 'lessons_completed' in requirement_types:
        values['lessons_completed'] = PracticeLesson.objects.annotate(
            total=Count('challenges', distinct=True),
            done=Count('challenges__user_progress', distinct=True, filter=Q(
                challenges__user_progress__user=user, challenges__user_progress__completed=True)),
        ).filter(total__gt=0, done=F('total')).count()
    if 'points_earned' in requirement_types:
        progress = UserProgress.objects.filter(user=user).first()
        values['points_earned'] = progress.points if progress else 0
    if 'streak_days' in requirement_types:
        streak = UserStreak.objects.filter(user=user).first()
        values['streak_days'] = streak.longest_streak if streak else 0
    return values
