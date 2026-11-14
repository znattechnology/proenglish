"""Pedido de opinião: quando aparece, uma vez por momento, e o envio."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import UserEngagementMetrics

User = get_user_model()
STATUS = '/api/v1/users/feedback/status/'


def com_metricas(**m):
    base = {'licoes': 0, 'cursos': 0, 'conversas': 0, 'dias': 0, 'sequencia': 0}
    base.update(m)
    return mock.patch('apps.users.opiniao.metricas', return_value=base)


class OpiniaoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='op@example.com', name='Rita Bento', password='Segura!2026x', role='student')
        self.c = APIClient()
        self.c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}')

    def test_sem_actividade_nao_pede(self):
        with com_metricas():
            r = self.c.get(STATUS)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['should_show_prompt'])

    def test_primeira_licao_pede_uma_vez(self):
        with com_metricas(licoes=1):
            r = self.c.get(STATUS)
        self.assertTrue(r.data['should_show_prompt'])
        self.assertEqual(r.data['chave'], 'primeira_licao')
        self.assertIn('primeira lição', r.data['frase'])
        self.c.post('/api/v1/users/feedback/dismiss/', {'trigger': 'first_lesson', 'action': 'skipped', 'context_data': {'chave': 'primeira_licao'}}, format='json')
        # Depois de adiar, espera 3 dias; e o mesmo momento não volta.
        UserEngagementMetrics.objects.filter(user=self.user).update(last_prompt_at=timezone.now() - timedelta(days=4))
        with com_metricas(licoes=3):
            r = self.c.get(STATUS)
        self.assertFalse(r.data['should_show_prompt'])

    def test_saltar_marcos_nao_perde_o_pedido(self):
        # Antes, o pedido só aparecia com exactamente 5 lições; com 7 nunca aparecia.
        with com_metricas(licoes=7):
            r = self.c.get(STATUS)
        self.assertEqual(r.data['chave'], 'primeira_licao')

    def test_enviar_e_esperar_7_dias(self):
        r = self.c.post('/api/v1/users/feedback/submit/', {'rating': 4, 'comment': 'As lições curtas ajudam.', 'trigger': 'first_lesson',
                                                          'context_data': {'chave': 'primeira_licao'}, 'allow_public': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['message'], 'Obrigado pela sua opinião.')
        with com_metricas(licoes=5):
            r = self.c.get(STATUS)
        self.assertFalse(r.data['should_show_prompt'])

    def test_enviar_vazio_recusado(self):
        r = self.c.post('/api/v1/users/feedback/submit/', {'comment': ''}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_metricas_reais_contam(self):
        from apps.users import opiniao
        m = opiniao.metricas(self.user)
        self.assertEqual(m['licoes'], 0)
        self.assertEqual(set(m), {'licoes', 'cursos', 'conversas', 'dias', 'sequencia'})


class TestemunhosTests(APITestCase):
    def test_so_aparecem_depois_de_aprovados(self):
        from apps.users.models import UserFeedback
        u = User.objects.create_user(email='t@example.com', name='Tomás Kiala', password='Segura!2026x', role='student')
        u.preferences = {'area': 'Industry English'}
        u.save()
        f = UserFeedback.objects.create(user=u, rating=5, comment='O tutor corrige sem me envergonhar.', allow_public=True)
        r = self.client.get('/api/v1/users/feedback/testimonials/')
        self.assertEqual(r.data['count'], 0)
        f.is_reviewed = True
        f.save()
        t = self.client.get('/api/v1/users/feedback/testimonials/').data['testimonials'][0]
        self.assertEqual((t['name'], t['area']), ('Tomás K.', 'Petróleo e Gás'))
