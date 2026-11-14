"""
Email service for user verification and notifications.
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from .models import EmailVerification

logger = logging.getLogger(__name__)


def _link(caminho, **params):
    """Endereço do site (FRONTEND_URL) com os parâmetros codificados (ex.: o email com '+')."""
    base = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    url = f'{base}{caminho}'
    if params:
        url = f'{url}?{urlencode(params)}'
    return url


def _contexto_base(user, email):
    return {
        'user_name': (getattr(user, 'name', '') or '').strip(),
        'user_email': email,
        'current_year': timezone.now().year,
        'frontend_url': _link(''),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', '') or 'suporte@proenglish.ao',
    }


def _enviar(assunto, template, context, destino):
    """Envia o email (HTML + texto). Devolve True/False; nunca regista o conteúdo (tem códigos)."""
    try:
        html = render_to_string(template, context)
        texto = strip_tags(html)
        msg = EmailMultiAlternatives(subject=assunto, body=texto,
                                     from_email=settings.DEFAULT_FROM_EMAIL, to=[destino])
        msg.attach_alternative(html, 'text/html')
        msg.send()
        logger.debug('Email "%s" enviado (%s)', assunto, template)
        return True
    except Exception:
        logger.exception('Falha ao enviar o email "%s" (%s)', assunto, template)
        return False


class EmailVerificationService:
    """Service for handling email verification codes."""
    
    @staticmethod
    def generate_verification_code():
        """Generate a 6-digit verification code."""
        return f'{secrets.randbelow(900000) + 100000}'
    
    @staticmethod
    def create_verification_code(user, email=None, finalidade=EmailVerification.FINALIDADE_VERIFICAR):
        """
        Create a new verification code for a user.
        
        Args:
            user: User instance
            email: Email address (defaults to user.email)
            
        Returns:
            EmailVerification instance
        """
        if email is None:
            email = user.email
        email = email.strip().lower()

        # Invalidate any existing codes with the same purpose for this user/email
        EmailVerification.objects.filter(
            user=user,
            email__iexact=email,
            finalidade=finalidade,
            is_used=False
        ).update(is_used=True)
        
        # Generate new code
        code = EmailVerificationService.generate_verification_code()
        expires_at = timezone.now() + timedelta(minutes=30)  # 30 minutes expiry
        
        # Create verification record
        verification = EmailVerification.objects.create(
            user=user,
            code=code,
            email=email,
            expires_at=expires_at,
            finalidade=finalidade,
        )
        
        return verification
    
    @staticmethod
    def send_verification_email(verification):
        """
        Envia o código de confirmação do email. Devolve True se o email saiu.
        O código nunca vai para os registos (logs).
        """
        context = {
            **_contexto_base(verification.user, verification.email),
            'verification_code': verification.code,
            'verification_url': _link('/verify-email', email=verification.email),
        }
        return _enviar('Confirme o seu email - ProEnglish', 'emails/email_verification.html',
                       context, verification.email)

    CODIGO_INVALIDO = 'O código não está certo ou já expirou. Peça um código novo.'

    @staticmethod
    def verify_code(email, code):
        """
        Confirma o email com o código de 6 dígitos.

        Só servem códigos de confirmação de email (nunca os de recuperar a palavra-passe), e só
        o último ainda não usado desse email. Um código errado conta como tentativa nesse código
        (no limite de max_attempts deixa de servir). Uma conta já confirmada não volta a ser
        "confirmada" (antes isso devolvia uma sessão a quem tivesse um código qualquer).
        A mensagem de erro é sempre a mesma, para não revelar que contas existem.

        Returns:
            dict: {'success', 'error', 'user'}
        """
        invalido = {'success': False, 'error': EmailVerificationService.CODIGO_INVALIDO, 'user': None}
        email = (email or '').strip().lower()
        code = str(code or '').strip()
        if not email or not code:
            return invalido
        try:
            verification = (EmailVerification.objects
                            .filter(email__iexact=email, finalidade=EmailVerification.FINALIDADE_VERIFICAR,
                                    is_used=False)
                            .select_related('user').order_by('-created_at').first())
            if not verification or verification.is_expired() or verification.attempts >= verification.max_attempts:
                return invalido
            user = verification.user
            if user.email_verified or not user.is_active:
                return invalido
            if verification.code != code:
                verification.increment_attempts()
                return invalido

            verification.is_used = True
            verification.save(update_fields=['is_used'])
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            return {'success': True, 'error': None, 'user': user}
        except Exception:
            return {'success': False, 'error': 'Ocorreu um erro. Tente outra vez.', 'user': None}
    
    @staticmethod
    def resend_verification_code(email):
        """
        Resend verification code for an email.
        
        Args:
            email: Email address
            
        Returns:
            dict: Result with success status
        """
        try:
            # Find user by email
            from .models import User
            user = User.objects.filter(email__iexact=(email or '').strip()).first()
            
            if not user:
                return {
                    'success': False,
                    'error': 'Email não encontrado'
                }
            
            if user.email_verified:
                return {
                    'success': False,
                    'error': 'Este email já está confirmado.'
                }
            
            # Create new verification code
            verification = EmailVerificationService.create_verification_code(user, user.email)
            
            # Send email
            if EmailVerificationService.send_verification_email(verification):
                return {
                    'success': True,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'error': 'Não conseguimos enviar o email.'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': 'Ocorreu um erro. Tente outra vez.'
            }
    
    @staticmethod
    def send_welcome_email(user):
        """Email de boas-vindas depois de confirmar o email. Devolve True se o email saiu."""
        context = {
            **_contexto_base(user, user.email),
            'platform_url': _link('/user/dashboard'),
            'profile_url': _link('/user/settings'),
        }
        return _enviar('Bem-vindo(a) ao ProEnglish', 'emails/welcome_email.html', context, user.email)

    @staticmethod
    def send_password_reset_email(verification):
        """Código para criar uma palavra-passe nova. Devolve True se o email saiu."""
        context = {
            **_contexto_base(verification.user, verification.email),
            'verification_code': verification.code,
            # A página do site lê ?email= e mostra os campos do código e da palavra-passe nova.
            'verification_url': _link('/forgot-password', email=verification.email),
        }
        return _enviar('Criar uma palavra-passe nova - ProEnglish', 'emails/password_reset.html',
                       context, verification.email)
