"""
Renovação manual de subscrições (Multicaixa Express não faz débito automático).

* ``expirar_subscricoes``: subscrições pagas cujo período terminou voltam ao
  plano Gratuito (o progresso de aprendizagem não é tocado).
* ``enviar_lembretes``: lembrete quando faltam <= 72 h (D3) e <= 24 h (D0) para o
  fim, uma única vez por período, apenas se ``lembretes_renovacao`` estiver ligado.

Ambos são idempotentes e o comando ``python manage.py enviar_lembretes_renovacao``
envia os lembretes ANTES de expirar; pode correr de hora a hora (ver
deploy/cron/proenglish.cron).
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.subscriptions.models import UserSubscription, SubscriptionHistory
from apps.subscriptions.services import obter_plano_gratuito, DURACAO_PLANO_GRATUITO

from .models import LembreteRenovacao
from .services import FUSO_ANGOLA
from .signals import lembrete_renovacao, subscricao_expirada

logger = logging.getLogger(__name__)

# Antecedência de cada lembrete (em relação a expires_at)
ANTECEDENCIA_D3 = timedelta(hours=72)
ANTECEDENCIA_D0 = timedelta(hours=24)


def expirar_subscricoes(agora=None, dry_run=False):
    """Volta ao Gratuito as subscrições pagas com o período terminado."""
    agora = agora or timezone.now()
    gratuito = obter_plano_gratuito()
    candidatas = (
        UserSubscription.objects
        .filter(expires_at__lte=agora)
        .exclude(plan__plan_type='FREE')
        .exclude(status='TRIAL')  # os testes terminam em teste.terminar_testes
        .select_related('plan')
    )
    total = 0
    for sub in candidatas:
        if dry_run:
            total += 1
            continue
        with transaction.atomic():
            s = UserSubscription.objects.select_for_update(of=('self',)).select_related('plan').get(pk=sub.pk)
            if s.plan.plan_type == 'FREE' or s.expires_at > agora or s.status == 'TRIAL':
                continue  # renovada entretanto
            plano_anterior = s.plan
            fim_anterior = s.expires_at
            s.plan = gratuito
            s.status = 'ACTIVE'
            s.canceled_at = None
            s.expires_at = agora + DURACAO_PLANO_GRATUITO
            # O preço contratado e o código em curso acabam com a subscrição
            s.preco_mensal_kz = s.preco_anual_kz = None
            s.promo_codigo = None
            s.promo_meses_usados = 0
            # Ajustar vidas ao limite do plano gratuito (sem tocar no progresso)
            if gratuito.hearts_limit and s.current_hearts > gratuito.hearts_limit:
                s.current_hearts = gratuito.hearts_limit
            s.save()
            SubscriptionHistory.objects.create(
                subscription=s,
                event_type='EXPIRED',
                previous_plan=plano_anterior,
                new_plan=gratuito,
                notes=f'Período pago terminou em {fim_anterior.isoformat()} sem renovação; '
                      f'voltou ao plano Gratuito.',
            )
            total += 1
            transaction.on_commit(
                lambda s=s, p=plano_anterior: subscricao_expirada.send(
                    sender=UserSubscription, subscription=s, plano_anterior=p)
            )
    return total


def enviar_lembretes(agora=None, dry_run=False):
    """
    Envia (sinal) os lembretes ainda não enviados para o período atual:
    D0 quando faltam <= 24 h, D3 quando faltam <= 72 h (e mais de 24 h).
    Uma vez por (subscrição, tipo, fim do período): seguro de correr de hora a hora.
    """
    agora = agora or timezone.now()
    candidatas = (
        UserSubscription.objects
        .filter(
            status='ACTIVE',
            lembretes_renovacao=True,
            expires_at__gt=agora,
            expires_at__lte=agora + ANTECEDENCIA_D3,
        )
        .exclude(plan__plan_type='FREE')
        .select_related('plan', 'user')
    )
    enviados = []
    for sub in candidatas:
        falta = sub.expires_at - agora
        tipo = LembreteRenovacao.D0 if falta <= ANTECEDENCIA_D0 else LembreteRenovacao.D3
        if LembreteRenovacao.objects.filter(
                subscription=sub, tipo=tipo, fim_periodo=sub.expires_at).exists():
            continue
        if dry_run:
            enviados.append((sub, tipo))
            continue
        try:
            with transaction.atomic():
                LembreteRenovacao.objects.create(
                    subscription=sub, tipo=tipo, fim_periodo=sub.expires_at)
        except IntegrityError:
            continue  # outra execução em paralelo já registou
        enviados.append((sub, tipo))
        try:
            lembrete_renovacao.send(
                sender=UserSubscription, subscription=sub, tipo=tipo,
                fim_periodo=sub.expires_at)
        except Exception:
            logger.exception('Falha num recetor de lembrete_renovacao (subscrição %s)', sub.pk)
    return enviados
