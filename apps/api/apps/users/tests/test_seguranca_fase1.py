"""
Segurança (fase 1): registo, confirmação do email, recuperação da palavra-passe, entrada com
o Google e sessão (cookies, refresh, logout).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.users.tests.test_seguranca_fase1
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.users.email_service import EmailVerificationService
from apps.users.models import EmailVerification
from apps.users.services import GoogleOAuthService

User = get_user_model()
U = '/api/v1/users/'
SENHA = 'Segura!2026xy'

GOOGLE_TESTE = {
    'GOOGLE': {
        'CLIENT_ID': 'cliente-teste.apps.googleusercontent.com',
        'CLIENT_SECRET': 'segredo-teste',
        'REDIRECT_URI': 'http://localhost:3000/auth/google/callback',
        'SCOPE': ['openid', 'email', 'profile'],
        'AUTH_URI': 'https://accounts.google.com/o/oauth2/auth',
        'TOKEN_URI': 'https://oauth2.googleapis.com/token',
        'USER_INFO_URI': 'https://www.googleapis.com/oauth2/v2/userinfo',
    }
}


class Base(APITestCase):
    def setUp(self):
        cache.clear()  # limites de pedidos por IP
        self.client = APIClient()

    def utilizador(self, email='ana-seg@example.com', verificado=True, **extra):
        u = User.objects.create_user(email=email, name='Ana Neto', password=SENHA, role=extra.pop('role', 'student'),
                                     **extra)
        u.email_verified = verificado
        u.save(update_fields=['email_verified'])
        return u

    def registar(self, **extra):
        corpo = {'email': 'novo-seg@example.com', 'name': 'Novo Aluno', 'password': SENHA,
                 'password_confirm': SENHA, **extra}
        return self.client.post(f'{U}register/', corpo, format='json')


# ---------------------------------------------------------------------------
# 1. Registo
# ---------------------------------------------------------------------------

class RegistoTests(Base):

    def test_role_do_cliente_e_ignorado(self):
        for i, role in enumerate(['admin', 'teacher', 'customer']):
            with self.subTest(role=role):
                r = self.registar(email=f'r{i}-seg@example.com', role=role)
                self.assertEqual(r.status_code, 201, r.content)
                self.assertEqual(User.objects.get(email=f'r{i}-seg@example.com').role, 'student')

    def test_sem_role_fica_aluno(self):
        self.assertEqual(self.registar().status_code, 201)
        self.assertEqual(User.objects.get(email='novo-seg@example.com').role, 'student')

    def test_manager_por_omissao_cria_aluno(self):
        u = User.objects.create_user(email='m-seg@example.com', name='M', password=SENHA)
        self.assertEqual(u.role, 'student')

    def test_email_em_minusculas_e_sem_duplicados(self):
        r = self.registar(email='Grande.Seg@Example.COM')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(User.objects.filter(email='grande.seg@example.com').exists())
        cache.clear()
        r = self.registar(email='GRANDE.SEG@example.com')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(User.objects.filter(email__iexact='grande.seg@example.com').count(), 1)

    def test_entrar_com_maiusculas(self):
        self.utilizador()
        r = self.client.post(f'{U}login/', {'email': 'ANA-SEG@example.com', 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 200, r.content)


# ---------------------------------------------------------------------------
# 2. Confirmar o email / recuperar a palavra-passe
# ---------------------------------------------------------------------------

class ConfirmarEmailTests(Base):

    def confirmar(self, email, code):
        return self.client.post(f'{U}verify-email/', {'email': email, 'code': code}, format='json')

    def test_codigo_de_recuperacao_nao_confirma_nem_da_sessao(self):
        # Ataque: pedir recuperação da palavra-passe de uma conta já confirmada e usar esse
        # código em verify-email/ para receber uma sessão.
        vitima = self.utilizador()
        self.client.post(f'{U}password-reset/', {'email': vitima.email}, format='json')
        v = EmailVerification.objects.get(user=vitima, is_used=False)
        self.assertEqual(v.finalidade, EmailVerification.FINALIDADE_RECUPERAR)
        r = self.confirmar(vitima.email, v.code)
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('access_token', r.cookies)

    def test_codigo_de_recuperacao_nao_confirma_conta_por_confirmar(self):
        u = self.utilizador(verificado=False)
        v = EmailVerificationService.create_verification_code(u, finalidade=EmailVerification.FINALIDADE_RECUPERAR)
        self.assertEqual(self.confirmar(u.email, v.code).status_code, 400)
        u.refresh_from_db()
        self.assertFalse(u.email_verified)

    def test_conta_ja_confirmada_nao_recebe_sessao(self):
        u = self.utilizador(verificado=True)
        v = EmailVerificationService.create_verification_code(u)
        r = self.confirmar(u.email, v.code)
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('access_token', r.cookies)
        self.assertIn('código', r.data['error'])

    def test_codigos_errados_contam_e_bloqueiam(self):
        u = self.utilizador(verificado=False)
        v = EmailVerificationService.create_verification_code(u)
        errado = '000000' if v.code != '000000' else '111111'
        for _ in range(v.max_attempts):
            self.assertEqual(self.confirmar(u.email, errado).status_code, 400)
        v.refresh_from_db()
        self.assertEqual(v.attempts, v.max_attempts)
        self.assertEqual(self.confirmar(u.email, v.code).status_code, 400)  # nem o certo serve
        u.refresh_from_db()
        self.assertFalse(u.email_verified)

    def test_codigo_certo_confirma_com_sessao_nos_cookies(self):
        u = self.utilizador(verificado=False)
        v = EmailVerificationService.create_verification_code(u)
        r = self.confirmar('ANA-SEG@example.com', v.code)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('access', r.data)
        self.assertNotIn('refresh', r.data)
        self.assertEqual(r.data['user']['email'], u.email)
        token = AccessToken(r.cookies['access_token'].value)
        self.assertEqual(token['role'], 'student')
        self.assertEqual(token['email'], u.email)
        self.assertEqual(self.confirmar(u.email, v.code).status_code, 400)  # só serve uma vez

    def test_codigo_de_confirmacao_nao_muda_a_palavra_passe(self):
        u = self.utilizador(verificado=False)
        v = EmailVerificationService.create_verification_code(u)
        r = self.client.post(f'{U}password-reset-confirm/',
                             {'email': u.email, 'code': v.code, 'newPassword': 'OutraSegura!2027'}, format='json')
        self.assertEqual(r.status_code, 400)
        u.refresh_from_db()
        self.assertTrue(u.check_password(SENHA))

    def test_recuperar_com_maiusculas(self):
        u = self.utilizador()
        self.client.post(f'{U}password-reset/', {'email': 'ANA-SEG@EXAMPLE.com'}, format='json')
        v = EmailVerification.objects.get(user=u, finalidade=EmailVerification.FINALIDADE_RECUPERAR, is_used=False)
        r = self.client.post(f'{U}password-reset-confirm/',
                             {'email': u.email, 'code': v.code, 'newPassword': 'OutraSegura!2027'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        u.refresh_from_db()
        self.assertTrue(u.check_password('OutraSegura!2027'))

    def test_reenviar_com_maiusculas(self):
        u = self.utilizador(verificado=False)
        r = self.client.post(f'{U}resend-verification/', {'email': 'ANA-SEG@example.com'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(EmailVerification.objects.filter(
            user=u, finalidade=EmailVerification.FINALIDADE_VERIFICAR, is_used=False).exists())


# ---------------------------------------------------------------------------
# 3. Google
# ---------------------------------------------------------------------------

def _info(email='g-seg@example.com', verificado=True, sub='google-123', **extra):
    return {'sub': sub, 'email': email, 'email_verified': verificado, 'name': 'Gil Gomes',
            'iss': 'https://accounts.google.com', 'aud': GOOGLE_TESTE['GOOGLE']['CLIENT_ID'], **extra}


@override_settings(OAUTH2_SETTINGS=GOOGLE_TESTE)
class GoogleTests(Base):

    def setUp(self):
        super().setUp()
        p = mock.patch.object(GoogleOAuthService, 'exchange_code_for_tokens', return_value={'id_token': 'tok'})
        self.trocar = p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(GoogleOAuthService, 'verify_id_token', return_value=_info())
        self.verificar = p2.start()
        self.addCleanup(p2.stop)
        p3 = mock.patch.object(GoogleOAuthService, 'get_user_info_from_token')
        self.userinfo = p3.start()
        self.addCleanup(p3.stop)

    def entrar(self, **corpo):
        return self.client.post(f'{U}oauth/google/login/', corpo or {'code': 'codigo'}, format='json')

    def test_access_token_do_cliente_e_recusado(self):
        r = self.entrar(access_token='token-de-outra-app')
        self.assertEqual(r.status_code, 400)
        r = self.entrar(code='codigo', access_token='token-de-outra-app')
        self.assertEqual(r.status_code, 400)
        self.userinfo.assert_not_called()
        self.trocar.assert_not_called()
        self.assertFalse(User.objects.filter(email='g-seg@example.com').exists())

    def test_conta_nova_e_aluno_sem_palavra_passe_e_sessao_so_nos_cookies(self):
        r = self.entrar()
        self.assertEqual(r.status_code, 200, r.content)
        u = User.objects.get(email='g-seg@example.com')
        self.assertEqual(u.role, 'student')
        self.assertFalse(u.has_usable_password())
        self.assertTrue(u.email_verified)
        self.assertNotIn('tokens', r.data)
        self.assertNotIn('access', r.data)
        self.assertEqual(r.data['user']['role'], 'student')
        token = AccessToken(r.cookies['access_token'].value)
        self.assertEqual(token['role'], 'student')
        self.assertIn('refresh_token', r.cookies)

    def test_email_nao_confirmado_no_google_nao_liga_contas(self):
        dono = self.utilizador(email='g-seg@example.com')
        self.verificar.return_value = _info(verificado=False)
        r = self.entrar()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('access_token', r.cookies)
        dono.refresh_from_db()
        self.assertIsNone(dono.google_id)

    def test_userinfo_sem_verified_email_e_recusado(self):
        self.trocar.return_value = {'access_token': 'nosso'}
        self.userinfo.return_value = {'id': '9', 'email': 'g-seg@example.com', 'name': 'G'}
        self.assertEqual(self.entrar().status_code, 400)
        self.assertFalse(User.objects.filter(email='g-seg@example.com').exists())

    def test_liga_conta_existente_quando_o_google_confirma(self):
        dono = self.utilizador(email='g-seg@example.com', role='teacher')
        self.verificar.return_value = _info(email='G-SEG@example.com')
        r = self.entrar()
        self.assertEqual(r.status_code, 200, r.content)
        dono.refresh_from_db()
        self.assertEqual(dono.google_id, 'google-123')
        self.assertEqual(dono.role, 'teacher')
        self.assertEqual(User.objects.filter(email__iexact='g-seg@example.com').count(), 1)

    def test_conta_desactivada_recusada(self):
        self.utilizador(email='g-seg@example.com', is_active=False)
        r = self.entrar()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('access_token', r.cookies)

    def test_erros_em_portugues_sem_detalhes_internos(self):
        self.trocar.side_effect = RuntimeError('client_secret=abc stack trace')
        r = self.entrar()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('abc', str(r.data))
        self.assertNotIn('Authentication failed', str(r.data))
        self.assertIn('Google', r.data['error'])

    def test_state_assinado(self):
        r = self.client.get(f'{U}oauth/google/url/')
        self.assertEqual(r.status_code, 200, r.content)
        state = r.data['state']
        from urllib.parse import parse_qs, urlparse
        self.assertEqual(parse_qs(urlparse(r.data['auth_url']).query)['state'], [state])
        self.assertEqual(self.entrar(code='c', state=state).status_code, 200)
        cache.clear()
        self.assertEqual(self.entrar(code='c', state='inventado').status_code, 400)
        # Expirado (mais de 10 minutos).
        with mock.patch('django.core.signing.time.time', return_value=timezone.now().timestamp() - 3600):
            antigo = signing.dumps({'n': 'x'}, salt='proenglish.google-oauth-state')
        self.assertEqual(self.entrar(code='c', state=antigo).status_code, 400)

    def test_redirect_uri_do_cliente_ignorado(self):
        r = self.client.get(f'{U}oauth/google/url/', {'redirect_uri': 'https://atacante.example/cb'})
        self.assertNotIn('atacante', r.data['auth_url'])


# ---------------------------------------------------------------------------
# 4. Sessão
# ---------------------------------------------------------------------------

class SessaoTests(Base):

    def entrar(self):
        r = self.client.post(f'{U}login/', {'email': self.u.email, 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r

    def setUp(self):
        super().setUp()
        self.u = self.utilizador()

    def test_login_sem_tokens_no_corpo(self):
        r = self.entrar()
        self.assertNotIn('access', r.data)
        self.assertNotIn('refresh', r.data)
        self.assertIn('user', r.data)
        self.assertTrue(r.cookies['access_token']['httponly'])
        self.assertTrue(r.cookies['refresh_token']['httponly'])

    def test_refresh_renova_os_dois_cookies_e_a_sessao_sobrevive(self):
        self.entrar()
        primeiro = self.client.cookies['refresh_token'].value
        for _ in range(3):  # antes morria no 2.º refresh
            r = self.client.post(f'{U}refresh-token/', {}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
            self.assertNotIn('access', r.data)
            self.assertNotIn('refresh', r.data)
            self.assertIn('access_token', r.cookies)
            self.assertIn('refresh_token', r.cookies)
        self.assertNotEqual(self.client.cookies['refresh_token'].value, primeiro)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=RefreshToken(primeiro, verify=False)['jti']).exists())

    def test_logout_com_access_expirado_apaga_cookies_e_bloqueia_refresh(self):
        self.entrar()
        refresh = self.client.cookies['refresh_token'].value
        expirado = AccessToken.for_user(self.u)
        expirado.set_exp(from_time=timezone.now() - timedelta(hours=2), lifetime=timedelta(minutes=1))
        self.client.cookies['access_token'] = str(expirado)
        r = self.client.post(f'{U}logout/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        for nome in ('access_token', 'refresh_token'):
            self.assertEqual(r.cookies[nome].value, '')
            self.assertEqual(r.cookies[nome]['path'], '/')
            self.assertEqual(r.cookies[nome]['max-age'], 0)
        self.client.cookies.clear()
        r = self.client.post(f'{U}refresh-token/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_logout_sem_sessao(self):
        r = self.client.post(f'{U}logout/', {}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_logout_com_refresh_no_corpo(self):
        refresh = str(RefreshToken.for_user(self.u))
        self.assertEqual(self.client.post(f'{U}logout/', {'refresh_token': refresh}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'{U}refresh-token/', {'refresh': refresh}, format='json').status_code, 401)
