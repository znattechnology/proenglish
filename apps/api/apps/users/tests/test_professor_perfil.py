"""
Perfil público do professor (/api/v1/professores/<id>/) e apagar a conta de professor.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.users.tests.test_professor_perfil
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from apps.courses.models import Course, CourseEnrollment
from apps.users.models import PerfilProfessor

User = get_user_model()
SENHA = 'Segura!2026xy'
NAO_ENCONTRADO = 'Professor não encontrado.'


def url(user_id):
    return f'/api/v1/professores/{user_id}/'


class PerfilPublicoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-perfil@example.com', name='Ana Prof',
                                             password=SENHA, role='teacher')

    def curso(self, titulo, **extra):
        dados = dict(teacher=self.prof, teacherName='Ana Prof', title=titulo, description='x',
                     course_type='video', status='Published')
        dados.update(extra)
        return Course.objects.create(**dados)

    def aluno(self, n):
        return User.objects.create_user(email=f'aluno-perfil-{n}@example.com', name=f'Aluno {n}', password=SENHA)

    def test_numeros_so_dos_cursos_listados_e_sem_escrita(self):
        visivel = self.curso('Visível')
        escondido = self.curso('Escondido', visivel_catalogo=False)
        self.curso('Rascunho', status='Draft')
        CourseEnrollment.objects.create(user=self.aluno(1), course=visivel)
        CourseEnrollment.objects.create(user=self.aluno(2), course=escondido)

        r = self.client.get(url(self.prof.id))
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual([c['titulo'] for c in d['cursos']], ['Visível'])
        self.assertEqual(d['cursos_publicados'], 1)
        self.assertEqual(d['alunos'], 1)
        self.assertIsNotNone(d['desde'])
        self.assertEqual(d['cidade'], '')
        self.assertFalse(PerfilProfessor.objects.filter(user=self.prof).exists())

    def test_mesmo_404_para_todos_os_casos(self):
        aluno = self.aluno(3)
        sem_cursos = self.client.get(url(self.prof.id))
        self.curso('Escondido', visivel_catalogo=False)
        so_escondidos = self.client.get(url(self.prof.id))
        nao_professor = self.client.get(url(aluno.id))
        nao_existe = self.client.get(url(uuid.uuid4()))
        for r in (sem_cursos, so_escondidos, nao_professor, nao_existe):
            self.assertEqual(r.status_code, 404)
            self.assertEqual((r.json()['message'], r.json()['code']), (NAO_ENCONTRADO, 'nao_encontrado'))
        self.assertFalse(PerfilProfessor.objects.exists())

    def test_proprio_professor_le_sem_criar(self):
        self.client.force_authenticate(self.prof)
        r = self.client.get('/api/v1/teacher/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PerfilProfessor.objects.filter(user=self.prof).exists())
        r = self.client.patch('/api/v1/teacher/perfil/', {'cidade': 'Luanda'}, format='json')
        self.assertEqual(r.json()['cidade'], 'Luanda')
        self.assertTrue(PerfilProfessor.objects.filter(user=self.prof).exists())


class ApagarContaProfessorTests(APITestCase):
    def test_professor_nao_apaga_a_conta(self):
        prof = User.objects.create_user(email='prof-apagar@example.com', name='Rui Prof',
                                        password=SENHA, role='teacher')
        self.client.force_authenticate(prof)
        r = self.client.post('/api/v1/users/apagar-conta/', {'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'conta_professor')
        self.assertEqual(r.json()['message'], 'Para fechar a conta de professor, fale com a equipa ProEnglish: '
                                              'os seus cursos têm alunos inscritos.')
        prof.refresh_from_db()
        self.assertTrue(prof.is_active)
        self.assertEqual(prof.email, 'prof-apagar@example.com')
