"""
Regras de negócio dos pagamentos Multicaixa Express.

Fluxo: orcamento (pré-visualização) -> criar_pagamento_mcx -> (provedor envia
push) -> atualizar_estado (lazy, na leitura) / callback futuro ->
confirmar_pagamento | marcar_falha. Com preço final 0 Kz (crédito do plano
atual ou código de 100%) usa-se ativar_sem_pagamento, sem Multicaixa.

Regras:

* Um único pagamento pendente por utilizador: criar outro cancela o anterior.
* Mudar para outro plano com um plano pago em vigor: os dias pagos que faltam
  viram crédito (valor do período x tempo que falta / duração do período). O
  novo plano começa já. Se o crédito for maior que o preço, paga 0 Kz e a sobra
  vira dias extra (sobra / preço diário do novo plano, arredondado para baixo).
* Mesmo plano = renovação (só nos últimos ``JANELA_RENOVACAO`` dias; estende a
  partir do fim atual).
* Código promocional: reservado na criação do pagamento (conta para o limite de
  utilizações), confirmado quando o pagamento é confirmado e libertado se o
  pagamento falhar, expirar ou for cancelado.
* ``confirmar_pagamento`` é idempotente: bloqueia a linha do pagamento e a
  subscrição e só ativa o plano na transição pendente -> pago. Um pagamento que
  chegue depois de outro pagamento do mesmo utilizador ter sido confirmado é
  anulado (nunca ativa duas vezes).
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.subscriptions.models import (
    SubscriptionPlan, UserSubscription, SubscriptionHistory, PromotionalCode, PromoCodeUsage,
)
from apps.subscriptions.services import (
    DURACAO_CICLO,
    FUSO_ANGOLA,
    JANELA_RENOVACAO,
    MENSAGENS_PROMO,
    PrecoPlano,
    ativar_plano,
    calcular_preco_plano,
    detem_plano,
    kz_inteiro as _kz,
    obter_ou_criar_assinatura,
    plano_pago_em_vigor,
    pode_renovar,
    preco_base_plano,
    promo_em_curso,
    MESES_POR_CICLO,
    preco_diario,
    validar_promo,
)

from .models import Pagamento, SequenciaRecibo
from .provedores import obter_provedor, provedor_disponivel, PROVEDORES
from .signals import pagamento_confirmado
from .telefone import normalizar_telefone, TelefoneInvalido

logger = logging.getLogger(__name__)

NOME_METODO = 'Multicaixa Express'
PERIODO_POR_CICLO = {v: k for k, v in Pagamento.CICLO_POR_PERIODO.items()}

MOTIVO_EXPIRADO = 'O pagamento expirou sem confirmação no telemóvel.'
MOTIVO_CANCELADO = 'Pagamento cancelado pelo utilizador.'
MOTIVO_SUBSTITUIDO = 'Substituído por um novo pedido de pagamento.'
MOTIVO_ANULADO = ('Anulado: outro pagamento seu foi confirmado entretanto. '
                  'Se o valor foi debitado, será devolvido.')

OPERACAO_NOVA = 'nova'
OPERACAO_RENOVACAO = 'renovacao'
OPERACAO_MUDANCA = 'mudanca_plano'
# Pagar o plano que está a experimentar: o período pago começa no fim do teste
OPERACAO_FIM_TESTE = 'conversao_teste'


class ErroPagamento(Exception):
    def __init__(self, mensagem, status=400, codigo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.codigo = codigo


def _iso(dt):
    return dt.isoformat() if dt else None


def _fmt_kz(valor):
    return f'{int(valor):,}'.replace(',', ' ') + ' Kz'


# ---------------------------------------------------------------------------
# Crédito do plano atual
# ---------------------------------------------------------------------------

@dataclass
class Credito:
    kz: int = 0
    dias_restantes: int = 0
    plano: Optional[SubscriptionPlan] = None
    termina_em: Optional[object] = None


def calcular_credito(user, plano_novo, agora=None, sub=None):
    """
    Valor (Kz) dos dias pagos que faltam no plano atual, se ``plano_novo`` for
    outro plano. Para cada período pago ainda em curso (pagamento confirmado do
    plano atual, não convertido): valor do período x tempo que falta / duração.
    O valor do período é o que foi pago mais o crédito que já trazia (o desconto
    de códigos não conta). Sem pagamentos (ex.: plano dado por um administrador)
    o crédito é 0.
    """
    agora = agora or timezone.now()
    if sub is None:
        sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    if not plano_pago_em_vigor(sub, agora) or sub.plan_id == plano_novo.id or sub.status == 'TRIAL':
        return Credito()  # o período de teste não foi pago: não dá crédito

    pagos = Pagamento.objects.filter(
        user=user, estado=Pagamento.PAGO, plan_id=sub.plan_id, creditado_em__isnull=True,
        periodo_inicio__isnull=False, periodo_fim__gt=agora,
    )
    total = Decimal('0')
    for p in pagos:
        duracao = (p.periodo_fim - p.periodo_inicio).total_seconds()
        falta = (min(p.periodo_fim, sub.expires_at) - max(agora, p.periodo_inicio)).total_seconds()
        if duracao <= 0 or falta <= 0:
            continue
        total += Decimal(p.valor_do_periodo_kz) * Decimal(falta) / Decimal(duracao)

    return Credito(
        kz=_kz(total),
        # Dias por usar, contando um dia começado como dia inteiro (só para mostrar)
        dias_restantes=max(0, math.ceil((sub.expires_at - agora).total_seconds() / 86400)),
        plano=sub.plan,
        termina_em=sub.expires_at,
    )


# ---------------------------------------------------------------------------
# Orçamento (preço que vai ser cobrado)
# ---------------------------------------------------------------------------

@dataclass
class Orcamento:
    plan: SubscriptionPlan
    periodo: str
    operacao: str
    preco: PrecoPlano
    credito: Credito
    valor_kz: int
    desconto_kz: int
    credito_abatido_kz: int
    dias_extra: int
    inicio: object
    termina_em: object
    motivo_bloqueio: Optional[str] = None
    codigo: Optional[str] = None
    linhas: list = field(default_factory=list)
    # Desconto de um código já usado que continua nesta renovação (sem nova utilização)
    promo_renovacao: bool = False
    sub: Optional[UserSubscription] = None
    user: Optional[object] = None

    @property
    def total_kz(self):
        return max(0, self.valor_kz - self.desconto_kz - self.credito_abatido_kz)

    @property
    def credito_usado_kz(self):
        """Crédito consumido: abatido ao preço + convertido em dias extra."""
        return self.credito.kz if (self.credito_abatido_kz or self.dias_extra) else 0


PLANO_INDISPONIVEL = ('Este plano já não está disponível para novas subscrições. '
                      'Escolha outro plano na página de planos.')


def _resolver_plano(plan_ref, user=None):
    """
    Plano pedido (tipo ou id). Um plano desactivado só serve a quem já o tem (renovar,
    converter o teste, ou voltar a pagá-lo pouco depois de terminar: ``detem_plano``).
    """
    if isinstance(plan_ref, SubscriptionPlan):
        plano = plan_ref
    else:
        plano = None
        ref = str(plan_ref or '').strip()
        if not ref:
            raise ErroPagamento('Indique o plano (plan_id).', codigo='plano_em_falta')
        if ref.upper() in dict(SubscriptionPlan.PLAN_TYPES):
            plano = SubscriptionPlan.objects.filter(plan_type=ref.upper()).first()
        else:
            try:
                plano = SubscriptionPlan.objects.filter(id=ref).first()
            except Exception:  # id mal formado
                plano = None
        if plano is None:
            raise ErroPagamento('Plano não encontrado.', status=404, codigo='plano_nao_encontrado')
    if not plano.is_active and not detem_plano(user, plano):
        raise ErroPagamento(PLANO_INDISPONIVEL, status=404, codigo='plano_indisponivel')
    return plano


def _validar_periodo(plan, periodo):
    if periodo not in (Pagamento.PERIODO_MENSAL, Pagamento.PERIODO_ANUAL):
        raise ErroPagamento('Indique o período: "mensal" ou "anual".')
    if plan.plan_type == 'FREE':
        raise ErroPagamento('O plano gratuito não pode ser comprado.')
    if periodo == Pagamento.PERIODO_ANUAL and not plan.yearly_price:
        raise ErroPagamento('Este plano não tem preço anual.')


def _motivo_bloqueio(sub, plan, agora):
    if sub and sub.status == 'TRIAL':
        return None  # em teste pode pagar quando quiser
    if sub and sub.plan_id == plan.id and plano_pago_em_vigor(sub, agora) and not pode_renovar(sub, agora):
        return (f'Já tem o plano {plan.name} activo. A renovação fica disponível '
                f'nos {JANELA_RENOVACAO.days} dias antes do fim do período.')
    return None


def calcular_orcamento(user, plan, periodo, codigo=None, agora=None):
    """Cálculo único usado na pré-visualização, na criação e no fluxo 0 Kz."""
    plan = _resolver_plano(plan, user)
    _validar_periodo(plan, periodo)
    agora = agora or timezone.now()
    codigo = (codigo or '').strip().upper() or None
    ciclo = Pagamento.CICLO_POR_PERIODO[periodo]

    sub = UserSubscription.objects.filter(user=user).select_related('plan', 'promo_codigo').first()
    credito = calcular_credito(user, plan, agora, sub=sub)
    continuo = promo_em_curso(sub, plan, ciclo, agora)
    if continuo is not None and codigo == continuo.code:
        codigo = None  # escreveu o código que já tem: continua (não é uma nova utilização)
    preco = calcular_preco_plano(user, plan, ciclo, codigo, credito=credito.kz, sub=sub,
                                 promo_continuo=continuo)
    promo_renovacao = bool(continuo is not None and not codigo and preco.promo is not None)

    valor_kz = _kz(preco.base)
    abatido = min(_kz(preco.credito_aplicado), valor_kz)
    desconto = min(_kz(preco.desconto), valor_kz - abatido)
    dias_extra = 0
    if preco.credito_sobra > 0:
        dias_extra = int(preco.credito_sobra // preco_diario(plan, ciclo))

    renovacao = bool(sub and sub.plan_id == plan.id and plano_pago_em_vigor(sub, agora))
    if renovacao:
        operacao = OPERACAO_FIM_TESTE if sub.status == 'TRIAL' else OPERACAO_RENOVACAO
        inicio = sub.expires_at
        fim = sub.expires_at + DURACAO_CICLO[ciclo]
    else:
        operacao = OPERACAO_MUDANCA if credito.plano else OPERACAO_NOVA
        inicio = agora
        fim = agora + DURACAO_CICLO[ciclo] + timedelta(days=dias_extra)

    o = Orcamento(
        plan=plan, periodo=periodo, operacao=operacao, preco=preco, credito=credito,
        valor_kz=valor_kz, desconto_kz=desconto if preco.promo else 0,
        credito_abatido_kz=abatido, dias_extra=dias_extra, inicio=inicio, termina_em=fim,
        motivo_bloqueio=_motivo_bloqueio(sub, plan, agora),
        codigo=preco.promo.code if promo_renovacao else codigo,
        promo_renovacao=promo_renovacao, sub=sub, user=user,
    )
    o.linhas = _linhas(o)
    return o


def _linhas(o):
    linhas = [{
        'tipo': 'plano',
        'descricao': f'Plano {o.plan.name} - {dict(Pagamento.PERIODOS)[o.periodo]}',
        'valor_kz': o.valor_kz,
    }]
    if o.desconto_kz:
        descricao = f'Código {o.codigo}' + (' (continua nesta renovação)' if o.promo_renovacao else '')
        linhas.append({'tipo': 'codigo', 'descricao': descricao, 'valor_kz': -o.desconto_kz})
    if o.credito_abatido_kz:
        linhas.append({
            'tipo': 'credito',
            'descricao': _descricao_credito(o.credito.plano, o.credito.dias_restantes),
            'valor_kz': -o.credito_abatido_kz,
        })
    return linhas


def _descricao_credito(plano, dias):
    nome = plano.name if plano else 'anterior'
    dias_txt = '1 dia' if dias == 1 else f'{dias} dias'
    return f'Crédito do plano {nome} ({dias_txt} por usar)'


def representar_orcamento(o):
    promo = o.preco.promo
    erro = None
    if o.preco.erro_promo:
        erro = {'code': o.preco.erro_promo, 'mensagem': o.preco.mensagem_erro_promo}
    total = o.total_kz
    return {
        'plano': {'id': str(o.plan.id), 'nome': o.plan.name, 'tipo': o.plan.plan_type},
        'periodo': o.periodo,
        'operacao': o.operacao,
        'pode_comprar': o.motivo_bloqueio is None,
        'motivo_bloqueio': o.motivo_bloqueio,
        'preco_base_kz': o.valor_kz,
        'codigo': {
            'codigo': promo.code,
            'tipo': promo.discount_type,
            'valor': str(promo.discount_value),
            'descricao': promo.description,
            'duracao': promo.duracao,
            'duracao_meses': promo.duracao_meses,
            'continua': o.promo_renovacao,
        } if promo else None,
        'desconto_codigo_kz': o.desconto_kz,
        'erro_codigo': erro,
        'aviso_codigo': o.preco.aviso_promo,
        'credito_kz': o.credito_abatido_kz,
        'credito_total_kz': o.credito.kz,
        'credito_dias_restantes': o.credito.dias_restantes if o.credito.kz else 0,
        'credito_plano': {
            'nome': o.credito.plano.name,
            'tipo': o.credito.plano.plan_type,
            'termina_em': _iso(o.credito.termina_em),
        } if o.credito.plano and o.credito.kz else None,
        'dias_extra': o.dias_extra,
        'final_kz': total,
        'final': total,
        'requer_pagamento': total > 0,
        'inicio': _iso(o.inicio),
        'termina_em': _iso(o.termina_em),
        'linhas': o.linhas,
        'moeda': 'AOA',
        **_teste_repr(o),
    }


def _teste_repr(o):
    from .teste import estado_teste
    return estado_teste(o.user, o.plan, sub=o.sub)


def orcamento(user, plan, periodo, codigo=None):
    return representar_orcamento(calcular_orcamento(user, plan, periodo, codigo))


# ---------------------------------------------------------------------------
# Códigos promocionais: reserva / confirmação / libertação
# ---------------------------------------------------------------------------

def _reservar_promo(user, promo, plan, desconto_kz, ciclo=None):
    """Chamar dentro de atomic. Revalida com o código bloqueado e conta a utilização."""
    promo = PromotionalCode.objects.select_for_update().get(pk=promo.pk)
    erro = validar_promo(user, promo, plan, ciclo=ciclo)
    if erro:
        raise ErroPagamento(MENSAGENS_PROMO[erro], codigo='codigo_promocional')
    uso = PromoCodeUsage.objects.create(
        user=user, promo_code=promo, subscription=obter_ou_criar_assinatura(user),
        discount_applied=Decimal(desconto_kz), estado=PromoCodeUsage.RESERVADO,
    )
    PromotionalCode.objects.filter(pk=promo.pk).update(current_uses=F('current_uses') + 1)
    return uso


def _libertar_promo(p):
    """Chamar dentro de atomic com ``p`` bloqueado: apaga a reserva e devolve a utilização."""
    if not p.uso_promo_id:
        return
    uso = PromoCodeUsage.objects.filter(pk=p.uso_promo_id, estado=PromoCodeUsage.RESERVADO).first()
    p.uso_promo = None
    if uso:
        PromotionalCode.objects.filter(pk=uso.promo_code_id, current_uses__gt=0).update(
            current_uses=F('current_uses') - 1)
        uso.delete()


def _confirmar_promo(p, sub):
    if p.promo_renovacao:
        return  # desconto de um código que já tinha: não é nova utilização
    if p.uso_promo_id:
        PromoCodeUsage.objects.filter(pk=p.uso_promo_id).update(
            estado=PromoCodeUsage.CONFIRMADO, subscription=sub)
        return
    if p.codigo_promocional and p.desconto_kz:
        # Pagamento criado antes de haver reservas: regista agora, sem bloquear a ativação
        promo = PromotionalCode.objects.filter(code=p.codigo_promocional).first()
        if promo and not PromoCodeUsage.objects.filter(user=p.user, promo_code=promo).exists():
            PromoCodeUsage.objects.create(
                user=p.user, promo_code=promo, subscription=sub,
                discount_applied=Decimal(p.desconto_kz), estado=PromoCodeUsage.CONFIRMADO)
            PromotionalCode.objects.filter(pk=promo.pk).update(current_uses=F('current_uses') + 1)


def _libertar_reservas_caducadas(codigo):
    """Pendentes já fora de prazo que seguram uma utilização do código: resolver."""
    if not codigo:
        return
    for p in Pagamento.objects.filter(
            estado=Pagamento.PENDENTE, codigo_promocional=codigo, expira_em__lte=timezone.now()):
        atualizar_estado(p)


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

def _preparar(user, plan_id, periodo, codigo_promocional):
    plan = _resolver_plano(plan_id, user)
    _validar_periodo(plan, periodo)
    # Resolver pendentes anteriores primeiro: um deles pode já ter sido pago.
    resolver_pendentes(user)
    _libertar_reservas_caducadas(codigo_promocional)

    o = calcular_orcamento(user, plan, periodo, codigo_promocional)
    if o.motivo_bloqueio:
        raise ErroPagamento(o.motivo_bloqueio, codigo='ja_tem_o_plano')
    if o.preco.erro_promo:
        raise ErroPagamento(o.preco.mensagem_erro_promo, codigo='codigo_promocional')
    return o


def _cancelar_pendentes(user):
    """Dentro de atomic: cancela todos os pendentes do utilizador. Devolve os cancelados."""
    cancelados = []
    for anterior in Pagamento.objects.select_for_update().filter(user=user, estado=Pagamento.PENDENTE):
        anterior.estado = Pagamento.CANCELADO
        anterior.motivo_falha = MOTIVO_SUBSTITUIDO
        _libertar_promo(anterior)
        anterior.save(update_fields=['estado', 'motivo_falha', 'uso_promo', 'updated_at'])
        cancelados.append(anterior)
    return cancelados


def _criar_registo(user, o, **campos):
    """Dentro de atomic: cancela pendentes, reserva o código e cria o pagamento."""
    cancelados = _cancelar_pendentes(user)
    uso = None
    if o.preco.promo is not None and o.desconto_kz and not o.promo_renovacao:
        uso = _reservar_promo(user, o.preco.promo, o.plan, o.desconto_kz,
                              ciclo=Pagamento.CICLO_POR_PERIODO[o.periodo])
    try:
        with transaction.atomic():
            pagamento = Pagamento.objects.create(
                user=user,
                plan=o.plan,
                periodo=o.periodo,
                valor_kz=o.valor_kz,
                desconto_kz=o.desconto_kz,
                codigo_promocional=o.preco.promo.code if (o.preco.promo and o.desconto_kz) else None,
                uso_promo=uso,
                promo_renovacao=bool(o.promo_renovacao and o.desconto_kz),
                credito_kz=o.credito_usado_kz,
                credito_abatido_kz=o.credito_abatido_kz,
                credito_dias_restantes=o.credito.dias_restantes if o.credito_usado_kz else 0,
                credito_plano=o.credito.plano if o.credito_usado_kz else None,
                dias_extra=o.dias_extra,
                **campos,
            )
    except IntegrityError:
        raise ErroPagamento('Já está a ser criado outro pagamento. Tente outra vez.',
                            status=409, codigo='pendente_em_curso')
    return pagamento, cancelados


def criar_pagamento_mcx(user, *, telefone, plan_id=None, periodo=None, codigo_promocional=None):
    """Valida o pedido, cancela o pendente anterior (de qualquer plano) e cria o pagamento."""
    try:
        telefone = normalizar_telefone(telefone)
    except TelefoneInvalido as e:
        raise ErroPagamento(str(e), codigo='telefone_invalido')

    provedor = obter_provedor()
    if not provedor_disponivel(provedor):
        raise ErroPagamento(
            'Os pagamentos por Multicaixa Express estão temporariamente indisponíveis.',
            status=503, codigo='indisponivel',
        )

    codigo_promocional = (codigo_promocional or '').strip().upper() or None
    if not plan_id:
        raise ErroPagamento('Indique o plano (plan_id).')
    o = _preparar(user, plan_id, periodo, codigo_promocional)
    if o.total_kz <= 0:
        raise ErroPagamento(
            'O valor a pagar é 0 Kz, por isso não é preciso pagar com Multicaixa Express. '
            'Confirme a activação do plano.',
            status=409, codigo='valor_zero',
        )

    with transaction.atomic():
        pagamento, cancelados = _criar_registo(
            user, o, telefone=telefone, provedor=provedor.codigo, metodo=Pagamento.METODO_MCX)
        transaction.on_commit(lambda: [_cancelar_no_provedor(c) for c in cancelados])

    # Pedido ao provedor fora da transação (no real é uma chamada HTTP)
    try:
        inicio = provedor.iniciar(pagamento)
    except Exception:
        logger.exception('Falha ao iniciar pagamento %s no provedor %s', pagamento.id, provedor.codigo)
        marcar_falha(pagamento, Pagamento.RECUSADO, 'Não foi possível contactar o Multicaixa Express.')
        raise ErroPagamento(
            'Não foi possível iniciar o pagamento. Tente novamente.', status=502,
            codigo='provedor_indisponivel',
        )
    pagamento.referencia_externa = inicio.referencia_externa
    pagamento.save(update_fields=['referencia_externa', 'updated_at'])
    return pagamento


def ativar_sem_pagamento(user, *, plan_id=None, periodo=None, codigo_promocional=None):
    """
    Preço final 0 Kz (crédito do plano atual e/ou código de 100%): ativa já,
    sem Multicaixa, com recibo de 0 Kz. Recusa se houver valor a pagar.
    """
    codigo_promocional = (codigo_promocional or '').strip().upper() or None
    if not plan_id:
        raise ErroPagamento('Indique o plano (plan_id).')
    o = _preparar(user, plan_id, periodo, codigo_promocional)
    if o.total_kz > 0:
        raise ErroPagamento(
            f'O valor a pagar é {_fmt_kz(o.total_kz)}: pague com Multicaixa Express.',
            status=409, codigo='pagamento_necessario',
        )

    with transaction.atomic():
        pagamento, cancelados = _criar_registo(
            user, o, telefone='', provedor=Pagamento.PROVEDOR_INTERNO,
            metodo=Pagamento.METODO_SEM_PAGAMENTO, referencia_externa='')
        transaction.on_commit(lambda: [_cancelar_no_provedor(c) for c in cancelados])
        confirmar_pagamento(pagamento)
    pagamento.refresh_from_db()
    return pagamento


def _cancelar_no_provedor(pagamento):
    if pagamento.provedor == Pagamento.PROVEDOR_INTERNO:
        return
    try:
        obter_provedor(pagamento.provedor).cancelar(pagamento)
    except Exception:
        logger.exception('Falha ao cancelar pagamento %s no provedor', pagamento.id)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

def atualizar_estado(pagamento):
    """Resolução lazy: consulta o provedor e aplica a transição, se houver."""
    if pagamento.estado != Pagamento.PENDENTE:
        return pagamento
    if pagamento.provedor == Pagamento.PROVEDOR_INTERNO:
        if timezone.now() >= pagamento.expira_em:
            return marcar_falha(pagamento, Pagamento.EXPIRADO, MOTIVO_EXPIRADO)
        return pagamento

    try:
        resultado = obter_provedor(pagamento.provedor).consultar(pagamento)
        estado = resultado.estado
        motivo = resultado.motivo
    except NotImplementedError:
        raise
    except Exception:
        logger.exception('Falha ao consultar pagamento %s', pagamento.id)
        estado, motivo = Pagamento.PENDENTE, ''

    if estado == Pagamento.PAGO:
        try:
            return confirmar_pagamento(pagamento)
        except ErroPagamento:
            # Cancelado/anulado em paralelo: devolver o estado atual
            pagamento.refresh_from_db()
            return pagamento
    if estado in (Pagamento.RECUSADO, Pagamento.EXPIRADO):
        return marcar_falha(pagamento, estado, motivo or MOTIVO_EXPIRADO)
    if timezone.now() >= pagamento.expira_em:
        return marcar_falha(pagamento, Pagamento.EXPIRADO, MOTIVO_EXPIRADO)
    return pagamento


def resolver_pendentes(user):
    for p in Pagamento.objects.filter(user=user, estado=Pagamento.PENDENTE):
        atualizar_estado(p)


def resolver_pendentes_caducados(agora=None):
    """Para o cron: resolve pendentes fora de prazo (liberta reservas de códigos)."""
    agora = agora or timezone.now()
    total = 0
    for p in Pagamento.objects.filter(estado=Pagamento.PENDENTE, expira_em__lte=agora):
        try:
            atualizar_estado(p)
            total += 1
        except Exception:
            logger.exception('Falha ao resolver pagamento pendente %s', p.pk)
    return total


def marcar_falha(pagamento, estado, motivo=''):
    """pendente -> recusado | expirado | cancelado. Sem efeito noutros estados."""
    with transaction.atomic():
        p = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
        if p.estado == Pagamento.PENDENTE:
            p.estado = estado
            p.motivo_falha = motivo
            _libertar_promo(p)
            p.save(update_fields=['estado', 'motivo_falha', 'uso_promo', 'updated_at'])
    pagamento.refresh_from_db()
    return pagamento


def cancelar_pagamento(pagamento):
    atualizar_estado(pagamento)
    if pagamento.estado != Pagamento.PENDENTE:
        raise ErroPagamento(
            f'Só é possível cancelar pagamentos pendentes (estado actual: {pagamento.estado}).',
            status=409, codigo='estado_invalido',
        )
    marcar_falha(pagamento, Pagamento.CANCELADO, MOTIVO_CANCELADO)
    if pagamento.estado != Pagamento.CANCELADO:
        raise ErroPagamento(
            f'Só é possível cancelar pagamentos pendentes (estado actual: {pagamento.estado}).',
            status=409, codigo='estado_invalido',
        )
    _cancelar_no_provedor(pagamento)
    return pagamento


def gerar_numero_recibo(quando=None):
    """PE-R-<YYYY>-<NNNNNN>, sequencial por ano (hora de Angola). Chamar dentro de atomic."""
    ano = timezone.localtime(quando or timezone.now(), FUSO_ANGOLA).year
    try:
        with transaction.atomic():
            SequenciaRecibo.objects.get_or_create(ano=ano)
    except IntegrityError:
        pass  # criado em paralelo
    seq = SequenciaRecibo.objects.select_for_update().get(ano=ano)
    seq.ultimo += 1
    seq.save(update_fields=['ultimo'])
    return f'PE-R-{ano}-{seq.ultimo:06d}'


def confirmar_pagamento(pagamento):
    """Marca como pago e ativa o plano. Idempotente; anula pagamentos ultrapassados."""
    confirmado_agora = False
    anulado = False
    with transaction.atomic():
        p = Pagamento.objects.select_for_update(of=('self',)).select_related('plan', 'user').get(pk=pagamento.pk)
        if p.estado == Pagamento.PAGO:
            pass
        elif p.estado != Pagamento.PENDENTE:
            raise ErroPagamento(
                f'O pagamento não pode ser confirmado (estado: {p.estado}).',
                status=409, codigo='estado_invalido',
            )
        else:
            # Serializa as confirmações do mesmo utilizador
            sub = obter_ou_criar_assinatura(p.user)
            sub = UserSubscription.objects.select_for_update().get(pk=sub.pk)
            outro = (Pagamento.objects
                     .filter(user=p.user, estado=Pagamento.PAGO, pago_em__gte=p.created_at)
                     .exclude(pk=p.pk).exists())
            if outro:
                logger.warning('Pagamento %s anulado: outro pagamento do utilizador %s foi '
                               'confirmado depois de este ter sido criado.', p.pk, p.user_id)
                p.estado = Pagamento.CANCELADO
                p.motivo_falha = MOTIVO_ANULADO
                _libertar_promo(p)
                p.save(update_fields=['estado', 'motivo_falha', 'uso_promo', 'updated_at'])
                anulado = True
            else:
                now = timezone.now()
                p.estado = Pagamento.PAGO
                p.pago_em = now
                p.motivo_falha = ''
                p.numero_recibo = gerar_numero_recibo(now)
                _ativar_subscricao(p, sub, now)
                _confirmar_promo(p, sub)
                p.save()
                confirmado_agora = True

    if anulado:
        pagamento.refresh_from_db()
        raise ErroPagamento(MOTIVO_ANULADO, status=409, codigo='anulado')
    if confirmado_agora:
        transaction.on_commit(
            lambda: pagamento_confirmado.send(sender=Pagamento, pagamento=p)
        )
    pagamento.refresh_from_db()
    return pagamento


def _ativar_subscricao(p, sub, agora):
    fim_anterior = sub.expires_at
    # Mesmo plano em vigor (renovação, ou pagar durante o teste): estende a partir do fim actual
    estende = bool(sub.plan_id == p.plan_id and sub.status != 'EXPIRED'
                   and fim_anterior and fim_anterior > agora)
    metodo = p.get_metodo_display()
    s, historico = ativar_plano(
        p.user, p.plan, p.billing_cycle,
        amount_paid=Decimal(p.total_kz),
        discount=Decimal(p.desconto_kz),
        promo=None,  # o uso do código é tratado pela reserva (_confirmar_promo)
        notas_extra=f'{metodo}. Recibo {p.numero_recibo}',
        credito=Decimal(p.credito_kz),
        dias_extra=p.dias_extra,
    )
    p.historico = historico
    p.periodo_fim = s.expires_at
    p.periodo_inicio = fim_anterior if estende else agora
    _seguir_promo(p, s, estende)


def _seguir_promo(p, s, estende):
    """Guarda na assinatura o código que continua nas renovações (duração meses/sempre)."""
    meses = MESES_POR_CICLO.get(p.billing_cycle, 1)
    promo = None
    if p.uso_promo_id:
        promo = PromotionalCode.objects.filter(usages__pk=p.uso_promo_id).first()
    if p.promo_renovacao and s.promo_codigo_id:
        s.promo_meses_usados += meses
    elif promo is not None:
        if promo.duracao == PromotionalCode.DURACAO_PRIMEIRO:
            s.promo_codigo, s.promo_meses_usados = None, 0
        else:
            s.promo_codigo, s.promo_meses_usados = promo, meses
    elif not estende:
        s.promo_codigo, s.promo_meses_usados = None, 0  # plano novo sem código
    else:
        return
    s.save(update_fields=['promo_codigo', 'promo_meses_usados', 'updated_at'])


def obter_pagamento_pago_de_plano(user, pagamento_id, plan):
    """Usado por subscriptions/upgrade/: pagamento do utilizador, deste plano, já pago."""
    try:
        pagamento = Pagamento.objects.get(
            id=pagamento_id, user=user, plan=plan,
        )
    except Exception:  # inexistente ou id mal formado
        return None
    atualizar_estado(pagamento)
    return pagamento if pagamento.estado == Pagamento.PAGO else None


def periodo_atual(sub):
    """
    Período (mensal/anual) do plano pago atual e o seu preço de renovação.
    Vem do último pagamento confirmado deste plano; sem pagamentos (plano dado
    por um administrador) usa o histórico. Plano Gratuito: ambos None.
    """
    vazio = {'periodo': None, 'valor_periodo_kz': None}
    if not sub or sub.plan.plan_type == 'FREE' or sub.status == 'TRIAL':
        return vazio
    p = (Pagamento.objects
         .filter(user_id=sub.user_id, estado=Pagamento.PAGO, plan_id=sub.plan_id, creditado_em__isnull=True)
         .order_by('-periodo_fim', '-pago_em').only('periodo').first())
    periodo = p.periodo if p else None
    if periodo is None:
        ultimo = (SubscriptionHistory.objects
                  .filter(subscription=sub, new_plan_id=sub.plan_id)
                  .exclude(event_type='EXPIRED').order_by('-created_at').first())
        notas = (ultimo.notes or '') if ultimo else ''
        if 'Ciclo: Anual' in notas or 'YEARLY' in notas:
            periodo = Pagamento.PERIODO_ANUAL
        elif 'Ciclo: Mensal' in notas or 'MONTHLY' in notas:
            periodo = Pagamento.PERIODO_MENSAL
    if periodo is None:
        return vazio
    return {
        'periodo': periodo,
        'valor_periodo_kz': _kz(preco_base_plano(sub.plan, Pagamento.CICLO_POR_PERIODO[periodo], sub)),
    }


# ---------------------------------------------------------------------------
# Representações
# ---------------------------------------------------------------------------

def _simulado(p):
    cls = PROVEDORES.get(p.provedor)
    return bool(cls and cls.simulado)


def _credito_repr(p):
    return {
        'credito_kz': p.credito_abatido_kz,
        'credito_total_kz': p.credito_kz,
        'credito_dias_restantes': p.credito_dias_restantes,
        'credito_plano': {'nome': p.credito_plano.name, 'tipo': p.credito_plano.plan_type}
        if p.credito_plano_id else None,
        'dias_extra': p.dias_extra,
    }


def representar_pagamento(p):
    dados = {
        'id': str(p.id),
        'tipo': p.tipo,
        'estado': p.estado,
        'estado_display': p.get_estado_display(),
        'descricao': p.descricao,
        'valor_kz': p.valor_kz,
        'desconto_kz': p.desconto_kz,
        **_credito_repr(p),
        'total_kz': p.total_kz,
        'moeda': 'AOA',
        'metodo': p.get_metodo_display(),
        'metodo_codigo': p.metodo,
        'telefone_mascarado': p.telefone_mascarado,
        'codigo_promocional': p.codigo_promocional,
        'periodo': p.periodo,
        'plano': {'id': str(p.plan_id), 'nome': p.plan.name, 'tipo': p.plan.plan_type},
        'motivo_falha': p.motivo_falha or None,
        'criado_em': _iso(p.created_at),
        'expira_em': _iso(p.expira_em),
        'pago_em': _iso(p.pago_em),
        'numero_recibo': p.numero_recibo,
        'simulado': _simulado(p),
        'ativacao': None,
    }
    if p.estado == Pagamento.PAGO:
        # O que ESTE pagamento ativou (não a subscrição atual, que pode ter mudado depois)
        dados['ativacao'] = {
            'plano': {
                'nome': p.plan.name,
                'tipo': p.plan.plan_type,
                'periodo': p.periodo,
                'inicio': _iso(p.periodo_inicio),
                'expira_em': _iso(p.periodo_fim),
            },
        }
    return dados


def representar_recibo(p):
    validade = None
    if p.periodo_fim:
        validade = {'inicio': _iso(p.periodo_inicio), 'fim': _iso(p.periodo_fim)}

    linhas = [{
        'tipo': 'plano',
        'descricao': p.descricao,
        'periodo': p.get_periodo_display() if p.periodo else None,
        'quantidade': 1,
        'preco_unitario_kz': p.valor_kz,
        'desconto_kz': p.desconto_kz,
        'total_kz': p.valor_kz - p.desconto_kz,
    }]
    credito_descricao = None
    if p.credito_abatido_kz:
        credito_descricao = _descricao_credito(p.credito_plano, p.credito_dias_restantes)
        linhas.append({
            'tipo': 'credito',
            'descricao': credito_descricao,
            'periodo': None,
            'quantidade': 1,
            'preco_unitario_kz': -p.credito_abatido_kz,
            'desconto_kz': 0,
            'total_kz': -p.credito_abatido_kz,
        })

    return {
        'numero_recibo': p.numero_recibo,
        'data_emissao': _iso(p.pago_em),
        'emitente': {'nome': 'ProEnglish'},
        'cliente': {
            'nome': p.user.name or p.user.get_full_name() or p.user.username,
            'email': p.user.email,
        },
        'linhas': linhas,
        'descricao': p.descricao,
        'tipo': p.tipo,
        'periodo': p.periodo,
        'periodo_display': p.get_periodo_display() if p.periodo else None,
        'validade': validade,
        'quantidade': 1,
        'subtotal_kz': p.valor_kz,
        'desconto_kz': p.desconto_kz,
        'codigo_promocional': p.codigo_promocional,
        **_credito_repr(p),
        'credito_descricao': credito_descricao,
        'total_kz': p.total_kz,
        'moeda': 'AOA',
        'metodo': p.get_metodo_display(),
        'metodo_codigo': p.metodo,
        'telefone_mascarado': p.telefone_mascarado or None,
        'referencia': p.referencia_externa or None,
        'estado': p.estado,
        'pagamento_id': str(p.id),
        'criado_em': _iso(p.created_at),
        'pago_em': _iso(p.pago_em),
    }


def _entrada_base(p):
    return {
        'description': p.descricao,
        'amount_kz': p.total_kz,
        'credit_kz': p.credito_abatido_kz,
        'extra_days': p.dias_extra,
        'method': p.get_metodo_display(),
        'phone_masked': p.telefone_mascarado or None,
        'receipt_number': p.numero_recibo,
        'status': p.estado,
        'pagamento_id': str(p.id),
    }


def enriquecer_historico_pagamentos(user, formatted_history):
    """
    Estende a lista de payment-history (subscriptions) com os dados dos pagamentos:
    as entradas pagas ganham método, telefone, crédito e recibo.
    """
    resolver_pendentes(user)
    pagos = Pagamento.objects.filter(
        user=user, estado=Pagamento.PAGO, historico__isnull=False).select_related('plan')
    por_historico = {str(p.historico_id): p for p in pagos}

    for item in formatted_history:
        p = por_historico.get(item['id'])
        if p:
            item.update(_entrada_base(p))
        else:
            novo_plano = item.get('new_plan') or {}
            item.setdefault('description', f"Plano {novo_plano.get('name', '')}".strip())
            item.setdefault('amount_kz', int(item.get('amount') or 0))
            item.setdefault('credit_kz', 0)
            item.setdefault('extra_days', 0)
            item.setdefault('method', None)
            item.setdefault('phone_masked', None)
            item.setdefault('receipt_number', None)
            item.setdefault('status', 'pago')
            item.setdefault('pagamento_id', None)
        item['source'] = 'subscription'

    formatted_history.sort(key=lambda i: i.get('date') or '', reverse=True)
    return formatted_history
