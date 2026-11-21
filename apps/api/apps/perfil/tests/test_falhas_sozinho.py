"""
Uma frase 'sozinho' falhada em dias seguidos volta a 'com_ajuda' (servico.registar_falha).

Caminhos de falha: revisão (resposta errada, fala não aceite), lição (exercício errado), conversa
(o tutor corrigiu a frase e o aluno não a disse bem sozinho). O histórico (vezes_sozinho,
dias_sozinho) fica; a nota do curso (frases ditas sozinho, 25%) é recalculada; um certificado já
emitido não muda.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (Chapter, Course, CourseCertificate, CourseSection, FraseAula,
                                 StudentCourseGrade)
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.perfil import fala, revisao, servico
from apps.perfil.models import ItemBanco, SessaoRevisao
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import (ChallengeAttempt, ChallengeOption, PracticeChallenge, PracticeLesson,
                                  PracticeUnit, VapiSession)

User = get_user_model()
FRASE_1 = 'Could you send me the report by Friday?'
FRASE_2 = 'Please check the pressure before you start the pump.'


def _aluno(email='fb-aluno@example.com', role='student'):
    return User.objects.create_user(email=email, name='Ana Maria', password='x', role=role)


def _sozinho(user, texto, traducao='pt', dias=2):
    """A frase dita sozinho em `dias` dias diferentes (histórico)."""
    agora = timezone.now()
    for d in range(dias, 0, -1):
        servico.registar_item(user, texto, traducao, estado=ItemBanco.SOZINHO, quando=agora - timedelta(days=d))
    return ItemBanco.objects.get(user=user, chave=servico.normalizar(texto))


def _servido(user, exercicio_id, forma, agora):
    s, _ = SessaoRevisao.objects.get_or_create(user=user, dia=hoje_luanda(agora))
    s.exercicios = {**(s.exercicios or {}), exercicio_id: {'forma': forma}}
    s.save()
    return exercicio_id


class Base(TestCase):

    def setUp(self):
        cache.clear()
        self.u = _aluno()
        self.agora = timezone.now()

    def dia(self, n):
        return self.agora + timedelta(days=n)

    def errar_revisao(self, item, n):
        eid = _servido(self.u, f'item:{item.pk}', revisao.TRADUZIR, self.dia(n))
        return revisao.responder(self.u, eid, revisao.TRADUZIR, 'Something else entirely.', segundos=5,
                                 agora=self.dia(n))

    def acertar_revisao(self, item, n):
        eid = _servido(self.u, f'item:{item.pk}', revisao.TRADUZIR, self.dia(n))
        return revisao.responder(self.u, eid, revisao.TRADUZIR, item.texto, segundos=5, agora=self.dia(n))


class RegrasTests(Base):

    def test_sobe_a_sozinho_e_conta_o_historico(self):
        item = _sozinho(self.u, FRASE_1, dias=2)
        self.assertEqual((item.estado, item.vezes_sozinho, item.dias_sozinho, item.falhas_seguidas),
                         (ItemBanco.SOZINHO, 2, 2, 0))

    def test_uma_falha_nao_desce_e_duas_no_mesmo_dia_contam_uma(self):
        item = _sozinho(self.u, FRASE_1)
        self.assertFalse(servico.registar_falha(item, self.dia(0)))
        self.assertFalse(servico.registar_falha(item, self.dia(0) + timedelta(minutes=5)))
        self.assertEqual((item.estado, item.falhas_seguidas), (ItemBanco.SOZINHO, 1))

    def test_falhas_em_estados_baixos_nao_descem_mais(self):
        item = servico.registar_item(self.u, FRASE_1, estado=ItemBanco.RECONHECIDA)
        for n in range(3):
            self.assertFalse(servico.registar_falha(item, self.dia(n)))
        self.assertEqual(item.estado, ItemBanco.RECONHECIDA)


class RevisaoTests(Base):

    def test_duas_falhas_seguidas_descem_a_com_ajuda_e_guardam_o_historico(self):
        item = _sozinho(self.u, FRASE_1, dias=2)
        r1 = self.errar_revisao(item, -1)
        self.assertEqual((r1['estado_depois'], r1['desceu'], r1['subiu']), ('sozinho', False, False))
        r2 = self.errar_revisao(item, 0)
        self.assertEqual((r2['estado_antes'], r2['estado_depois'], r2['desceu'], r2['subiu']),
                         ('sozinho', 'com_ajuda', True, False))
        item.refresh_from_db()
        self.assertEqual(item.estado, ItemBanco.COM_AJUDA)
        self.assertEqual((item.vezes_sozinho, item.dias_sozinho, item.falhas_seguidas), (2, 2, 0))
        self.assertIsNotNone(item.ultima_vez_sozinho)
        t = revisao.terminar(self.u)
        self.assertEqual(t['subiram'], [])
        self.assertEqual([(d['texto'], d['depois']) for d in t['desceram']], [(FRASE_1, 'com_ajuda')])
        # Volta a ser frase a aprender (objectivos das conversas).
        self.assertIn(item.pk, [i.pk for i in servico.banco_a_aprender(self.u)])

    def test_acerto_no_meio_repoe_o_contador(self):
        item = _sozinho(self.u, FRASE_1)
        self.errar_revisao(item, 0)
        r = self.acertar_revisao(item, 1)
        self.assertTrue(r['correcta'])
        item.refresh_from_db()
        self.assertEqual(item.falhas_seguidas, 0)
        self.errar_revisao(item, 2)
        item.refresh_from_db()
        self.assertEqual((item.estado, item.falhas_seguidas), (ItemBanco.SOZINHO, 1))

    def test_dita_sozinho_numa_conversa_repoe_o_contador(self):
        item = _sozinho(self.u, FRASE_1)
        self.errar_revisao(item, 0)
        servico.registar_item(self.u, FRASE_1, estado=ItemBanco.SOZINHO, quando=self.dia(1))
        item.refresh_from_db()
        self.assertEqual((item.falhas_seguidas, item.vezes_sozinho), (0, 3))

    def test_fala_nao_aceite_conta_como_falha(self):
        item = _sozinho(self.u, FRASE_1)
        for n in (0, 1):
            eid = _servido(self.u, f'item:{item.pk}', revisao.OUVIR, self.dia(n))
            d = revisao.definicao(self.u, eid, agora=self.dia(n))
            r = revisao.registar_fala(self.u, d, eid, False, 40, segundos=4, agora=self.dia(n))
        self.assertTrue(r['desceu'])
        item.refresh_from_db()
        self.assertEqual(item.estado, ItemBanco.COM_AJUDA)

    def test_segunda_resposta_no_mesmo_dia_nao_conta(self):
        item = _sozinho(self.u, FRASE_1)
        self.errar_revisao(item, 0)
        self.errar_revisao(item, 0)
        item.refresh_from_db()
        self.assertEqual((item.estado, item.falhas_seguidas), (ItemBanco.SOZINHO, 1))


class LicaoEConversaTests(Base):

    def test_erro_na_licao_conta_como_falha(self):
        prof = _aluno('fb-prof@example.com', role='teacher')
        curso = Course.objects.create(teacher=prof, teacherName='Prof', title='FB curso', description='-',
                                      course_type='practice', status='Published')
        unidade = PracticeUnit.objects.create(course=curso, title='U', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        ch = PracticeChallenge.objects.create(lesson=licao, type='TRANSLATION', order=1, question='Pode enviar?')
        ChallengeOption.objects.create(challenge=ch, text=FRASE_1, is_correct=True, order=1)
        item = _sozinho(self.u, FRASE_1)
        item.falhas_seguidas, item.ultima_falha = 1, self.dia(-1)  # falhou ontem
        item.save()
        with self.captureOnCommitCallbacks(execute=True):
            ChallengeAttempt.objects.create(user=self.u, challenge=ch, is_correct=False)
        item.refresh_from_db()
        self.assertEqual((item.estado, item.vezes_sozinho), (ItemBanco.COM_AJUDA, 2))

    def _conversa(self, falas, correccoes, sid):
        s = VapiSession.objects.create(
            session_id=sid, user=self.u, level='B1', domain='general', duration_minutes=5,
            status=VapiSession.STATUS_AVALIADA,
            full_session_data={'config': {'objectivos': []}, 'correccoes': correccoes,
                               'transcricao': [{'quem': q, 'texto': t} for q, t in falas]})
        servico.registar_conversa(s)

    def test_frase_corrigida_numa_conversa_conta_como_falha(self):
        item = _sozinho(self.u, FRASE_1)
        item.falhas_seguidas, item.ultima_falha = 1, self.dia(-1)
        item.save()
        self._conversa([('tutor', 'What do you need?'), ('aluno', 'You send me report for Friday?')],
                       [{'disse': 'You send me report for Friday?', 'certo': FRASE_1}], 'fb-s1')
        item.refresh_from_db()
        self.assertEqual(item.estado, ItemBanco.COM_AJUDA)

    def test_corrigida_mas_dita_bem_sozinho_na_mesma_conversa_nao_conta(self):
        item = _sozinho(self.u, FRASE_1)
        item.falhas_seguidas, item.ultima_falha = 1, self.dia(-1)
        item.save()
        self._conversa([('tutor', 'What do you need?'), ('aluno', 'You send me report for Friday?'),
                        ('tutor', 'Try again.'), ('aluno', 'Sorry. Could you send me the report by Friday?')],
                       [{'disse': 'You send me report for Friday?', 'certo': FRASE_1}], 'fb-s2')
        item.refresh_from_db()
        self.assertEqual((item.estado, item.falhas_seguidas), (ItemBanco.SOZINHO, 1))


class NotaECertificadoTests(Base):

    def setUp(self):
        super().setUp()
        prof = _aluno('fb-prof2@example.com', role='teacher')
        self.curso = Course.objects.create(teacher=prof, teacherName='Prof', title='FB vídeo', description='x',
                                           category='Industry English', level='B1', course_type='video',
                                           status='Published', access_level='free')
        sec = CourseSection.objects.create(course=self.curso, sectionTitle='S1', order=1)
        aula = Chapter.objects.create(section=sec, title='Pedir', content='x', type='Video', order=1,
                                      video='https://x.ao/v.mp4')
        for i, texto in enumerate((FRASE_1, FRASE_2)):
            FraseAula.objects.create(chapter=aula, texto=texto, traducao='pt', tipo='frase',
                                     estado=FraseAula.APROVADA, ordem=i)
        matricular_em_curso(self.u, self.curso)
        self.item = _sozinho(self.u, FRASE_1)
        _sozinho(self.u, FRASE_2)

    def test_nota_do_curso_recalculada_e_certificado_emitido_fica(self):
        g = GradeCalculatorService(self.u, self.curso).calculate_and_save()
        self.assertEqual(g.phrases_score, 100.0)
        cert = CourseCertificate.objects.create(user=self.u, course=self.curso, final_grade=g.final_grade_percentage,
                                                final_grade_letter=g.final_grade_letter)
        nota_cert = cert.final_grade

        with self.captureOnCommitCallbacks(execute=True):
            self.errar_revisao(self.item, 0)
        self.assertEqual(StudentCourseGrade.objects.get(user=self.u, course=self.curso).phrases_score, 100.0)
        with self.captureOnCommitCallbacks(execute=True):
            self.errar_revisao(self.item, 1)
        g = StudentCourseGrade.objects.get(user=self.u, course=self.curso)
        self.assertEqual(g.phrases_score, 50.0)  # recalculada sem o aluno abrir as notas

        cert.refresh_from_db()
        self.assertIsNone(cert.revoked_at)
        self.assertEqual(cert.final_grade, nota_cert)
        from apps.courses.certificados import emitir_certificado
        self.assertEqual(emitir_certificado(self.u, self.curso), (cert, False))

    def test_ecras_de_progresso(self):
        for n in (0, 1):
            self.errar_revisao(self.item, n)
        p = servico.resumo_progresso(self.u)['frases_sozinho']
        self.assertEqual((p['total'], p['a_recuperar']), (1, 1))
        self.assertEqual([r['texto'] for r in p['recentes']], [FRASE_2])
        # O resumo da semana conta o que disse sozinho (facto da semana), mesmo a frase que desceu.
        self.assertEqual(fala.resumo_painel(self.u)['semana']['frases_sozinho'], 2)
