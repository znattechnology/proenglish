"""Perfil e definições do estudante: dados, preferências, palavra-passe e apagar a conta."""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class PerfilEstudanteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='perfil@example.com', name='Maria Santos', password='Segura!2026x', role='student')
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')

    def test_guardar_dados_e_preferencias(self):
        r = self.client.patch('/api/v1/users/profile/', {
            'name': ' Maria Santos ', 'phone': '+244923456789',
            'preferences': {'cidade': 'Luanda', 'area': 'Industry English', 'nivel': 'Intermediate'},
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Maria Santos')
        self.assertEqual(self.user.phone, '+244923456789')
        self.assertEqual(self.user.preferences['cidade'], 'Luanda')
        # Só muda as chaves enviadas; as outras ficam.
        self.client.patch('/api/v1/users/profile/', {'preferences': {'cidade': 'Benguela'}}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferences, {'cidade': 'Benguela', 'area': 'Industry English', 'nivel': 'Intermediate'})

    def test_preferencias_desconhecidas_ou_invalidas(self):
        r = self.client.patch('/api/v1/users/profile/', {'preferences': {'qualquer': 'coisa'}}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch('/api/v1/users/profile/', {'preferences': {'nivel': 'Expert'}}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_email_nao_muda(self):
        self.client.patch('/api/v1/users/profile/', {'email': 'outro@example.com'}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'perfil@example.com')

    def test_mudar_palavra_passe_termina_outras_sessoes(self):
        outra = RefreshToken.for_user(self.user)  # outro dispositivo
        self.client.cookies['refresh_token'] = str(self.refresh)
        r = self.client.post('/api/v1/users/change-password/', {
            'current_password': 'Segura!2026x', 'new_password': 'NovaSegura!2027y', 'new_password_confirm': 'NovaSegura!2027y',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NovaSegura!2027y'))
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=outra['jti']).exists())
        self.assertFalse(BlacklistedToken.objects.filter(token__jti=self.refresh['jti']).exists())

    def test_palavra_passe_actual_errada(self):
        r = self.client.post('/api/v1/users/change-password/', {
            'current_password': 'errada', 'new_password': 'NovaSegura!2027y', 'new_password_confirm': 'NovaSegura!2027y',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_apagar_conta(self):
        from apps.pagamentos.models import Pagamento  # noqa: F401 (os pagamentos ficam; aqui só se verifica o utilizador)
        r = self.client.post('/api/v1/users/apagar-conta/', {'password': 'errada'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/v1/users/apagar-conta/', {'password': 'Segura!2026x'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotEqual(self.user.email, 'perfil@example.com')
        self.assertEqual(self.user.name, 'Conta apagada')
        self.assertFalse(self.user.has_usable_password())
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=self.refresh['jti']).exists())
        # Já não entra com o token que tinha
        self.assertIn(self.client.get('/api/v1/users/profile/').status_code, (401, 403))
        self.assertFalse(OutstandingToken.objects.filter(user=self.user).exclude(blacklistedtoken__isnull=False).exists())


class AcolhimentoTests(APITestCase):
    def test_marca_o_fim_da_primeira_entrada(self):
        user = User.objects.create_user(email='novo2@example.com', name='Paulo Lima', password='Segura!2026x', role='student')
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        r = c.patch('/api/v1/users/profile/', {'preferences': {'area': 'Industry English', 'nivel': 'Beginner', 'acolhimento': 'concluido'}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        user.refresh_from_db()
        self.assertEqual(user.preferences['acolhimento'], 'concluido')
        self.assertEqual(c.patch('/api/v1/users/profile/', {'preferences': {'acolhimento': 'talvez'}}, format='json').status_code, 400)
