"""
Quota diária de conversa com o tutor, calculada no servidor.

O que limita a conversa é SubscriptionPlan.daily_speaking_minutes (ou
trial_speaking_minutes durante o período de teste do plano gratuito). O campo
SubscriptionPlan.ai_tutor NÃO é usado aqui: no código existente não controla nada
(só aparece em ecrãs de planos) e no Premium está a False, o que bloquearia o
Premium apesar de ter 10 min/dia. Ver relatório.

Uma assinatura paga expirada passa a ter as regras do plano gratuito.
"""
from django.conf import settings

from apps.subscriptions.models import SubscriptionPlan, UserSubscription

MOTIVO_SEM_MINUTOS = 'sem_minutos'
MOTIVO_PLANO_SEM_TUTOR = 'plano_sem_tutor'
MOTIVO_TESTE_EXPIRADO = 'teste_expirado'

MENSAGENS = {
    MOTIVO_SEM_MINUTOS: 'Já usou todos os minutos de conversa de hoje. Volte amanhã ou mude de plano.',
    MOTIVO_PLANO_SEM_TUTOR: 'O seu plano não inclui conversa com o tutor.',
    MOTIVO_TESTE_EXPIRADO: 'O seu período de teste terminou. Escolha um plano para continuar a conversar.',
}


def obter_assinatura(user, bloquear=False):
    from apps.subscriptions.services import obter_ou_criar_assinatura
    sub = obter_ou_criar_assinatura(user)
    if bloquear:
        sub = UserSubscription.objects.select_for_update().select_related('plan').get(pk=sub.pk)
    sub.reset_daily_usage_if_needed()
    return sub


def _plano_efectivo(sub):
    if sub.plan.plan_type != 'FREE' and not sub.is_active():
        gratuito = SubscriptionPlan.objects.filter(plan_type='FREE').first()
        if gratuito:
            return gratuito, True
    return sub.plan, False


def limite_diario(sub):
    """Minutos/dia (None = ilimitado) e se o plano é o gratuito fora do período de teste."""
    plano, _ = _plano_efectivo(sub)
    if plano.plan_type == 'FREE' and plano.trial_days and sub.is_in_trial_period():
        return (plano.trial_speaking_minutes or plano.daily_speaking_minutes), False
    teste_acabou = plano.plan_type == 'FREE' and bool(plano.trial_days)
    return plano.daily_speaking_minutes, teste_acabou


def estado_quota(user, sub=None):
    sub = sub or obter_assinatura(user)
    plano, expirada = _plano_efectivo(sub)
    limite, teste_acabou = limite_diario(sub)
    usados = sub.daily_speaking_minutes_used
    max_sessao = settings.CONVERSA_MAX_MINUTOS_SESSAO

    if limite is None:
        restantes = None
        max_minutos = max_sessao
    else:
        restantes = max(0, limite - usados)
        max_minutos = min(max_sessao, restantes)

    motivo = None
    if limite is not None and limite <= 0:
        motivo = MOTIVO_TESTE_EXPIRADO if teste_acabou else MOTIVO_PLANO_SEM_TUTOR
    elif restantes is not None and restantes < 1:
        motivo = MOTIVO_SEM_MINUTOS

    return {
        'plano': plano.name,
        'minutos_dia': limite,
        'minutos_usados': usados,
        'minutos_restantes': restantes,
        'max_minutos_sessao': max_minutos if motivo is None else 0,
        'pode_comecar': motivo is None,
        'motivo': motivo,
    }
