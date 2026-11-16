"""
Exame oral por nível (conteúdo do A1, docs/conteudo/a1/revisao-1/exame.md, secção 4):

1. Situações só do exame (Situacao.extras.exame): escondidas do aluno, sorteadas em cada exame e
   as mesmas na avaliação.
2. Guião do examinador por nível (A1 com guião próprio) ou guardado no curso (exam_script).
3. Escala de avaliação por nível (ou a do guião do curso) enviada ao Claude.

O Vapi e o Claude são sempre simulados.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_exame_nivel
"""
from unittest import mock

from apps.courses.api.tests.test_fase6_fala import C, EXAME_BOM, Base, _claude
from apps.courses.models import ExameOral
from apps.courses.services.grade_calculator import curso_tem_conversa
from apps.practice.conversa import exame
from apps.practice.models import Situacao, VapiSession


def _situacao(curso, slug, nome, exame_so=False, ordem=1, **extra):
    extras = {'exame': True, 'parte': 3, 'frase_inicial': f'Now a situation: {nome}.'} if exame_so else {}
    return Situacao.objects.create(slug=slug, nome=nome, descricao=f'Descrição de {nome}', curso=curso,
                                   estado=Situacao.ACTIVO, nivel='A1', ordem=ordem, extras=extras, **extra)


class SituacoesDeExameTests(Base):

    def setUp(self):
        super().setUp()
        self.conversa = _situacao(self.curso, 'nv-conversa', 'Conversa do curso')
        self.ex1 = _situacao(self.curso, 'nv-exame-1', 'Exam restaurant', exame_so=True)
        self.ex2 = _situacao(self.curso, 'nv-exame-2', 'Exam pharmacy', exame_so=True, ordem=2)

    def test_aluno_nao_ve_nem_usa_as_situacoes_do_exame(self):
        ids = [s['id'] for s in self.client.get(f'{C}preparar/').data['situacoes']]
        self.assertIn('nv-conversa', ids)
        self.assertNotIn('nv-exame-1', ids)
        self.assertNotIn('nv-exame-2', ids)
        r = self.client.post(f'{C}sessoes/', {'situacao': 'nv-exame-1', 'nivel': 'A1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('situacao', r.data['campos'])

    def test_so_situacoes_de_exame_nao_contam_como_conversa_do_curso(self):
        self.assertTrue(curso_tem_conversa(self.curso))
        self.conversa.delete()
        self.assertFalse(curso_tem_conversa(self.curso))

    def test_estado_mostra_so_os_titulos_das_situacoes_do_exame(self):
        temas = self.client.get(f'{self.v}/{self.curso.id}/exame/').data['temas']
        self.assertEqual(temas, [{'titulo': 'Exam restaurant', 'descricao': ''},
                                 {'titulo': 'Exam pharmacy', 'descricao': ''}])

    def test_sorteia_do_banco_do_exame_e_avalia_com_as_mesmas(self):
        self.concluir()
        with mock.patch('apps.practice.conversa.exame.random.SystemRandom.sample',
                        side_effect=lambda banco, n: [banco[1]]):
            ex, r = self.fazer_exame()
        prompt = r.data['sessao']['vapi']['assistant_overrides']['model']['messages'][0]['content']
        self.assertIn('Exam pharmacy', prompt)
        self.assertNotIn('Exam restaurant', prompt)
        self.assertNotIn('Conversa do curso', prompt)
        cfg = VapiSession.objects.get(pk=ex.sessao_id).full_session_data['config']
        self.assertEqual(cfg[exame.CHAVE_SITUACOES], ['nv-exame-2'])
        # A avaliação recebe a situação sorteada, não as outras.
        user_msg = next(c.args[1] for c in self.claude.call_args_list if c.args[0] == exame.EXAME_SYSTEM)
        self.assertIn('Exam pharmacy', user_msg)
        self.assertNotIn('Exam restaurant', user_msg)
        self.assertEqual(ex.estado, ExameOral.AVALIADO)

    def test_sem_banco_de_exame_usa_as_situacoes_do_curso_como_antes(self):
        Situacao.objects.filter(exame.q_situacao_de_exame()).delete()
        self.concluir()
        ex, r = self.fazer_exame()
        prompt = r.data['sessao']['vapi']['assistant_overrides']['model']['messages'][0]['content']
        self.assertIn('Conversa do curso', prompt)
        self.assertEqual(VapiSession.objects.get(pk=ex.sessao_id).full_session_data['config'][exame.CHAVE_SITUACOES],
                         ['nv-conversa'])

    @property
    def v(self):
        from apps.courses.api.tests.test_fase6_fala import V
        return V


_ = (EXAME_BOM, _claude)
