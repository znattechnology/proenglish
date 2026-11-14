"""
Serviços de assinatura partilhados.

Lógica única para calcular o preço de um plano (código promocional e crédito
do plano atual) e para ativar/alterar o plano de um utilizador. É usada pelo
endpoint ``upgrade/`` (só administradores) e pela app ``pagamentos`` quando um
pagamento é confirmado, para que a ativação nunca seja duplicada.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    SubscriptionPlan,
    UserSubscription,
    SubscriptionHistory,
    PromotionalCode,
    PromoCodeUsage,
)

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')

# Duração de cada ciclo de faturação (mesmos valores usados historicamente em upgrade/)
DURACAO_CICLO = {
    'MONTHLY': timedelta(days=30),
    'YEARLY': timedelta(days=365),
}
NOME_CICLO = {'MONTHLY': 'Mensal', 'YEARLY': 'Anual'}

# O plano Gratuito não tem fim: usa-se uma data muito distante.
DURACAO_PLANO_GRATUITO = timedelta(days=365 * 10)

# Renovação: o plano atual pode ser pago de novo quando faltam <= N dias
JANELA_RENOVACAO = timedelta(days=7)

# Códigos de erro de código promocional
PROMO_INEXISTENTE = 'inexistente'
PROMO_INVALIDO = 'invalido'
PROMO_JA_USADO = 'ja_usado'
PROMO_NAO_APLICAVEL = 'nao_aplicavel'
PROMO_SO_PRIMEIRA_COMPRA = 'so_primeira_compra'
PROMO_TIPO_NAO_SUPORTADO = 'tipo_nao_suportado'
PROMO_PERIODO = 'periodo_nao_aplicavel'
PROMO_EXPIRADO = 'expirado'
PROMO_ESGOTADO = 'esgotado'
PROMO_DESLIGADO = 'desligado'
PROMO_SO_MENSAL = 'so_mensal'

MENSAGENS_PROMO = {
    PROMO_INEXISTENTE: 'Código promocional inválido.',
    PROMO_INVALIDO: 'Código promocional expirado ou esgotado.',
    PROMO_JA_USADO: 'Já utilizou este código promocional.',
    PROMO_NAO_APLICAVEL: 'Este código promocional não é válido para o plano escolhido.',
    PROMO_SO_PRIMEIRA_COMPRA: 'Este código promocional é válido apenas no primeiro pagamento.',
    PROMO_TIPO_NAO_SUPORTADO: 'Este código promocional não pode ser usado no pagamento.',
    PROMO_PERIODO: 'Este código promocional não é válido para o período escolhido.',
    PROMO_EXPIRADO: 'Este código promocional já expirou.',
    PROMO_ESGOTADO: 'Este código promocional já atingiu o limite de utilizações.',
    PROMO_DESLIGADO: 'Este código promocional já não está disponível.',
    PROMO_SO_MENSAL: 'Este código dá desconto nos primeiros meses e só vale no pagamento mensal. '
                     'Escolha o pagamento mensal para o usar.',
}

# Mensal = 1 mês; anual = 12 meses (para a duração "meses" dos códigos)
MESES_POR_CICLO = {'MONTHLY': 1, 'YEARLY': 12}
CICLO_POR_PERIODO = {'mensal': 'MONTHLY', 'anual': 'YEARLY'}
PERIODO_POR_CICLO = {v: k for k, v in CICLO_POR_PERIODO.items()}

AVISO_PROMO_DESNECESSARIO = (
    'O crédito do seu plano actual já cobre o preço, por isso o código não foi aplicado '
    '(fica disponível para outra altura).'
)


def kz_inteiro(valor):
    """Decimal -> inteiro de kwanzas (arredondamento comercial)."""
    return int(Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


@dataclass
class PrecoPlano:
    base: Decimal
    desconto: Decimal
    final: Decimal
    promo: Optional[PromotionalCode] = None
    erro_promo: Optional[str] = None
    aviso_promo: Optional[str] = None
    # Crédito do plano atual (dias pagos que sobram), em kwanzas
    credito: Decimal = Decimal('0')
    credito_aplicado: Decimal = Decimal('0')
    credito_sobra: Decimal = Decimal('0')

    @property
    def mensagem_erro_promo(self):
        return MENSAGENS_PROMO.get(self.erro_promo) if self.erro_promo else None


def obter_plano_gratuito():
    plano, _ = SubscriptionPlan.objects.get_or_create(
        plan_type='FREE',
        defaults={
            'name': 'Gratuito',
            'description': 'Plano gratuito',
            'monthly_price': Decimal('0.00'),
            'is_active': True,
        },
    )
    return plano


def vidas_iniciais(plan):
    return plan.hearts_limit if plan.hearts_limit and plan.hearts_limit > 0 else 999


def obter_ou_criar_assinatura(user):
    """Assinatura do utilizador; cria a do plano Gratuito se ainda não existir."""
    subscription = UserSubscription.objects.filter(user=user).select_related('plan').first()
    if subscription is not None:
        return subscription
    gratuito = obter_plano_gratuito()
    subscription, _ = UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            'plan': gratuito,
            'expires_at': timezone.now() + DURACAO_PLANO_GRATUITO,
            'status': 'ACTIVE',
            'current_hearts': vidas_iniciais(gratuito),
        },
    )
    return subscription


def precos_contratados(sub, plan, agora=None):
    """
    (mensal, anual) que o assinante contratou, se ``plan`` é o plano pago que tem em vigor
    (não em teste). Mudar o preço do plano não afecta quem já paga: as renovações usam
    estes valores até a subscrição terminar. None se não se aplica.
    """
    if (sub is None or plan is None or sub.plan_id != plan.id or sub.status == 'TRIAL'
            or sub.preco_mensal_kz is None or not plano_pago_em_vigor(sub, agora)):
        return None
    return sub.preco_mensal_kz, sub.preco_anual_kz


def preco_base_plano(plan, billing_cycle, sub=None):
    """
    Preço do plano para o ciclo pedido (anual cai para mensal se não houver preço anual).
    Com ``sub`` (assinatura do utilizador) usa o preço contratado nas renovações.
    """
    contratado = precos_contratados(sub, plan)
    if contratado:
        mensal, anual = contratado
        if billing_cycle == 'YEARLY':
            if anual:
                return Decimal(anual)
            if plan.yearly_price:
                return plan.yearly_price
        return Decimal(mensal)
    if billing_cycle == 'YEARLY' and plan.yearly_price:
        return plan.yearly_price
    return plan.monthly_price


def preco_diario(plan, billing_cycle, sub=None):
    """Preço de um dia do plano no ciclo pedido (para converter crédito em dias)."""
    dias = DURACAO_CICLO.get(billing_cycle, DURACAO_CICLO['MONTHLY']).days
    return Decimal(preco_base_plano(plan, billing_cycle, sub)) / dias


def utilizador_ja_pagou(user):
    """True se o utilizador já fez algum pagamento de assinatura (inclui activações a 0 Kz)."""
    from apps.pagamentos.models import Pagamento
    return (
        SubscriptionHistory.objects.filter(subscription__user=user, amount_paid__gt=0).exists()
        or Pagamento.objects.filter(user=user, estado=Pagamento.PAGO).exists()
    )


# ---------------------------------------------------------------------------
# Planos desactivados: quem já os tem continua a poder renovar
# ---------------------------------------------------------------------------

# Depois de o plano (ou o teste) terminar, ainda pode voltar a pagá-lo durante este tempo
JANELA_RECUPERAR_PLANO = timedelta(days=30)


def detem_plano(user, plan, agora=None, sub=None):
    """
    O utilizador tem (ou teve há pouco) ``plan``: assinatura actual desse plano (paga, em teste
    ou terminada mas ainda não passada ao Gratuito), ou o plano/teste terminou há menos de
    ``JANELA_RECUPERAR_PLANO`` e desde então não mudou de plano. Serve para deixar renovar ou
    converter um plano que entretanto foi desactivado (sai do catálogo só para pessoas novas).
    """
    if plan is None or plan.plan_type == 'FREE' or user is None or not getattr(user, 'is_authenticated', False):
        return False
    agora = agora or timezone.now()
    if sub is None:
        sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    if sub is None:
        return False
    if sub.plan_id == plan.id:
        return True
    if sub.plan.plan_type != 'FREE':
        return False  # tem agora outro plano pago
    ultimo = (SubscriptionHistory.objects.filter(subscription=sub)
              .exclude(event_type__in=('PAYMENT_FAILED',)).order_by('-created_at').first())
    return bool(
        ultimo and ultimo.event_type in ('EXPIRED', 'TRIAL_ENDED') and ultimo.previous_plan_id == plan.id
        and ultimo.created_at >= agora - JANELA_RECUPERAR_PLANO
    )


def planos_detidos_inactivos(user, agora=None):
    """Planos pagos desactivados que ``user`` ainda pode renovar (ver ``detem_plano``)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return []
    sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    return [p for p in SubscriptionPlan.objects.filter(is_active=False).exclude(plan_type='FREE')
            if detem_plano(user, p, agora, sub=sub)]


# ---------------------------------------------------------------------------
# Renovação (regra única, usada no pagamento e na API da subscrição)
# ---------------------------------------------------------------------------

def plano_pago_em_vigor(sub, agora=None):
    agora = agora or timezone.now()
    return bool(
        sub and sub.plan.plan_type != 'FREE' and sub.status != 'EXPIRED'
        and sub.expires_at and sub.expires_at > agora
    )


def renovavel_a_partir_de(sub):
    if not sub or sub.plan.plan_type == 'FREE' or not sub.expires_at or sub.status == 'TRIAL':
        return None
    return sub.expires_at - JANELA_RENOVACAO


def pode_renovar(sub, agora=None):
    """O plano pago atual pode ser pago de novo (mesmo plano)?

    Igual à regra aplicada em ``pagamentos._validar_plano``: só fica bloqueado
    se ainda faltarem mais de ``JANELA_RENOVACAO`` dias para o fim.
    """
    agora = agora or timezone.now()
    if not sub or sub.plan.plan_type == 'FREE':
        return False
    if sub.status in ('EXPIRED', 'TRIAL') or not sub.expires_at:
        return True  # em teste pode pagar quando quiser (o período pago começa no fim do teste)
    return sub.expires_at <= agora + JANELA_RENOVACAO


def termina_hoje(sub, agora=None):
    if not sub or sub.plan.plan_type == 'FREE' or not sub.expires_at:
        return False
    agora = agora or timezone.now()
    return (timezone.localtime(sub.expires_at, FUSO_ANGOLA).date()
            == timezone.localtime(agora, FUSO_ANGOLA).date())


# ---------------------------------------------------------------------------
# Códigos promocionais
# ---------------------------------------------------------------------------

def validar_promo(user, promo, plan, *, ciclo=None, ignorar_reservas_proprias=False):
    """Devolve o código de erro (ou None) para usar ``promo`` em ``plan`` (e no ``ciclo``).

    ``ignorar_reservas_proprias``: na pré-visualização, as reservas do próprio
    utilizador (de um pagamento pendente que vai ser substituído) não contam
    como uso nem para o limite. A reserva definitiva valida sem esta exceção.
    """
    if promo.estado == PromotionalCode.RASCUNHO:
        return PROMO_INEXISTENTE  # um rascunho não existe para os alunos
    if promo.estado != PromotionalCode.ACTIVO or not promo.is_active:
        return PROMO_DESLIGADO
    if promo.discount_type not in PromotionalCode.TIPOS_SUPORTADOS:
        return PROMO_TIPO_NAO_SUPORTADO
    usos = PromoCodeUsage.objects.filter(user=user, promo_code=promo)
    proprias = 0
    if ignorar_reservas_proprias:
        proprias = usos.filter(estado=PromoCodeUsage.RESERVADO).count()
        usos = usos.exclude(estado=PromoCodeUsage.RESERVADO)
    now = timezone.now()
    if promo.valid_from and promo.valid_from > now:
        return PROMO_INVALIDO
    if promo.expirado(now):
        return PROMO_EXPIRADO
    if usos.exists():
        return PROMO_JA_USADO
    if promo.max_uses is not None and promo.current_uses - proprias >= promo.max_uses:
        return PROMO_ESGOTADO
    if plan is not None and plan.plan_type == 'FREE':
        return PROMO_NAO_APLICAVEL
    if promo.applicable_plans.exists() and not promo.applicable_plans.filter(pk=plan.pk).exists():
        return PROMO_NAO_APLICAVEL
    periodo = PERIODO_POR_CICLO.get(ciclo)
    if promo.duracao == PromotionalCode.DURACAO_MESES and periodo == 'anual':
        return PROMO_SO_MENSAL  # "os primeiros N meses" não se aplica a um ano inteiro
    if periodo and promo.periodo_aplicavel not in (PromotionalCode.PERIODO_TODOS, periodo):
        return PROMO_PERIODO
    if promo.first_time_users_only and utilizador_ja_pagou(user):
        return PROMO_SO_PRIMEIRA_COMPRA
    return None


def promo_em_curso(sub, plan, billing_cycle, agora=None):
    """
    Código já usado que continua a dar desconto nesta renovação (mesmo plano, em vigor):
    duração "sempre", ou "meses" enquanto os meses pagos com desconto < N. O período e os
    planos do código continuam a contar. Um código desligado ou expirado depois de usado
    continua a ser honrado para quem já o tinha.
    """
    promo = getattr(sub, 'promo_codigo', None) if sub else None
    if promo is None or sub.plan_id != plan.id or sub.status == 'TRIAL' or not plano_pago_em_vigor(sub, agora):
        return None
    if promo.discount_type not in PromotionalCode.TIPOS_SUPORTADOS:
        return None
    periodo = PERIODO_POR_CICLO.get(billing_cycle)
    if promo.periodo_aplicavel not in (PromotionalCode.PERIODO_TODOS, periodo):
        return None
    if promo.duracao == PromotionalCode.DURACAO_MESES and periodo != 'mensal':
        return None  # os meses com desconto contam-se só em pagamentos mensais
    if promo.applicable_plans.exists() and not promo.applicable_plans.filter(pk=plan.pk).exists():
        return None
    if promo.duracao == PromotionalCode.DURACAO_SEMPRE:
        return promo
    if promo.duracao == PromotionalCode.DURACAO_MESES and sub.promo_meses_usados < (promo.duracao_meses or 0):
        return promo
    return None


def desconto_do_codigo(promo, base):
    """Desconto do código sobre o preço base, sempre entre 0 e o preço base."""
    valor = Decimal(promo.discount_value or 0)
    if promo.discount_type == 'PERCENTAGE':
        valor = min(max(valor, Decimal('0')), Decimal('100'))
        desconto = (Decimal(base) * valor) / 100
    elif promo.discount_type == 'FIXED_AMOUNT':
        desconto = valor
    else:
        desconto = Decimal('0')
    return min(max(desconto, Decimal('0')), Decimal(base))


def calcular_preco_plano(user, plan, billing_cycle, promo_code=None, credito=Decimal('0'), sub=None,
                         promo_continuo=None):
    """
    Calcula preço base, desconto do código, crédito e preço final. Não regista uso do código.

    Ordem: o crédito do plano atual abate primeiro; se cobrir o preço todo, o
    código não é aplicado (``aviso_promo``) e o que sobra do crédito vira dias
    extra (calculado por quem chama). Caso contrário o código é calculado sobre o
    preço base e limitado ao que falta pagar. ``final`` nunca é negativo.

    Se o código não puder ser aplicado, ``erro_promo`` indica a razão e o
    desconto é 0 (o chamador decide se isso é um erro ou se é ignorado).

    ``sub``: assinatura do utilizador (preço contratado nas renovações; procurada se faltar).
    ``promo_continuo``: código já usado que continua nesta renovação (ver ``promo_em_curso``);
    aplica-se sem validar nem contar nova utilização, quando não foi escrito outro código.
    """
    if sub is None:
        sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    base = Decimal(preco_base_plano(plan, billing_cycle, sub))
    credito = max(Decimal(credito or 0), Decimal('0'))
    aplicado = min(credito, base)
    resultado = PrecoPlano(
        base=base, desconto=Decimal('0.00'), final=base - aplicado,
        credito=credito, credito_aplicado=aplicado, credito_sobra=credito - aplicado,
    )
    if not promo_code and promo_continuo is not None:
        if resultado.final > 0:
            desconto = min(desconto_do_codigo(promo_continuo, base), resultado.final)
            resultado.promo = promo_continuo
            resultado.desconto = desconto
            resultado.final = max(resultado.final - desconto, Decimal('0'))
        return resultado
    if not promo_code:
        return resultado

    try:
        promo = PromotionalCode.objects.get(code=promo_code.strip().upper())
    except PromotionalCode.DoesNotExist:
        resultado.erro_promo = PROMO_INEXISTENTE
        return resultado

    resultado.erro_promo = validar_promo(user, promo, plan, ciclo=billing_cycle,
                                         ignorar_reservas_proprias=True)
    if resultado.erro_promo:
        return resultado

    if resultado.final <= 0:
        resultado.aviso_promo = AVISO_PROMO_DESNECESSARIO
        return resultado

    desconto = min(desconto_do_codigo(promo, base), resultado.final)
    resultado.promo = promo
    resultado.desconto = desconto
    resultado.final = max(resultado.final - desconto, Decimal('0'))
    return resultado


@transaction.atomic
def registar_uso_promo(user, promo, subscription, desconto, plan=None, ciclo=None):
    """Regista o uso do código (fluxo de administração). Revalida com o código bloqueado.

    Lança ValueError com a mensagem se o código já não puder ser usado.
    """
    promo = PromotionalCode.objects.select_for_update().get(pk=promo.pk)
    if PromoCodeUsage.objects.filter(user=user, promo_code=promo).exists():
        return False
    erro = validar_promo(user, promo, plan or subscription.plan, ciclo=ciclo)
    if erro:
        raise ValueError(MENSAGENS_PROMO[erro])
    PromoCodeUsage.objects.create(
        user=user, promo_code=promo, subscription=subscription,
        discount_applied=desconto, estado=PromoCodeUsage.CONFIRMADO,
    )
    PromotionalCode.objects.filter(pk=promo.pk).update(current_uses=F('current_uses') + 1)
    return True


# ---------------------------------------------------------------------------
# Ativação
# ---------------------------------------------------------------------------

def _fmt_kz(valor):
    return f'{kz_inteiro(valor):,}'.replace(',', ' ') + ' Kz'


@transaction.atomic
def ativar_plano(user, new_plan, billing_cycle, amount_paid, discount=Decimal('0.00'),
                 promo=None, notas_extra='', credito=Decimal('0'), dias_extra=0):
    """
    Ativa/altera o plano do utilizador para o período pago e regista histórico
    (e uso de código promocional, no fluxo de administração).

    * Mesmo plano ainda em vigor: renovação, estende a partir do fim atual.
    * Outro plano: começa agora, dura um ciclo + ``dias_extra`` (sobra do
      crédito); os dias pagos do plano anterior já foram convertidos em
      ``credito`` por quem chama.
    * Plano Gratuito (só administradores): sem fim e sem valor pago.

    Returns:
        (subscription, history)
    """
    subscription = obter_ou_criar_assinatura(user)
    subscription = UserSubscription.objects.select_for_update().get(pk=subscription.pk)
    old_plan = subscription.plan
    now = timezone.now()

    if promo is not None:
        registar_uso_promo(user, promo, subscription, discount, plan=new_plan, ciclo=billing_cycle)

    gratuito = new_plan.plan_type == 'FREE'
    duracao = DURACAO_CICLO.get(billing_cycle, DURACAO_CICLO['MONTHLY'])
    # Renovação do mesmo plano ainda em vigor: estende a partir do fim atual
    renovacao = (
        old_plan.pk == new_plan.pk
        and not gratuito
        and subscription.status != 'EXPIRED'
        and subscription.expires_at
        and subscription.expires_at > now
    )

    if not renovacao:
        # Os períodos pagos que estavam em curso deixam de contar (o que sobrava
        # foi convertido em crédito, ou o plano foi mudado por um administrador).
        from apps.pagamentos.models import Pagamento
        Pagamento.objects.filter(
            user=user, estado=Pagamento.PAGO, periodo_fim__gt=now, creditado_em__isnull=True,
        ).update(creditado_em=now)

    em_teste = subscription.status == 'TRIAL' and renovacao
    # Preço contratado: fixa-se na compra (plano novo, ou fim do teste) e mantém-se nas renovações.
    if gratuito:
        subscription.preco_mensal_kz = subscription.preco_anual_kz = None
        subscription.promo_codigo = None
        subscription.promo_meses_usados = 0
    elif not renovacao or subscription.preco_mensal_kz is None:
        subscription.preco_mensal_kz = kz_inteiro(new_plan.monthly_price)
        subscription.preco_anual_kz = kz_inteiro(new_plan.yearly_price) if new_plan.yearly_price else None

    subscription.plan = new_plan
    if gratuito:
        subscription.expires_at = now + DURACAO_PLANO_GRATUITO
    elif renovacao:
        subscription.expires_at = subscription.expires_at + duracao
    else:
        subscription.expires_at = now + duracao + timedelta(days=int(dias_extra or 0))
    subscription.status = 'ACTIVE'
    subscription.canceled_at = None
    if not gratuito:
        subscription.last_payment_at = now
    # Vidas: o novo limite manda (0 = ilimitadas, tratado em recharge_hearts_if_needed)
    if new_plan.hearts_limit and subscription.current_hearts > new_plan.hearts_limit:
        subscription.current_hearts = new_plan.hearts_limit
    elif not new_plan.hearts_limit:
        subscription.current_hearts = 999
    subscription.save()

    partes = [f'Ciclo: {NOME_CICLO.get(billing_cycle, billing_cycle)}']
    if discount:
        partes.append(f'Desconto do código: {_fmt_kz(discount)}')
    if credito:
        extra = f' (+{dias_extra} dias)' if dias_extra else ''
        partes.append(f'Crédito do plano {old_plan.name}: {_fmt_kz(credito)}{extra}')
    if em_teste:
        partes.append('Pago durante o período de teste: o período pago começa no fim do teste')
    if notas_extra:
        partes.append(notas_extra)
    notes = '. '.join(partes)

    if em_teste:
        event_type = 'CREATED'
    elif renovacao:
        event_type = 'RENEWED'
    elif old_plan.pk == new_plan.pk:
        event_type = 'CREATED'
    elif new_plan.monthly_price > old_plan.monthly_price:
        event_type = 'UPGRADED'
    else:
        event_type = 'DOWNGRADED'

    history = SubscriptionHistory.objects.create(
        subscription=subscription,
        event_type=event_type,
        previous_plan=old_plan,
        new_plan=new_plan,
        amount_paid=None if gratuito else amount_paid,
        notes=notes,
    )
    return subscription, history
