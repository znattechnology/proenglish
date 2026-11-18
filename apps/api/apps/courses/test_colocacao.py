"""
Colocação no curso geral: A1 directo; outro nível pede um teste com perguntas de todos os níveis
abaixo do escolhido, e entra-se a seguir ao último nível aprovado (70%) a contar do A1.

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
T = '/api/v1/student/teste-basico/'


def _curso(prof, nivel, titulo, tipo='video', categoria='Inglês Geral', estado='Published'):
    return Course.objects.create(teacher=prof, teacherName='Prof', title=titulo, description='-',
                                 category=categoria, level=nivel, status=estado, course_type=tipo,
                                 access_level='free')


def _respostas(t, aprovar=(), certas_por_nivel=None):
    """Respostas certas nos níveis de `aprovar` e erradas nos outros (ou `certas_por_nivel` exactas)."""
    r, contagem = {}, {}
    for item in t.perguntas:
        nivel = item['nivel']
        contagem[nivel] = contagem.get(nivel, 0) + 1
        certa = item['ordem'].index(0)
        quer = (contagem[nivel] <= certas_por_nivel.get(nivel, 0)) if certas_por_nivel else nivel in aprovar
        r[item['id']] = certa if quer else (certa + 1) % len(item['ordem'])
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
        self.c1_1 = _curso(self.prof, 'C1', 'C1.1 English Communication Skills')
        _curso(self.prof, 'B1', 'Petróleo B1', categoria='Industry English')   # de sector: não conta
        _curso(self.prof, 'B2', 'B2.1 rascunho', estado='Draft')               # não publicado: não conta

    def _fazer_teste(self, nivel, **respostas):
        r = self.c.post(f'{U}teste/', {'nivel': nivel}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        r = self.c.post(f'{T}{t.id}/entregar/', {'respostas': _respostas(t, **respostas)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def _colocar(self, nivel):
        return self.c.post(U, {'nivel': nivel}, format='json')

    def test_lista_os_cinco_niveis_e_o_que_cada_teste_cobre(self):
        r = self.c.get(U)
        self.assertEqual(r.status_code, 200)
        niveis = {n['nivel']: n for n in r.data['niveis']}
        self.assertEqual(list(niveis), ['A1', 'A2', 'B1', 'B2', 'C1'])
        self.assertEqual(niveis['C1']['niveis_teste'], ['A1', 'A2', 'B1', 'B2'])
        self.assertEqual([niveis[n]['perguntas'] for n in niveis], [0, 30, 30, 30, 30])
        self.assertEqual(niveis['A1']['curso']['id'], str(self.a1_1.id))
        self.assertIsNone(niveis['B2']['curso'])
        self.assertEqual([niveis[n]['pode_entrar'] for n in niveis], [True, False, False, False, False])

    def test_a1_inscreve_logo_no_primeiro_curso_do_nivel(self):
        r = self._colocar('A1')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['nivel'], r.data['inscrito'], r.data['curso']['id']), ('A1', True, str(self.a1_1.id)))
        self.aluno.refresh_from_db()
        self.assertEqual((self.aluno.preferences['nivel'], self.aluno.preferences['acolhimento']), ('A1', 'concluido'))
        self.assertEqual(self.c.post(f'{U}teste/', {'nivel': 'A1'}, format='json').status_code, 400)

    def test_outro_nivel_sem_teste_devolve_409(self):
        r = self._colocar('B1')
        self.assertEqual((r.status_code, r.data['code']), (409, 'teste_necessario'))
        self.assertFalse(CourseEnrollment.objects.filter(user=self.aluno).exists())

    def test_teste_do_c1_tem_perguntas_de_todos_os_niveis_abaixo(self):
        r = self.c.post(f'{U}teste/', {'nivel': 'C1'}, format='json')
        self.assertEqual(r.data['niveis'], ['A1', 'A2', 'B1', 'B2'])
        self.assertEqual(len(r.data['perguntas']), 30)
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        self.assertEqual({n: sum(1 for p in t.perguntas if p['nivel'] == n) for n in t.niveis},
                         {'A1': 8, 'A2': 8, 'B1': 7, 'B2': 7})
        self.assertEqual(round((t.expira_em - t.created_at).total_seconds() / 60), 30)
        self.assertNotIn('nivel', r.data['perguntas'][0])   # o cliente não sabe o nível de cada pergunta

    def test_passa_tudo_entra_no_escolhido(self):
        d = self._fazer_teste('C1', aprovar={'A1', 'A2', 'B1', 'B2'})
        self.assertEqual((d['aprovado'], d['provado']), (True, 'B2'))
        r = self._colocar('C1')
        self.assertEqual((r.data['nivel'], r.data['no_nivel_escolhido'], r.data['inscrito']), ('C1', True, True))

    def test_entra_a_seguir_ao_ultimo_nivel_seguido_aprovado(self):
        # passa A1 e A2, falha B1, "passa" B2: o B2 não conta porque o B1 falhou
        d = self._fazer_teste('C1', aprovar={'A1', 'A2', 'B2'})
        self.assertEqual((d['aprovado'], d['provado']), (False, 'A2'))
        self.assertTrue(d['resultado']['B2']['aprovado'])
        r = self._colocar('C1')
        self.assertEqual((r.data['nivel'], r.data['escolhido'], r.data['no_nivel_escolhido']), ('B1', 'C1', False))
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.b1_1).exists())
        self.assertTrue(svc.tem_nivel_basico(self.aluno))   # provou o A2
        self.assertTrue(r.data['tem_nivel_basico'])

    def test_escolhe_c1_e_erra_tudo_comeca_no_a1(self):
        d = self._fazer_teste('C1')
        self.assertIsNone(d['provado'])
        r = self._colocar('C1')
        self.assertEqual(r.data['nivel'], 'A1')
        self.assertTrue(CourseEnrollment.objects.filter(user=self.aluno, course=self.a1_1).exists())
        self.assertFalse(svc.tem_nivel_basico(self.aluno))

    def test_70_por_cento_em_cada_nivel(self):
        # B2: 10 perguntas de cada nível; 7 certas (70%) passa, 6 não
        d = self._fazer_teste('B2', certas_por_nivel={'A1': 7, 'A2': 6, 'B1': 10})
        self.assertEqual(d['provado'], 'A1')
        self.assertEqual(self._colocar('B2').data['nivel'], 'A2')

    def test_teste_em_curso_e_espera_de_24_horas(self):
        self.c.post(f'{U}teste/', {'nivel': 'B1'}, format='json')
        self.assertEqual(self._colocar('B1').status_code, 409)                       # ainda não entregou
        r = self.c.post(f'{U}teste/', {'nivel': 'C1'}, format='json')
        self.assertEqual((r.status_code, r.data['code'], r.data['para']), (409, 'teste_em_curso', 'B1'))
        self.assertEqual(self.c.post(f'{U}teste/', {'nivel': 'B1'}, format='json').status_code, 201)  # retoma
        t = TesteNivelBasico.objects.get(user=self.aluno)
        self.c.post(f'{T}{t.id}/entregar/', {'respostas': {}}, format='json')
        r = self.c.post(f'{U}teste/', {'nivel': 'C1'}, format='json')
        self.assertEqual((r.status_code, r.data['code']), (429, 'espera'))
        self.assertIsNotNone(self.c.get(U).data['proxima_tentativa_em'])

    def test_teste_que_expirou_conta_como_reprovado(self):
        self.c.post(f'{U}teste/', {'nivel': 'B1'}, format='json')
        TesteNivelBasico.objects.filter(user=self.aluno).update(expira_em=timezone.now() - timedelta(hours=1))
        self.assertEqual(self._colocar('B1').data['nivel'], 'A1')

    def test_nivel_ja_provado_no_teste_basico_dispensa_o_teste(self):
        r = self.c.post(f'{T}iniciar/')
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        self.c.post(f'{T}{t.id}/entregar/', {'respostas': _respostas(t, aprovar={'A2'})}, format='json')
        self.assertTrue(self.c.get(U).data['niveis'][2]['pode_entrar'])                 # B1
        self.assertEqual(self.c.post(f'{U}teste/', {'nivel': 'B1'}, format='json').data['code'], 'ja_provado')
        self.assertEqual(self._colocar('B1').data['nivel'], 'B1')
        self.assertEqual(self._colocar('A2').data['nivel'], 'A2')

    def test_sem_curso_publicado_guarda_o_nivel(self):
        self._fazer_teste('B2', aprovar={'A1', 'A2', 'B1'})
        r = self._colocar('B2')
        self.assertEqual((r.data['nivel'], r.data['inscrito'], r.data['motivo']), ('B2', False, 'sem_curso'))

    def test_nivel_invalido(self):
        for nivel in ('C2', 'X', '', None, 3):
            self.assertEqual(self._colocar(nivel).status_code, 400, nivel)
            self.assertEqual(self.c.post(f'{U}teste/', {'nivel': nivel}, format='json').status_code, 400, nivel)

    def test_activa_o_laboratorio_ligado_ao_curso(self):
        lab = _curso(self.prof, 'A1', 'A1.1 Laboratório', tipo='practice', categoria='General')
        unidade = PracticeUnit.objects.create(course=lab, title='U1', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='1A', order=1)
        seccao = CourseSection.objects.create(course=self.a1_1, sectionTitle='Unidade 1', order=1)
        Chapter.objects.create(section=seccao, title='1A — Hello', type='Video', order=1, practice_lesson=licao)
        r = self._colocar('A1')
        self.assertEqual(r.data['curso_pratica']['id'], str(lab.id))
        self.assertEqual(UserProgress.objects.get(user=self.aluno).active_course_id, lab.id)

    def test_pergunta_anulada_conta_como_errada_mesmo_respondida(self):
        r = self.c.post(f'{U}teste/', {'nivel': 'A2'}, format='json')     # 30 perguntas do A1
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        for item in t.perguntas[:10]:
            a = self.c.post(f'{T}{t.id}/anular/', {'pergunta': item['id']}, format='json')
            self.assertEqual(a.status_code, 200, a.data)
        self.c.post(f'{T}{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json')
        t.refresh_from_db()
        self.assertEqual(len(t.anuladas), 10)                              # idempotente
        r = self.c.post(f'{T}{t.id}/entregar/', {'respostas': _respostas(t, aprovar={'A1'})}, format='json')
        self.assertEqual((r.data['certas'], r.data['aprovado']), (20, False))   # 20/30 < 70%

    def test_anular_pergunta_de_fora_ou_teste_entregue(self):
        r = self.c.post(f'{U}teste/', {'nivel': 'A2'}, format='json')
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        self.assertEqual(self.c.post(f'{T}{t.id}/anular/', {'pergunta': 'x'}, format='json').status_code, 400)
        self.c.post(f'{T}{t.id}/entregar/', {'respostas': {}}, format='json')
        self.assertEqual(self.c.post(f'{T}{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json').status_code, 409)
        outro = APIClient()
        outro.force_authenticate(self.prof)
        self.assertEqual(outro.post(f'{T}{t.id}/anular/', {'pergunta': t.perguntas[0]['id']}, format='json').status_code, 404)

    def test_banco_insuficiente_da_503_e_nao_500(self):
        from unittest import mock
        with mock.patch.dict(svc.BANCOS, {'A1': svc.BANCOS['A1'][:3]}):
            r = self.c.post(f'{U}teste/', {'nivel': 'A2'}, format='json')
        self.assertEqual((r.status_code, r.data['code']), (503, 'teste_indisponivel'))

    def test_bancos_e_funcoes_auxiliares(self):
        for nivel in svc.NIVEIS_TESTE:
            self.assertGreaterEqual(len(svc.BANCOS[nivel]), svc.N_PERGUNTAS, nivel)
        self.assertEqual([colocacao.niveis_do_teste(n) for n in ('A1', 'B1')], [[], ['A1', 'A2']])
        self.assertEqual([colocacao.seguinte(n) for n in (None, 'A2', 'B2')], ['A1', 'B1', 'C1'])
