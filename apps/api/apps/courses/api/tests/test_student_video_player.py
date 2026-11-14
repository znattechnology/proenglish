"""
Regressões do leitor de cursos de vídeo do aluno (capítulo, comentários, quiz, progresso, notas).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseSection, StudentQuizAttempt, UserCourseProgress,
)
from apps.practice.models import PracticeChallenge, PracticeLesson, PracticeUnit
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
BASE = '/api/v1/student/video-courses'


class StudentVideoPlayerTests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(email='prof-player@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-player@example.com', name='Aluno', password='x', role='student')
        self.gratuito = User.objects.create_user(email='free-player@example.com', name='Free', password='x', role='student')
        premium, _ = SubscriptionPlan.objects.get_or_create(
            plan_type='PREMIUM', defaults={'name': 'Premium'},
        )
        UserSubscription.objects.update_or_create(
            user=self.aluno, defaults={'plan': premium, 'status': 'ACTIVE',
                                       'expires_at': timezone.now() + timedelta(days=30)},
        )
        self.course = Course.objects.create(
            teacher=self.teacher, teacherName='Prof', title='Reuniões', course_type='video',
            status='Published', access_level='premium',
        )
        sec = CourseSection.objects.create(course=self.course, sectionTitle='Secção 1', order=1)
        self.ch1 = Chapter.objects.create(section=sec, title='Vídeo', content='x', type='Video',
                                          video='https://example.com/v.mp4', order=1)
        self.ch_quiz = Chapter.objects.create(section=sec, title='Quiz', content='x', type='Quiz', order=2, quiz_data={
            'settings': {'passingScore': 70, 'maxAttempts': 2},
            'questions': [
                {'id': f'q{i}', 'points': 10, 'question': f'P{i}?', 'explanation': f'Porque {i}.',
                 'correctOptionId': 'a',
                 'options': [{'id': 'a', 'text': 'Certa', 'isCorrect': True},
                             {'id': 'b', 'text': 'Errada', 'isCorrect': False}]}
                for i in range(1, 5)
            ],
        })
        unit = PracticeUnit.objects.create(course=self.course, title='U', description='', order=1)
        lesson = PracticeLesson.objects.create(unit=unit, title='L', order=1)
        PracticeChallenge.objects.create(lesson=lesson, type='SELECT', question='Q?', order=1)
        self.quiz = ChapterQuiz.objects.create(chapter=self.ch_quiz, practice_lesson=lesson, title='Quiz',
                                               created_by=self.teacher, max_attempts=2, passing_score=70)
        matricular_em_curso(self.aluno, self.course)

        other = Course.objects.create(teacher=self.teacher, teacherName='Prof', title='Outro',
                                      course_type='video', status='Published', access_level='free')
        osec = CourseSection.objects.create(course=other, sectionTitle='S', order=1)
        self.other_chapter = Chapter.objects.create(section=osec, title='Outro', content='x', type='Text', order=1)
        self.auth(self.aluno)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def attempt(self, certas=3, **extra):
        """Responde ao quiz de 4 perguntas acertando `certas` (cada uma vale 10 pontos)."""
        respostas = {f'q{i}': ('a' if i <= certas else 'b') for i in range(1, 5)}
        return self.client.post(f'{BASE}/chapters/{self.ch_quiz.id}/quiz/attempts/',
                                {'respostas': respostas, **extra}, format='json')

    def test_chapter_detail_for_enrolled_student(self):
        resp = self.client.get(f'{BASE}/chapters/{self.ch1.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['video'], 'https://example.com/v.mp4')

    def test_comment_post_without_user_in_body(self):
        resp = self.client.post(f'{BASE}/chapters/{self.ch1.id}/comments/', {'text': 'Olá'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['user'], str(self.aluno.id))

    def test_comments_require_access(self):
        self.auth(self.gratuito)
        self.assertEqual(self.client.get(f'{BASE}/chapters/{self.ch1.id}/comments/').status_code, 403)
        resp = self.client.post(f'{BASE}/chapters/{self.ch1.id}/comments/', {'text': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_quiz_attempt_uses_url_quiz_and_enforces_limit(self):
        self.assertEqual(self.attempt().status_code, 201)
        self.assertEqual(self.attempt().status_code, 201)
        resp = self.attempt()
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(StudentQuizAttempt.objects.filter(student=self.aluno, chapter_quiz=self.quiz).count(), 2)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.total_attempts, 2)

    def test_quiz_attempt_is_passed_decided_by_server(self):
        self.assertFalse(self.attempt(certas=1).json()['data']['is_passed'])  # 25% < 70%
        self.assertTrue(self.attempt(certas=3).json()['data']['is_passed'])   # 75%

    def test_quiz_corrigido_no_servidor_ignora_pontuacao_do_browser(self):
        resp = self.attempt(certas=1, score=40, max_score=40, is_passed=True)
        self.assertEqual(resp.status_code, 201, resp.content)
        dados = resp.json()['data']
        self.assertEqual((dados['score'], dados['max_score']), (10, 40))
        self.assertFalse(dados['is_passed'])
        self.assertEqual(len(dados['correccao']), 4)
        self.assertTrue(dados['correccao'][0]['certa'])
        self.assertFalse(dados['correccao'][1]['certa'])
        # Não passou e ainda tem 1 tentativa: a correcção não revela as opções certas.
        self.assertFalse(dados['revela_respostas'])
        self.assertNotIn('opcoes_certas', dados['correccao'][1])
        self.assertNotIn('explicacao', dados['correccao'][1])
        self.assertEqual(dados['tentativas_restantes'], 1)
        # Sem respostas não há tentativa
        sem = self.client.post(f'{BASE}/chapters/{self.ch_quiz.id}/quiz/attempts/', {'score': 40, 'max_score': 40}, format='json')
        self.assertEqual(sem.status_code, 400)

    def test_respostas_do_quiz_nunca_vao_para_o_browser(self):
        resp = self.client.get(f'{BASE}/chapters/{self.ch_quiz.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        texto = resp.content.decode()
        self.assertNotIn('isCorrect', texto)
        self.assertNotIn('correctOptionId', texto)
        self.assertNotIn('Porque 1.', texto)
        self.assertEqual(len(resp.json()['quiz_data']['questions']), 4)
        detalhe = self.client.get(f'{BASE}/{self.course.id}/').content.decode()
        self.assertNotIn('isCorrect', detalhe)

    def test_sem_inscricao_ve_so_a_estrutura(self):
        # Tem o plano mas não está inscrito: vê títulos e tipos, não o conteúdo.
        outro = User.objects.create_user(email='premium2@example.com', name='P2', password='x', role='student')
        premium = SubscriptionPlan.objects.get(plan_type='PREMIUM')
        UserSubscription.objects.update_or_create(user=outro, defaults={
            'plan': premium, 'status': 'ACTIVE', 'expires_at': timezone.now() + timedelta(days=30)})
        self.auth(outro)
        dados = self.client.get(f'{BASE}/{self.course.id}/').json()
        curso = dados.get('data', dados)
        capitulo = curso['sections'][0]['chapters'][0]
        self.assertEqual(capitulo['title'], 'Vídeo')
        self.assertNotIn('video', capitulo)
        self.assertNotIn('content', capitulo)
        self.assertEqual(curso['enrollments'], [])
        lista = self.client.get(f'{BASE}/sections/{self.ch1.section_id}/chapters/').json()
        capitulos = lista['results'] if isinstance(lista, dict) else lista
        self.assertEqual(capitulos[0]['title'], 'Vídeo')
        self.assertNotIn('video', capitulos[0])

    def test_quiz_attempt_requires_enrollment(self):
        self.auth(self.gratuito)
        self.assertEqual(self.attempt().status_code, 403)

    def test_progress_update_requires_plan_access(self):
        self.auth(self.gratuito)
        url = f'{BASE}/users/{self.gratuito.id}/progress/{self.course.id}/update/'
        body = {'sections': [{'chapters': [{'chapterId': str(self.ch1.id), 'completed': True}]}]}
        self.assertEqual(self.client.put(url, body, format='json').status_code, 403)
        self.assertFalse(UserCourseProgress.objects.filter(user=self.gratuito).exists())

    def test_progress_update_ignores_chapters_of_other_courses(self):
        url = f'{BASE}/users/{self.aluno.id}/progress/{self.course.id}/update/'
        body = {'sections': [{'chapters': [
            {'chapterId': str(self.ch1.id), 'completed': True},
            {'chapterId': str(self.other_chapter.id), 'completed': True},
            {'chapterId': 'nao-e-uuid', 'completed': True},
        ]}]}
        resp = self.client.put(url, body, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['data']['overallProgress'], 50.0)
        self.assertFalse(ChapterProgress.objects.filter(chapter=self.other_chapter).exists())

    def test_course_grade_with_quiz(self):
        self.attempt(certas=4)
        resp = self.client.get(f'{BASE}/{self.course.id}/grade/')
        self.assertEqual(resp.status_code, 200, resp.content)
        quizzes = resp.json()['data']['grades']['quizzes']
        self.assertEqual(quizzes['score'], 100.0)
        self.assertEqual(quizzes['details'][0]['section_title'], 'Secção 1')
        self.assertEqual(resp.json()['data']['grades']['practice']['count'], 1)
        self.assertEqual(self.client.get(f'{BASE}/grades/all/').status_code, 200)


class InscricaoSemCustoTests(APITestCase):
    """Os cursos estão incluídos nos planos: a inscrição não pede valor nem identificador ao cliente."""

    def setUp(self):
        self.teacher = User.objects.create_user(email='prof-insc@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-insc@example.com', name='Aluno', password='x', role='student')
        self.gratis = Course.objects.create(teacher=self.teacher, teacherName='Prof', title='Grátis', course_type='video',
                                            status='Published', access_level='free')
        self.premium = Course.objects.create(teacher=self.teacher, teacherName='Prof', title='Premium', course_type='video',
                                             status='Published', access_level='premium')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.aluno).access_token}')

    def test_inscricao_so_com_o_curso(self):
        from apps.courses.models import CourseEnrollment, Transaction
        r = self.client.post(f'{BASE}/transactions/create/', {'courseId': str(self.gratis.id), 'amount': 9999}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.gratis).exists())
        self.assertEqual(Transaction.objects.get(user=self.aluno).amount, 0)

    def test_plano_insuficiente_nao_inscreve(self):
        from apps.courses.models import CourseEnrollment
        r = self.client.post(f'{BASE}/transactions/create/', {'courseId': str(self.premium.id)}, format='json')
        self.assertIn(r.status_code, (400, 403))
        self.assertFalse(CourseEnrollment.objects.filter(user=self.aluno, course=self.premium).exists())
