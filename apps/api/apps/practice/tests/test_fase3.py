"""
Fase 3 (aprendizagem do aluno, laboratório de prática): regressões.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_fase3

Nenhum teste chama a OpenAI: o analisador é substituído por um mock.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice import study_services
from apps.practice.models import (
    ChallengeOption, ChallengeProgress, DailyStudyLog, LessonCompletion, PracticeChallenge, PracticeLesson,
    PracticeUnit, UserProgress, VapiSession,
)
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
P = '/api/v1/student/practice-courses/'
ANALISE = '/api/v1/practice/analyze-ai-pronunciation/'


class Base(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-p3@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-p3@example.com', name='Aluno', password='x', role='student')
        self.free = SubscriptionPlan.objects.get(plan_type='FREE')
        self.sub = UserSubscription.objects.get(user=self.aluno)
        UserSubscription.objects.filter(pk=self.sub.pk).update(plan=self.free, status='ACTIVE')
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Prática', description='-',
                                           course_type='practice', status='Published', access_level='free')
        unidade = PracticeUnit.objects.create(course=self.curso, title='U1', description='', order=1)
        self.l1 = PracticeLesson.objects.create(unit=unidade, title='L1', order=1)
        self.l2 = PracticeLesson.objects.create(unit=unidade, title='L2', order=2)
        self.c1 = self._select(self.l1, 1)
        self.c2 = self._select(self.l2, 1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.aluno).access_token}')

    def _select(self, licao, ordem):
        ch = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question=f'Q{licao.title}', order=ordem)
        ch.certa = ChallengeOption.objects.create(challenge=ch, text='certa', is_correct=True, order=1)
        ch.errada = ChallengeOption.objects.create(challenge=ch, text='errada', is_correct=False, order=2)
        return ch

    def responder(self, ch, certo=True):
        ChallengeProgress.objects.filter(user=self.aluno, challenge=ch).update(
            updated_at=timezone.now() - timedelta(seconds=30))
        return self.client.post(f'{P}challenge-progress/', {
            'challenge_id': str(ch.id), 'selected_option': str((ch.certa if certo else ch.errada).id)},
            format='json')


# 9 ---------------------------------------------------------------------------
class VidasTests(Base):

    def test_vida_perdida_nao_volta_logo(self):
        # Vidas no máximo e o relógio parado há dias.
        UserSubscription.objects.filter(pk=self.sub.pk).update(
            current_hearts=self.free.hearts_limit, last_heart_recharge=timezone.now() - timedelta(days=5))
        r = self.responder(self.c1, certo=False)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['user_progress']['hearts'], self.free.hearts_limit - 1)
        estado = self.client.get(f'{P}hearts-status/').json()
        self.assertEqual(estado['current'], self.free.hearts_limit - 1)
        self.assertIsNotNone(estado['next_heart_at'])

    def test_recarga_guarda_o_tempo_que_sobra(self):
        horas = self.free.hearts_recharge_hours
        UserSubscription.objects.filter(pk=self.sub.pk).update(
            current_hearts=0, last_heart_recharge=timezone.now() - timedelta(hours=horas * 1.5))
        sub = UserSubscription.objects.select_related('plan').get(pk=self.sub.pk)
        sub.recharge_hearts_if_needed()
        self.assertEqual(sub.current_hearts, 1)
        self.assertLess(timezone.now() - sub.last_heart_recharge, timedelta(hours=horas))
        self.assertGreater(timezone.now() - sub.last_heart_recharge, timedelta(hours=horas * 0.4))

    def test_repeticao_com_vidas_cheias_nao_da_vida(self):
        UserSubscription.objects.filter(pk=self.sub.pk).update(current_hearts=self.free.hearts_limit)
        self.responder(self.c1)
        self.client.post(f'{P}complete-lesson/', {'lesson_id': str(self.l1.id)}, format='json')
        ChallengeProgress.objects.filter(user=self.aluno).update(updated_at=timezone.now() + timedelta(seconds=5))
        r = self.client.post(f'{P}complete-lesson/', {'lesson_id': str(self.l1.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['points_awarded'], study_services.REPEAT_PRACTICE_POINTS)
        self.assertEqual(r.json()['hearts_awarded'], 0)

    def test_repeticao_sem_vidas_cheias_da_vida(self):
        self.responder(self.c1)
        self.client.post(f'{P}complete-lesson/', {'lesson_id': str(self.l1.id)}, format='json')
        UserSubscription.objects.filter(pk=self.sub.pk).update(current_hearts=1, last_heart_recharge=timezone.now())
        ChallengeProgress.objects.filter(user=self.aluno).update(updated_at=timezone.now() + timedelta(seconds=5))
        r = self.client.post(f'{P}complete-lesson/', {'lesson_id': str(self.l1.id)}, format='json')
        self.assertEqual(r.json()['hearts_awarded'], 1)
        self.assertEqual(r.json()['hearts'], 2)


# 10 --------------------------------------------------------------------------
class LicaoBloqueadaTests(Base):

    def test_licao_bloqueada_nao_abre_nem_responde(self):
        r = self.client.get(f'{P}lessons/{self.l2.id}/jogar/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), {'codigo': 'licao_bloqueada',
                                    'mensagem': 'Termine as lições anteriores para abrir esta.'})
        r = self.responder(self.c2)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'licao_bloqueada')
        self.assertFalse(ChallengeProgress.objects.filter(user=self.aluno, challenge=self.c2).exists())
        # Depois de fazer a primeira, a segunda abre e a primeira pode ser repetida.
        self.assertEqual(self.responder(self.c1).status_code, 200)
        self.assertEqual(self.client.get(f'{P}lessons/{self.l2.id}/jogar/').status_code, 200)
        self.assertEqual(self.client.get(f'{P}lessons/{self.l1.id}/jogar/').status_code, 200)
        trilho = self.client.get(f'{P}courses/{self.curso.id}/trilho/').json()
        self.assertEqual([l['estado'] for l in trilho['unidades'][0]['licoes']], ['feita', 'actual'])

    def test_curso_premium_com_plano_gratuito(self):
        self.curso.access_level = 'premium'
        self.curso.save()
        r = self.client.get(f'{P}lessons/{self.l1.id}/jogar/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'plano_insuficiente')
        self.assertEqual(self.responder(self.c1).status_code, 403)

    def test_pronuncia_de_licao_bloqueada(self):
        falar = PracticeChallenge.objects.create(lesson=self.l2, type='SPEAKING', question='Hello there.', order=2)
        audio = SimpleUploadedFile('g.webm', b'\x00' * 4096, content_type='audio/webm')
        r = self.client.post(ANALISE, {'challenge_id': str(falar.id), 'audio': audio}, format='multipart')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'licao_bloqueada')


# 11 --------------------------------------------------------------------------
class MinutosConversaTests(Base):

    def test_estatisticas_usam_uma_so_fonte_de_minutos(self):
        hoje = timezone.localdate()
        DailyStudyLog.objects.create(user=self.aluno, date=hoje, conversation_minutes=5.5)
        VapiSession.objects.create(session_id='p3-s1', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=9, overall_score=70)
        d = self.client.get(f'{P}estatisticas/', {'periodo': '7'}).json()
        self.assertEqual(d['conversacao']['sessoes'], 1)
        self.assertEqual(d['conversacao']['minutos'], d['tempo_estudo']['por_tipo']['conversacao'])
        self.assertEqual(d['conversacao']['minutos'], 6)


# 13 --------------------------------------------------------------------------
class TextosTests(Base):

    def test_vidas_cheias_e_pontos_sem_tu(self):
        UserSubscription.objects.filter(pk=self.sub.pk).update(current_hearts=self.free.hearts_limit)
        payload, erro = study_services.refill_hearts_with_points(self.aluno)
        self.assertTrue(erro)
        self.assertEqual(payload['message'], 'As suas vidas já estão no máximo.')
        UserSubscription.objects.filter(pk=self.sub.pk).update(current_hearts=0, last_heart_recharge=timezone.now())
        payload, _ = study_services.refill_hearts_with_points(self.aluno)
        self.assertIn('Precisa de', payload['message'])


# 14 --------------------------------------------------------------------------
@override_settings(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test')
class PronunciaIndisponivelTests(Base):

    def setUp(self):
        super().setUp()
        self.falar = PracticeChallenge.objects.create(lesson=self.l1, type='SPEAKING', question='Hello there.', order=2)

    def analisar(self):
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer

        async def falha(self_, audio_file, expected_text, difficulty_level='intermediate'):
            return self_._create_fallback_result(expected_text)

        audio = SimpleUploadedFile('g.webm', b'\x00' * 4096, content_type='audio/webm')
        with mock.patch.object(AIPronunciationAnalyzer, '__init__', lambda s: None), \
                mock.patch.object(AIPronunciationAnalyzer, 'analyze_pronunciation', falha):
            return self.client.post(ANALISE, {'challenge_id': str(self.falar.id), 'audio': audio}, format='multipart')

    def test_modelo_actual(self):
        # A análise pelo texto passou para o Claude (PRONUNCIA_CLAUDE_MODELO).
        from apps.practice.services import ai_pronunciation
        with override_settings(PRONUNCIA_CLAUDE_MODELO='claude-opus-5-5'):
            self.assertEqual(ai_pronunciation.modelo_de_analise(), 'claude-opus-5-5')
        with override_settings(PRONUNCIA_CLAUDE_MODELO='claude-haiku-5-5'):
            self.assertEqual(ai_pronunciation.modelo_de_analise(), 'claude-haiku-5-5')

    def test_falha_do_modelo_e_indisponivel(self):
        import asyncio
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
        a = AIPronunciationAnalyzer.__new__(AIPronunciationAnalyzer)
        with mock.patch('apps.practice.conversa.analise._json', side_effect=RuntimeError('404 model')):
            r = asyncio.run(a._analyze_with_gpt4('hello there', 'Hello there.', 'intermediate'))
        self.assertTrue(r.indisponivel)

    def test_503_e_saltar_sem_pontos_nem_vidas(self):
        progresso = UserProgress.objects.get_or_create(user=self.aluno)[0]
        vidas, pontos = progresso.hearts, progresso.points
        r = self.analisar()
        self.assertEqual(r.status_code, 503)
        d = r.json()
        self.assertEqual(d['codigo'], 'analise_indisponivel')
        self.assertTrue(d['pode_saltar'])

        # Sem token (ou com token de outro exercício) não salta.
        r = self.client.post(f'{P}challenge-progress/', {'challenge_id': str(self.falar.id), 'saltar': True},
                             format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['codigo'], 'analise_disponivel')
        r = self.client.post(f'{P}challenge-progress/', {'challenge_id': str(self.c1.id), 'saltar': True,
                                                         'token_saltar': d['token_saltar']}, format='json')
        self.assertEqual(r.status_code, 400)

        r = self.client.post(f'{P}challenge-progress/', {'challenge_id': str(self.falar.id), 'saltar': True,
                                                         'token_saltar': d['token_saltar']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['saltado'])
        cp = ChallengeProgress.objects.get(user=self.aluno, challenge=self.falar)
        self.assertTrue(cp.completed and cp.skipped)
        progresso.refresh_from_db()
        self.assertEqual((progresso.hearts, progresso.points), (vidas, pontos))

        # Conta como feito: a lição pode ser concluída.
        self.responder(self.c1)
        r = self.client.post(f'{P}complete-lesson/', {'lesson_id': str(self.l1.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(LessonCompletion.objects.filter(user=self.aluno, lesson=self.l1).exists())

    @override_settings(OPENAI_API_KEY='')
    def test_sem_chave_configurada_pode_saltar_sem_token(self):
        r = self.client.post(f'{P}challenge-progress/', {'challenge_id': str(self.falar.id), 'saltar': True},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
