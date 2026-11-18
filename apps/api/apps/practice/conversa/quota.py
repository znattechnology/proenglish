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
MOTIVO_SEM_MINUTOS_MES = 'sem_minutos_mes'

MENSAGENS = {
    MOTIVO_SEM_MINUTOS: 'Já usou os minutos de conversa de hoje. Volte amanhã ou assine um plano com mais minutos.',
    MOTIVO_PLANO_SEM_TUTOR: 'O seu plano não inclui conversa com o tutor.',
    MOTIVO_TESTE_EXPIRADO: 'O seu período de teste terminou. Escolha um plano para continuar a conversar.',
    MOTIVO_SEM_MINUTOS_MES: ('Já usou os minutos de conversa deste mês. Renovam no dia 1 do próximo mês, '
                             'ou pode passar a um plano com mais minutos.'),
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
    from .configuracao import actual
    max_sessao = actual()['max_minutos_sessao']   # editável no admin
    # Mensal (só nos planos que o têm): o que acabar primeiro, o do dia ou o do mês.
    limite_mes = plano.monthly_speaking_minutes
    usados_mes = sub.monthly_speaking_minutes_used
    restantes_mes = None if limite_mes is None else max(0, limite_mes - usados_mes)

    restantes = None if limite is None else max(0, limite - usados)
    candidatos = [x for x in (restantes, restantes_mes) if x is not None]
    max_minutos = min([max_sessao, *candidatos])

    motivo = None
    if limite is not None and limite <= 0:
        motivo = MOTIVO_TESTE_EXPIRADO if teste_acabou else MOTIVO_PLANO_SEM_TUTOR
    elif restantes_mes is not None and restantes_mes < 1:
        motivo = MOTIVO_SEM_MINUTOS_MES
    elif restantes is not None and restantes < 1:
        motivo = MOTIVO_SEM_MINUTOS

    return {
        'plano': plano.name,
        'minutos_dia': limite,
        'minutos_usados': usados,
        'minutos_restantes': restantes if restantes_mes is None else (
            restantes_mes if restantes is None else min(restantes, restantes_mes)),
        'minutos_mes': limite_mes,
        'minutos_usados_mes': usados_mes,
        'minutos_restantes_mes': restantes_mes,
        'max_minutos_sessao': max_minutos if motivo is None else 0,
        'pode_comecar': motivo is None,
        'motivo': motivo,
    }
