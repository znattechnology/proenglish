"""
Requisito dos cursos de sector (nível básico) e o teste que o dá.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.test_teste_basico
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses import ciclo, teste_basico as svc
from apps.courses.models import Course, CourseCertificate, CourseEnrollment, TesteNivelBasico

User = get_user_model()


def _curso(prof, categoria, tipo='video', titulo='Curso'):
    return Course.objects.create(teacher=prof, teacherName='Prof', title=titulo, description='-',
                                 category=categoria, level='A2', status='Published', course_type=tipo,
                                 access_level='free')


def _respostas(t, certas):
    """Respostas com `certas` perguntas certas e as restantes erradas."""
    r = {}
    for i, item in enumerate(t.perguntas):
        certa = item['ordem'].index(0)
        r[item['id']] = certa if i < certas else (certa + 1) % len(item['ordem'])
    return r


class RequisitoBasicoTest(TestCase):
    def setUp(self):
        self.prof = User.objects.create_user(email='prof-tb@exemplo.ao', name='prof-tb', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-tb@exemplo.ao', name='aluno-tb', password='x', role='student')
        self.geral = _curso(self.prof, 'Inglês Geral', titulo='ECS L1')
        self.sector = _curso(self.prof, 'Industry English', titulo='Petróleo')
        self.pratica_sector = _curso(self.prof, 'Banking', tipo='practice', titulo='Banca')
        self.pratica_geral = _curso(self.prof, 'General', tipo='practice', titulo='Geral')

    def test_curso_geral_nao_pede_requisito(self):
        self.assertIsNone(ciclo.bloqueio_inscricao(self.aluno, self.geral))
        self.assertIsNone(ciclo.bloqueio_requisito_pratica(self.aluno, self.pratica_geral))

    def test_curso_de_sector_bloqueia_sem_nivel_basico(self):
        b = ciclo.bloqueio_inscricao(self.aluno, self.sector)
        self.assertEqual((b[0], b[2]), ('requisito_basico', 403))
        self.assertEqual(ciclo.bloqueio_requisito_pratica(self.aluno, self.pratica_sector)[0], 'requisito_basico')

    def test_quem_ja_estava_inscrito_continua(self):
        CourseEnrollment.objects.create(user=self.aluno, course=self.sector)
        self.assertIsNone(ciclo.bloqueio_inscricao(self.aluno, self.sector))

    def test_professor_do_curso_e_staff_passam(self):
        self.assertIsNone(ciclo.bloqueio_inscricao(self.prof, self.sector))
        self.assertIsNone(ciclo.bloqueio_requisito_pratica(self.prof, self.pratica_sector))

    def test_certificado_do_curso_geral_da_o_nivel(self):
        CourseCertificate.objects.create(user=self.aluno, course=self.geral, certificate_number='CERT-TB-1',
                                         completion_percentage=100, final_grade=80)
        self.assertIsNone(ciclo.bloqueio_inscricao(self.aluno, self.sector))
        self.assertIsNone(ciclo.bloqueio_requisito_pratica(self.aluno, self.pratica_sector))

    def test_certificado_revogado_nao_conta(self):
        CourseCertificate.objects.create(user=self.aluno, course=self.geral, certificate_number='CERT-TB-2',
                                         completion_percentage=100, final_grade=80, revoked_at=timezone.now())
        self.assertIsNotNone(ciclo.bloqueio_inscricao(self.aluno, self.sector))

    def test_teste_aprovado_abre_os_sectores(self):
        t = svc.iniciar(self.aluno)
        t = svc.submeter(self.aluno, t.id, _respostas(t, 14))   # 70%
        self.assertTrue(t.aprovado)
        self.assertIsNone(ciclo.bloqueio_inscricao(self.aluno, self.sector))
        self.assertIsNone(ciclo.bloqueio_requisito_pratica(self.aluno, self.pratica_sector))

    def test_teste_reprovado_nao_abre_e_obriga_a_esperar(self):
        t = svc.iniciar(self.aluno)
        t = svc.submeter(self.aluno, t.id, _respostas(t, 13))   # 65%
        self.assertFalse(t.aprovado)
        self.assertIsNotNone(ciclo.bloqueio_inscricao(self.aluno, self.sector))
        e = svc.estado(self.aluno)
        self.assertFalse(e['pode_iniciar'])
        self.assertIsNotNone(e['proxima_tentativa_em'])
        with self.assertRaises(svc.ErroTeste) as c:
            svc.iniciar(self.aluno)
        self.assertEqual(c.exception.codigo, 'espera')
        # 24 horas depois já pode
        TesteNivelBasico.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(hours=25))
        self.assertTrue(svc.estado(self.aluno)['pode_iniciar'])

    def test_iniciar_duas_vezes_devolve_a_mesma_tentativa(self):
        a = svc.iniciar(self.aluno)
        b = svc.iniciar(self.aluno)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(TesteNivelBasico.objects.filter(user=self.aluno).count(), 1)

    def test_tempo_esgotado_conta_como_reprovado(self):
        t = svc.iniciar(self.aluno)
        TesteNivelBasico.objects.filter(pk=t.pk).update(expira_em=timezone.now() - timedelta(minutes=5))
        with self.assertRaises(svc.ErroTeste) as c:
            svc.submeter(self.aluno, t.id, _respostas(t, 20))
        self.assertEqual(c.exception.codigo, 'tempo_esgotado')
        e = svc.estado(self.aluno)
        self.assertFalse(e['tem_nivel_basico'])
        self.assertFalse(e['pode_iniciar'])

    def test_nao_se_entrega_duas_vezes_nem_o_teste_de_outro(self):
        t = svc.iniciar(self.aluno)
        svc.submeter(self.aluno, t.id, _respostas(t, 0))
        with self.assertRaises(svc.ErroTeste) as c:
            svc.submeter(self.aluno, t.id, _respostas(t, 20))
        self.assertEqual(c.exception.codigo, 'ja_entregue')
        outro = User.objects.create_user(email='outro-tb@exemplo.ao', name='outro-tb', password='x', role='student')
        t2 = svc.iniciar(outro)
        with self.assertRaises(svc.ErroTeste) as c:
            svc.submeter(self.aluno, t2.id, _respostas(t2, 20))
        self.assertEqual(c.exception.codigo, 'not_found')

    def test_respostas_invalidas_contam_como_erradas(self):
        t = svc.iniciar(self.aluno)
        lixo = {item['id']: v for item, v in zip(t.perguntas, [True, 'a', 99, -1, None] * 4)}
        t = svc.submeter(self.aluno, t.id, lixo)
        self.assertEqual(t.certas, 0)

    def test_banco_tem_perguntas_suficientes_e_bem_formadas(self):
        self.assertGreaterEqual(len(svc.BANCO), svc.N_PERGUNTAS * 2)
        ids = [p[0] for p in svc.BANCO]
        self.assertEqual(len(ids), len(set(ids)))
        for _, enunciado, opcoes in svc.BANCO:
            self.assertTrue(enunciado.strip())
            self.assertEqual(len(opcoes), 3)
            self.assertEqual(len(set(opcoes)), 3)


class TesteBasicoApiTest(TestCase):
    def setUp(self):
        self.prof = User.objects.create_user(email='prof-tba@exemplo.ao', name='prof-tba', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-tba@exemplo.ao', name='aluno-tba', password='x', role='student')
        self.sector = _curso(self.prof, 'Financial English', titulo='Banca')
        self.c = APIClient()
        self.c.force_authenticate(self.aluno)

    def test_sem_sessao_nao_entra(self):
        self.assertIn(APIClient().get('/api/v1/student/teste-basico/').status_code, (401, 403))

    def test_fluxo_completo_e_as_respostas_nunca_saem(self):
        r = self.c.get('/api/v1/student/teste-basico/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['pode_iniciar'])
        r = self.c.post('/api/v1/student/teste-basico/iniciar/')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data['perguntas']), svc.N_PERGUNTAS)
        self.assertEqual(set(r.data['perguntas'][0]), {'id', 'enunciado', 'opcoes'})
        t = TesteNivelBasico.objects.get(pk=r.data['id'])
        r = self.c.post(f'/api/v1/student/teste-basico/{t.id}/entregar/', {'respostas': _respostas(t, 20)}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['aprovado'])
        self.assertEqual(r.data['certas'], 20)
        self.assertTrue(r.data['estado']['tem_nivel_basico'])
        # já aprovado: não abre outro teste
        self.assertEqual(self.c.post('/api/v1/student/teste-basico/iniciar/').status_code, 400)

    def test_inscricao_num_sector_devolve_403_com_o_codigo(self):
        r = self.c.post('/api/v1/student/video-courses/transactions/create/', {'courseId': str(self.sector.id)}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data['code'], 'requisito_basico')
