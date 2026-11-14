"""Recuperar a palavra-passe com o código enviado por email."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import EmailVerification

User = get_user_model()
URL = '/api/v1/users/password-reset-confirm/'


class RecuperarSenhaTests(APITestCase):
    def setUp(self):
        cache.clear()  # limites de pedidos por IP
        self.client = APIClient()
        self.user = User.objects.create_user(email='rec@example.com', name='Rui Costa', password='Antiga!2026x', role='student')
        self.v = EmailVerification.objects.create(user=self.user, email=self.user.email, code='482913',
                                                  expires_at=timezone.now() + timedelta(minutes=30),
                                                  finalidade=EmailVerification.FINALIDADE_RECUPERAR)

    def pedir(self, code='482913', senha='NovaSegura!2026'):
        return self.client.post(URL, {'email': 'REC@example.com', 'code': code, 'newPassword': senha}, format='json')

    def test_codigo_certo_muda_e_termina_sessoes(self):
        RefreshToken.for_user(self.user)
        r = self.pedir()
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NovaSegura!2026'))
        self.v.refresh_from_db()
        self.assertTrue(self.v.is_used)
        self.assertEqual(BlacklistedToken.objects.count(), OutstandingToken.objects.filter(user=self.user).count())
        self.assertEqual(self.pedir().status_code, 400)  # o código não volta a servir

    def test_codigo_errado_conta_tentativas_e_bloqueia(self):
        for _ in range(self.v.max_attempts):
            self.assertEqual(self.pedir(code='000000').status_code, 400)
        self.v.refresh_from_db()
        self.assertEqual(self.v.attempts, self.v.max_attempts)
        r = self.pedir()  # nem o código certo serve depois do limite
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Antiga!2026x'))

    def test_senha_fraca_recusada(self):
        r = self.pedir(senha='123')
        self.assertEqual(r.status_code, 400)
        self.v.refresh_from_db()
        self.assertFalse(self.v.is_used)

    def test_codigo_expirado(self):
        self.v.expires_at = timezone.now() - timedelta(minutes=1)
        self.v.save()
        self.assertEqual(self.pedir().status_code, 400)


class ReenviarCodigoTests(APITestCase):
    URL = '/api/v1/users/resend-verification/'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='novo@example.com', name='Ana Neto', password='Segura!2026x', role='student')
        self.user.email_verified = False
        self.user.save()

    def test_nao_revela_se_o_email_existe(self):
        a = self.client.post(self.URL, {'email': 'naoexiste@example.com'}, format='json')
        self.assertEqual(a.status_code, 200)
        self.assertNotIn('encontrado', str(a.data))

    def test_espera_entre_codigos(self):
        EmailVerification.objects.create(user=self.user, email=self.user.email, code='111111',
                                         expires_at=timezone.now() + timedelta(minutes=30))
        r = self.client.post(self.URL, {'email': 'novo@example.com'}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertGreater(r.data['aguardar_segundos'], 0)


class ConfirmarEmailTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='conf@example.com', name='Carla Mendes', password='Segura!2026x', role='student')
        self.user.email_verified = False
        self.user.save()

    def test_confirmar_grava_a_sessao_nos_cookies(self):
        from apps.users.email_service import EmailVerificationService
        v = EmailVerificationService.create_verification_code(self.user, self.user.email)
        r = self.client.post('/api/v1/users/verify-email/', {'email': self.user.email, 'code': v.code}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access_token', r.cookies)
        self.assertIn('refresh_token', r.cookies)
        self.assertTrue(r.cookies['access_token']['httponly'])
        self.assertNotIn('access', r.data)  # o token não vai no corpo (o JavaScript não o lê)
