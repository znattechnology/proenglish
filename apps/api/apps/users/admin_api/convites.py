"""
Convites de professor.

Administração (EAdministrador):
- GET    /api/v1/admin/convites/
- POST   /api/v1/admin/convites/                {email, nome, area, publica_sem_revisao}
- DELETE /api/v1/admin/convites/<id>/           cancela
- POST   /api/v1/admin/convites/<id>/reenviar/  token novo, mais 7 dias

Público (sem sessão, com limite por IP):
- GET  /api/v1/convites/<token>/           {nome, email, area, valido, estado}
- POST /api/v1/convites/<token>/aceitar/   {nome, password} -> cria a conta de professor e entra
                                            (mesmos cookies e mesmo corpo que o login)
"""
import hashlib
import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErroDjango
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import (api_view, authentication_classes, permission_classes,
                                       throttle_classes)
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.core.ip import ip_do_cliente
from apps.core.permissions import EAdministrador

from ..models import ConviteProfessor, PerfilProfessor, User
from . import servicos as sv


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _novo_token(convite):
    token = secrets.token_urlsafe(32)
    convite.token_hash = _hash(token)
    return token


def area_rotulo(area):
    """
    Área como o aluno a vê ('Industry English' -> 'Petróleo e Gás'), com os mesmos rótulos dos
    cursos (apps.courses.ciclo.area_pt). Texto livre fica como está; vazio -> None.
    """
    from apps.courses.ciclo import area_pt
    return area_pt((area or '').strip()) or None


def convite_dict(c):
    d = {
        'id': c.pk,
        'email': c.email,
        'nome': c.nome,
        'publica_sem_revisao': c.publica_sem_revisao,
        'estado': c.estado_actual,
        'enviado_em': sv.iso(c.enviado_em),
        'expira_em': sv.iso(c.expira_em),
        'aceite_em': sv.iso(c.aceite_em),
    }
    area = area_rotulo(c.area)
    if area:
        d['area'] = area
    return d


def _mensagem_envio(convite, enviado, reenvio=False):
    if enviado:
        return f'Convite {"reenviado" if reenvio else "enviado"} para {convite.email}. É válido durante 7 dias.'
    return (f'O convite foi {"renovado" if reenvio else "criado"}, mas não conseguimos enviar o email para '
            f'{convite.email}. Tente reenviar daqui a pouco.')


def _enviar_convite(convite, token, actor):
    destinatario = User(name=convite.nome, email=convite.email)  # só para o contexto do email
    return sv.enviar_email(destinatario, 'Convite para ensinar no ProEnglish', 'emails/admin_convite_professor.html', {
        'link': sv.frontend(f'/convite/{token}'),
        'area': area_rotulo(convite.area),
        'expira_em': timezone.localtime(convite.expira_em, sv.FUSO_LUANDA).strftime('%d/%m/%Y'),
        'quem_convida': getattr(actor, 'name', '') or 'A equipa ProEnglish',
    })


# ---------------------------------------------------------------------------
# Administração
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([EAdministrador])
def convites(request):
    if request.method == 'GET':
        return Response([convite_dict(c) for c in ConviteProfessor.objects.all()[:500]])

    d = request.data if isinstance(request.data, dict) else {}
    erros = {}
    email = (d.get('email') or '').strip().lower() if isinstance(d.get('email'), (str, type(None))) else ''
    nome = (d.get('nome') or '').strip() if isinstance(d.get('nome'), (str, type(None))) else ''
    area = (d.get('area') or '').strip() if isinstance(d.get('area'), (str, type(None))) else ''
    publica = d.get('publica_sem_revisao', False)
    try:
        validate_email(email)
    except ErroDjango:
        erros['email'] = ['Escreva um email válido.']
    if not (2 <= len(nome) <= 255):
        erros['nome'] = ['Escreva o nome do professor.']
    area = area_rotulo(area) or ''  # guarda-se o rótulo pt-PT ('Petróleo e Gás'), não a categoria
    if len(area) > 120:
        erros['area'] = ['A área tem no máximo 120 caracteres.']
    if not isinstance(publica, bool):
        erros['publica_sem_revisao'] = ['Use true ou false.']
    if erros:
        return sv.erro_validacao(erros)
    if User.objects.filter(email__iexact=email).exists():
        return sv.erro('Já existe uma conta com este email.', 'email_existe', 409)

    agora = timezone.now()
    # Um só convite pendente por email: os anteriores ficam cancelados.
    ConviteProfessor.objects.filter(email__iexact=email, estado=ConviteProfessor.PENDENTE).update(
        estado=ConviteProfessor.CANCELADO, cancelado_em=agora)
    convite = ConviteProfessor(email=email, nome=nome, area=area, publica_sem_revisao=publica,
                               enviado_em=agora, expira_em=agora + ConviteProfessor.VALIDADE,
                               criado_por=request.user)
    token = _novo_token(convite)
    convite.save()
    enviado = _enviar_convite(convite, token, request.user)
    sv.registar(request, 'convite_criar', convite, alvo_tipo='convite', detalhes={
        'email': email, 'nome': nome, 'area': area, 'publica_sem_revisao': publica, 'email_enviado': enviado})
    corpo = convite_dict(convite)
    corpo['email_enviado'] = enviado
    corpo['message'] = _mensagem_envio(convite, enviado)
    return Response(corpo, status=201)


def _convite_admin(convite_id):
    return ConviteProfessor.objects.filter(pk=convite_id).first()


@api_view(['DELETE'])
@permission_classes([EAdministrador])
def cancelar(request, convite_id):
    convite = _convite_admin(convite_id)
    if convite is None:
        return sv.erro('Não encontrámos este convite.', 'not_found', 404)
    if convite.estado == ConviteProfessor.ACEITE:
        return sv.erro('Este convite já foi aceite.', 'convite_aceite', 409)
    if convite.estado != ConviteProfessor.CANCELADO:
        convite.estado = ConviteProfessor.CANCELADO
        convite.cancelado_em = timezone.now()
        convite.save(update_fields=['estado', 'cancelado_em'])
        sv.registar(request, 'convite_cancelar', convite, alvo_tipo='convite', detalhes={'email': convite.email})
    return Response(convite_dict(convite))


@api_view(['POST'])
@permission_classes([EAdministrador])
def reenviar(request, convite_id):
    convite = _convite_admin(convite_id)
    if convite is None:
        return sv.erro('Não encontrámos este convite.', 'not_found', 404)
    if convite.estado == ConviteProfessor.ACEITE:
        return sv.erro('Este convite já foi aceite.', 'convite_aceite', 409)
    if User.objects.filter(email__iexact=convite.email).exists():
        return sv.erro('Já existe uma conta com este email.', 'email_existe', 409)
    agora = timezone.now()
    # Um só convite pendente por email: ao reenviar um convite antigo ou cancelado, os outros
    # pendentes para o mesmo email ficam cancelados.
    (ConviteProfessor.objects.filter(email__iexact=convite.email, estado=ConviteProfessor.PENDENTE)
     .exclude(pk=convite.pk).update(estado=ConviteProfessor.CANCELADO, cancelado_em=agora))
    token = _novo_token(convite)  # o link antigo deixa de servir
    convite.estado = ConviteProfessor.PENDENTE
    convite.cancelado_em = None
    convite.enviado_em = agora
    convite.expira_em = agora + ConviteProfessor.VALIDADE
    convite.save()
    enviado = _enviar_convite(convite, token, request.user)
    sv.registar(request, 'convite_reenviar', convite, alvo_tipo='convite',
                detalhes={'email': convite.email, 'email_enviado': enviado})
    corpo = convite_dict(convite)
    corpo['email_enviado'] = enviado
    corpo['message'] = _mensagem_envio(convite, enviado, reenvio=True)
    return Response(corpo)


# ---------------------------------------------------------------------------
# Público
# ---------------------------------------------------------------------------

class ConvitePublicoThrottle(SimpleRateThrottle):
    scope = 'convite_publico'
    rate = '60/hour'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': ip_do_cliente(request)}


class AceitarConviteThrottle(ConvitePublicoThrottle):
    scope = 'convite_aceitar'
    rate = '10/hour'


def _convite_publico(token):
    if not token or len(token) > 200:
        return None
    return ConviteProfessor.objects.filter(token_hash=_hash(token)).first()


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@throttle_classes([ConvitePublicoThrottle])
def publico(request, token):
    convite = _convite_publico(token)
    if convite is None:
        return sv.erro('Este convite não existe. Peça um convite novo à equipa ProEnglish.', 'not_found', 404)
    estado = convite.estado_actual
    corpo = {
        'nome': convite.nome,
        'email': convite.email,
        'valido': estado == ConviteProfessor.PENDENTE,
        'estado': estado,
    }
    area = area_rotulo(convite.area)
    if area:
        corpo['area'] = area
    return Response(corpo)


MENSAGENS_INVALIDO = {
    ConviteProfessor.EXPIRADO: 'Este convite expirou. Peça um convite novo à equipa ProEnglish.',
    ConviteProfessor.ACEITE: 'Este convite já foi usado. Entre com o seu email e palavra-passe.',
    ConviteProfessor.CANCELADO: 'Este convite foi cancelado. Fale com a equipa ProEnglish.',
}


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@throttle_classes([AceitarConviteThrottle])
def aceitar(request, token):
    from ..views import dados_utilizador, definir_cookies_sessao, emitir_sessao

    convite = _convite_publico(token)
    if convite is None:
        return sv.erro('Este convite não existe. Peça um convite novo à equipa ProEnglish.', 'not_found', 404)
    estado = convite.estado_actual
    if estado != ConviteProfessor.PENDENTE:
        return sv.erro(MENSAGENS_INVALIDO[estado], f'convite_{estado}', 410)

    d = request.data if isinstance(request.data, dict) else {}
    nome = d.get('nome') if isinstance(d.get('nome'), str) else ''
    nome = (nome or '').strip() or convite.nome
    password = d.get('password') if isinstance(d.get('password'), str) else ''
    erros = {}
    if not (2 <= len(nome) <= 255):
        erros['nome'] = ['Escreva o seu nome.']
    if not password:
        erros['password'] = ['Escolha uma palavra-passe.']
    else:
        try:
            validate_password(password, user=User(email=convite.email, name=nome))
        except ErroDjango as e:
            erros['password'] = list(e.messages)
    if erros:
        return sv.erro_validacao(erros)
    if User.objects.filter(email__iexact=convite.email).exists():
        return sv.erro('Já existe uma conta com este email. Entre com o seu email e palavra-passe.',
                       'email_existe', 409)

    agora = timezone.now()
    try:
        with transaction.atomic():
            # Bloqueia o convite: dois pedidos ao mesmo tempo não criam duas contas.
            convite = ConviteProfessor.objects.select_for_update().get(pk=convite.pk)
            if convite.estado_actual != ConviteProfessor.PENDENTE:
                return sv.erro(MENSAGENS_INVALIDO.get(convite.estado_actual, 'Este convite já não é válido.'),
                               f'convite_{convite.estado_actual}', 410)
            user = User.objects.create_user(email=convite.email, name=nome, password=password, role='teacher')
            user.email_verified = True
            user.last_login_at = agora
            user.save(update_fields=['email_verified', 'last_login_at'])
            PerfilProfessor.objects.update_or_create(
                user=user, defaults={'publica_sem_revisao': convite.publica_sem_revisao})
            convite.estado = ConviteProfessor.ACEITE
            convite.aceite_em = agora
            convite.utilizador = user
            convite.save(update_fields=['estado', 'aceite_em', 'utilizador'])
    except IntegrityError:
        return sv.erro('Já existe uma conta com este email. Entre com o seu email e palavra-passe.',
                       'email_existe', 409)
    sv.registar(request, 'convite_aceite', user, detalhes={'convite': convite.pk})

    access, refresh = emitir_sessao(user)
    resposta = Response({'user': dados_utilizador(user)})
    return definir_cookies_sessao(resposta, access, refresh)
