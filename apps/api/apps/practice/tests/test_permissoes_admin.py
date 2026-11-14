"""
"É administrador" na prática = apps.core.permissions.e_administrador (papel admin activo ou
superutilizador); is_staff sozinho não chega. E os ajudantes de IA do professor validam a entrada
antes de chamar a IA e têm limite por pessoa.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_permissoes_admin
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice import acesso_licoes
from apps.practice.models import PracticeLesson, PracticeUnit
from apps.practice.permissions import IsCourseOwner, IsOwnerOrTeacher, IsTeacher, IsTeacherOrReadOnly
from apps.practice.views_ai import AIGeracaoThrottle

User = get_user_model()
P = '/api/v1/practice/'


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        mk = lambda email, **kw: User.objects.create_user(email=email, name=email, password='x12345678', **kw)  # noqa
        self.prof = mk('prof-pa@example.com', role='teacher')
        self.outro_prof = mk('outro-pa@example.com', role='teacher', is_staff=True)
        self.admin = mk('admin-pa@example.com', role='admin')
        self.admin_inactivo = mk('admin-off-pa@example.com', role='admin', is_active=False)
        self.su = mk('su-pa@example.com', role='student', is_superuser=True)
        self.staff = mk('staff-pa@example.com', role='student', is_staff=True)
        self.aluno = mk('aluno-pa@example.com', role='student')
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Inglês', description='-',
                                           course_type='practice', status='Published')

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')


class SemRestricoesTests(Base):
    def test_dono_e_administradores(self):
        for user, esperado in ((self.prof, True), (self.admin, True), (self.su, True),
                               (self.staff, False), (self.outro_prof, False), (self.aluno, False),
                               (self.admin_inactivo, False)):
            self.assertEqual(acesso_licoes._sem_restricoes(user, self.curso), esperado, user.email)

    def test_limite_diario_nao_e_saltado_por_is_staff(self):
        unidade = PracticeUnit.objects.create(course=self.curso, title='U', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        bloqueio = {'codigo': 'limite_licoes', 'error': 'x', 'message': 'x', 'code': 'limite_licoes', 'details': []}
        with mock.patch('apps.practice.acesso_licoes.erro_acesso_licao', return_value=None), \
                mock.patch('apps.practice.limite_licoes.erro_limite', return_value=bloqueio) as limite:
            self.entrar(self.staff)
            r = self.client.get(f'/api/v1/student/practice-courses/lessons/{licao.id}/')
            self.assertEqual(r.status_code, 403)
            self.assertTrue(limite.called)
            limite.reset_mock()
            self.entrar(self.admin)
            r = self.client.get(f'/api/v1/student/practice-courses/lessons/{licao.id}/')
            self.assertFalse(limite.called)


class ClassesDePermissaoTests(Base):
    def _pedido(self, user, metodo='POST'):
        return SimpleNamespace(user=user, method=metodo)

    def test_is_teacher_e_escrita(self):
        for user, esperado in ((self.prof, True), (self.admin, True), (self.su, True),
                               (self.staff, False), (self.aluno, False), (self.admin_inactivo, False)):
            self.assertEqual(IsTeacher().has_permission(self._pedido(user), None), esperado, user.email)
            self.assertEqual(IsTeacherOrReadOnly().has_permission(self._pedido(user), None), esperado, user.email)
            self.assertTrue(IsTeacherOrReadOnly().has_permission(self._pedido(user, 'GET'), None)
                            or not user.is_active)

    def test_dono_do_curso(self):
        p = IsCourseOwner()
        self.assertTrue(p.has_permission(self._pedido(self.admin), None))
        self.assertFalse(p.has_permission(self._pedido(self.staff), None))
        self.assertTrue(p.has_object_permission(self._pedido(self.admin), None, self.curso))
        self.assertTrue(p.has_object_permission(self._pedido(self.prof), None, self.curso))
        # Professor com is_staff não manda nos cursos dos outros.
        self.assertFalse(p.has_object_permission(self._pedido(self.outro_prof), None, self.curso))
        self.assertFalse(p.has_object_permission(self._pedido(self.staff), None, self.curso))

    def test_dono_ou_professor(self):
        p = IsOwnerOrTeacher()
        obj = SimpleNamespace(user=self.aluno)
        self.assertTrue(p.has_object_permission(self._pedido(self.admin), None, obj))
        self.assertTrue(p.has_object_permission(self._pedido(self.aluno), None, obj))
        self.assertFalse(p.has_object_permission(self._pedido(self.staff), None, obj))


class CriarCursoTests(Base):
    DADOS = {'title': 'Inglês no Terminal', 'description': 'Curso de prática para o terminal.',
             'category': 'General'}

    def test_admin_cria_e_so_staff_nao(self):
        self.entrar(self.staff)
        self.assertEqual(self.client.post(f'{P}courses/create/', self.DADOS, format='json').status_code, 403)
        self.entrar(self.admin)
        r = self.client.post(f'{P}courses/create/', self.DADOS, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)


class AjudantesIATests(Base):
    URLS = ('generate-pronunciation-exercise/', 'generate-translation-suggestions/', 'generate-reference-audio/')

    def test_corpo_vazio_da_400_sem_chamar_a_ia(self):
        self.entrar(self.prof)
        with mock.patch('apps.practice.services.ai_pronunciation.AIPronunciationAnalyzer') as pron, \
                mock.patch('apps.practice.services.ai_translation.AITranslationValidator') as trad:
            for url in self.URLS:
                r = self.client.post(P + url, {}, format='json')
                self.assertEqual(r.status_code, 400, url)
                corpo = r.json()
                self.assertEqual(corpo['code'], 'dados_invalidos', url)
                self.assertIsInstance(corpo['details'], list, url)
                self.assertTrue(corpo['message'], url)
            self.assertFalse(pron.called)
            self.assertFalse(trad.called)

    def test_valores_invalidos(self):
        self.entrar(self.prof)
        casos = (
            ('generate-pronunciation-exercise/', {'topic': 'trabalho', 'difficulty_level': 'expert'}),
            ('generate-pronunciation-exercise/', {'topic': 'x' * 201}),
            ('generate-translation-suggestions/', {'source_text': 'Olá', 'count': 50}),
            ('generate-reference-audio/', {'text': 'Hello', 'voice': 'robot'}),
        )
        with mock.patch('apps.practice.services.ai_pronunciation.AIPronunciationAnalyzer') as pron, \
                mock.patch('apps.practice.services.ai_translation.AITranslationValidator') as trad:
            for url, dados in casos:
                self.assertEqual(self.client.post(P + url, dados, format='json').status_code, 400, (url, dados))
            self.assertFalse(pron.called or trad.called)

    def test_so_professores_e_administradores(self):
        for user in (self.aluno, self.staff):
            self.entrar(user)
            self.assertEqual(self.client.post(P + self.URLS[0], {'topic': 'x'}, format='json').status_code, 403)

    def test_limite_por_pessoa(self):
        self.entrar(self.prof)
        with mock.patch.object(AIGeracaoThrottle, 'rate', '2/hour'):
            codigos = [self.client.post(P + self.URLS[0], {}, format='json').status_code for _ in range(3)]
        self.assertEqual(codigos, [400, 400, 429])
