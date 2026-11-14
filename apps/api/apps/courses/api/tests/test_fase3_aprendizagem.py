"""
Fase 3 (aprendizagem do aluno, cursos de vídeo): regressões.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_fase3_aprendizagem
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseGradingConfig, CourseSection, GradeHistory,
    StudentCourseGrade, StudentQuizAttempt, UserCourseProgress, VideoWatchLog,
)
from apps.practice.models import DailyStudyLog, PracticeLesson, PracticeUnit, VapiSession
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
V = '/api/v1/student/video-courses'


def quiz_data(n=4, tentativas=2, aprovacao=70):
    return {
        'title': 'Quiz do professor',
        'settings': {'passingScore': aprovacao, 'maxAttempts': tentativas, 'pointsPerQuestion': 10},
        'questions': [
            {'id': f'q{i}', 'points': 10, 'question': f'P{i}?', 'explanation': f'Porque {i}.',
             'correctOptionId': 'a',
             'options': [{'id': 'a', 'text': 'Certa', 'isCorrect': True},
                         {'id': 'b', 'text': 'Errada', 'isCorrect': False}]}
            for i in range(1, n + 1)
        ],
    }


class Base(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-f3@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-f3@example.com', name='Aluno', password='x', role='student')
        self.outro = User.objects.create_user(email='outro-f3@example.com', name='Outro', password='x', role='student')
        self._plano(self.aluno, 'PREMIUM')
        self._plano(self.outro, 'PREMIUM')
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Reuniões em inglês',
                                           description='Reuniões de segurança', category='Petróleo',
                                           course_type='video', status='Published', access_level='premium')
        CourseGradingConfig.objects.create(course=self.curso, practice_enabled=False, conversation_enabled=False)
        self.sec = CourseSection.objects.create(course=self.curso, sectionTitle='S1', order=1)
        self.video = Chapter.objects.create(section=self.sec, title='Vídeo', content='x', type='Video',
                                            video='https://example.com/v.mp4', order=1)
        with self.captureOnCommitCallbacks(execute=True):
            self.cap_quiz = Chapter.objects.create(section=self.sec, title='Quiz', content='x', type='Quiz',
                                                   order=2, quiz_data=quiz_data())
        matricular_em_curso(self.aluno, self.curso)
        self.auth(self.aluno)

    def _plano(self, user, tipo):
        UserSubscription.objects.update_or_create(user=user, defaults=dict(
            plan=SubscriptionPlan.objects.get(plan_type=tipo), status='ACTIVE',
            expires_at=timezone.now() + timedelta(days=30)))

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def responder(self, certas=None, vazias=False):
        if vazias:
            respostas = {}
        else:
            respostas = {f'q{i}': ('a' if certas and i <= certas else 'b') for i in range(1, 5)}
        return self.client.post(f'{V}/chapters/{self.cap_quiz.id}/quiz/attempts/', {'respostas': respostas},
                                format='json')


# 1 ---------------------------------------------------------------------------
class QuizNaoRevelaRespostasTests(Base):

    def test_tentativa_falhada_com_tentativas_restantes_nao_revela(self):
        r = self.responder(certas=1)
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()['data']
        self.assertFalse(r.json()['revela_respostas'])
        self.assertFalse(d['revela_respostas'])
        for item in d['correccao']:
            self.assertEqual(set(item), {'pergunta', 'certa', 'respondida'})
        self.assertNotIn('Porque', r.content.decode())

    def test_tentativa_vazia_e_recusada(self):
        r = self.responder(vazias=True)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(StudentQuizAttempt.objects.filter(student=self.aluno).count(), 0)
        # Respostas para perguntas que não existem também não contam como respondidas.
        r = self.client.post(f'{V}/chapters/{self.cap_quiz.id}/quiz/attempts/', {'respostas': {'zz': 'a'}},
                             format='json')
        self.assertEqual(r.status_code, 400)

    def test_revela_quando_passa(self):
        d = self.responder(certas=3).json()  # 75% >= 70%
        self.assertTrue(d['revela_respostas'])
        self.assertEqual(d['data']['correccao'][3]['opcoes_certas'], ['a'])
        self.assertEqual(d['data']['correccao'][3]['explicacao'], 'Porque 4.')

    def test_revela_quando_esgota_tentativas_e_no_resumo(self):
        self.responder(certas=1)
        resumo = self.client.get(f'{V}/chapters/{self.cap_quiz.id}/quiz/summary/').json()
        self.assertFalse(resumo['revela_respostas'])
        self.assertNotIn('opcoes_certas', resumo['data']['last_attempt']['correccao'][0])
        d = self.responder(certas=0).json()
        self.assertTrue(d['revela_respostas'])
        self.assertEqual(d['data']['tentativas_restantes'], 0)
        self.assertIn('opcoes_certas', d['data']['correccao'][0])
        resumo = self.client.get(f'{V}/chapters/{self.cap_quiz.id}/quiz/summary/').json()
        self.assertTrue(resumo['data']['revela_respostas'])
        self.assertEqual(resumo['data']['last_attempt']['correccao'][0]['opcoes_certas'], ['a'])
        lista = self.client.get(f'{V}/chapters/{self.cap_quiz.id}/quiz/attempts/').json()
        self.assertTrue(lista['revela_respostas'])
        self.assertEqual(len(lista['data']), 2)


# 2 ---------------------------------------------------------------------------
class QuizDoProfessorTests(Base):

    def test_capitulo_quiz_cria_chapter_quiz_com_as_definicoes(self):
        quiz = ChapterQuiz.objects.get(chapter=self.cap_quiz)
        self.assertIsNone(quiz.practice_lesson)
        self.assertEqual((quiz.passing_score, quiz.max_attempts, quiz.points_reward, quiz.is_active),
                         (70, 2, 40, True))
        self.assertEqual(quiz.created_by, self.prof)
        self.assertEqual(self.responder(certas=4).status_code, 201)

    def test_editar_e_deixar_de_ser_quiz(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.cap_quiz.quiz_data = quiz_data(tentativas=5, aprovacao=50)
            self.cap_quiz.save()
        quiz = ChapterQuiz.objects.get(chapter=self.cap_quiz)
        self.assertEqual((quiz.max_attempts, quiz.passing_score), (5, 50))
        with self.captureOnCommitCallbacks(execute=True):
            self.cap_quiz.type = 'Text'
            self.cap_quiz.quiz_enabled = False
            self.cap_quiz.save()
        self.assertFalse(ChapterQuiz.objects.get(chapter=self.cap_quiz).is_active)

    def test_comando_cria_os_que_faltam(self):
        cap = Chapter.objects.create(section=self.sec, title='Quiz antigo', content='x', type='Quiz', order=3,
                                     quiz_data=quiz_data())  # sem on_commit: como os antigos
        self.assertFalse(ChapterQuiz.objects.filter(chapter=cap).exists())
        call_command('sincronizar_questionarios', stdout=mock.MagicMock())
        self.assertTrue(ChapterQuiz.objects.filter(chapter=cap, is_active=True).exists())
        call_command('sincronizar_questionarios', stdout=mock.MagicMock())  # idempotente
        self.assertEqual(ChapterQuiz.objects.filter(chapter=cap).count(), 1)

    def test_quiz_semeado_sem_quiz_data_fica_activo(self):
        unidade = PracticeUnit.objects.create(course=self.curso, title='U', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        cap = Chapter.objects.create(section=self.sec, title='Semeado', content='x', type='Quiz', order=4)
        ChapterQuiz.objects.create(chapter=cap, practice_lesson=licao, title='Q', created_by=self.prof)
        call_command('sincronizar_questionarios', stdout=mock.MagicMock())
        self.assertTrue(ChapterQuiz.objects.get(chapter=cap).is_active)

    def test_resumo_exige_inscricao(self):
        self.auth(self.outro)  # tem plano mas não está inscrito
        r = self.client.get(f'{V}/chapters/{self.cap_quiz.id}/quiz/summary/')
        self.assertEqual(r.status_code, 403)
        self.auth(self.aluno)
        r = self.client.get(f'{V}/chapters/{self.cap_quiz.id}/quiz/summary/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['data']['attempts_remaining'], 2)


# 3 + 4 -------------------------------------------------------------------------
class NotasTests(Base):

    def test_notas_so_de_cursos_de_video_publicados(self):
        pratica = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Prática', course_type='practice',
                                        status='Published')
        rascunho = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Rascunho', course_type='video',
                                         status='Draft')
        matricular_em_curso(self.aluno, pratica)
        matricular_em_curso(self.aluno, rascunho)
        cursos = [c['course']['id'] for c in self.client.get(f'{V}/grades/all/').json()['data']['courses']]
        self.assertEqual(cursos, [str(self.curso.id)])

    def test_elegibilidade_inclui_conclusao_do_curso(self):
        self.responder(certas=4)  # nota 100%, mas o vídeo não foi visto
        d = self.client.get(f'{V}/{self.curso.id}/grade/').json()['data']
        el = d['certificate_eligibility']
        self.assertFalse(el['is_eligible'])
        self.assertFalse(el['pode_emitir'])
        self.assertIn('conclusao_curso', [m['requirement'] for m in el['missing_requirements']])
        self.assertIn('conclusao_curso', [m['requisito'] for m in el['em_falta']])
        self.assertEqual((d['nota_minima'], d['plano_inclui_certificados']), (70.0, True))
        todas = self.client.get(f'{V}/grades/all/').json()['data']
        self.assertFalse(todas['courses'][0]['is_eligible_for_certificate'])

        prog = UserCourseProgress.objects.get(user=self.aluno, course=self.curso)
        ChapterProgress.objects.filter(user_progress=prog).update(completed=True)
        el = self.client.get(f'{V}/{self.curso.id}/grade/').json()['data']['certificate_eligibility']
        self.assertTrue(el['is_eligible'])
        self.assertEqual(el['missing_requirements'], [])

    def test_plano_sem_certificados(self):
        self._plano(self.aluno, 'FREE')
        self.curso.access_level = 'free'
        self.curso.save()
        d = self.client.get(f'{V}/{self.curso.id}/grade/').json()['data']
        self.assertFalse(d['plano_inclui_certificados'])
        self.assertFalse(d['certificate_eligibility']['pode_emitir'])


# 5 ---------------------------------------------------------------------------
class InscritosOrdemTests(Base):

    def test_ultimo_acedido_primeiro(self):
        outro_curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Novo', course_type='video',
                                            status='Published')
        matricular_em_curso(self.aluno, outro_curso)  # inscrito depois
        antigo = UserCourseProgress.objects.get(user=self.aluno, course=self.curso)
        antigo.save()  # acedido agora (lastAccessedTimestamp)
        UserCourseProgress.objects.filter(user=self.aluno, course=outro_curso).update(
            lastAccessedTimestamp=timezone.now() - timedelta(days=2))
        ids = [c['courseId'] for c in self.client.get(f'{V}/users/{self.aluno.id}/enrolled/').json()['data']]
        self.assertEqual(ids, [str(self.curso.id), str(outro_curso.id)])


# 6 ---------------------------------------------------------------------------
class CatalogoTests(Base):

    def setUp(self):
        super().setUp()
        for i in range(14):
            Course.objects.create(teacher=self.prof, teacherName='Prof', title=f'Curso {i}', description='geral',
                                  category='Geral', course_type='video', status='Published')

    def test_pesquisa_no_servidor_em_todas_as_paginas(self):
        r = self.client.get(f'{V}/', {'search': 'segurança', 'status': 'Published'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c['title'] for c in r.json()['data']['results']], ['Reuniões em inglês'])
        r = self.client.get(f'{V}/', {'search': 'petról'})
        self.assertEqual(r.json()['data']['count'], 1)

    def test_page_size_ate_50(self):
        d = self.client.get(f'{V}/').json()['data']
        self.assertEqual((d['count'], len(d['results'])), (15, 12))
        d = self.client.get(f'{V}/', {'page_size': 50}).json()['data']
        self.assertEqual(len(d['results']), 15)
        d = self.client.get(f'{V}/', {'page_size': 500}).json()['data']
        self.assertEqual(d['page_size'], 50)

    def test_ordenacao_so_da_lista(self):
        self.assertEqual(self.client.get(f'{V}/', {'ordering': 'nao_existe'}).status_code, 200)
        self.assertEqual(self.client.get(f'{V}/', {'ordering': 'teacher__password'}).status_code, 200)
        titulos = [c['title'] for c in self.client.get(f'{V}/', {'ordering': 'title', 'page_size': 50})
                   .json()['data']['results']]
        self.assertEqual(titulos, sorted(titulos))


# 7 + 12 ------------------------------------------------------------------------
class ProgressoTests(Base):

    def test_progresso_calculado_na_leitura_e_actualizado_quando_muda_o_curso(self):
        prog = UserCourseProgress.objects.get(user=self.aluno, course=self.curso)
        ChapterProgress.objects.filter(user_progress=prog).update(completed=True)
        UserCourseProgress.objects.filter(pk=prog.pk).update(overallProgress=100.0)
        with self.captureOnCommitCallbacks(execute=True):
            Chapter.objects.create(section=self.sec, title='Novo', content='x', type='Text', order=3)
        d = self.client.get(f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/').json()['data']
        self.assertAlmostEqual(d['overallProgress'], 200 / 3)
        prog.refresh_from_db()
        self.assertAlmostEqual(prog.overallProgress, 200 / 3)
        self.assertEqual(len(d['sections'][0]['chapters']), 3)

    def test_secoes_sem_uma_consulta_por_capitulo(self):
        for i in range(10):
            Chapter.objects.create(section=self.sec, title=f'C{i}', content='x', type='Text', order=10 + i)
        url = f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/'
        with CaptureQueriesContext(connection) as q:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertLess(len(q.captured_queries), 15)

    def test_lista_de_certificados_nao_escreve(self):
        self.responder(certas=4)
        notas = StudentCourseGrade.objects.get(user=self.aluno, course=self.curso)
        historico = GradeHistory.objects.count()
        antes = notas.last_calculated_at
        r = self.client.get(f'{V}/certificados/')
        self.assertEqual(r.status_code, 200)
        notas.refresh_from_db()
        self.assertEqual(notas.last_calculated_at, antes)
        self.assertEqual(GradeHistory.objects.count(), historico)
        em_curso = r.json()['em_curso'][0]
        self.assertIn('conclusao_curso', [m['requisito'] for m in em_curso['em_falta']])


# 8 ---------------------------------------------------------------------------
class MinutosDeVideoTests(Base):

    def put(self, segundos, **extra):
        corpo = {'sections': [{'sectionId': str(self.sec.id), 'chapters': [
            {'chapterId': str(self.video.id), 'completed': False}]}], 'watched_seconds': segundos, **extra}
        return self.client.put(f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/update/', corpo, format='json')

    def minutos(self):
        log = DailyStudyLog.objects.filter(user=self.aluno).first()
        return log.video_minutes if log else 0

    def test_valor_absurdo_limitado_e_reenvio_nao_soma(self):
        r = self.put(99999)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['segundos_creditados'], 30 * 60)
        self.assertEqual(self.minutos(), 30)
        for _ in range(3):
            self.assertEqual(self.put(99999).json()['segundos_creditados'], 0)
        self.assertEqual(self.minutos(), 30)

    def test_duracao_conhecida_e_tempo_real(self):
        self.video.metadata = {'duration_seconds': 300}
        self.video.save()
        self.assertEqual(self.put(1000).json()['segundos_creditados'], 300)
        self.assertEqual(self.minutos(), 5)
        # Outro capítulo, segundo envio logo a seguir: só conta o tempo que passou.
        self.video.metadata = {}
        self.video.save()
        VideoWatchLog.objects.filter(user=self.aluno).update(seconds=60)
        self.assertLessEqual(self.put(600).json()['segundos_creditados'], 20)

    def test_sem_capitulo_nao_conta(self):
        r = self.client.put(f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/update/',
                            {'sections': [], 'watched_seconds': 120}, format='json')
        self.assertEqual(r.json()['segundos_creditados'], 0)
        r = self.client.put(f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/update/',
                            {'sections': [], 'watched_seconds': 120, 'chapter_id': str(self.video.id)}, format='json')
        self.assertEqual(r.json()['segundos_creditados'], 120)


# 11 --------------------------------------------------------------------------
class MinutosConversaNaNotaTests(Base):

    def test_minutos_da_nota_sao_os_segundos_reais(self):
        cfg = self.curso.grading_config
        cfg.conversation_enabled = True
        cfg.require_conversation_if_available = True
        cfg.save()
        self.curso.level = 'Intermediate'
        self.curso.save()
        VapiSession.objects.create(session_id='f3-a', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=8, duration_seconds=330, overall_score=70)
        VapiSession.objects.create(session_id='f3-b', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=2, overall_score=80)  # antiga, sem segundos
        conv = self.client.get(f'{V}/{self.curso.id}/grade/').json()['data']['grades']['conversation']
        self.assertEqual((conv['sessions'], conv['minutes']), (2, round((330 + 120) / 60)))


# 13 --------------------------------------------------------------------------
class TextosPtTests(Base):

    def test_mensagens_sem_pt_br(self):
        self.auth(self.outro)
        r = self.client.get(f'{V}/chapters/{self.video.id}/')
        self.assertEqual(r.status_code, 403)
        self.assertIn('Precisa de estar inscrito', r.content.decode())
        r = self.client.get(f'{V}/{self.curso.id}/grade/')
        self.assertNotIn('Você', r.content.decode())
        self.auth(self.aluno)
        r = self.responder(certas=4)
        self.assertEqual(r.json()['message'], 'Tentativa registada com sucesso')
