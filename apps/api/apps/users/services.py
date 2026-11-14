"""
Services for user authentication and OAuth.
"""

import requests
import secrets
import logging
from typing import Dict, Any
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

User = get_user_model()
logger = logging.getLogger(__name__)


class GoogleOAuthErro(Exception):
    """Erro da entrada com o Google; a mensagem (pt-PT) pode ser mostrada à pessoa."""


ERRO_GOOGLE = 'Não foi possível entrar com o Google. Tente outra vez.'
STATE_SALT = 'proenglish.google-oauth-state'
STATE_MAX_AGE = 10 * 60  # segundos


class GoogleOAuthService:
    """
    Entrada com o Google (fluxo "authorization code").

    - Só se aceita o `code` devolvido pelo Google, trocado aqui com o nosso client id/secret e o
      redirect_uri configurado, ou um `id_token` verificado com google-auth para o nosso client
      id (aud). Um `access_token` enviado pelo cliente nunca é aceite: pode ter sido emitido
      para outra aplicação.
    - O Google tem de confirmar o email (email_verified) antes de ligar ou criar a conta.
    - Contas novas são de aluno e não têm palavra-passe utilizável; contas desactivadas são
      recusadas.
    - `state`: valor assinado (django.core.signing) devolvido por oauth/google/url/; se o cliente
      o enviar no login, tem de ser válido e recente.
    """
    
    def __init__(self):
        self.config = settings.OAUTH2_SETTINGS.get('GOOGLE', {})
        self.client_id = self.config.get('CLIENT_ID')
        self.client_secret = self.config.get('CLIENT_SECRET')
        self.redirect_uri = self.config.get('REDIRECT_URI')
        self.scope = ' '.join(self.config.get('SCOPE', []))
        self.auth_uri = self.config.get('AUTH_URI')
        self.token_uri = self.config.get('TOKEN_URI')
        self.user_info_uri = self.config.get('USER_INFO_URI')

    # -- state ---------------------------------------------------------------

    @staticmethod
    def criar_state() -> str:
        return signing.dumps({'n': secrets.token_urlsafe(16)}, salt=STATE_SALT)

    @staticmethod
    def state_valido(state: str) -> bool:
        try:
            signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
            return True
        except signing.BadSignature:  # inclui SignatureExpired
            return False

    # -- Google --------------------------------------------------------------
    
    def generate_auth_url(self, state: str = None) -> str:
        """URL de autorização do Google, sempre com o redirect_uri configurado."""
        if not self.client_id:
            raise GoogleOAuthErro('A entrada com o Google não está configurada.')
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'response_type': 'code',
            'access_type': 'online',
            'prompt': 'select_account',
            'state': state or self.criar_state(),
        }
        return f"{self.auth_uri}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Troca o código de autorização pelos tokens do Google (no servidor)."""
        if not self.client_id or not self.client_secret:
            raise GoogleOAuthErro('A entrada com o Google não está configurada.')
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
        }
        try:
            response = requests.post(self.token_uri, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            raise GoogleOAuthErro('O Google não aceitou a autorização. Tente outra vez.')
    
    def get_user_info_from_token(self, access_token: str) -> Dict[str, Any]:
        """Dados da pessoa com um access token obtido por nós na troca do código."""
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(self.user_info_uri, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error getting user info from token: {str(e)}")
            raise GoogleOAuthErro(ERRO_GOOGLE)
    
    def verify_id_token(self, id_token_str: str) -> Dict[str, Any]:
        """Verifica um ID token do Google emitido para o nosso client id (aud)."""
        if not self.client_id:
            raise GoogleOAuthErro('A entrada com o Google não está configurada.')
        try:
            id_info = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                self.client_id
            )
        except Exception as e:
            logger.error(f"Error verifying ID token: {str(e)}")
            raise GoogleOAuthErro(ERRO_GOOGLE)
        if id_info.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
            raise GoogleOAuthErro(ERRO_GOOGLE)
        if id_info.get('aud') != self.client_id:
            raise GoogleOAuthErro(ERRO_GOOGLE)
        return id_info
    
    def authenticate_user(self, code: str = None, id_token: str = None, state: str = None,
                          access_token: str = None, **_ignorar) -> User:
        """
        Devolve o utilizador da entrada com o Google (sem tokens: a sessão é criada na view,
        como no login normal).
        """
        if access_token:
            raise GoogleOAuthErro('Pedido inválido para entrar com o Google.')
        if state and not self.state_valido(state):
            raise GoogleOAuthErro('O pedido de entrada com o Google expirou. Tente outra vez.')

        user_info = None
        if code:
            token_response = self.exchange_code_for_tokens(code)
            if token_response.get('id_token'):
                # O id_token vem directamente do Google na troca; verifica-se na mesma (aud).
                user_info = self.verify_id_token(token_response['id_token'])
            elif token_response.get('access_token'):
                user_info = self.get_user_info_from_token(token_response['access_token'])
        elif id_token:
            user_info = self.verify_id_token(id_token)
        else:
            raise GoogleOAuthErro('Pedido inválido para entrar com o Google.')

        if not user_info:
            raise GoogleOAuthErro(ERRO_GOOGLE)

        google_id = user_info.get('sub') or user_info.get('id')
        email = (user_info.get('email') or '').strip().lower()
        verificado = user_info.get('email_verified', user_info.get('verified_email', False))
        if isinstance(verificado, str):
            verificado = verificado.lower() == 'true'
        if not email or not google_id:
            raise GoogleOAuthErro('O Google não indicou o seu email.')
        if verificado is not True:
            raise GoogleOAuthErro('O seu email ainda não está confirmado no Google. '
                                  'Confirme-o no Google ou entre com email e palavra-passe.')

        return self._get_or_create_user(google_id=str(google_id), email=email,
                                        name=(user_info.get('name') or '').strip())
    
    def _get_or_create_user(self, google_id: str, email: str, name: str) -> User:
        user = User.objects.filter(google_id=google_id).first() or User.objects.filter(email__iexact=email).first()
        if user:
            if not user.is_active:
                raise GoogleOAuthErro('Esta conta está desactivada.')
            if user.google_id and user.google_id != google_id:
                # A conta já está ligada a outra conta Google.
                raise GoogleOAuthErro(ERRO_GOOGLE)
            campos = []
            if not user.google_id:
                user.google_id = google_id
                campos.append('google_id')
            if not user.name and name:
                user.name = name
                campos.append('name')
            if not user.email_verified:
                # O Google confirmou que a pessoa é dona deste email.
                user.email_verified = True
                campos.append('email_verified')
            if campos:
                user.save(update_fields=campos)
            logger.info(f"Google OAuth: utilizador existente {user.pk}")
            return user

        user = User(email=email, name=name or email.split('@')[0], google_id=google_id,
                    email_verified=True, role='student', is_active=True)
        user.set_unusable_password()
        user.save()
        logger.info(f"Google OAuth: utilizador novo {user.pk}")
        return user


class UserService:
    """Service for general user operations."""
    
    @staticmethod
    def create_user_tokens(user: User) -> Dict[str, str]:
        """
        Create JWT tokens for user.
        
        Args:
            user: User instance
            
        Returns:
            Dictionary with access and refresh tokens
        """
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
    
    @staticmethod
    def get_user_profile_data(user: User) -> Dict[str, Any]:
        """
        Get complete user profile data.
        
        Args:
            user: User instance
            
        Returns:
            User profile dictionary
        """
        return {
            'id': str(user.id),
            'email': user.email,
            'name': user.name,
            'phone': user.phone,
            'role': user.role,
            'avatar': user.avatar or None,
            'email_verified': user.email_verified,
            'google_id': user.google_id,
            'preferences': user.preferences,
            'created_at': user.created_at,
            'last_login_at': user.last_login_at,
        }