"""
Quando pedir a opinião do aluno.

As métricas vêm dos dados reais (lições concluídas, certificados, conversas avaliadas, dias de estudo),
porque os contadores de UserEngagementMetrics nunca eram actualizados e o pedido nunca aparecia.

Cada momento ("chave") é pedido no máximo uma vez: quando a pessoa envia ou adia, o registo
(FeedbackPromptLog) guarda a chave em context_data.
"""
from datetime import timedelta

from django.utils import timezone

# (chave, trigger do modelo, métrica, mínimo, frase para o topo do pedido)
MOMENTOS = [
    ('primeira_licao', 'first_lesson', 'licoes', 1, 'Concluiu a primeira lição. Como está a correr?'),
    ('curso_concluido', 'course_complete', 'cursos', 1, 'Concluiu o primeiro curso. O que achou?'),
    ('licoes_5', 'milestone_lessons', 'licoes', 5, 'Já fez 5 lições. Como está a correr?'),
    ('conversas_5', 'ai_sessions', 'conversas', 5, 'Já conversou 5 vezes com o tutor. Está a ajudar?'),
    ('dias_7', 'days_active', 'dias', 7, 'Estudou em 7 dias diferentes. Como está a correr?'),
    ('licoes_25', 'milestone_lessons', 'licoes', 25, 'Já fez 25 lições. O que mudaria?'),
    ('dias_30', 'days_active', 'dias', 30, 'Um mês a estudar connosco. Como está a correr?'),
]
ESPERA_DEPOIS_DE_OPINIAO = timedelta(days=7)
ESPERA_DEPOIS_DE_PEDIDO = timedelta(days=3)


def metricas(user):
    from apps.courses.models import CourseCertificate
    from apps.practice.models import DailyStudyLog, LessonCompletion, UserStreak, VapiSession

    streak = UserStreak.objects.filter(user=user).first()
    return {
        'licoes': LessonCompletion.objects.filter(user=user).count(),
        'cursos': CourseCertificate.objects.filter(user=user).count(),
        'conversas': VapiSession.objects.filter(user=user, status='avaliada').count(),
        'dias': DailyStudyLog.objects.filter(user=user).values('date').distinct().count(),
        'sequencia': getattr(streak, 'current_streak', 0) or 0,
    }


def chaves_ja_pedidas(user):
    from .models import FeedbackPromptLog
    return {
        (c or {}).get('chave')
        for c in FeedbackPromptLog.objects.filter(user=user).values_list('context_data', flat=True)
    } - {None}


def pedido(user, engagement):
    """Devolve (mostrar, chave, trigger, frase, metricas)."""
    m = metricas(user)
    agora = timezone.now()
    if engagement.last_feedback_at and agora - engagement.last_feedback_at < ESPERA_DEPOIS_DE_OPINIAO:
        return False, None, None, None, m
    if engagement.last_prompt_at and agora - engagement.last_prompt_at < ESPERA_DEPOIS_DE_PEDIDO:
        return False, None, None, None, m
    pedidas = chaves_ja_pedidas(user)
    for chave, trigger, metrica, minimo, frase in MOMENTOS:
        if m[metrica] >= minimo and chave not in pedidas:
            return True, chave, trigger, frase, m
    return False, None, None, None, m


def sincronizar(engagement, m):
    """Mantém os contadores do modelo alinhados com os dados reais (para a administração)."""
    engagement.total_lessons_completed = m['licoes']
    engagement.total_courses_completed = m['cursos']
    engagement.total_ai_sessions = m['conversas']
    engagement.total_days_active = m['dias']
    engagement.current_streak = m['sequencia']
    engagement.longest_streak = max(engagement.longest_streak or 0, m['sequencia'])
    engagement.save(update_fields=['total_lessons_completed', 'total_courses_completed', 'total_ai_sessions',
                                   'total_days_active', 'current_streak', 'longest_streak'])
