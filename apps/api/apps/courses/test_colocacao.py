"""
Colocação no curso geral: A1 directo; outro nível pede o teste escrito do nível anterior (70%).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.test_colocacao --settings=core.test_settings
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses import colocacao, teste_basico as svc
from apps.courses.models import Chapter, Course, CourseEnrollment, CourseSection, TesteNivelBasico
from apps.practice.models import PracticeLesson, PracticeUnit, UserProgress

User = get_user_model()
U = '/api/v1/student/colocacao/'


def _curso(prof, nivel, titulo, tipo='video', categoria='Inglês Geral', estado='Published'):
    return Course.objects.create(teacher=prof, teacherName='Prof', title=titulo, description='-',
                                 category=categoria, level=nivel, status=estado, course_type=tipo,
                                 access_level='free')


def _respostas(t, certas):
    r = {}
    for i, item in enumerate(t.perguntas):
        certa = item['ordem'].index(0)
        r[item['id']] = certa if i < certas else (certa + 1) % len(item['ordem'])
    return r


class ColocacaoTest(TestCase):
    def setUp(self):
        self.prof = User.objects.create_user(email='prof-col@exemplo.ao', name='prof-col', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-col@exemplo.ao', name='aluno-col', password='x', role='student')
        self.c = APIClient()
        self.c.force_authenticate(self.aluno)
        # Dois cursos por nível: entra-se no primeiro pelo título.
        self.a1_2 = _curso(self.prof, 'A1', 'A1.2 English Communication Skills')
        self.a1_1 = _curso(self.prof, 'A1', 'A1.1 English Communication Skills')
        self.a2_1 = _curso(self.prof, 'A2', 'A2.1 English Communication Skills')
        self.b1_1 = _curso(self.prof, 'B1', 'B1.1 English Communication Skills')
        _curso(self.prof, 'B1', 'Petróleo B1', categoria='Industry English')   # de sector: não conta
        _curso(self.prof, 'B2', 'B2.1 rascunho', estado='Draft')               # não publicado: não conta

    def _teste(self, nivel, certas):
        r = self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': nivel}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        r = self.c.post(f'/api/v1/student/teste-basico/{t.id}/entregar/', {'respostas': _respostas(t, certas)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_lista_os_cinco_niveis_e_o_teste_de_cada_um(self):
        r = self.c.get(U)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([n['nivel'] for n in r.data['niveis']], ['A1', 'A2', 'B1', 'B2', 'C1'])
        self.assertEqual([n['teste'] for n in r.data['niveis']], [None, 'A1', 'A2', 'B1', 'B2'])
        por_nivel = {n['nivel']: n for n in r.data['niveis']}
        self.assertEqual(por_nivel['A1']['curso']['id'], str(self.a1_1.id))
        self.assertIsNone(por_nivel['B2']['curso'])
        self.assertTrue(por_nivel['A1']['pode_entrar'])
        self.assertFalse(por_nivel['B1']['pode_entrar'])

    def test_a1_inscreve_logo_no_primeiro_curso_do_nivel(self):
        r = self.c.post(U, {'nivel': 'A1'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['nivel'], r.data['inscrito']), ('A1', True))
        self.assertEqual(r.data['curso']['id'], str(self.a1_1.id))
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.a1_1).exists())
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.preferences['nivel'], 'A1')
        self.assertEqual(self.aluno.preferences['acolhimento'], 'concluido')

    def test_outro_nivel_sem_teste_devolve_409(self):
        r = self.c.post(U, {'nivel': 'B1'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual((r.data['code'], r.data['teste']), ('teste_necessario', 'A2'))
        self.assertFalse(CourseEnrollment.objects.filter(user=self.aluno).exists())

    def test_aprovado_no_teste_anterior_entra_no_nivel_escolhido(self):
        self.assertTrue(self._teste('A2', 14)['aprovado'])          # 14/20 = 70%
        r = self.c.post(U, {'nivel': 'B1'}, format='json')
        self.assertEqual((r.data['nivel'], r.data['no_nivel_escolhido'], r.data['inscrito']), ('B1', True, True))
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.b1_1).exists())
        # o teste do A2 é o do nível básico: abre os cursos de sector
        self.assertTrue(svc.tem_nivel_basico(self.aluno))

    def test_reprovado_entra_no_nivel_testado(self):
        self.assertFalse(self._teste('A2', 13)['aprovado'])         # 13/20 = 65%
        r = self.c.post(U, {'nivel': 'B1'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['nivel'], r.data['escolhido'], r.data['no_nivel_escolhido']), ('A2', 'B1', False))
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.a2_1).exists())
        self.assertFalse(CourseEnrollment.objects.filter(user=self.aluno, course=self.b1_1).exists())

    def test_teste_em_curso_nao_conta_como_reprovado(self):
        self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'A2'}, format='json')
        self.assertEqual(self.c.post(U, {'nivel': 'B1'}, format='json').status_code, 409)

    def test_teste_que_expirou_conta_como_reprovado(self):
        self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'A1'}, format='json')
        TesteNivelBasico.objects.filter(user=self.aluno).update(expira_em=timezone.now() - timedelta(hours=1))
        r = self.c.post(U, {'nivel': 'A2'}, format='json')
        self.assertEqual(r.data['nivel'], 'A1')

    def test_aprovado_num_nivel_acima_vale_para_os_de_baixo(self):
        self.assertTrue(self._teste('B1', 20)['aprovado'])
        self.assertEqual(self.c.post(U, {'nivel': 'A2'}, format='json').data['nivel'], 'A2')   # pede o A1
        self.assertEqual(self.c.post(U, {'nivel': 'B2'}, format='json').data['nivel'], 'B2')   # pede o B1

    def test_sem_curso_publicado_guarda_o_nivel(self):
        self._teste('B1', 20)
        r = self.c.post(U, {'nivel': 'B2'}, format='json')
        self.assertEqual((r.data['nivel'], r.data['inscrito'], r.data['motivo']), ('B2', False, 'sem_curso'))
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.preferences['colocacao']['nivel'], 'B2')

    def test_nivel_invalido(self):
        for nivel in ('C2', 'X', '', None, 3):
            self.assertEqual(self.c.post(U, {'nivel': nivel}, format='json').status_code, 400, nivel)

    def test_activa_o_laboratorio_ligado_ao_curso(self):
        lab = _curso(self.prof, 'A1', 'A1.1 Laboratório', tipo='practice', categoria='General')
        unidade = PracticeUnit.objects.create(course=lab, title='U1', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='1A', order=1)
        seccao = CourseSection.objects.create(course=self.a1_1, sectionTitle='Unidade 1', order=1)
        Chapter.objects.create(section=seccao, title='1A — Hello', type='Video', order=1, practice_lesson=licao)
        r = self.c.post(U, {'nivel': 'A1'}, format='json')
        self.assertEqual(r.data['curso_pratica']['id'], str(lab.id))
        self.assertEqual(UserProgress.objects.get(user=self.aluno).active_course_id, lab.id)

    def test_os_testes_de_cada_nivel_usam_o_banco_desse_nivel(self):
        for nivel in svc.NIVEIS_TESTE:
            self.assertGreaterEqual(len(svc.BANCOS[nivel]), svc.N_PERGUNTAS, nivel)
        r = self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'B2'}, format='json')
        self.assertEqual(r.data['nivel'], 'B2')
        self.assertTrue(all(p['id'].startswith('b2-') for p in r.data['perguntas']))
        self.assertEqual(self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'C1'}, format='json').status_code, 400)

    def test_pergunta_anulada_conta_como_errada_mesmo_respondida(self):
        r = self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'A1'}, format='json')
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        for item in t.perguntas[:7]:                               # saiu do ecrã em 7 perguntas
            a = self.c.post(f'/api/v1/student/teste-basico/{t.id}/anular/', {'pergunta': item['id']}, format='json')
            self.assertEqual(a.status_code, 200, a.data)
        self.c.post(f'/api/v1/student/teste-basico/{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json')
        t.refresh_from_db()
        self.assertEqual(len(t.anuladas), 7)                       # idempotente
        r = self.c.post(f'/api/v1/student/teste-basico/{t.id}/entregar/', {'respostas': _respostas(t, 20)}, format='json')
        self.assertEqual((r.data['certas'], r.data['aprovado']), (13, False))   # 13/20 < 70%
        self.assertEqual(len(r.data['anuladas']), 7)

    def test_anular_pergunta_de_fora_ou_teste_entregue(self):
        r = self.c.post('/api/v1/student/teste-basico/iniciar/', {'nivel': 'A1'}, format='json')
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        self.assertEqual(self.c.post(f'/api/v1/student/teste-basico/{t.id}/anular/', {'pergunta': 'x'}, format='json').status_code, 400)
        self.c.post(f'/api/v1/student/teste-basico/{t.id}/entregar/', {'respostas': {}}, format='json')
        self.assertEqual(self.c.post(f'/api/v1/student/teste-basico/{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json').status_code, 409)
        outro = APIClient()
        outro.force_authenticate(self.prof)
        self.assertEqual(outro.post(f'/api/v1/student/teste-basico/{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json').status_code, 404)

    def test_nivel_do_teste(self):
        self.assertEqual([colocacao.nivel_do_teste(n) for n in colocacao.NIVEIS_ESCOLHA], [None, 'A1', 'A2', 'B1', 'B2'])
