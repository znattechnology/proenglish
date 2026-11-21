"""A app móvel (X-Cliente: app) recebe a sessão no corpo, sem cookies; o browser continua só com cookies."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User


class SessaoAppTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='app-sessao@local.test', password='Senha-Teste-123', name='Ana App')
        self.user.email_verified = True
        self.user.is_active = True
        self.user.save()

    def entrar(self, **headers):
        return APIClient().post('/api/v1/users/login/', {'email': self.user.email, 'password': 'Senha-Teste-123'},
                                format='json', **headers)

    def test_app_recebe_tokens_no_corpo_sem_cookies(self):
        r = self.entrar(HTTP_X_CLIENTE='app')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access', r.data['tokens'])
        self.assertIn('refresh', r.data['tokens'])
        self.assertNotIn('access_token', r.cookies)

    def test_browser_continua_so_com_cookies(self):
        r = self.entrar()
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('tokens', r.data)
        self.assertIn('access_token', r.cookies)

    def test_app_renova_com_refresh_no_corpo(self):
        tokens = self.entrar(HTTP_X_CLIENTE='app').data['tokens']
        r = APIClient().post('/api/v1/users/refresh-token/', {'refresh': tokens['refresh']}, format='json',
                             HTTP_X_CLIENTE='app')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access', r.data['tokens'])
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['tokens']['access']}")
        self.assertEqual(c.get('/api/v1/users/profile/').status_code, 200)
