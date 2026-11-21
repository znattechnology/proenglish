"""
Regressões da revisão de hoje (correcções da revisão de código): forma servida pelo servidor, quota
de novos, saltar exercícios falados, revisões no mesmo dia, limite de análises sem assinatura e a
data da última conversa em Luanda.

    ./venv/bin/python manage.py test apps.perfil.tests.test_revisao_correccoes
"""
from datetime import datetime, timedelta, timezone as dt_tz
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.perfil import agenda, revisao, servico
from apps.perfil.models import ItemBanco, RespostaRevisao
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import TentativaPronuncia, UserProgress, VapiSession

User = get_user_model()
R = '/api/v1/student/revisao/'


def _aluno(email):
    return User.objects.create_user(email=email, name='Ana', password='x', role='student')


def _audio():
    return SimpleUploadedFile('gravacao.webm', b'\x1a' * 4096, content_type='audio/webm')


class Api(APITestCase):
    def setUp(self):
        cache.clear()
        self.u = _aluno('fxc-rev@example.com')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.u).access_token}')
        p = mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', side_effect=RuntimeError('sem rede'))
        p.start()
        self.addCleanup(p.stop)

    def test_forma_trocada_pelo_cliente_e_recusada(self):
        """Antes: um 'ouvir_repetir' servido podia ser respondido como 'traduzir' (escrevendo)."""
        it = servico.registar_item(self.u, 'The pump needs a new valve', 'A bomba precisa de uma válvula nova')
        ex = self.client.get(f'{R}hoje/').json()['exercicios'][0]
        self.assertEqual(ex['forma'], revisao.OUVIR)
        r = self.client.post(f'{R}responder/', {'exercicio_id': ex['id'], 'forma': 'traduzir',
                                                'resposta': it.texto, 'segundos': 5}, format='json')
        self.assertEqual(r.status_code, 404)
        it.refresh_from_db()
        self.assertEqual((it.estado, it.proxima_revisao), (ItemBanco.VISTA, None))
        self.assertFalse(RespostaRevisao.objects.exists())

    def test_forma_servida_fica_igual_o_dia_todo(self):
        a = servico.registar_item(self.u, 'Please check the valve now.', 'Verifique a válvula agora.')
        servico.registar_item(self.u, 'The truck is late today.', 'O camião está atrasado hoje.')
        primeira = {e['id']: e['forma'] for e in self.client.get(f'{R}hoje/').json()['exercicios']}
        # Muda o que escolher_formas daria (outro estado): a forma servida mantém-se.
        ItemBanco.objects.filter(pk=a.pk).update(estado=ItemBanco.COM_AJUDA, repeticoes=1)
        segunda = {e['id']: e['forma'] for e in self.client.get(f'{R}hoje/').json()['exercicios']}
        self.assertEqual(primeira, segunda)

    def test_saltar_exercicio_falado(self):
        it = servico.registar_item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        ex = self.client.get(f'{R}hoje/').json()['exercicios'][0]
        self.assertEqual(ex['forma'], revisao.OUVIR)
        r = self.client.post(f'{R}saltar/', {'exercicio_id': ex['id']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['saltado'])
        it.refresh_from_db()
        self.assertEqual(it.proxima_revisao, agenda.para_o_dia(1))  # volta amanhã
        self.assertEqual((it.repeticoes, it.estabilidade, it.estado), (0, None, ItemBanco.VISTA))
        self.assertFalse(RespostaRevisao.objects.exists())
        self.assertFalse(UserProgress.objects.filter(user=self.u, points__gt=0).exists())
        self.assertEqual(self.client.get(f'{R}hoje/').json()['total'], 0)

    def test_saltar_so_exercicios_falados(self):
        it = servico.registar_item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        from apps.perfil.models import SessaoRevisao
        SessaoRevisao.objects.create(user=self.u, dia=hoje_luanda(), exercicios={f'item:{it.pk}': {'forma': 'escolher'}})
        r = self.client.post(f'{R}saltar/', {'exercicio_id': f'item:{it.pk}'}, format='json')
        self.assertEqual(r.status_code, 404)
        r = self.client.post(f'{R}saltar/', {'exercicio_id': 'item:999999'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_limite_sem_assinatura_usa_o_gratuito_e_pode_saltar(self):
        from apps.subscriptions.models import SubscriptionPlan, UserSubscription
        UserSubscription.objects.filter(user=self.u).delete()
        SubscriptionPlan.objects.update_or_create(plan_type='FREE', defaults=dict(
            name='Gratuito', description='-', monthly_price=Decimal('0'), daily_speaking_minutes=0,
            daily_ai_analyses_limit=1))
        servico.registar_item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        ex = self.client.get(f'{R}hoje/').json()['exercicios'][0]
        TentativaPronuncia.objects.create(user=self.u, texto_esperado='x', transcricao='x', nota_geral=80, aceite=True,
                                          origem=TentativaPronuncia.ORIGEM_AULA)
        with mock.patch('apps.perfil.views_revisao._analisar') as analisar:
            r = self.client.post(f'{R}falar/', {'exercicio_id': ex['id'], 'audio': _audio()}, format='multipart')
        analisar.assert_not_called()
        self.assertEqual(r.status_code, 429)
        self.assertTrue(r.json()['pode_saltar'])
        self.assertEqual(self.client.post(f'{R}saltar/', {'exercicio_id': ex['id']}, format='json').status_code, 200)

    def test_gravacao_grande_413(self):
        servico.registar_item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        ex = self.client.get(f'{R}hoje/').json()['exercicios'][0]
        grande = SimpleUploadedFile('g.webm', b'\x1a' * (5 * 1024 * 1024 + 1), content_type='audio/webm')
        with mock.patch('apps.perfil.views_revisao._analisar') as analisar:
            r = self.client.post(f'{R}falar/', {'exercicio_id': ex['id'], 'audio': grande}, format='multipart')
        self.assertEqual(r.status_code, 413)
        analisar.assert_not_called()

    @override_settings(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test-x', ANTHROPIC_API_KEY='x',
                       AZURE_SPEECH_KEY='')
    def test_silencio_422_sem_claude_e_sem_contar(self):
        from apps.practice.services.transcricao_fala import Transcricao
        servico.registar_item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        ex = self.client.get(f'{R}hoje/').json()['exercicios'][0]
        with mock.patch('apps.practice.services.transcricao_fala.transcrever', return_value=Transcricao(texto='')), \
                mock.patch('apps.practice.services.ai_pronunciation._claude_json') as claude, \
                mock.patch('apps.perfil.views_revisao.contar_analise') as contar:
            r = self.client.post(f'{R}falar/', {'exercicio_id': ex['id'], 'audio': _audio()}, format='multipart')
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()['codigo'], 'sem_fala')
        claude.assert_not_called()
        contar.assert_not_called()
        self.assertFalse(RespostaRevisao.objects.exists())


class Quota(TestCase):
    def setUp(self):
        self.u = _aluno('fxc-rev-q@example.com')

    def test_erros_de_licao_nao_gastam_a_quota_de_novos(self):
        ontem = timezone.now() - timedelta(days=1)
        for i in range(8):
            it = servico.registar_item(self.u, f'FXC lesson error phrase number {i}', f'erro {i}')
            agenda.marcar_para_amanha(it, ontem)  # erro na lição ontem -> volta hoje
            it.save()
        for i in range(5):
            servico.registar_item(self.u, f'FXC brand new phrase {i} here', f'nova {i}')
        devidos, novos = revisao.itens_para_hoje(self.u)
        self.assertEqual((len(devidos), len(novos)), (8, 2))
        revisao.sessao_de_hoje(self.u, com_padroes=False)
        servidos = revisao.servidos_hoje(self.u)
        for it in devidos:
            eid = f'item:{it.pk}'
            d = revisao.definicao(self.u, eid, servidos[eid]['forma'])
            revisao.registar_resposta(self.u, d, eid, True, agenda.CERTO, it.traducao, 5)
        self.assertEqual(revisao._novos_introduzidos_hoje(self.u), 0)
        devidos, novos = revisao.itens_para_hoje(self.u)
        self.assertEqual((len(devidos), len(novos)), (0, 5))

    def test_item_novo_gasta_a_quota(self):
        it = servico.registar_item(self.u, 'FXC a truly new phrase', 'nova')
        revisao.sessao_de_hoje(self.u, com_padroes=False)
        eid = f'item:{it.pk}'
        d = revisao.definicao(self.u, eid)
        revisao.registar_resposta(self.u, d, eid, True, agenda.CERTO, '', 5)
        self.assertEqual(revisao._novos_introduzidos_hoje(self.u), 1)


class MesmoDia(TestCase):
    def setUp(self):
        self.u = _aluno('fxc-rev-d@example.com')

    def test_tres_conversas_no_mesmo_dia_nao_multiplicam_a_estabilidade(self):
        it = servico.registar_item(self.u, 'FXC said alone three times', '')
        manha = timezone.now().replace(microsecond=0)
        agenda.rever_por_conversa(it, manha)
        s1, p1 = it.estabilidade, it.proxima_revisao
        for k in range(1, 3):
            agenda.rever_por_conversa(it, manha + timedelta(seconds=k))
        if hoje_luanda(manha + timedelta(seconds=2)) == hoje_luanda(manha):
            self.assertEqual((it.estabilidade, it.proxima_revisao, it.repeticoes), (s1, p1, 1))
        # No dia seguinte volta a crescer.
        agenda.rever_por_conversa(it, manha + timedelta(days=1))
        self.assertGreater(it.estabilidade, s1)

    def test_erro_no_mesmo_dia_aplica_se(self):
        it = servico.registar_item(self.u, 'FXC an error later the same day', '')
        agora = datetime(2026, 3, 10, 9, 0, tzinfo=dt_tz.utc)
        agenda.aplicar(it, agenda.FACIL, agora)
        s = it.estabilidade
        agenda.aplicar(it, agenda.ERREI, agora + timedelta(hours=2))
        self.assertLess(it.estabilidade, s)
        self.assertEqual(it.proxima_revisao, agenda.para_o_dia(1, agora))


class UltimaConversa(TestCase):
    def test_data_em_luanda(self):
        u = _aluno('fxc-rev-c@example.com')
        # 23:30 UTC do dia 10 = 00:30 do dia 11 em Luanda.
        VapiSession.objects.create(session_id='fxc-ultima-1', user=u, level='B1', domain='general', duration_minutes=5,
                                   status=VapiSession.STATUS_AVALIADA, overall_score=70,
                                   started_at=datetime(2026, 3, 10, 23, 30, tzinfo=dt_tz.utc))
        self.assertTrue(servico._ultima_conversa(u).startswith('11 Mar 2026'))
