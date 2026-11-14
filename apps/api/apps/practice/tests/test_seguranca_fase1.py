"""
Segurança (fase 1), lado da prática: exercícios com IA, vidas, fluxo antigo da Vapi e
limites da subscrição.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_seguranca_fase1
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice.models import (ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson,
                                  PracticeUnit, UserProgress)
from apps.practice.services.ai_translation import TranslationResult
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
P = '/api/v1/practice/'


def _audio():
    return SimpleUploadedFile('gravacao.webm', b'\x1a' * 4096, content_type='audio/webm')


def _veredicto(aceitavel=True):
    return TranslationResult(semantic_score=90, fluency_score=90, fidelity_score=90, overall_score=90,
                             is_acceptable=aceitavel, feedback='Boa.', suggestions=[], explanation='-',
                             partial_credit=10)


class Base(APITestCase):

    def setUp(self):
        cache.clear()  # throttles
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-seg@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-seg@example.com', name='Aluno', password='x', role='student')
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Inglês', description='-',
                                           course_type='practice', status='Published')
        self.rascunho = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Rascunho',
                                              description='-', course_type='practice', status='Draft')
        unidade = PracticeUnit.objects.create(course=self.curso, title='U1', description='', order=1)
        self.licao = PracticeLesson.objects.create(unit=unidade, title='L1', order=1)
        u2 = PracticeUnit.objects.create(course=self.rascunho, title='U2', description='', order=1)
        licao2 = PracticeLesson.objects.create(unit=u2, title='L2', order=1)

        self.falar = PracticeChallenge.objects.create(lesson=self.licao, type='SPEAKING', order=1,
                                                      question='Please check the valve pressure.')
        self.traduzir = PracticeChallenge.objects.create(lesson=self.licao, type='TRANSLATION', order=2,
                                                         question='O relatório está pronto.')
        ChallengeOption.objects.create(challenge=self.traduzir, text='The report is ready.', is_correct=True, order=1)
        self.escolher = PracticeChallenge.objects.create(lesson=self.licao, type='SELECT', order=3, question='?')
        self.falar_rascunho = PracticeChallenge.objects.create(lesson=licao2, type='SPEAKING', order=1,
                                                               question='Hidden sentence.')
        self.traduzir_rascunho = PracticeChallenge.objects.create(lesson=licao2, type='TRANSLATION', order=2,
                                                                  question='Escondido.')
        self.entrar(self.aluno)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def pronunciar(self, challenge=None, **extra):
        corpo = {'audio': _audio(), **extra}
        if challenge is not None:
            corpo['challenge_id'] = str(challenge.id)
        return self.client.post(f'{P}analyze-ai-pronunciation/', corpo, format='multipart')

    def traduzir_pedido(self, challenge, **extra):
        return self.client.post(f'{P}validate-ai-translation/',
                                {'challenge_id': str(challenge.id), 'user_translation': 'The report is ready.', **extra},
                                format='json')


@override_settings(PRONUNCIA_SIMULADA=True, DEBUG=True)
class PronunciaTests(Base):

    def test_frase_vem_da_base_de_dados_e_ignora_expected_text(self):
        r = self.pronunciar(self.falar, expected_text='hacked', frase='hacked')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['ai_analysis']['expected_text'], 'Please check the valve pressure.')

    def test_exige_exercicio(self):
        r = self.pronunciar(None, expected_text='Anything I want')
        self.assertEqual(r.status_code, 400)

    def test_exige_tipo_speaking(self):
        for ch in (self.escolher, self.traduzir):
            with self.subTest(tipo=ch.type):
                self.assertEqual(self.pronunciar(ch).status_code, 400)
        self.assertFalse(ChallengeProgress.objects.filter(user=self.aluno).exists())

    def test_curso_nao_publicado(self):
        self.assertEqual(self.pronunciar(self.falar_rascunho).status_code, 404)

    def test_id_invalido(self):
        r = self.client.post(f'{P}analyze-ai-pronunciation/', {'audio': _audio(), 'challenge_id': 'nao-e-uuid'},
                             format='multipart')
        self.assertEqual(r.status_code, 404)

    def test_repetir_nao_da_pontos(self):
        self.assertEqual(self.pronunciar(self.falar).status_code, 200)
        pontos = UserProgress.objects.get(user=self.aluno).points
        for _ in range(3):
            r = self.pronunciar(self.falar)
            self.assertEqual(r.json()['points_earned'], 0)
        self.assertEqual(UserProgress.objects.get(user=self.aluno).points, pontos)

    def test_limite_de_pedidos(self):
        codigos = [self.pronunciar(self.escolher).status_code for _ in range(21)]
        self.assertEqual(codigos[-1], 429)
        self.assertNotIn(429, codigos[:20])


class TraducaoTests(Base):

    def setUp(self):
        super().setUp()
        p = mock.patch('apps.practice.services.ai_translation.AITranslationValidator.validate_translation',
                       new_callable=mock.AsyncMock, return_value=_veredicto())
        self.validar = p.start()
        self.addCleanup(p.stop)
        mi = mock.patch('apps.practice.services.ai_translation.AITranslationValidator.__init__', return_value=None)
        mi.start()
        self.addCleanup(mi.stop)

    def test_texto_de_partida_vem_da_base_de_dados(self):
        r = self.traduzir_pedido(self.traduzir, source_text='Outra coisa qualquer')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.validar.call_args.kwargs['source_text'], 'O relatório está pronto.')
        self.assertEqual(r.json()['source_text'], 'O relatório está pronto.')

    def test_exige_tipo_traducao_e_acesso(self):
        self.assertEqual(self.traduzir_pedido(self.falar).status_code, 400)
        self.assertEqual(self.traduzir_pedido(self.traduzir_rascunho).status_code, 404)
        r = self.client.post(f'{P}validate-ai-translation/', {'source_text': 'x', 'user_translation': 'y'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.validar.assert_not_called()

    def test_so_devolve_o_veredicto_sem_vidas_nem_pontos(self):
        sub = UserSubscription.objects.get(user=self.aluno)
        sub.current_hearts = 2
        sub.save(update_fields=['current_hearts'])
        UserProgress.objects.create(user=self.aluno, points=0)
        # Exercício já feito (modo prática): antes cada pedido dava +1 vida e pontos.
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.traduzir, completed=True)
        for _ in range(5):
            self.assertEqual(self.traduzir_pedido(self.traduzir).status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.current_hearts, 2)
        self.assertEqual(UserProgress.objects.get(user=self.aluno).points, 0)
        # Resposta errada também não mexe nas vidas.
        self.validar.return_value = _veredicto(aceitavel=False)
        ChallengeProgress.objects.filter(user=self.aluno).delete()
        r = self.traduzir_pedido(self.traduzir)
        self.assertFalse(r.json()['ai_validation']['is_acceptable'])
        sub.refresh_from_db()
        self.assertEqual(sub.current_hearts, 2)
        self.assertFalse(ChallengeProgress.objects.filter(user=self.aluno).exists())

    def test_limite_de_pedidos(self):
        codigos = [self.traduzir_pedido(self.traduzir).status_code for _ in range(21)]
        self.assertEqual(codigos[-1], 429)
        self.assertNotIn(429, codigos[:20])


class VidasTests(Base):

    def _plano(self, tipo, vidas):
        return SubscriptionPlan.objects.update_or_create(plan_type=tipo, defaults=dict(
            name=tipo.title(), description='-', monthly_price=Decimal('0'), hearts_limit=vidas))[0]

    def test_vidas_nunca_passam_do_maximo_do_plano(self):
        plano = self._plano('FREE', 5)
        UserSubscription.objects.filter(user=self.aluno).update(
            plan=plano, current_hearts=999, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30))
        progresso = UserProgress.objects.create(user=self.aluno)
        self.assertEqual(progresso.hearts, 5)
        self.assertEqual(UserSubscription.objects.get(user=self.aluno).current_hearts, 5)

    def test_plano_ilimitado_que_terminou_vale_o_maximo_normal(self):
        plano = self._plano('PREMIUM', 0)
        UserSubscription.objects.filter(user=self.aluno).update(
            plan=plano, current_hearts=999, status='ACTIVE', expires_at=timezone.now() - timedelta(days=1))
        progresso = UserProgress.objects.create(user=self.aluno)
        self.assertEqual(progresso.hearts, 5)

    def test_plano_ilimitado_activo_mantem_ilimitado(self):
        plano = self._plano('PREMIUM', 0)
        UserSubscription.objects.filter(user=self.aluno).update(
            plan=plano, current_hearts=3, status='ACTIVE', expires_at=timezone.now() + timedelta(days=10))
        progresso = UserProgress.objects.create(user=self.aluno)
        self.assertEqual(progresso.hearts, 999)


class RotasRetiradasTests(Base):

    def test_consumo_e_verificacao_de_limites_ja_nao_existem(self):
        for url in ('/api/v1/subscriptions/consume-usage/', '/api/v1/subscriptions/check-access/'):
            with self.subTest(url=url):
                r = self.client.post(url, {'feature_type': 'hearts', 'amount': -500}, format='json')
                self.assertEqual(r.status_code, 404)

    def test_sessao_vapi_antiga_retirada_mesmo_sem_login(self):
        self.client.credentials()
        r = self.client.post(f'{P}vapi/session/', {'session_id': 'x', 'elapsed_seconds': 7200}, format='json')
        self.assertEqual(r.status_code, 404)


class WebhookVapiTests(APITestCase):
    URL = '/api/v1/practice/vapi/webhook/'

    def setUp(self):
        cache.clear()

    def enviar(self, segredo=None):
        extra = {'HTTP_X_VAPI_SECRET': segredo} if segredo is not None else {}
        return self.client.post(self.URL, {'message': {'type': 'transcript'}}, format='json', **extra)

    @override_settings(VAPI_WEBHOOK_SECRET='default_webhook_secret')
    def test_segredo_predefinido_nao_e_aceite(self):
        self.assertEqual(self.enviar('default_webhook_secret').status_code, 404)

    @override_settings(VAPI_WEBHOOK_SECRET='')
    def test_sem_segredo_nao_existe(self):
        self.assertEqual(self.enviar('').status_code, 404)

    @override_settings(VAPI_WEBHOOK_SECRET='s3gredo-proprio-123')
    def test_segredo_configurado(self):
        self.assertEqual(self.enviar().status_code, 403)
        self.assertEqual(self.enviar('errado').status_code, 403)
        self.assertEqual(self.enviar('s3gredo-proprio-123').status_code, 200)
