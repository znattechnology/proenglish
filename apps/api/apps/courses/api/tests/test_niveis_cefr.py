"""
Escala única de níveis (CEFR A1..C2): ajudantes, migrações de dados (cursos e preferences.nivel),
filtro do catálogo e escrita do nível pelo professor.
"""
import importlib

from django.apps import apps as registo
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses import ciclo, niveis
from apps.courses.models import Course
from apps.users.models import User

migracao_cursos = importlib.import_module('apps.courses.migrations.0028_niveis_cefr')
migracao_users = importlib.import_module('apps.users.migrations.0017_preferencias_nivel_cefr')


class AjudantesTests(TestCase):
    def test_normalizar_le_valores_antigos(self):
        self.assertEqual([niveis.normalizar(v) for v in ('Beginner', 'Intermediate', 'Advanced')], ['A2', 'B1', 'B2'])
        self.assertEqual(niveis.normalizar('b2'), 'B2')
        self.assertIsNone(niveis.normalizar('Expert'))
        self.assertIsNone(niveis.normalizar(None))

    def test_entrada_so_cefr(self):
        self.assertEqual(niveis.cefr_de_entrada(' c1 '), 'C1')
        for v in ('Beginner', 'iniciante', 'D1', '', None, 3):
            self.assertIsNone(niveis.cefr_de_entrada(v))
        self.assertIsNone(ciclo.nivel_de_entrada('Advanced'))

    def test_rotulo(self):
        self.assertEqual(ciclo.nivel_pt('B1'), 'Nível B1')
        self.assertEqual(ciclo.nivel_pt('Intermediate'), 'Nível B1')
        self.assertIsNone(ciclo.nivel_pt(''))

    def test_filtro(self):
        self.assertEqual(niveis.filtro('B1'), ['B1'])
        self.assertEqual(niveis.filtro('b1, a2'), ['A2', 'B1'])
        self.assertEqual(niveis.filtro('Beginner'), ['A1', 'A2'])
        self.assertEqual(niveis.filtro('Advanced'), ['B2', 'C1', 'C2'])
        self.assertEqual(niveis.filtro('Expert'), [])


class MigracaoTests(TestCase):
    def setUp(self):
        self.prof = User.objects.create_user(email='f2b-prof@example.com', name='Prof', password='x12345678',
                                             role='teacher')

    def curso(self, level):
        c = Course.objects.create(teacher=self.prof, teacherName='Prof', title=f'Curso {level}', category='Banking',
                                  course_type='practice')
        Course.objects.filter(pk=c.pk).update(level=level)  # contorna as escolhas (dados antigos)
        return c

    def niveis_de(self, cursos):
        return [Course.objects.get(pk=c.pk).level for c in cursos]

    def test_cursos_para_cefr_e_para_tras(self):
        antigos = [self.curso(v) for v in ('Beginner', 'Intermediate', 'Advanced', 'beginner')]
        migracao_cursos.para_cefr(registo, None)
        self.assertEqual(self.niveis_de(antigos), ['A2', 'B1', 'B2', 'A2'])

        novos = [self.curso(v) for v in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')]
        migracao_cursos.para_antigo(registo, None)
        self.assertEqual(self.niveis_de(novos),
                         ['Beginner', 'Beginner', 'Intermediate', 'Advanced', 'Advanced', 'Advanced'])

    def test_preferencias_para_cefr_e_para_tras(self):
        pessoas = []
        for i, prefs in enumerate([{'nivel': 'Beginner', 'area': 'Banking'}, {'nivel': 'Intermediate'},
                                   {'nivel': 'Advanced'}, {'cidade': 'Luanda'}, {}]):
            u = User.objects.create_user(email=f'f2b-aluno{i}@example.com', name='Aluno', password='x12345678',
                                         role='student')
            User.objects.filter(pk=u.pk).update(preferences=prefs)
            pessoas.append(u)
        migracao_users.para_cefr(registo, None)
        prefs = [User.objects.get(pk=u.pk).preferences for u in pessoas]
        self.assertEqual(prefs, [{'nivel': 'A2', 'area': 'Banking'}, {'nivel': 'B1'}, {'nivel': 'B2'},
                                 {'cidade': 'Luanda'}, {}])
        User.objects.filter(pk=pessoas[0].pk).update(preferences={'nivel': 'C1'})
        migracao_users.para_antigo(registo, None)
        self.assertEqual([User.objects.get(pk=u.pk).preferences.get('nivel') for u in pessoas[:3]],
                         ['Advanced', 'Intermediate', 'Advanced'])


class CatalogoEProfessorTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='f2b-prof2@example.com', name='Prof', password='x12345678',
                                             role='teacher')
        self.cursos = {}
        for nivel in ('A1', 'A2', 'B1', 'B2', 'C1'):
            self.cursos[nivel] = Course.objects.create(
                teacher=self.prof, teacherName='Prof', title=f'F2B Curso {nivel}', category='Industry English',
                level=nivel, course_type='video', status='Published')

    def titulos(self, query):
        r = self.client.get(f'/api/v1/student/video-courses/{query}')
        self.assertEqual(r.status_code, 200, r.content)
        return sorted(c['level'] for c in r.json()['data']['results'])

    def test_filtro_do_catalogo(self):
        self.assertEqual(self.titulos('?level=B1'), ['B1'])
        self.assertEqual(self.titulos('?level=A2,B1'), ['A2', 'B1'])
        # Um cliente antigo que ainda pede "Beginner" recebe a banda A1–A2.
        self.assertEqual(self.titulos('?level=Beginner'), ['A1', 'A2'])
        # Valor desconhecido: sem filtro.
        self.assertEqual(self.titulos('?level=Expert'), ['A1', 'A2', 'B1', 'B2', 'C1'])

    def test_ordenar_por_nivel(self):
        r = self.client.get('/api/v1/student/video-courses/?ordering=-level')
        self.assertEqual([c['level'] for c in r.json()['data']['results']], ['C1', 'B2', 'B1', 'A2', 'A1'])

    def test_professor_muda_nivel_so_em_cefr(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.prof).access_token}')
        curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='F2B Rascunho',
                                      category='Industry English', level='A2', course_type='video')
        url = f'/api/v1/teacher/cursos/{curso.id}/'
        r = self.client.patch(url, {'nivel': 'Beginner'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.client.patch(url, {'nivel': 'C2'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['nivel'], r.json()['nivel_codigo']), ('Nível C2', 'C2'))
        curso.refresh_from_db()
        self.assertEqual(curso.level, 'C2')
