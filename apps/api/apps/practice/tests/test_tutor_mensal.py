"""
Minutos de conversa por mês (planos) e a configuração do tutor no admin (modelo e duração).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_tutor_mensal --settings=core.test_settings
"""
from django.test import override_settings
from rest_framework.test import APIClient

from apps.practice.conversa import configuracao
from apps.practice.conversa.quota import estado_quota
from apps.practice.conversa.servico import modelo_vapi
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import ConfiguracaoTutor

from .test_conversa import Base


class MinutosPorMesTests(Base):
    def test_sem_limite_mensal_fica_como_antes(self):
        q = estado_quota(self.aluno)
        self.assertIsNone(q['minutos_mes'])
        self.assertTrue(q['pode_comecar'])

    def test_limite_mensal_corta_antes_do_diario(self):
        self.plus.monthly_speaking_minutes = 90
        self.plus.save()
        self.sub.monthly_speaking_minutes_used = 88
        self.sub.speaking_month = hoje_luanda().strftime('%Y-%m')
        self.sub.save()
        q = estado_quota(self.aluno)
        self.assertEqual((q['minutos_restantes_mes'], q['minutos_restantes'], q['max_minutos_sessao']), (2, 2, 2))
        self.sub.monthly_speaking_minutes_used = 90
        self.sub.save()
        q = estado_quota(self.aluno)
        self.assertEqual((q['pode_comecar'], q['motivo']), (False, 'sem_minutos_mes'))
        r = self.criar()
        self.assertEqual(r.status_code, 403, r.data)

    def test_mes_novo_renova_os_minutos(self):
        self.plus.monthly_speaking_minutes = 90
        self.plus.save()
        self.sub.monthly_speaking_minutes_used = 90
        self.sub.speaking_month = '2000-01'
        self.sub.save()
        q = estado_quota(self.aluno)
        self.assertEqual((q['pode_comecar'], q['minutos_usados_mes']), (True, 0))

    def test_admin_muda_os_minutos_do_plano(self):
        admin = self.outro
        admin.role = 'admin'
        admin.save(update_fields=['role'])
        c = APIClient()
        c.force_authenticate(admin)
        from decimal import Decimal
        self.premium.monthly_price, self.premium.yearly_price = Decimal('14950'), Decimal('149500')
        self.premium.save()
        r = c.patch(f'/api/v1/admin/planos/{self.premium.pk}/', {'limites': {'conversa_min_mes': 60, 'conversa_min_dia': None,
                                                                             'teste_conversa_min_dia': 2,
                                                                             'teste_conversa_dias': 3}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.premium.refresh_from_db()
        self.assertEqual((self.premium.monthly_speaking_minutes, self.premium.daily_speaking_minutes,
                          self.premium.trial_speaking_minutes, self.premium.trial_days), (60, None, 2, 3))


@override_settings(CONVERSA_VAPI_PROVEDOR='anthropic', CONVERSA_VAPI_MODELO='claude-sonnet-5', CONVERSA_MAX_MINUTOS_SESSAO=15)
class ConfiguracaoTutorTests(Base):
    def setUp(self):
        super().setUp()
        self.outro.role = 'admin'
        self.outro.save(update_fields=['role'])
        self.admin = APIClient()
        self.admin.force_authenticate(self.outro)

    def test_sem_linha_usa_as_definicoes_do_servidor(self):
        self.assertEqual(configuracao.actual()['modelo'], 'claude-sonnet-5')
        self.assertEqual(modelo_vapi('x')['model'], 'claude-sonnet-5')

    def test_admin_troca_o_modelo_e_a_duracao(self):
        r = self.admin.patch('/api/v1/admin/tutor/', {'modelo': 'claude-haiku-5-5', 'max_minutos_sessao': 8}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['modelo'], r.data['max_minutos_sessao']), ('claude-haiku-5-5', 8))
        self.assertEqual(modelo_vapi('x')['model'], 'claude-haiku-5-5')
        self.assertEqual(estado_quota(self.aluno)['max_minutos_sessao'], 8)
        self.assertEqual(ConfiguracaoTutor.objects.count(), 1)
        self.admin.patch('/api/v1/admin/tutor/', {'provedor': 'openai', 'modelo': 'gpt-4.1-mini'}, format='json')
        m = modelo_vapi('x')
        self.assertEqual((m['provider'], m['model'], m['temperature']), ('openai', 'gpt-4.1-mini', 0.6))
        self.assertEqual(ConfiguracaoTutor.objects.count(), 1)

    def test_valores_invalidos(self):
        for corpo in ({'provedor': 'google'}, {'modelo': 'Claude Sonnet!'}, {'max_minutos_sessao': 0},
                      {'max_minutos_sessao': 61}, {'max_minutos_sessao': True}):
            self.assertEqual(self.admin.patch('/api/v1/admin/tutor/', corpo, format='json').status_code, 400, corpo)

    def test_so_o_admin(self):
        c = APIClient()
        c.force_authenticate(self.aluno)
        self.assertEqual(c.get('/api/v1/admin/tutor/').status_code, 403)
