"""Testes do progresso dos alunos visto pelo professor (prática e vídeo)."""
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.courses.models import Chapter, Course, CourseEnrollment, CourseSection, UserCourseProgress
from apps.courses.models.enrollment import ChapterProgress
from apps.courses.api.tests.test_student_study_tracking import StudyTrackingTestBase

User = get_user_model()


class AlunosCursoPraticaTests(StudyTrackingTestBase):
    url = "/api/v1/practice/student-progress/"

    def test_professor_ve_alunos_com_progresso_real(self):
        self.authenticate(self.student)
        self.answer(self.ch1)
        self.answer(self.ch2, correct=False)
        self.answer(self.ch2)
        self.complete()

        self.authenticate(self.teacher)
        r = self.client.get(self.url, {"course": str(self.course.id)})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        aluno = r.json()[0]
        self.assertEqual(aluno["student_id"], str(self.student.id))
        self.assertEqual(aluno["completed_lessons"], 1)
        self.assertEqual(aluno["total_lessons"], 2)
        self.assertEqual(aluno["progress_percentage"], 50)
        self.assertEqual(aluno["average_accuracy"], 67)  # 2 certas em 3 respostas
        self.assertIsNotNone(aluno["last_activity"])

    def test_outro_professor_nao_ve(self):
        outro = User.objects.create_user(email="outro-prof@example.com", name="Outro", password="password123", role="teacher")
        self.authenticate(outro)
        self.assertEqual(self.client.get(self.url, {"course": str(self.course.id)}).status_code, 403)

    def test_estudante_nao_ve(self):
        self.authenticate(self.student)
        self.assertEqual(self.client.get(self.url, {"course": str(self.course.id)}).status_code, 403)

    def test_curso_obrigatorio_e_sessao_obrigatoria(self):
        self.authenticate(self.teacher)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.client.force_authenticate(user=None)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url, {"course": str(self.course.id)}).status_code, 401)


class InscritosCursoVideoTests(StudyTrackingTestBase):
    def setUp(self):
        super().setUp()
        self.video = Course.objects.create(
            teacher=self.teacher, teacherName=self.teacher.name, title="Reuniões de segurança",
            description="Vídeo", course_type="video", status="Published",
        )
        s1 = CourseSection.objects.create(course=self.video, sectionTitle="Antes", order=1)
        s2 = CourseSection.objects.create(course=self.video, sectionTitle="Durante", order=2)
        self.c1 = Chapter.objects.create(section=s1, title="Vocabulário", content="", order=1)
        self.c2 = Chapter.objects.create(section=s2, title="Pedir um relatório", content="", order=1)
        self.c3 = Chapter.objects.create(section=s2, title="Relatar um incidente", content="", order=2)
        CourseEnrollment.objects.create(user=self.student, course=self.video)
        self.url = f"/api/v1/teacher/video-courses/courses/{self.video.id}/enrollments/"

    def test_professor_ve_inscritos_e_capitulos(self):
        progresso = UserCourseProgress.objects.create(
            user=self.student, course=self.video, overallProgress=33.3, total_time_spent=12, enrollmentDate=timezone.now()
        )
        ChapterProgress.objects.create(user_progress=progresso, chapter=self.c1, completed=True)
        ChapterProgress.objects.create(user_progress=progresso, chapter=self.c2, completed=False)

        self.authenticate(self.teacher)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        aluno = r.json()[0]
        self.assertEqual(aluno["userId"], str(self.student.id))
        self.assertEqual(aluno["progress"], 33)
        self.assertEqual(aluno["completedChapters"], 1)
        self.assertEqual(aluno["totalChapters"], 3)
        self.assertEqual(aluno["completedSections"], 1)  # a secção 1 só tem um capítulo
        self.assertEqual(aluno["totalSections"], 2)
        self.assertEqual(aluno["totalWatchTime"], 12)

    def test_inscrito_sem_progresso_aparece_a_zero(self):
        self.authenticate(self.teacher)
        aluno = self.client.get(self.url).json()[0]
        self.assertEqual(aluno["progress"], 0)
        self.assertEqual(aluno["completedChapters"], 0)

    def test_so_o_dono_ou_admin(self):
        self.authenticate(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        admin = User.objects.create_user(email="admin-prog@example.com", name="Admin", password="password123", role="admin")
        self.authenticate(admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
