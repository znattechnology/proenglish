"""
Período de teste grátis de um plano pago (``SubscriptionPlan.dias_teste``).

* Quem pode: só alunos (``role='student'``) que nunca fizeram um teste nem uma subscrição
  paga (inclui activações a 0 Kz) e não têm agora um plano pago em vigor. O plano tem de
  estar activo (um plano desactivado não dá testes novos).
* Um teste por pessoa (qualquer plano). A pessoa indica o número Multicaixa Express
  (angolano, 9xxxxxxxx): o número normalizado fica no ``TesteGratis`` e não pode servir
  para outro teste, noutra conta. O email também conta, normalizado (maiúsculas, "+etiqueta"
  e, no Gmail, os pontos): a mesma caixa de correio não volta a experimentar. Sem SMS por agora.
* ``iniciar_teste``: a assinatura passa ao plano, com ``status='TRIAL'`` e
  ``trial_ends_at = expires_at = agora + dias_teste``. Sem pagamento.
* Pagar durante o teste (checkout normal) converte: o período pago começa no fim do
  teste, por isso não se perdem dias (ver ``ativar_plano``). Pagar outro plano começa já.
* ``avisar_testes_a_terminar``: aviso + email 2 dias antes do fim (uma vez por teste).
* ``terminar_testes``: testes terminados sem pagamento voltam ao Gratuito (o progresso
  não é tocado). Comando ``python manage.py terminar_testes`` (cron de hora a hora).
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.subscriptions.models import (
    SubscriptionHistory, SubscriptionPlan, TesteGratis, UserSubscription, normalizar_email,
)
from apps.subscriptions.services import (
    DURACAO_PLANO_GRATUITO,
    obter_ou_criar_assinatura,
    obter_plano_gratuito,
    plano_pago_em_vigor,
    utilizador_ja_pagou,
)

from .models import LembreteRenovacao
from .signals import teste_a_terminar, teste_iniciado, teste_terminado
from .telefone import TelefoneInvalido, normalizar_telefone

logger = logging.getLogger(__name__)

MAX_DIAS_TESTE = 30
ANTECEDENCIA_T2 = timedelta(hours=48)

SEM_TESTE = 'sem_teste'
TESTE_JA_USADO = 'teste_ja_usado'
JA_ASSINANTE = 'ja_assinante'
PLANO_ACTIVO = 'plano_activo'
SEM_SESSAO = 'sem_sessao'
SO_ALUNOS = 'so_alunos'
TELEFONE_JA_USADO = 'telefone_ja_usado'
TELEFONE_INVALIDO = 'telefone_invalido'

MENSAGENS = {
    SEM_TESTE: 'Este plano não tem período de teste grátis.',
    TESTE_JA_USADO: 'Já usou o seu período de teste grátis. Para continuar, pague com Multicaixa Express.',
    JA_ASSINANTE: 'O teste grátis é só para quem ainda não teve um plano pago. '
                  'Pode pagar com Multicaixa Express.',
    PLANO_ACTIVO: 'Já tem um plano pago activo.',
    SEM_SESSAO: 'Entre na sua conta para experimentar.',
    SO_ALUNOS: 'O teste grátis é só para contas de aluno.',
    TELEFONE_JA_USADO: 'Este número Multicaixa Express já foi usado num teste grátis. '
                       'Cada pessoa só pode experimentar uma vez. Para continuar, pague com Multicaixa Express.',
}

# Estado HTTP de cada motivo
ESTADO_HTTP = {SEM_TESTE: 400, SO_ALUNOS: 403, SEM_SESSAO: 401, TELEFONE_INVALIDO: 400}


def _iso(dt):
    return dt.isoformat() if dt else None


def e_aluno(user):
    return getattr(user, 'role', None) == 'student'


def ja_experimentou(user):
    """Esta conta, ou outra com a mesma caixa de correio, já fez um teste."""
    if SubscriptionHistory.objects.filter(subscription__user=user, event_type='TRIAL_STARTED').exists():
        return True
    email = normalizar_email(getattr(user, 'email', ''))
    return TesteGratis.objects.filter(user=user).exists() or bool(
        email and TesteGratis.objects.filter(email_normalizado=email).exists())


def telefone_ja_usado(telefone):
    return bool(telefone) and TesteGratis.objects.filter(telefone=telefone).exists()


def em_teste(sub, agora=None):
    return bool(sub and sub.status == 'TRIAL' and plano_pago_em_vigor(sub, agora))


def motivo_sem_teste(user, plan, sub=None, agora=None, _historico=None):
    """None se ``user`` pode experimentar ``plan`` agora; senão o código do motivo."""
    if plan is None or plan.plan_type == 'FREE' or not plan.is_active or not (plan.dias_teste or 0) > 0:
        return SEM_TESTE
    if user is None or not getattr(user, 'is_authenticated', False):
        return SEM_SESSAO
    if not e_aluno(user):
        return SO_ALUNOS
    if sub is None:
        sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    if sub is not None and sub.plan.plan_type != 'FREE' and plano_pago_em_vigor(sub, agora):
        return TESTE_JA_USADO if sub.status == 'TRIAL' else PLANO_ACTIVO
    experimentou, pagou = _historico if _historico is not None else (ja_experimentou(user), utilizador_ja_pagou(user))
    if experimentou:
        return TESTE_JA_USADO
    if pagou:
        return JA_ASSINANTE
    return None


def historico_teste(user):
    """(já experimentou, já pagou): calcular uma vez por pedido quando há vários planos."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return (False, False)
    return (ja_experimentou(user), utilizador_ja_pagou(user))


def estado_teste(user, plan=None, sub=None, agora=None):
    """
    Campos do teste para a API do aluno: em_teste, teste_termina_em, pode_experimentar, dias_teste.

    Com ``plan``: se pode experimentar esse plano e quantos dias tem. Sem ``plan`` (a
    assinatura): dias do teste em curso, ou o maior teste disponível, e ``plano_teste``
    (o tipo do plano a que esses dias pertencem, para o botão "Experimentar N dias grátis").
    """
    if sub is None and user is not None and getattr(user, 'is_authenticated', False):
        sub = UserSubscription.objects.filter(user=user).select_related('plan').first()
    activo = em_teste(sub, agora)
    historico = historico_teste(user)
    if plan is not None:
        pode = motivo_sem_teste(user, plan, sub, agora, _historico=historico) is None
        dias = plan.dias_teste or 0
        plano_teste = plan.plan_type if pode else None
    else:
        planos = list(SubscriptionPlan.objects.filter(is_active=True, dias_teste__gt=0).exclude(plan_type='FREE')
                      .order_by('sort_order', 'monthly_price'))
        elegiveis = [p for p in planos if motivo_sem_teste(user, p, sub, agora, _historico=historico) is None]
        pode = bool(elegiveis)
        if activo:
            dias = sub.plan.dias_teste or 0
            plano_teste = sub.plan.plan_type
        else:
            melhor = max(elegiveis, key=lambda p: p.dias_teste, default=None)
            dias = melhor.dias_teste if melhor else 0
            plano_teste = melhor.plan_type if melhor else None
    termina = (sub.trial_ends_at or sub.expires_at) if activo else None
    return {
        'em_teste': activo,
        'teste_termina_em': _iso(termina),
        'pode_experimentar': pode,
        'dias_teste': dias,
        'plano_teste': plano_teste,
    }


class ErroTeste(Exception):
    def __init__(self, codigo, status=None, mensagem=None):
        self.mensagem = mensagem or MENSAGENS.get(codigo, codigo)
        super().__init__(self.mensagem)
        self.codigo = codigo
        self.status = status or ESTADO_HTTP.get(codigo, 409)


def iniciar_teste(user, plan, telefone=None, agora=None):
    """
    Começa o teste grátis de ``plan`` (SubscriptionPlan) com o número Multicaixa Express
    ``telefone`` (obrigatório). Lança ErroTeste se não puder.
    """
    agora = agora or timezone.now()
    if not e_aluno(user):
        raise ErroTeste(SO_ALUNOS)
    try:
        telefone = normalizar_telefone(telefone)
    except TelefoneInvalido as e:
        raise ErroTeste(TELEFONE_INVALIDO, mensagem=str(e))
    email = normalizar_email(getattr(user, 'email', ''))
    with transaction.atomic():
        sub = obter_ou_criar_assinatura(user)
        sub = UserSubscription.objects.select_for_update().select_related('plan').get(pk=sub.pk)
        motivo = motivo_sem_teste(user, plan, sub, agora)
        if motivo:
            raise ErroTeste(motivo)
        if telefone_ja_usado(telefone):
            raise ErroTeste(TELEFONE_JA_USADO)
        fim = agora + timedelta(days=plan.dias_teste)
        try:
            with transaction.atomic():
                TesteGratis.objects.create(user=user, plan=plan, telefone=telefone, email_normalizado=email,
                                           iniciado_em=agora, termina_em=fim)
        except IntegrityError:
            # Outro pedido em paralelo usou o mesmo número ou a mesma caixa de correio
            raise ErroTeste(TELEFONE_JA_USADO if telefone_ja_usado(telefone) else TESTE_JA_USADO)
        anterior = sub.plan
        sub.plan = plan
        sub.status = 'TRIAL'
        sub.trial_ends_at = fim
        sub.expires_at = fim
        sub.canceled_at = None
        sub.preco_mensal_kz = sub.preco_anual_kz = None
        sub.promo_codigo = None
        sub.promo_meses_usados = 0
        if not plan.hearts_limit:
            sub.current_hearts = 999
        elif sub.current_hearts > plan.hearts_limit:
            sub.current_hearts = plan.hearts_limit
        sub.save()
        SubscriptionHistory.objects.create(
            subscription=sub, event_type='TRIAL_STARTED', previous_plan=anterior, new_plan=plan,
            amount_paid=None,
            notes=f'Teste grátis de {plan.dias_teste} dias, até {fim.isoformat()}.',
        )
        transaction.on_commit(lambda: _enviar(teste_iniciado, subscription=sub))
    return sub


def _enviar(sinal, **kwargs):
    try:
        sinal.send(sender=UserSubscription, **kwargs)
    except Exception:
        logger.exception('Falha num recetor de %s', sinal)


def avisar_testes_a_terminar(agora=None, dry_run=False):
    """Aviso 2 dias (<= 48 h) antes do fim do teste, uma vez por teste."""
    agora = agora or timezone.now()
    candidatas = (UserSubscription.objects
                  .filter(status='TRIAL', expires_at__gt=agora, expires_at__lte=agora + ANTECEDENCIA_T2)
                  .exclude(plan__plan_type='FREE')
                  .select_related('plan', 'user'))
    enviados = []
    for sub in candidatas:
        fim = sub.trial_ends_at or sub.expires_at
        if LembreteRenovacao.objects.filter(subscription=sub, tipo=LembreteRenovacao.T2, fim_periodo=fim).exists():
            continue
        if dry_run:
            enviados.append(sub)
            continue
        try:
            with transaction.atomic():
                LembreteRenovacao.objects.create(subscription=sub, tipo=LembreteRenovacao.T2, fim_periodo=fim)
        except IntegrityError:
            continue
        enviados.append(sub)
        _enviar(teste_a_terminar, subscription=sub, fim=fim)
    return enviados


def terminar_testes(agora=None, dry_run=False):
    """Testes terminados sem pagamento: voltam ao Gratuito (o progresso fica)."""
    agora = agora or timezone.now()
    candidatas = UserSubscription.objects.filter(status='TRIAL', expires_at__lte=agora).values_list('pk', flat=True)
    total = 0
    gratuito = obter_plano_gratuito()
    for pk in list(candidatas):
        if dry_run:
            total += 1
            continue
        with transaction.atomic():
            s = UserSubscription.objects.select_for_update(of=('self',)).select_related('plan').get(pk=pk)
            if s.status != 'TRIAL' or s.expires_at > agora:
                continue  # pagou entretanto
            plano_teste = s.plan
            s.plan = gratuito
            s.status = 'ACTIVE'
            s.expires_at = agora + DURACAO_PLANO_GRATUITO
            s.preco_mensal_kz = s.preco_anual_kz = None
            s.promo_codigo = None
            s.promo_meses_usados = 0
            if gratuito.hearts_limit and s.current_hearts > gratuito.hearts_limit:
                s.current_hearts = gratuito.hearts_limit
            s.save()
            SubscriptionHistory.objects.create(
                subscription=s, event_type='TRIAL_ENDED', previous_plan=plano_teste, new_plan=gratuito,
                notes='O período de teste terminou sem pagamento; voltou ao plano Gratuito.',
            )
            total += 1
            transaction.on_commit(
                lambda s=s, p=plano_teste: _enviar(teste_terminado, subscription=s, plano_anterior=p))
    return total
