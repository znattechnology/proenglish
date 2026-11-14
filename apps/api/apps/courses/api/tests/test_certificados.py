"""
Certificados: número PE-C-..., emissão automática (signals) e manual, lista do aluno,
PDF do dono e verificação pública sem autenticação.

    ./venv/bin/python manage.py test apps.courses.api.tests.test_certificados --settings=core.test_settings
"""
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.certificados import gerar_numero_certificado
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseCertificate, CourseGradingConfig,
    CourseSection, StudentCourseGrade, StudentQuizAttempt, UserCourseProgress,
)
from apps.courses.matriculas import matricular_em_curso
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.practice.models import PracticeLesson, PracticeUnit
from apps.subscriptions.models import SubscriptionPlan, UserSubscription
from apps.users.models import Notification

User = get_user_model()
V = '/api/v1/student/video-courses/'
NUMERO = re.compile(r'^PE-C-\d{4}-\d{6}$')


class CertificadosBase(APITestCase):

    def setUp(self):
        cache.clear()  # throttling da verificação pública
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-cert@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='ana-cert@example.com', name='Ana Maria Santos',
                                              password='x', role='student')
        self.outro = User.objects.create_user(email='outro-cert@example.com', name='Outro', password='x',
                                              role='student')
        self._plano(self.aluno, 'PREMIUM')
        self._plano(self.outro, 'PREMIUM')

        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='E-mails em inglês',
                                           description='d', course_type='video', status='Published')
        # Só quizzes contam (sem prática nem conversação), para o teste ser determinístico.
        CourseGradingConfig.objects.create(course=self.curso, practice_enabled=False,
                                           conversation_enabled=False)
        sec = CourseSection.objects.create(course=self.curso, order=1, sectionTitle='S1')
        self.cap1 = Chapter.objects.create(section=sec, order=1, title='Texto', type='Text', content='x')
        self.cap2 = Chapter.objects.create(section=sec, order=2, title='Quiz', type='Quiz', content='x')
        unidade = PracticeUnit.objects.create(course=self.curso, title='U', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        self.quiz = ChapterQuiz.objects.create(chapter=self.cap2, practice_lesson=licao, title='Quiz',
                                               passing_score=70, created_by=self.prof)

    # -- helpers -------------------------------------------------------------
    def _plano(self, user, plan_type):
        UserSubscription.objects.update_or_create(user=user, defaults=dict(
            plan=SubscriptionPlan.objects.get(plan_type=plan_type), status='ACTIVE',
            expires_at=timezone.now() + timedelta(days=30)))

    def _auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def _quiz(self, user, score):
        StudentQuizAttempt.objects.create(student=user, chapter_quiz=self.quiz, score=score, max_score=10,
                                          is_completed=True)

    def _concluir(self, user):
        _, prog = matricular_em_curso(user, self.curso)
        ChapterProgress.objects.filter(user_progress=prog).update(completed=True)
        UserCourseProgress.objects.get(pk=prog.pk).update_overall_progress()


class NumeroCertificadoTests(CertificadosBase):

    def test_formato_e_sequencia_por_ano(self):
        ano = timezone.localtime(timezone.now(), timezone.get_fixed_timezone(60)).year
        a, b = gerar_numero_certificado(), gerar_numero_certificado()
        self.assertRegex(a, NUMERO)
        self.assertTrue(a.startswith(f'PE-C-{ano}-'))
        self.assertEqual(int(b[-6:]), int(a[-6:]) + 1)


class EmissaoAutomaticaTests(CertificadosBase):

    def test_quiz_aprovado_com_curso_concluido_emite_um_certificado(self):
        matricular_em_curso(self.aluno, self.curso)
        self._quiz(self.aluno, 9)  # signal recalcula a nota (ainda sem 100% -> sem certificado)
        self.assertFalse(CourseCertificate.objects.filter(user=self.aluno).exists())
        self.assertTrue(StudentCourseGrade.objects.get(user=self.aluno, course=self.curso).is_eligible_for_certificate)

        self._concluir(self.aluno)  # progresso a 100% -> signal emite
        certs = CourseCertificate.objects.filter(user=self.aluno, course=self.curso)
        self.assertEqual(certs.count(), 1)
        cert = certs.get()
        self.assertRegex(cert.certificate_number, NUMERO)
        self.assertEqual(cert.final_grade, 90.0)
        self.assertTrue(Notification.objects.filter(user=self.aluno, kind='certificate').exists())

        # Recalcular de novo não duplica nem entra em recursão
        GradeCalculatorService(self.aluno, self.curso).calculate_and_save()
        self.assertEqual(certs.count(), 1)

    def test_nota_insuficiente_nao_emite(self):
        self._concluir(self.aluno)
        self._quiz(self.aluno, 5)
        self.assertFalse(CourseCertificate.objects.filter(user=self.aluno).exists())

    def test_plano_gratuito_nao_emite(self):
        self._plano(self.aluno, 'FREE')
        self._concluir(self.aluno)
        self._quiz(self.aluno, 10)
        self.assertFalse(CourseCertificate.objects.filter(user=self.aluno).exists())


class EmitirEndpointTests(CertificadosBase):

    def test_emitir_quando_elegivel_e_idempotente(self):
        self._concluir(self.aluno)
        self._quiz(self.aluno, 9)
        CourseCertificate.objects.filter(user=self.aluno).delete()  # simula signal que falhou
        self._auth(self.aluno)
        r = self.client.post(f'{V}{self.curso.id}/certificado/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['criado'])
        self.assertRegex(r.data['certificado']['numero'], NUMERO)
        self.assertTrue(r.data['certificado']['ligacao_verificacao'].endswith(r.data['certificado']['numero']))
        r2 = self.client.post(f'{V}{self.curso.id}/certificado/')
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.data['criado'])
        self.assertEqual(r2.data['certificado']['id'], r.data['certificado']['id'])

    def test_requisitos_em_falta(self):
        matricular_em_curso(self.aluno, self.curso)
        self._quiz(self.aluno, 5)
        self._auth(self.aluno)
        r = self.client.post(f'{V}{self.curso.id}/certificado/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['codigo'], 'REQUISITOS_EM_FALTA')
        requisitos = {x['requisito'] for x in r.data['em_falta']}
        self.assertIn('conclusao_curso', requisitos)
        self.assertIn('final_grade', requisitos)

    def test_plano_sem_certificados_403_e_nao_inscrito_404(self):
        self._plano(self.aluno, 'FREE')
        self._auth(self.aluno)
        r = self.client.post(f'{V}{self.curso.id}/certificado/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['codigo'], 'CERTIFICADOS_NAO_INCLUIDOS')
        self._auth(self.outro)
        self.assertEqual(self.client.post(f'{V}{self.curso.id}/certificado/').status_code, 404)

    def test_requer_autenticacao(self):
        self.assertEqual(self.client.post(f'{V}{self.curso.id}/certificado/').status_code, 401)


class ListaEPdfTests(CertificadosBase):

    def test_lista_certificados_e_cursos_em_curso(self):
        self._concluir(self.aluno)
        self._quiz(self.aluno, 9)
        curso2 = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Reuniões',
                                       description='d', course_type='video', status='Published')
        matricular_em_curso(self.aluno, curso2)
        # certificado de outro aluno não aparece
        self._concluir(self.outro)
        self._quiz(self.outro, 10)

        self._auth(self.aluno)
        r = self.client.get(f'{V}certificados/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['plano_inclui_certificados'])
        self.assertEqual(len(r.data['certificados']), 1)
        c = r.data['certificados'][0]
        self.assertEqual(c['curso']['titulo'], 'E-mails em inglês')
        self.assertEqual(c['estado'], 'valido')
        self.assertIn('/pdf/', c['pdf_url'])
        self.assertEqual([x['curso']['titulo'] for x in r.data['em_curso']], ['Reuniões'])
        em_curso = r.data['em_curso'][0]
        self.assertFalse(em_curso['pode_emitir'])
        self.assertEqual(em_curso['nota_minima'], 70.0)
        self.assertTrue(any(x['requisito'] == 'conclusao_curso' for x in em_curso['em_falta']))

    def test_pdf_so_para_o_dono_e_nao_revogado(self):
        self._concluir(self.aluno)
        self._quiz(self.aluno, 9)
        cert = CourseCertificate.objects.get(user=self.aluno)
        url = f'{V}certificados/{cert.id}/pdf/'
        self._auth(self.aluno)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertIn(cert.certificate_number, r['Content-Disposition'])
        self._auth(self.outro)
        self.assertEqual(self.client.get(url).status_code, 404)
        CourseCertificate.objects.filter(pk=cert.pk).update(revoked_at=timezone.now())
        self._auth(self.aluno)
        self.assertEqual(self.client.get(url).status_code, 409)


class VerificacaoPublicaTests(CertificadosBase):

    def setUp(self):
        super().setUp()
        self._concluir(self.aluno)
        self._quiz(self.aluno, 9)
        self.cert = CourseCertificate.objects.get(user=self.aluno)

    def test_valido_sem_autenticacao_so_campos_publicos(self):
        r = self.client.get(f'/api/v1/certificados/verificar/{self.cert.certificate_number}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {'valido', 'estado', 'numero', 'nome_aluno', 'curso', 'emitido_em',
                                       'nota_final', 'revogado_em'})
        self.assertTrue(r.data['valido'])
        self.assertEqual(r.data['nome_aluno'], 'Ana Maria Santos')
        self.assertEqual(r.data['curso'], 'E-mails em inglês')
        self.assertEqual(r.data['nota_final'], 90.0)
        corpo = r.content.decode()
        self.assertNotIn(self.aluno.email, corpo)
        self.assertNotIn(str(self.aluno.id), corpo)
        self.assertNotIn(str(self.cert.id), corpo)

    def test_numero_em_minusculas_e_revogado(self):
        CourseCertificate.objects.filter(pk=self.cert.pk).update(revoked_at=timezone.now(),
                                                                  revocation_reason='fraude no quiz')
        r = self.client.get(f'/api/v1/certificados/verificar/{self.cert.certificate_number.lower()}/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['valido'])
        self.assertEqual(r.data['estado'], 'revogado')
        self.assertIsNotNone(r.data['revogado_em'])
        self.assertNotIn('fraude', r.content.decode())

    def test_nao_encontrado_e_formato_invalido(self):
        r = self.client.get('/api/v1/certificados/verificar/PE-C-2000-999999/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data['estado'], 'nao_encontrado')
        r = self.client.get('/api/v1/certificados/verificar/CERT-ABC/')
        self.assertEqual(r.status_code, 400)
