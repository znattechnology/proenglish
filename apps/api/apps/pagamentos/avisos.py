"""
Avisos ao aluno a partir dos sinais da app pagamentos (ligados em apps.py).

Todos são do tipo ``subscription`` (mensagens de serviço, sempre ligadas) e
deduplicados por ``dedupe_key``, por isso repetir um sinal não duplica avisos.
"""

import logging

from django.dispatch import receiver
from django.utils import timezone

from .services import FUSO_ANGOLA
from .signals import (
    lembrete_renovacao, pagamento_confirmado, subscricao_expirada,
    teste_a_terminar, teste_iniciado, teste_terminado,
)

logger = logging.getLogger(__name__)

LINK_SUBSCRICAO = '/user/subscription'
LINK_RECIBOS = '/user/billing'


def formatar_kz(valor):
    """15000 -> '15 000 Kz' (separador de milhares com espaço, como em pt-PT)."""
    return f'{int(valor):,}'.replace(',', ' ') + ' Kz'


def _data(dt):
    return timezone.localtime(dt, FUSO_ANGOLA).strftime('%d/%m/%Y')


def _notify(user, **kwargs):
    from apps.users.models import Notification
    try:
        return Notification.notify(user, Notification.KIND_SUBSCRIPTION, **kwargs)
    except Exception:  # nunca bloquear pagamentos/renovações por causa de um aviso
        logger.exception('Falha ao criar aviso de subscrição (user=%s)', getattr(user, 'pk', None))
        return None


def _hora(dt):
    return timezone.localtime(dt, FUSO_ANGOLA).strftime('%H:%M')


@receiver(pagamento_confirmado, dispatch_uid='avisos_pagamento_confirmado')
def avisar_pagamento_confirmado(sender, pagamento, **kwargs):
    recibo = f' Recibo n.º {pagamento.numero_recibo}.' if pagamento.numero_recibo else ''
    validade = f' O plano está activo até {_data(pagamento.periodo_fim)}.' if pagamento.periodo_fim else ''
    credito = ''
    credito_kz = getattr(pagamento, 'credito_kz', 0) or 0
    if credito_kz:
        credito = f' Os dias que faltavam no plano anterior valeram {formatar_kz(credito_kz)} de crédito.'
    if pagamento.total_kz > 0:
        title = 'Pagamento recebido'
        inicio = (f'Recebemos {formatar_kz(pagamento.total_kz)} por Multicaixa Express '
                  f'({pagamento.descricao}).')
    else:
        title = 'Plano activado'
        inicio = f'Activámos o {pagamento.descricao} sem pagamento (0 Kz).'
    _notify(
        pagamento.user,
        title=title,
        body=f'{inicio}{credito}{validade}{recibo}',
        link=LINK_RECIBOS,
        dedupe_key=f'pagamento:{pagamento.pk}',
    )


@receiver(lembrete_renovacao, dispatch_uid='avisos_lembrete_renovacao')
def avisar_lembrete_renovacao(sender, subscription, tipo, fim_periodo, **kwargs):
    plano = subscription.plan.name
    dias = (timezone.localtime(fim_periodo, FUSO_ANGOLA).date()
            - timezone.localtime(timezone.now(), FUSO_ANGOLA).date()).days
    if tipo == 'D0':
        quando = 'hoje' if dias <= 0 else 'amanhã'
        title = f'A sua subscrição termina {quando}'
        body = (f'O plano {plano} termina {quando} às {_hora(fim_periodo)}. Renove com Multicaixa '
                f'Express para continuar com acesso aos cursos sem interrupções.')
    else:
        quando = 'amanhã' if dias <= 1 else f'dentro de {dias} dias'
        title = f'A sua subscrição termina {quando}'
        body = (f'O plano {plano} termina a {_data(fim_periodo)}. Renove com Multicaixa '
                f'Express para não perder o acesso aos cursos.')
    _notify(
        subscription.user, title=title, body=body, link=LINK_SUBSCRICAO,
        dedupe_key=f'renovacao:{tipo}:{subscription.pk}:{fim_periodo:%Y%m%d%H%M}',
    )


@receiver(subscricao_expirada, dispatch_uid='avisos_subscricao_expirada')
def avisar_subscricao_expirada(sender, subscription, plano_anterior, **kwargs):
    hoje = timezone.localtime(timezone.now(), FUSO_ANGOLA).date()
    _notify(
        subscription.user,
        title='O seu plano terminou',
        body=(f'O plano {plano_anterior.name} terminou e a sua conta voltou ao plano Gratuito. '
              f'O seu progresso foi mantido. Renove quando quiser para recuperar o acesso.'),
        link=LINK_SUBSCRICAO,
        dedupe_key=f'plano-expirado:{subscription.pk}:{hoje.isoformat()}',
    )


# ---------------------------------------------------------------------------
# Período de teste grátis (apps/pagamentos/teste.py): aviso in-app + email
# ---------------------------------------------------------------------------

def _email_teste(user, assunto, paragrafos, botao_texto=None, botao_caminho=None):
    if not getattr(user, 'email', None):
        return False
    try:
        from apps.users.email_service import _contexto_base, _enviar, _link
        ctx = {**_contexto_base(user, user.email), 'assunto': assunto, 'paragrafos': paragrafos,
               'botao_texto': botao_texto, 'botao_link': _link(botao_caminho) if botao_caminho else None}
        return _enviar(f'{assunto} - ProEnglish', 'emails/teste_plano.html', ctx, user.email)
    except Exception:
        logger.exception('Falha ao enviar email do teste (user=%s)', getattr(user, 'pk', None))
        return False


def _link_pagar(plano):
    return f'/user/upgrade?plan={plano.plan_type}'


@receiver(teste_iniciado, dispatch_uid='avisos_teste_iniciado')
def avisar_teste_iniciado(sender, subscription, **kwargs):
    plano = subscription.plan
    fim = subscription.trial_ends_at or subscription.expires_at
    title = f'Começou o seu teste do {plano.name}'
    body = (f'Tem o {plano.name} grátis até {_data(fim)}. Não paga nada agora. Para continuar depois '
            f'disso, pague com Multicaixa Express; se não pagar, a conta volta ao Gratuito e o '
            f'progresso fica guardado.')
    _notify(subscription.user, title=title, body=body, link=LINK_SUBSCRICAO,
            dedupe_key=f'teste:inicio:{subscription.pk}:{fim:%Y%m%d%H%M}')
    _email_teste(subscription.user, title, [body], 'Ver a subscrição', LINK_SUBSCRICAO)


@receiver(teste_a_terminar, dispatch_uid='avisos_teste_a_terminar')
def avisar_teste_a_terminar(sender, subscription, fim, **kwargs):
    plano = subscription.plan
    dias = (timezone.localtime(fim, FUSO_ANGOLA).date()
            - timezone.localtime(timezone.now(), FUSO_ANGOLA).date()).days
    quando = 'hoje' if dias <= 0 else 'amanhã' if dias == 1 else f'dentro de {dias} dias'
    title = f'O seu teste do {plano.name} termina {quando}'
    body = (f'O teste termina a {_data(fim)} às {_hora(fim)}. Pague por Multicaixa Express para '
            f'continuar com o {plano.name}. Se não pagar, a conta volta ao Gratuito e o progresso '
            f'fica guardado.')
    _notify(subscription.user, title=title, body=body, link=_link_pagar(plano),
            dedupe_key=f'teste:t2:{subscription.pk}:{fim:%Y%m%d%H%M}')
    _email_teste(subscription.user, title, [body], f'Pagar o {plano.name}', _link_pagar(plano))


@receiver(teste_terminado, dispatch_uid='avisos_teste_terminado')
def avisar_teste_terminado(sender, subscription, plano_anterior, **kwargs):
    title = f'O seu teste do {plano_anterior.name} terminou'
    body = (f'A sua conta voltou ao plano Gratuito e o progresso foi mantido. Quando quiser voltar '
            f'ao {plano_anterior.name}, pague com Multicaixa Express.')
    hoje = timezone.localtime(timezone.now(), FUSO_ANGOLA).date()
    _notify(subscription.user, title=title, body=body, link=_link_pagar(plano_anterior),
            dedupe_key=f'teste:fim:{subscription.pk}:{hoje.isoformat()}')
    _email_teste(subscription.user, title, [body], f'Pagar o {plano_anterior.name}', _link_pagar(plano_anterior))
