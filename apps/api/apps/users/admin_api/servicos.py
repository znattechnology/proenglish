"""
Regras partilhadas da administração de utilizadores.

Usadas pelas APIs novas (/api/v1/admin/...) e pelas rotas antigas de users/admin/*, para que
as mesmas regras (registo, sessões, suspensão, plano, email) valham em todo o lado.
"""
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.ip import ip_do_cliente

from ..models import PerfilProfessor, RegistoAdmin, SuspensaoConta, User

logger = logging.getLogger(__name__)

FUSO_LUANDA = ZoneInfo('Africa/Luanda')
NOME_PLANO = {'FREE': 'Gratuito', 'PREMIUM': 'Premium', 'PREMIUM_PLUS': 'Premium Plus'}
PLANOS_PAGOS = ('PREMIUM', 'PREMIUM_PLUS')
PAPEIS = ('student', 'teacher', 'admin')
NOME_PAPEL = {'student': 'estudante', 'teacher': 'professor', 'admin': 'administrador'}
DIAS_PLANO_ATRIBUIDO = 30


# ---------------------------------------------------------------------------
# Respostas e registo
# ---------------------------------------------------------------------------

def erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details or {}, **extra), status=status_http)


def erro_validacao(details):
    """400 com details {campo: [mensagens]}; a mensagem é o primeiro erro."""
    primeira = next(iter(details.values()))[0]
    return erro(primeira, 'validation_error', 400, details)


def registar(request, accao, alvo=None, alvo_tipo='', detalhes=None, alvo_id=''):
    """Grava um RegistoAdmin para uma alteração feita pela administração."""
    if alvo is not None and not alvo_tipo:
        alvo_tipo = 'utilizador' if isinstance(alvo, User) else alvo.__class__.__name__.lower()
    try:
        ip = ip_do_cliente(request)[:45] if request is not None else ''
    except Exception:
        ip = ''
    autor = getattr(request, 'user', None) if request is not None else None
    return RegistoAdmin.objects.create(
        autor=autor if getattr(autor, 'is_authenticated', False) else None,
        accao=accao,
        alvo_tipo=alvo_tipo,
        alvo_id=str(getattr(alvo, 'pk', '') or '') if alvo is not None else str(alvo_id or ''),
        detalhes=detalhes or {},
        ip=ip,
    )


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def inicio_mes_luanda(agora=None):
    agora = timezone.localtime(agora or timezone.now(), FUSO_LUANDA)
    return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def iso(valor):
    return valor.isoformat() if valor else None


# ---------------------------------------------------------------------------
# Quem pode gerir quem
# ---------------------------------------------------------------------------

def e_admin_alvo(user):
    return user.role == 'admin' or user.is_superuser


def pode_gerir(actor, alvo):
    """O actor pode alterar/suspender/terminar sessões deste alvo (nunca a si próprio)."""
    return alvo.pk != actor.pk and (actor.is_superuser or not e_admin_alvo(alvo))


def recusa_editar(actor, alvo):
    """
    Response 403 se `actor` não pode editar os dados de `alvo` (qualquer campo); None se pode.
    A conta de outro administrador ou de um superutilizador só um superutilizador a altera
    (senão, um administrador podia mudar o email de um superutilizador e pedir a recuperação
    da palavra-passe para o email novo). A própria conta pode ser editada (o papel não).
    """
    if alvo.pk != actor.pk and e_admin_alvo(alvo) and not actor.is_superuser:
        return erro('Só um superutilizador pode alterar a conta de outro administrador.',
                    'alvo_administrador', 403)
    return None


def recusa_gerir(actor, alvo, accao='alterar'):
    """
    Response 403 se `actor` não pode suspender/despromover/terminar `alvo`; None se pode.
    Ninguém o faz a si próprio; a outro administrador, só um superutilizador.
    """
    if alvo.pk == actor.pk:
        return erro('Não pode fazer isto à sua própria conta.', 'propria_conta', 403)
    if e_admin_alvo(alvo) and not actor.is_superuser:
        return erro('Só um superutilizador pode fazer isto a outro administrador.', 'alvo_administrador', 403)
    return None


# ---------------------------------------------------------------------------
# Sessões
# ---------------------------------------------------------------------------

def terminar_todas_sessoes(user):
    """
    Termina já todas as sessões: refresh tokens para a lista negra e tokens de acesso
    emitidos até agora deixam de valer (User.sessoes_invalidas_antes, ver middleware).
    Devolve o número de refresh tokens que estavam por usar.
    """
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    from ..views import terminar_sessoes
    agora = timezone.now()
    n = (OutstandingToken.objects.filter(user=user, expires_at__gt=agora, blacklistedtoken__isnull=True)
         .count())
    terminar_sessoes(user)
    User.objects.filter(pk=user.pk).update(sessoes_invalidas_antes=agora)
    user.sessoes_invalidas_antes = agora
    return n


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def enviar_email(user, assunto, template, contexto=None, destino=None):
    from ..email_service import _contexto_base, _enviar
    destino = destino or user.email
    ctx = {**_contexto_base(user, destino), **(contexto or {})}
    return _enviar(assunto, template, ctx, destino)


def enviar_verificacao(user):
    """Código de confirmação para o email actual (mesmo fluxo do registo)."""
    from ..email_service import EmailVerificationService
    try:
        v = EmailVerificationService.create_verification_code(user, user.email)
        return EmailVerificationService.send_verification_email(v)
    except Exception:
        logger.exception('Falha ao enviar a confirmação do email (user=%s)', user.pk)
        return False


def pedir_mudanca_email(user, novo, request=None):
    """
    Mudança de email pedida pela administração: o email novo fica em `email_pendente` e só
    passa a ser o da conta quando a pessoa o confirmar com o código enviado para ele
    (POST /api/v1/users/confirmar-email-novo/). Até lá o email actual, a sua confirmação e a
    entrada não mudam, e a recuperação da palavra-passe continua a ir para o email actual.
    O email actual recebe um aviso de que foi pedida a mudança.

    Devolve (codigo_enviado: bool, aviso_enviado: bool). Chamar fora de transacções longas.
    """
    from ..email_service import EmailVerificationService, _contexto_base, _enviar, _link
    from ..models import EmailVerification
    novo = novo.strip().lower()
    User.objects.filter(pk=user.pk).update(email_pendente=novo)
    user.email_pendente = novo
    enviado = False
    try:
        v = EmailVerificationService.create_verification_code(
            user, novo, finalidade=EmailVerification.FINALIDADE_MUDAR_EMAIL)
        ctx = {**_contexto_base(user, novo), 'verification_code': v.code,
               'verification_url': _link('/confirmar-email-novo', email=novo)}
        enviado = _enviar('Confirme o seu email novo - ProEnglish', 'emails/admin_email_novo.html', ctx, novo)
    except Exception:
        logger.exception('Falha ao enviar o código do email novo (user=%s)', user.pk)
    avisado = enviar_email(user, 'Pedido de mudança do email da sua conta ProEnglish',
                           'emails/admin_email_mudanca_pedida.html', {'email_novo': novo})
    return enviado, avisado


CODIGO_EMAIL_NOVO_INVALIDO = 'O código não está certo ou já expirou. Peça à equipa ProEnglish um código novo.'


def confirmar_mudanca_email(email, code):
    """
    Confirma o email novo pedido pela administração com o código de 6 dígitos.
    Devolve (user, None) ou (None, (mensagem, code)). Um código errado conta como tentativa.
    """
    from ..models import EmailVerification
    email = (email or '').strip().lower()
    code = str(code or '').strip()
    invalido = (None, (CODIGO_EMAIL_NOVO_INVALIDO, 'codigo_invalido'))
    if not email or not code:
        return invalido
    with transaction.atomic():
        v = (EmailVerification.objects.select_for_update()
             .filter(email__iexact=email, finalidade=EmailVerification.FINALIDADE_MUDAR_EMAIL, is_used=False)
             .order_by('-created_at').first())
        if v is None or v.is_expired() or v.attempts >= v.max_attempts:
            return invalido
        user = User.objects.select_for_update().get(pk=v.user_id)
        if not user.is_active or (user.email_pendente or '').lower() != email:
            return invalido
        if v.code != code:
            v.increment_attempts()
            return invalido
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return None, ('Já existe outra conta com este email. Fale com a equipa ProEnglish.', 'email_existe')
        antigo = user.email
        v.is_used = True
        v.save(update_fields=['is_used'])
        user.email = email
        user.email_verified = True
        user.email_pendente = None
        user.save(update_fields=['email', 'email_verified', 'email_pendente', 'updated_at'])
        # Códigos ainda por usar do email antigo (recuperação, confirmação) deixam de servir.
        EmailVerification.objects.filter(user=user, is_used=False).update(is_used=True)
        registar(None, 'email_mudado', user, detalhes={'antes': antigo, 'depois': email})
    return user, None


# ---------------------------------------------------------------------------
# Plano (subscrição)
# ---------------------------------------------------------------------------

def plano_em_vigor(sub, agora=None):
    """plan_type pago em vigor ('PREMIUM'/'PREMIUM_PLUS') ou 'FREE'."""
    agora = agora or timezone.now()
    if (sub is not None and sub.plan.plan_type in PLANOS_PAGOS and sub.status != 'EXPIRED'
            and sub.expires_at and sub.expires_at > agora):
        return sub.plan.plan_type
    return 'FREE'


def subscricao(user):
    from apps.subscriptions.models import UserSubscription
    return UserSubscription.objects.filter(user=user).select_related('plan').first()


@transaction.atomic
def atribuir_plano(user, plan_type, actor, request=None):
    """
    Muda o plano sem cobrar (decisão da administração).

    * PREMIUM / PREMIUM_PLUS: se já há um plano pago (comprado) em vigor, o fim mantém-se (só muda
      o plano); se vinha do Gratuito, de um plano expirado ou de um teste grátis, o plano dura
      30 dias a partir de agora. Estado ACTIVE.
    * Durante um teste grátis (status TRIAL), atribuir um plano pago (mesmo o do teste) converte
      o teste numa assinatura normal ACTIVE de 30 dias: o fim do teste (trial_ends_at) é limpo e
      o trabalho que termina os testes (pagamentos.teste.terminar_testes, que só lê
      status='TRIAL') já não a reverte para o Gratuito.
    * FREE: o plano pago (ou o teste) acaba já (plano Gratuito, sem fim, como os outros gratuitos).
    * Preço contratado e código promocional, como em subscriptions.services.ativar_plano quando
      não é renovação: ao mudar de plano (ou vindo do Gratuito/expirado/teste) o preço
      contratado passa a ser o preço actual do plano novo (None no Gratuito) e o código
      promocional deixa de se aplicar.
    * Em qualquer mudança de plano, os pagamentos com período em curso deixam de dar crédito
      (Pagamento.creditado_em = agora), como em subscriptions.services.ativar_plano.
    * Fica um SubscriptionHistory (UPGRADED/DOWNGRADED/CANCELED/CREATED, amount_paid=None) com a
      nota "Atribuído pela administração, sem pagamento".

    Devolve (mudou: bool, detalhes: dict).
    """
    from apps.subscriptions.models import SubscriptionHistory, SubscriptionPlan, UserSubscription
    from apps.subscriptions.services import DURACAO_PLANO_GRATUITO, kz_inteiro, obter_ou_criar_assinatura

    agora = timezone.now()
    sub = obter_ou_criar_assinatura(user)
    sub = UserSubscription.objects.select_for_update().select_related('plan').get(pk=sub.pk)
    actual = plano_em_vigor(sub, agora)
    em_teste = sub.status == 'TRIAL' and actual != 'FREE'
    if actual == plan_type and not em_teste:
        return False, {}

    novo = SubscriptionPlan.objects.filter(plan_type=plan_type).first()
    if novo is None:
        if plan_type != 'FREE':
            raise SubscriptionPlan.DoesNotExist(plan_type)
        from apps.subscriptions.services import obter_plano_gratuito
        novo = obter_plano_gratuito()
    antigo = sub.plan
    fim_antes = sub.expires_at

    if plan_type == 'FREE':
        sub.expires_at = agora + DURACAO_PLANO_GRATUITO
        sub.canceled_at = agora
        evento = 'CANCELED'
    else:
        if actual == 'FREE' or em_teste:
            sub.expires_at = agora + timedelta(days=DIAS_PLANO_ATRIBUIDO)
        if em_teste and antigo.pk == novo.pk:
            evento = 'CREATED'
        else:
            evento = 'UPGRADED' if novo.monthly_price >= antigo.monthly_price else 'DOWNGRADED'
        sub.canceled_at = None
    # Preço contratado e promoção: o plano mudou (ou vem do Gratuito/expirado/teste).
    if plan_type == 'FREE':
        sub.preco_mensal_kz = sub.preco_anual_kz = None
    else:
        sub.preco_mensal_kz = kz_inteiro(novo.monthly_price)
        sub.preco_anual_kz = kz_inteiro(novo.yearly_price) if novo.yearly_price else None
    sub.promo_codigo = None
    sub.promo_meses_usados = 0
    sub.trial_ends_at = None
    sub.plan = novo
    sub.status = 'ACTIVE'
    if novo.hearts_limit and sub.current_hearts > novo.hearts_limit:
        sub.current_hearts = novo.hearts_limit
    elif not novo.hearts_limit:
        sub.current_hearts = 999
    sub.save()

    from apps.pagamentos.models import Pagamento
    Pagamento.objects.filter(
        user=user, estado=Pagamento.PAGO, periodo_fim__gt=agora, creditado_em__isnull=True,
    ).update(creditado_em=agora)

    nota = f'Atribuído pela administração, sem pagamento ({getattr(actor, "email", "")}).'
    if em_teste:
        nota += ' O teste grátis foi convertido numa assinatura normal.'
    SubscriptionHistory.objects.create(
        subscription=sub, event_type=evento, previous_plan=antigo, new_plan=novo, amount_paid=None,
        notes=nota,
    )
    return True, {
        'plano_antes': actual, 'plano_depois': plan_type, 'era_teste': em_teste,
        'fim_antes': iso(fim_antes), 'fim_depois': iso(sub.expires_at),
    }


# ---------------------------------------------------------------------------
# Suspensão
# ---------------------------------------------------------------------------

def suspensao_activa(user):
    return SuspensaoConta.objects.filter(user=user, terminada_em__isnull=True).select_related('por').first()


MOTIVO_PAGAMENTO_SUSPENSAO = 'Cancelado: a conta foi suspensa pela administração.'


def cancelar_pagamentos_pendentes(user):
    """
    Cancela os pagamentos Multicaixa pendentes (também no provedor), para não serem confirmados
    com a conta suspensa. Antes, cada um é actualizado junto do provedor: se afinal já foi
    pago, fica pago (e o plano activado) e conta para o tempo em pausa. Devolve os cancelados.
    """
    from apps.pagamentos import services as pag
    from apps.pagamentos.models import Pagamento
    cancelados = []
    for p in Pagamento.objects.filter(user=user, estado=Pagamento.PENDENTE):
        try:
            pag.atualizar_estado(p)
            if p.estado != Pagamento.PENDENTE:
                continue
            pag.marcar_falha(p, Pagamento.CANCELADO, MOTIVO_PAGAMENTO_SUSPENSAO)
            if p.estado == Pagamento.CANCELADO:
                pag._cancelar_no_provedor(p)
                cancelados.append(p)
        except Exception:
            logger.exception('Falha ao cancelar o pagamento pendente %s ao suspender', p.pk)
    return cancelados


@transaction.atomic
def suspender(user, actor, motivo, nota='', avisar=False, request=None):
    """
    Suspende a conta: is_active=False, registo SuspensaoConta, todas as sessões terminadas,
    subscrição paga em pausa (guarda o plano e o tempo que faltava) e, se pedido, email.
    """
    cancelados = cancelar_pagamentos_pendentes(user)
    agora = timezone.now()
    sub = subscricao(user)
    plano = plano_em_vigor(sub, agora)
    suspensao = SuspensaoConta.objects.create(
        user=user, motivo=motivo, nota=nota or '', por=actor, desde=agora,
        plano_pausado=plano if plano != 'FREE' else '',
        segundos_restantes=int((sub.expires_at - agora).total_seconds()) if plano != 'FREE' else 0,
    )
    user.is_active = False
    user.save(update_fields=['is_active'])
    terminar_todas_sessoes(user)
    if avisar:
        motivo_txt = dict(SuspensaoConta.MOTIVOS).get(motivo, motivo)
        ok = enviar_email(user, 'A sua conta ProEnglish foi suspensa', 'emails/admin_conta_suspensa.html',
                          {'motivo': motivo_txt})
        if ok:
            suspensao.avisado = True
            suspensao.save(update_fields=['avisado'])
    registar(request, 'suspender', user, detalhes={
        'motivo': motivo, 'nota': nota or '', 'avisar': bool(avisar), 'plano_pausado': suspensao.plano_pausado,
        'segundos_restantes': suspensao.segundos_restantes,
        'pagamentos_cancelados': [str(p.pk) for p in cancelados],
    })
    return suspensao


@transaction.atomic
def reactivar(user, actor, request=None):
    """Volta a activar a conta e retoma o plano pago em pausa (fim = agora + o que faltava)."""
    agora = timezone.now()
    suspensao = suspensao_activa(user)
    retomado = None
    if suspensao is not None:
        suspensao.terminada_em = agora
        suspensao.terminada_por = actor
        suspensao.save(update_fields=['terminada_em', 'terminada_por'])
        if suspensao.plano_pausado and suspensao.segundos_restantes:
            from apps.subscriptions.models import SubscriptionPlan, UserSubscription
            sub = UserSubscription.objects.select_for_update().filter(user=user).first()
            plano = SubscriptionPlan.objects.filter(plan_type=suspensao.plano_pausado).first()
            if sub is not None and plano is not None:
                fim_pausa = agora + timedelta(seconds=suspensao.segundos_restantes)
                if (plano_em_vigor(sub, agora) != 'FREE' and sub.status != 'TRIAL'
                        and sub.expires_at and sub.expires_at >= fim_pausa):
                    # Já há um plano pago que acaba depois do tempo em pausa: nunca encurtar.
                    retomado = iso(sub.expires_at)
                else:
                    sub.plan = plano
                    sub.status = 'ACTIVE'
                    sub.expires_at = fim_pausa
                    sub.save(update_fields=['plan', 'status', 'expires_at', 'updated_at'])
                    retomado = iso(sub.expires_at)
    user.is_active = True
    user.save(update_fields=['is_active'])
    registar(request, 'reactivar', user, detalhes={'plano_retomado_ate': retomado})
    return retomado


# ---------------------------------------------------------------------------
# Apagar definitivamente
# ---------------------------------------------------------------------------

def motivo_para_nao_apagar(user):
    """Texto a explicar porque não se pode apagar a conta de vez (None = pode)."""
    from apps.pagamentos.models import Pagamento
    if Pagamento.objects.filter(user=user).exists():
        return 'Esta conta tem pagamentos registados (registos fiscais). Suspenda-a em vez de a apagar.'
    try:
        from apps.courses.models import Course, CourseCertificate
        if CourseCertificate.objects.filter(user=user).exists():
            return 'Esta conta tem certificados emitidos. Suspenda-a em vez de a apagar.'
        if Course.objects.filter(teacher=user).exists():
            return 'Esta conta tem cursos. Suspenda-a em vez de a apagar.'
    except ImportError:
        pass
    return None


def apagar_definitivamente(request, user):
    """DELETE: só superutilizadores, nunca a própria conta, só contas sem pagamentos/certificados/cursos."""
    actor = request.user
    if user.pk == actor.pk:
        return erro('Não pode apagar a sua própria conta aqui.', 'propria_conta', 400)
    if not actor.is_superuser:
        return erro('Só um superutilizador pode apagar contas de vez. Pode suspender a conta.',
                    'so_superutilizador', 403)
    motivo = motivo_para_nao_apagar(user)
    if motivo:
        return erro(motivo, 'utilizador_protegido', 409)
    from django.db.models import ProtectedError
    info = {'id': str(user.id), 'nome': user.name, 'email': user.email, 'papel': user.role}
    try:
        with transaction.atomic():
            user.delete()
    except ProtectedError:
        return erro('Não é possível apagar esta conta: tem dados que têm de ser guardados. Suspenda-a.',
                    'utilizador_protegido', 409)
    registar(request, 'apagar', None, alvo_tipo='utilizador', alvo_id=info['id'], detalhes=info)
    return Response({'message': f'A conta de {info["nome"]} foi apagada.', 'utilizador': info})


def garantir_perfil_professor(user):
    perfil, _ = PerfilProfessor.objects.get_or_create(user=user)
    return perfil


def frontend(caminho=''):
    return f'{(getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")}{caminho}'
