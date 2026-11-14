"""
Views for user authentication and profile management.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db import models
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

# S3 imports for avatar upload
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

from rest_framework.throttling import UserRateThrottle
from apps.cms.views import AdminWritePermissionMixin
from .models import User, UserAddress, NotificationSettings, EmailVerification

logger = logging.getLogger(__name__)


# ============================================================
# Custom Permission Classes for Feedback System
# ============================================================

from apps.core.permissions import EAdministrador

# Nome antigo: as vistas de administração usam a regra única EAdministrador
# (papel admin ou superutilizador, conta activa; is_staff sozinho não chega).
IsAdminUser = EAdministrador


class FeedbackSubmitThrottle(UserRateThrottle):
    """Rate limiting for feedback submissions - 10 per hour per user"""
    rate = '10/hour'


class FeedbackDismissThrottle(UserRateThrottle):
    """Rate limiting for feedback dismissals - 20 per hour per user"""
    rate = '20/hour'
from .serializers import (
    UserRegistrationSerializer, CustomTokenObtainPairSerializer,
    UserProfileSerializer, PasswordChangeSerializer,
    UserAddressSerializer, NotificationSettingsSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    EmailVerificationSerializer, GoogleOAuthSerializer,
    GoogleOAuthURLSerializer
)
from .services import GoogleOAuthService
from .email_service import EmailVerificationService


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class UserRegistrationView(generics.CreateAPIView):
    """
    View for user registration with rate limiting (5 registrations per minute per IP).
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # User starts with email_verified = False (default)
        # Create and send verification code
        try:
            verification = EmailVerificationService.create_verification_code(user)
            if not EmailVerificationService.send_verification_email(verification):
                logger.error('Não foi possível enviar o código de confirmação (user=%s)', user.pk)
        except Exception:
            # O registo continua: a pessoa pode pedir outro código em resend-verification/.
            logger.exception('Erro ao criar/enviar o código de confirmação (user=%s)', user.pk)

        # Sem sessão até confirmar o email.
        return Response({
            'message': 'Conta criada. Enviámos um código para o seu email para activar a conta.',
            'email': user.email,
            'requires_verification': True
        }, status=status.HTTP_201_CREATED)


def definir_cookies_sessao(response, access_token, refresh_token):
    """Grava a sessão (JWT) em cookies HttpOnly. Em produção, Secure + SameSite=None."""
    is_secure = not settings.DEBUG
    samesite = 'None' if is_secure else 'Lax'
    if access_token:
        response.set_cookie(key='access_token', value=access_token, max_age=60 * 60,
                            httponly=True, secure=is_secure, samesite=samesite, path='/')
    if refresh_token:
        response.set_cookie(key='refresh_token', value=refresh_token, max_age=60 * 60 * 24 * 7,
                            httponly=True, secure=is_secure, samesite=samesite, path='/')
    return response


def apagar_cookies_sessao(response):
    """Apaga os cookies da sessão com os mesmos atributos (path/samesite) usados ao gravá-los."""
    samesite = 'None' if not settings.DEBUG else 'Lax'
    for nome in ('access_token', 'refresh_token'):
        response.delete_cookie(nome, path='/', samesite=samesite)
    return response


def emitir_sessao(user):
    """
    Tokens de uma sessão nova, iguais aos do login normal (com os claims role/email/name).
    Devolve (access, refresh) em texto.
    """
    refresh = CustomTokenObtainPairSerializer.get_token(user)
    return str(refresh.access_token), str(refresh)


def dados_utilizador(user):
    return {
        'id': str(user.id),
        'email': user.email,
        'name': user.name,
        'role': user.role,
        'avatar': user.avatar or None,
        'email_verified': user.email_verified,
        'has_password': user.has_usable_password(),
        'deve_mudar_senha': user.deve_mudar_senha,
    }


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def provincias(request):
    """GET /api/v1/users/provincias/ -> [{valor, nome}] (as 21 províncias de Angola)."""
    from .models import PROVINCIAS
    return Response([{'valor': v, 'nome': n} for v, n in PROVINCIAS])


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with additional user data and rate limiting (10 attempts per minute per IP).
    Sets HttpOnly cookies for cross-domain authentication.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Os tokens vão só nos cookies HttpOnly; o corpo leva apenas o utilizador.
            access_token = response.data.pop('access', None)
            refresh_token = response.data.pop('refresh', None)
            definir_cookies_sessao(response, access_token, refresh_token)

        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom JWT token refresh view that sets HttpOnly cookies.
    Also supports reading refresh token from cookie if not in request body.
    """

    def post(self, request, *args, **kwargs):
        # Sem refresh no corpo, usa o do cookie. Sem nenhum dos dois: 401 "A sessão terminou".
        if not request.data.get('refresh'):
            if not request.COOKIES.get('refresh_token'):
                from rest_framework.exceptions import NotAuthenticated
                raise NotAuthenticated()
            request._full_data = request.data.copy()
            request._full_data['refresh'] = request.COOKIES.get('refresh_token')

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Com ROTATE_REFRESH_TOKENS o refresh antigo vai para a lista negra: o novo tem de
            # ficar no cookie, senão a sessão morre no refresh seguinte. Nada vai no corpo.
            access_token = response.data.pop('access', None)
            refresh_token = response.data.pop('refresh', None)
            definir_cookies_sessao(response, access_token, refresh_token)
            response.data['message'] = 'Sessão renovada.'

        return response


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for user profile management.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def get_avatar_upload_url(request):
    """
    Generate presigned URL for user avatar upload to S3.

    POST /api/v1/users/get-avatar-upload-url/

    Request body:
    {
        "fileName": "profile.jpg",
        "fileType": "image/jpeg"
    }

    Response:
    {
        "message": "URL de upload de avatar gerado com sucesso",
        "data": {
            "uploadUrl": "https://s3.amazonaws.com/...",
            "avatarUrl": "https://cloudfront.net/avatars/..."
        }
    }
    """
    fileName = request.data.get('fileName')
    fileType = request.data.get('fileType')

    if not fileName or not fileType:
        return Response({
            'error': 'Indique o nome e o tipo do ficheiro.',
            'message': 'Indique o nome e o tipo do ficheiro.',
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validate image file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if fileType not in allowed_types:
        return Response({
            'error': 'Este tipo de ficheiro não é aceite. Use JPG, PNG ou WebP.',
            'message': 'Este tipo de ficheiro não é aceite. Use JPG, PNG ou WebP.',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        if not S3_AVAILABLE:
            logger.error('Envio de fotografias: boto3 não está instalado')
            return Response({
                'error': 'O envio de fotografias não está disponível agora.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME]):
            logger.error('Envio de fotografias: configuração S3 incompleta')
            return Response({
                'error': 'O envio de fotografias não está disponível agora.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        # Generate unique filename and S3 key
        file_extension = fileName.split('.')[-1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f'avatars/{request.user.id}/{unique_filename}'

        # Generate presigned URL for PUT operation
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': s3_key,
                'ContentType': fileType,
                'CacheControl': 'max-age=86400'
            },
            ExpiresIn=3600  # 1 hour expiration
        )

        # Generate final avatar URL (using CloudFront if available)
        if getattr(settings, 'AWS_CLOUDFRONT_DOMAIN', ''):
            avatar_url = f"{settings.AWS_CLOUDFRONT_DOMAIN}/avatars/{request.user.id}/{unique_filename}"
        else:
            avatar_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/avatars/{request.user.id}/{unique_filename}"

        return Response({
            'message': 'Pode enviar a fotografia.',
            'data': {
                'uploadUrl': upload_url,
                'avatarUrl': avatar_url
            }
        })

    except Exception:
        logger.exception('Erro ao preparar o envio da fotografia (user=%s)', request.user.pk)
        return Response({
            'error': 'Não foi possível preparar o envio da fotografia. Tente outra vez.'
        }, status=status.HTTP_502_BAD_GATEWAY)


class PasswordChangeView(generics.GenericAPIView):
    """
    POST /api/v1/users/change-password/

    Com palavra-passe:  {current_password, new_password, new_password_confirm}
    Sem palavra-passe (conta criada com o Google, has_password=false): define a primeira
    palavra-passe com {new_password, new_password_confirm}; current_password é ignorado.

    Resposta: {message, has_password: true}. As sessões nos outros dispositivos terminam.
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        definir = not request.user.has_usable_password()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if request.user.deve_mudar_senha:
            request.user.deve_mudar_senha = False
            request.user.save(update_fields=['deve_mudar_senha'])
        # Termina as sessões nos outros dispositivos (refresh tokens na lista negra e tokens de
        # acesso já emitidos sem valor: sessoes_invalidas_antes); esta continua com uma sessão
        # nova, emitida já a seguir e gravada nos cookies.
        actual = request.COOKIES.get('refresh_token') or request.data.get('refresh_token')
        terminar_sessoes(request.user, excepto=actual)
        invalidar_tokens_acesso(request.user)
        access, refresh = _acesso_da_sessao_actual(request.user, actual)

        if definir:
            mensagem = 'Palavra-passe definida. Também pode entrar com o email e esta palavra-passe.'
        else:
            mensagem = 'Palavra-passe mudada. As sessões nos outros dispositivos foram terminadas.'
        resposta = Response({'message': mensagem, 'has_password': True, 'deve_mudar_senha': False})
        return definir_cookies_sessao(resposta, access, refresh)


def _acesso_da_sessao_actual(user, refresh_actual):
    """
    Depois de invalidar os tokens de acesso: (access, None) novo para a sessão actual (o refresh
    dela continua), ou (access, refresh) de uma sessão nova se o pedido não trouxe um refresh
    válido desta conta (p. ex. clientes com o cabeçalho Authorization).
    """
    if refresh_actual:
        try:
            rt = RefreshToken(refresh_actual)
            if str(rt['user_id']) == str(user.pk):
                return str(rt.access_token), None
        except Exception:
            pass
    return emitir_sessao(user)


def invalidar_tokens_acesso(user):
    """
    Os tokens de acesso emitidos antes de agora deixam de valer (ver apps.users.middleware, que
    compara o iat em segundos inteiros: os emitidos neste mesmo segundo ainda valem).
    """
    agora = timezone.now()
    User.objects.filter(pk=user.pk).update(sessoes_invalidas_antes=agora)
    user.sessoes_invalidas_antes = agora
    return agora


def terminar_sessoes(user, excepto=None):
    """Põe na lista negra todos os refresh tokens do utilizador (menos, se indicado, o actual)."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
    jti_actual = None
    if excepto:
        try:
            jti_actual = RefreshToken(excepto)['jti']
        except Exception:
            jti_actual = None
    for t in OutstandingToken.objects.filter(user=user).exclude(jti=jti_actual or ''):
        BlacklistedToken.objects.get_or_create(token=t)


def _confirmar_verdadeiro(valor):
    return valor is True or (isinstance(valor, str) and valor.strip().lower() in ('true', '1', 'sim'))


class ApagarContaView(generics.GenericAPIView):
    """
    POST /api/v1/users/apagar-conta/

    Com palavra-passe (has_password=true):  {"password": "..."}
    Sem palavra-passe (conta do Google, has_password=false):  {"confirmar": true}

    O próprio utilizador apaga a conta. Os dados pessoais são anonimizados e a conta fica
    desactivada (deixa de poder entrar); apagam-se também os códigos enviados por email (têm o
    email original), as moradas, as subscrições push, as preferências e a lista de avisos.
    As opiniões deixam de poder ser mostradas em público. Os pagamentos e recibos ficam
    guardados sem o nome, porque são registos fiscais. Não se pode desfazer.
    Professores não apagam a conta aqui (403 conta_professor): fecham-na com a equipa.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if getattr(user, 'role', None) == 'teacher':
            # Os cursos do professor têm alunos e ganhos por pagar: fecha-se com a equipa.
            from apps.core.exceptions import corpo_erro
            return Response(corpo_erro(
                'Para fechar a conta de professor, fale com a equipa ProEnglish: '
                'os seus cursos têm alunos inscritos.', 'conta_professor'),
                status=status.HTTP_403_FORBIDDEN)
        if not user.has_usable_password() and not _confirmar_verdadeiro(request.data.get('confirmar')):
            return Response({'error': 'Confirme que quer apagar a conta.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.has_usable_password() and not user.check_password(request.data.get('password') or ''):
            return Response({'error': 'A palavra-passe não está certa.'}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(user, 'role', None) == 'admin' or user.is_superuser:
            return Response({'error': 'As contas de administração não se apagam aqui.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.db import transaction
        from apps.core.models import Address
        from .models import (Notification, PreferenciasAvisos, PushSubscription, UserFeedback)

        terminar_sessoes(user)
        with transaction.atomic():
            # Dados ligados à conta que guardam o email original ou dados pessoais
            EmailVerification.objects.filter(user=user).delete()
            PushSubscription.objects.filter(user=user).delete()
            PreferenciasAvisos.objects.filter(user=user).delete()
            NotificationSettings.objects.filter(user=user).delete()
            Notification.objects.filter(user=user).delete()
            ids_moradas = list(UserAddress.objects.filter(user=user).values_list('address_id', flat=True))
            UserAddress.objects.filter(user=user).delete()
            Address.objects.filter(id__in=ids_moradas).delete()
            UserFeedback.objects.filter(user=user).update(allow_public=False, allow_contact=False)

            anonimo = f'apagado-{user.id.hex}'
            user.name = 'Conta apagada'
            user.first_name = ''
            user.last_name = ''
            user.email = f'{anonimo}@apagado.invalid'
            user.username = anonimo
            user.phone = ''
            user.avatar = ''
            user.preferences = {}
            user.google_id = None
            user.email_verification_token = ''
            user.reset_password_token = ''
            user.reset_password_expires = None
            user.is_active = False
            user.set_unusable_password()
            user.save()

        # Gravações dos exames orais (fase 6): apagadas com a conta (no Vapi e o URL aqui).
        try:
            from apps.practice.conversa.exame import apagar_gravacoes_do_aluno
            apagar_gravacoes_do_aluno(user)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Falha ao apagar as gravações dos exames da conta %s', user.pk)

        response = Response({'message': 'A sua conta foi apagada.'})
        return apagar_cookies_sessao(response)


class UserAddressListCreateView(generics.ListCreateAPIView):
    """
    View for listing and creating user addresses.
    """
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user).order_by('address_type', '-is_default', 'created_at')


class UserAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for managing individual user addresses.
    """
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user).order_by('address_type', '-is_default', 'created_at')


class NotificationSettingsView(generics.RetrieveUpdateAPIView):
    """
    View for notification settings management.
    """
    serializer_class = NotificationSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        settings, created = NotificationSettings.objects.get_or_create(
            user=self.request.user
        )
        return settings


@method_decorator(ratelimit(key='ip', rate='3/m', method='POST', block=True), name='post')
class PasswordResetRequestView(generics.GenericAPIView):
    """
    View for password reset request with rate limiting (3 requests per minute per IP).
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Só para o email actual da conta e já confirmado (nunca para um email por confirmar,
        # p. ex. um email novo pedido pela administração, que fica em email_pendente).
        user = User.objects.filter(
            email__iexact=serializer.validated_data['email'].strip(),
            is_active=True,
            email_verified=True,
        ).first()
        if user:  # Don't reveal if email exists
            # Código de recuperar a palavra-passe (só serve em password-reset-confirm/).
            # create_verification_code invalida os códigos de recuperação anteriores.
            verification = EmailVerificationService.create_verification_code(
                user, user.email, finalidade=EmailVerification.FINALIDADE_RECUPERAR)
            EmailVerificationService.send_password_reset_email(verification)
        
        return Response({
            'message': 'Se houver uma conta com este email, enviámos um código para criar uma palavra-passe nova.'
        })


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Nova palavra-passe com o código de 6 dígitos enviado por email.

    O código é o último ainda não usado desse email. Cada código errado conta como tentativa
    (no limite de max_attempts o código deixa de servir), para não se adivinhar por força bruta.
    Depois da mudança, as outras sessões abertas terminam.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as ErroValidacao
        from .models import EmailVerification

        email = (request.data.get('email') or '').strip().lower()
        code = (request.data.get('code') or '').strip()
        new_password = request.data.get('newPassword') or request.data.get('new_password') or ''

        if not email or not code or not new_password:
            return Response({'error': 'Indique o email, o código e a nova palavra-passe.'},
                            status=status.HTTP_400_BAD_REQUEST)

        invalido = Response({'error': 'O código não está certo ou já expirou. Peça um código novo.'},
                            status=status.HTTP_400_BAD_REQUEST)
        verification = (EmailVerification.objects
                        .filter(email__iexact=email, is_used=False, code__isnull=False,
                                finalidade=EmailVerification.FINALIDADE_RECUPERAR)
                        .select_related('user').order_by('-created_at').first())
        if not verification or verification.is_expired() or verification.attempts >= verification.max_attempts:
            return invalido
        if verification.code != code:
            verification.increment_attempts()
            return invalido

        user = verification.user
        if not user.is_active:
            return invalido
        try:
            validate_password(new_password, user=user)
        except ErroValidacao as e:
            return Response({'error': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.deve_mudar_senha = False
        user.save(update_fields=['password', 'deve_mudar_senha'])
        verification.is_used = True
        verification.save(update_fields=['is_used'])
        terminar_sessoes(user)
        invalidar_tokens_acesso(user)
        return Response({'message': 'A palavra-passe foi alterada. Já pode entrar com a nova.'})


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class ConfirmarEmailNovoView(generics.GenericAPIView):
    """
    POST /api/v1/users/confirmar-email-novo/ {email, code}

    Confirma o email novo pedido pela administração (User.email_pendente) com o código enviado
    para ele. Só então o email da conta muda (e fica confirmado). Não abre sessão: a pessoa
    entra depois com o email novo e a palavra-passe de sempre.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from apps.core.exceptions import corpo_erro
        from .admin_api import servicos as sv
        user, erro = sv.confirmar_mudanca_email(request.data.get('email'), request.data.get('code'))
        if erro:
            mensagem, code = erro
            return Response(corpo_erro(mensagem, code), status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': f'Email confirmado. A partir de agora entre com {user.email}.',
                         'email': user.email})


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class EmailVerificationView(generics.GenericAPIView):
    """
    View for email verification with 6-digit code and rate limiting (10 attempts per minute per IP).
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        
        if not email or not code:
            return Response({
                'error': 'Email e código são obrigatórios.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the code
        result = EmailVerificationService.verify_code(email, code)
        
        if result['success']:
            user = result['user']
            access, refresh = emitir_sessao(user)
            
            # Send welcome email
            try:
                EmailVerificationService.send_welcome_email(user)
            except Exception:
                # O email de boas-vindas não pode impedir a confirmação
                logger.exception('Erro ao enviar o email de boas-vindas (user=%s)', user.pk)
            
            response = Response({
                'message': 'Email verificado com sucesso! Bem-vindo(a) ao ProEnglish!',
                'user': dados_utilizador(user),
            })
            # A sessão vai nos cookies HttpOnly, como no login (antes só ia no corpo e a pessoa
            # ficava sem sessão logo a seguir a confirmar o email).
            definir_cookies_sessao(response, access, refresh)
            return response
        else:
            return Response({
                'error': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)


ESPERA_REENVIO_SEGUNDOS = 60


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def resend_verification_email(request):
    """
    Envia outro código de verificação.

    A resposta é a mesma quer o email tenha conta ou não (não revela que emails existem),
    e há uma espera de ESPERA_REENVIO_SEGUNDOS entre códigos para o mesmo email.
    """
    from .models import EmailVerification, User as Utilizador

    email = (request.data.get('email') or '').strip().lower()
    if not email:
        return Response({'error': 'Indique o email.'}, status=status.HTTP_400_BAD_REQUEST)

    resposta = {'message': 'Se houver uma conta por confirmar com este email, enviámos um código novo.',
                'aguardar_segundos': ESPERA_REENVIO_SEGUNDOS}
    ultimo = EmailVerification.objects.filter(email__iexact=email).order_by('-created_at').first()
    if ultimo:
        passaram = (timezone.now() - ultimo.created_at).total_seconds()
        if passaram < ESPERA_REENVIO_SEGUNDOS:
            falta = int(ESPERA_REENVIO_SEGUNDOS - passaram) + 1
            return Response({'error': f'Pode pedir outro código daqui a {falta} segundos.', 'aguardar_segundos': falta},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

    user = Utilizador.objects.filter(email__iexact=email, is_active=True).first()
    if user and not user.email_verified:
        resultado = EmailVerificationService.resend_verification_code(user.email)
        if not resultado['success']:
            return Response({'error': 'Não conseguimos enviar o email. Tente outra vez daqui a pouco.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(resposta)


class GoogleOAuthURLView(generics.GenericAPIView):
    """
    GET/POST /api/v1/users/oauth/google/url/

    Devolve {auth_url, state}. O `state` é um valor assinado pelo servidor (válido 10 minutos)
    que o Google devolve em `?state=` no endereço de volta; o cliente envia-o tal e qual em
    oauth/google/login/ e o servidor confirma que o pedido saiu daqui. O redirect_uri é sempre o
    configurado no servidor (o mesmo usado na troca do código).
    """
    serializer_class = GoogleOAuthURLSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return self._generate_auth_url(request)

    def post(self, request):
        return self._generate_auth_url(request)

    def _generate_auth_url(self, request):
        from .services import GoogleOAuthErro
        oauth_service = GoogleOAuthService()
        try:
            state = oauth_service.criar_state()
            auth_url = oauth_service.generate_auth_url(state=state)
        except GoogleOAuthErro as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'error': 'A entrada com o Google não está disponível agora.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'auth_url': auth_url, 'state': state})


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class GoogleOAuthLoginView(generics.GenericAPIView):
    """
    POST /api/v1/users/oauth/google/login/  {code, state?}

    Só aceita o `code` que o Google devolve (trocado no servidor com o nosso client id/secret)
    ou um `id_token` emitido para o nosso client id. `access_token` é recusado.
    """
    serializer_class = GoogleOAuthSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from .services import GoogleOAuthErro

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Pedido inválido para entrar com o Google.'},
                            status=status.HTTP_400_BAD_REQUEST)

        oauth_service = GoogleOAuthService()
        try:
            user = oauth_service.authenticate_user(**serializer.validated_data)
        except GoogleOAuthErro as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Erro na entrada com o Google')
            return Response({'error': 'Não foi possível entrar com o Google. Tente outra vez.'},
                            status=status.HTTP_400_BAD_REQUEST)

        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])

        access, refresh = emitir_sessao(user)
        response = Response({
            'message': 'Entrou com o Google.',
            'user': {**dados_utilizador(user), 'google_id': user.google_id},
        })
        definir_cookies_sessao(response, access, refresh)
        return response


class LogoutView(generics.GenericAPIView):
    """
    POST /api/v1/users/logout/

    Funciona mesmo com o access token expirado (sem autenticação): põe na lista negra o
    refresh token do cookie (ou do corpo, `refresh_token`/`refresh`) se for válido e apaga
    sempre os dois cookies.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = (request.COOKIES.get('refresh_token')
                         or request.data.get('refresh_token') or request.data.get('refresh'))
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass  # inválido, expirado ou já na lista negra: nada a fazer
        response = Response({'message': 'Saiu da sua conta.'})
        return apagar_cookies_sessao(response)


# ============================================================================
# ADMINISTRAÇÃO (rotas antigas users/admin/users/...)
#
# Mantidas para compatibilidade; as novas estão em /api/v1/admin/utilizadores/ (apps.users.admin_api).
# Usam as mesmas regras: EAdministrador, RegistoAdmin, sessões terminadas ao mudar o papel ou
# desactivar, confirmação do email novo, apagar de vez só por superutilizadores.
# ============================================================================

def _utilizador_legado(user):
    return {
        'id': str(user.id),
        'name': user.name,
        'email': user.email,
        'phone': user.phone or '',
        'role': user.role,
        'is_active': user.is_active,
        'email_verified': user.email_verified,
        'date_joined': user.date_joined.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'avatar': user.avatar or None,
    }


def _erro_legado(mensagem, code, estado):
    from apps.core.exceptions import corpo_erro
    return Response(corpo_erro(mensagem, code), status=estado)


def _inteiro_param(valor, defeito, minimo=1, maximo=None):
    try:
        n = max(minimo, int(valor))
    except (TypeError, ValueError):
        return defeito
    return min(n, maximo) if maximo else n


class _AdminLegado(APIView):
    permission_classes = [EAdministrador]

    def _obter(self, id):
        user = User.objects.filter(pk=id).first()
        if user is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('Não encontrámos este utilizador.')
        return user


class AdminUsersListView(_AdminLegado):
    """GET users/admin/users/?page=&limit=&search=&role=&status=active|inactive"""

    def get(self, request, *args, **kwargs):
        page = _inteiro_param(request.query_params.get('page'), 1)
        limit = _inteiro_param(request.query_params.get('limit'), 20, maximo=100)
        search = request.query_params.get('search', '')
        role = request.query_params.get('role', '')
        status_filter = request.query_params.get('status', '')

        # Sem as contas que o próprio apagou (anonimizadas), como em /api/v1/admin/utilizadores/.
        queryset = User.objects.exclude(email__endswith='@apagado.invalid').order_by('-date_joined')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(email__icontains=search)
                | models.Q(phone__icontains=search))
        if role and role != 'all':
            queryset = queryset.filter(role=role)
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        return Response({
            'users': [_utilizador_legado(u) for u in queryset[start:end]],
            'pagination': {
                'page': page, 'limit': limit, 'total': total,
                'total_pages': (total + limit - 1) // limit,
                'has_next': end < total, 'has_prev': page > 1,
            },
            'stats': {
                'total_users': total,
                'active_users': queryset.filter(is_active=True).count(),
                'student_users': queryset.filter(role='student').count(),
                'teacher_users': queryset.filter(role='teacher').count(),
                'admin_users': queryset.filter(role='admin').count(),
                'verified_users': queryset.filter(email_verified=True).count(),
            },
        })


class AdminUserDetailView(_AdminLegado):
    def get(self, request, id):
        user = self._obter(id)
        return Response({'user': {**_utilizador_legado(user), 'google_id': user.google_id}})


class AdminUserUpdateView(_AdminLegado):
    """
    PATCH {name, email, phone}. A conta de outro administrador/superutilizador só um
    superutilizador a altera. Email novo: fica pendente (email_pendente) até ser confirmado com
    o código enviado para ele; até lá o email actual continua a valer.
    """

    def patch(self, request, id):
        from .admin_api import servicos as sv
        user = self._obter(id)
        recusa = sv.recusa_editar(request.user, user)
        if recusa:
            return recusa
        name = request.data.get('name')
        email = request.data.get('email')
        phone = request.data.get('phone')
        if not isinstance(name, str) or not name.strip():
            return _erro_legado('Indique o nome.', 'validation_error', status.HTTP_400_BAD_REQUEST)
        if not isinstance(email, str) or not email.strip():
            return _erro_legado('Indique o email.', 'validation_error', status.HTTP_400_BAD_REQUEST)
        email = email.strip().lower()
        email_mudou = email != user.email.lower()
        if email_mudou:
            from django.core.exceptions import ValidationError as ErroDjango
            from django.core.validators import validate_email
            try:
                validate_email(email)
            except ErroDjango:
                return _erro_legado('Escreva um email válido.', 'validation_error', status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
                return _erro_legado('Já existe outra conta com este email.', 'validation_error',
                                    status.HTTP_400_BAD_REQUEST)
        antes = {'name': user.name, 'email': user.email, 'phone': user.phone}
        user.name = name.strip()
        user.phone = phone.strip() if isinstance(phone, str) and phone.strip() else None
        user.save()
        sv.registar(request, 'editar_utilizador', user, detalhes={
            'antes': antes, 'depois': {'name': user.name, 'email': user.email, 'phone': user.phone},
            **({'email_pendente': email} if email_mudou else {})})
        mensagem = 'Utilizador actualizado.'
        if email_mudou:
            enviado, _ = sv.pedir_mudanca_email(user, email, request)
            mensagem = (f'Utilizador actualizado. Enviámos um código para {email}: o email só muda quando for '
                        'confirmado.' if enviado else
                        f'Utilizador actualizado, mas não conseguimos enviar o código para {email}. O email não mudou.')
        return Response({'message': mensagem,
                         'user': {**_utilizador_legado(user), 'email_pendente': user.email_pendente or None}})


class AdminUserRoleUpdateView(_AdminLegado):
    """PATCH {role}. Nunca o próprio (400); de/para admin só superutilizador; termina as sessões."""

    def patch(self, request, id):
        from .admin_api import servicos as sv
        user = self._obter(id)
        new_role = request.data.get('role')
        valid_roles = ['student', 'teacher', 'admin']
        if not new_role or new_role not in valid_roles:
            return _erro_legado(f'Papel inválido. Use um destes: {", ".join(valid_roles)}.', 'validation_error',
                                status.HTTP_400_BAD_REQUEST)
        if user.id == request.user.id:
            return _erro_legado('Não pode mudar o seu próprio perfil.', 'propria_conta', status.HTTP_400_BAD_REQUEST)
        if (user.role == 'admin' or new_role == 'admin' or user.is_superuser) and not request.user.is_superuser:
            return _erro_legado('Só um superutilizador pode dar ou tirar o papel de administrador.',
                                'alvo_administrador', status.HTTP_403_FORBIDDEN)
        old_role = user.role
        if old_role != new_role:
            user.role = new_role
            user.save(update_fields=['role', 'updated_at'])
            sv.terminar_todas_sessoes(user)
            if new_role == 'teacher':
                sv.garantir_perfil_professor(user)
            sv.registar(request, 'editar_utilizador', user, detalhes={'alterado': {'papel': [old_role, new_role]}})
        return Response({
            'message': f'Papel mudado de {old_role} para {new_role}.',
            'user': {'id': str(user.id), 'name': user.name, 'email': user.email, 'role': user.role,
                     'is_active': user.is_active},
        })


class AdminUserToggleStatusView(_AdminLegado):
    """PATCH: desactivar = suspender (motivo "outro"); activar = reactivar."""

    def patch(self, request, id):
        from .admin_api import servicos as sv
        user = self._obter(id)
        if user.email.endswith('@apagado.invalid'):
            return _erro_legado('Esta conta foi apagada pelo próprio utilizador.', 'conta_apagada',
                                status.HTTP_409_CONFLICT)
        if user.id == request.user.id:
            return _erro_legado('Não pode desactivar a sua própria conta.', 'propria_conta',
                                status.HTTP_400_BAD_REQUEST)
        if sv.e_admin_alvo(user) and not request.user.is_superuser:
            return _erro_legado('Só um superutilizador pode fazer isto a outro administrador.',
                                'alvo_administrador', status.HTTP_403_FORBIDDEN)
        if user.is_active:
            sv.suspender(user, request.user, 'outro', '', False, request)
        else:
            sv.reactivar(user, request.user, request)
        user.refresh_from_db()
        action = 'activado' if user.is_active else 'desactivado'
        return Response({
            'message': f'Utilizador {action}.',
            'user': {'id': str(user.id), 'name': user.name, 'email': user.email, 'role': user.role,
                     'is_active': user.is_active},
        })


class AdminUserDeleteView(_AdminLegado):
    """DELETE: apagar de vez (só superutilizador; contas sem pagamentos, certificados nem cursos)."""

    def delete(self, request, id):
        from .admin_api import servicos as sv
        return sv.apagar_definitivamente(request, self._obter(id))


# ============================================================================
# FEEDBACK VIEWS
# ============================================================================

class FeedbackStatusView(generics.GenericAPIView):
    """
    Se o aluno deve ver agora o pedido de opinião, e com que frase.

    GET /api/v1/users/feedback/status/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import UserEngagementMetrics
        from . import opiniao

        metrics, _ = UserEngagementMetrics.objects.get_or_create(user=request.user)
        mostrar, chave, trigger, frase, m = opiniao.pedido(request.user, metrics)
        opiniao.sincronizar(metrics, m)
        return Response({
            'should_show_prompt': mostrar,
            'trigger': trigger,
            'chave': chave,
            'frase': frase,
            'last_feedback_at': metrics.last_feedback_at,
            'total_feedbacks_given': metrics.total_feedbacks_given,
            'engagement_summary': {
                'lessons_completed': m['licoes'],
                'courses_completed': m['cursos'],
                'ai_sessions': m['conversas'],
                'days_active': m['dias'],
                'current_streak': m['sequencia'],
            },
        })


class SubmitFeedbackView(generics.CreateAPIView):
    """
    Submit user feedback.

    POST /api/users/feedback/submit/
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [FeedbackSubmitThrottle]

    def post(self, request):
        from .models import UserFeedback, UserEngagementMetrics, FeedbackPromptLog
        from .serializers import SubmitFeedbackSerializer, MinhaOpiniaoSerializer
        from django.utils import timezone

        serializer = SubmitFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create feedback
        feedback = UserFeedback.objects.create(
            user=request.user,
            **serializer.validated_data
        )

        # Update engagement metrics
        metrics, _ = UserEngagementMetrics.objects.get_or_create(
            user=request.user
        )
        metrics.total_feedbacks_given += 1
        metrics.last_feedback_at = timezone.now()
        metrics.save()

        # Log the feedback completion if there was a prompt
        trigger = serializer.validated_data.get('trigger', 'manual')
        if trigger != 'manual':
            FeedbackPromptLog.objects.create(
                user=request.user,
                trigger=trigger,
                status='completed',
                feedback=feedback,
                context_data=serializer.validated_data.get('context_data', {})
            )

        return Response({
            'message': 'Obrigado pela sua opinião.',
            'feedback': MinhaOpiniaoSerializer(feedback).data
        }, status=status.HTTP_201_CREATED)


class DismissFeedbackPromptView(generics.GenericAPIView):
    """
    Dismiss a feedback prompt without submitting feedback.

    POST /api/users/feedback/dismiss/
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [FeedbackDismissThrottle]

    def post(self, request):
        from .models import UserEngagementMetrics, FeedbackPromptLog
        from django.utils import timezone
        import json

        from .models import UserFeedback

        trigger = request.data.get('trigger') or 'prompt'
        validos = {c for c, _ in UserFeedback.TRIGGER_CHOICES}
        if not isinstance(trigger, str) or trigger not in validos:
            return Response({'error': 'Motivo do pedido de opinião inválido.',
                             'message': 'Motivo do pedido de opinião inválido.',
                             'code': 'validation_error',
                             'details': {'trigger': [f'Use um destes: {", ".join(sorted(validos))}.']}},
                            status=status.HTTP_400_BAD_REQUEST)
        action = request.data.get('action', 'dismissed')  # 'dismissed' or 'skipped'

        # Validate action
        if action not in ('dismissed', 'skipped'):
            action = 'dismissed'

        # Validate and limit context_data size
        context_data = request.data.get('context_data', {})
        if not isinstance(context_data, dict):
            context_data = {}
        # Limit context_data to 10KB
        try:
            if len(json.dumps(context_data)) > 10240:
                context_data = {'erro': 'context_data demasiado grande'}
        except (TypeError, ValueError):
            context_data = {}

        # Update last prompt time
        metrics, _ = UserEngagementMetrics.objects.get_or_create(
            user=request.user
        )
        metrics.last_prompt_at = timezone.now()
        metrics.save()

        # Log the dismissal
        FeedbackPromptLog.objects.create(
            user=request.user,
            trigger=trigger,
            status=action,
            context_data=context_data
        )

        return Response({
            'message': 'Pedido de opinião fechado.',
            'next_prompt_available_in': '3 dias'
        })


class UserFeedbackListView(generics.ListAPIView):
    """
    List user's own feedback submissions.

    GET /api/users/feedback/my-feedback/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import UserFeedback
        from .serializers import MinhaOpiniaoSerializer

        feedbacks = UserFeedback.objects.filter(
            user=request.user
        ).order_by('-created_at')[:20]

        return Response({
            'count': feedbacks.count(),
            'feedbacks': MinhaOpiniaoSerializer(feedbacks, many=True).data
        })


class AdminFeedbackListView(generics.ListAPIView):
    """
    Admin view to list all feedbacks with filters.

    GET /api/users/feedback/admin/list/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from .models import UserFeedback
        from .serializers import UserFeedbackSerializer

        queryset = UserFeedback.objects.all().select_related('user').order_by('-created_at')

        # Apply filters
        feedback_type = request.query_params.get('type')
        if feedback_type:
            queryset = queryset.filter(feedback_type=feedback_type)

        rating = request.query_params.get('rating')
        if rating:
            try:
                queryset = queryset.filter(rating=int(rating))
            except (TypeError, ValueError):
                from apps.core.exceptions import corpo_erro
                return Response(corpo_erro('A nota tem de ser um número de 1 a 5.', 'validation_error',
                                           {'rating': ['A nota tem de ser um número de 1 a 5.']}),
                                status=status.HTTP_400_BAD_REQUEST)

        allow_public = request.query_params.get('allow_public')
        if allow_public:
            queryset = queryset.filter(allow_public=allow_public.lower() == 'true')

        is_reviewed = request.query_params.get('is_reviewed')
        if is_reviewed:
            queryset = queryset.filter(is_reviewed=is_reviewed.lower() == 'true')

        # Pagination
        limit = _inteiro_param(request.query_params.get('limit'), 50, maximo=200)
        offset = _inteiro_param(request.query_params.get('offset'), 0, minimo=0)

        total = queryset.count()
        feedbacks = queryset[offset:offset + limit]

        return Response({
            'total': total,
            'limit': limit,
            'offset': offset,
            'feedbacks': UserFeedbackSerializer(feedbacks, many=True).data
        })


# Área profissional (preferences.area = categoria dos cursos) como aparece no site.
AREAS_PT = {
    'Industry English': 'Petróleo e Gás', 'Financial English': 'Banca', 'Business English': 'Negócios',
    'Medical English': 'Saúde', 'Legal English': 'Direito', 'Technical English': 'Tecnologia',
}


class PublicTestimonialsView(generics.ListAPIView):
    """
    Get public testimonials for landing page.

    GET /api/users/feedback/testimonials/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .models import UserFeedback

        # Só as aprovadas pela administração, com autorização do aluno e marcadas para mostrar,
        # pela ordem escolhida na administração (GET/PATCH /api/v1/admin/testemunhos/).
        from .admin_api.opinioes import area_de, no_site_qs, nome_curto
        # Só as aprovadas pela administração, com autorização do aluno, marcadas para mostrar e
        # de contas activas, pela ordem escolhida na administração (/api/v1/admin/testemunhos/).
        # O nome é o mesmo da pré-visualização da administração (nome_curto).
        feedbacks = no_site_qs().select_related('user').order_by('ordem', '-created_at')[:12]
        testimonials = []
        for feedback in feedbacks:
            # Sem o UUID interno: índice sequencial.
            testimonials.append({
                'id': len(testimonials) + 1,
                'name': nome_curto(feedback.user.name),
                'rating': feedback.rating,
                'comment': feedback.comment,
                'area': area_de(feedback.user),
                'feedback_type': feedback.feedback_type,
                'created_at': feedback.created_at
            })

        return Response({
            'count': len(testimonials),
            'testimonials': testimonials
        })


class AdminFeedbackUpdateView(generics.UpdateAPIView):
    """
    Admin view to update feedback (mark as reviewed, add admin notes).

    PATCH /api/users/feedback/admin/<uuid:id>/

    Note: Admin can only REMOVE allow_public (set to False), not add it.
    Only the user can grant public permission.
    """
    permission_classes = [IsAdminUser]

    def patch(self, request, id):
        from .models import UserFeedback
        from .serializers import UserFeedbackSerializer
        import logging

        logger = logging.getLogger(__name__)

        try:
            feedback = UserFeedback.objects.select_related('user').get(id=id)
        except UserFeedback.DoesNotExist:
            return Response({
                'error': 'Não encontrámos esta opinião.'
            }, status=status.HTTP_404_NOT_FOUND)

        changes = []

        # Update allowed fields
        if 'is_reviewed' in request.data:
            old_value = feedback.is_reviewed
            feedback.is_reviewed = bool(request.data['is_reviewed'])
            if old_value != feedback.is_reviewed:
                changes.append(f"is_reviewed: {old_value} -> {feedback.is_reviewed}")
                # Rota antiga: revista = aprovada (fica no fim da ordem); tirar a revisão volta a "por rever".
                if feedback.is_reviewed:
                    from .admin_api.opinioes import aprovar
                    aprovar(feedback)
                else:
                    feedback.estado = UserFeedback.POR_REVER

        if 'admin_notes' in request.data:
            from .admin_api.opinioes import NOTA_INTERNA_MAX
            notes = str(request.data['admin_notes'] or '')
            if len(notes) > NOTA_INTERNA_MAX:
                from apps.core.exceptions import corpo_erro
                msg = f'A nota interna tem no máximo {NOTA_INTERNA_MAX} caracteres.'
                return Response(corpo_erro(msg, 'validation_error', {'admin_notes': [msg]}),
                                status=status.HTTP_400_BAD_REQUEST)
            if feedback.admin_notes != notes:
                changes.append("admin_notes updated")
                feedback.admin_notes = notes

        # SECURITY: Admin can only REMOVE public permission, not ADD it
        # This protects user privacy - only users can consent to public display
        if 'allow_public' in request.data:
            new_value = bool(request.data['allow_public'])
            if feedback.allow_public and not new_value:
                # Admin is removing public permission - allowed
                feedback.allow_public = False
                changes.append("allow_public: True -> False (removed by admin)")
            elif not feedback.allow_public and new_value:
                # Admin trying to add public permission - NOT allowed
                return Response({
                    'error': 'Não é possível tornar pública sem autorização do aluno. Só o próprio pode autorizar a publicação da sua opinião.'
                }, status=status.HTTP_403_FORBIDDEN)

        feedback.save()

        # Log admin action for audit
        if changes:
            from .admin_api.servicos import registar
            registar(request, 'opiniao', feedback, alvo_tipo='opiniao', detalhes={'alteracoes': changes})

        return Response({
            'message': 'Opinião actualizada.',
            'feedback': UserFeedbackSerializer(feedback).data
        })


class AdminFeedbackStatsView(generics.GenericAPIView):
    """
    Admin view to get feedback statistics.

    GET /api/users/feedback/admin/stats/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from .models import UserFeedback
        from django.db.models import Avg, Count

        # Get total counts
        total = UserFeedback.objects.count()
        reviewed = UserFeedback.objects.filter(is_reviewed=True).count()
        pending_review = UserFeedback.objects.filter(is_reviewed=False).count()
        public_testimonials = UserFeedback.objects.filter(allow_public=True).count()

        # Get average rating
        avg_rating = UserFeedback.objects.filter(rating__isnull=False).aggregate(
            avg=Avg('rating')
        )['avg'] or 0

        # Get counts by type
        by_type = UserFeedback.objects.values('feedback_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Get counts by rating
        by_rating = UserFeedback.objects.filter(rating__isnull=False).values('rating').annotate(
            count=Count('id')
        ).order_by('rating')

        # Get counts by trigger
        by_trigger = UserFeedback.objects.values('trigger').annotate(
            count=Count('id')
        ).order_by('-count')

        # Recent feedbacks (last 7 days)
        from django.utils import timezone
        from datetime import timedelta
        recent_date = timezone.now() - timedelta(days=7)
        recent_count = UserFeedback.objects.filter(created_at__gte=recent_date).count()

        return Response({
            'total': total,
            'reviewed': reviewed,
            'pending_review': pending_review,
            'public_testimonials': public_testimonials,
            'average_rating': round(avg_rating, 2),
            'recent_count': recent_count,
            'by_type': list(by_type),
            'by_rating': list(by_rating),
            'by_trigger': list(by_trigger),
        })