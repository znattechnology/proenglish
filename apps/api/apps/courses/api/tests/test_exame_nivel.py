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


class GuiaoPorNivelTests(Base):

    def setUp(self):
        super().setUp()
        self.curso.level = 'A1'
        self.curso.save(update_fields=['level'])
        self.banco = [_situacao(self.curso, f'nv-a1-{i}', f'A1 exam situation {i}', exame_so=True, ordem=i)
                      for i in (1, 2, 3)]
        self.concluir()

    def prompt_e_sessao(self):
        ex, r = self.fazer_exame()
        sessao = r.data['sessao']
        return sessao['vapi']['assistant_overrides']['model']['messages'][0]['content'], sessao, ex

    def test_curso_a1_sem_guiao_usa_o_guiao_do_a1(self):
        prompt, sessao, ex = self.prompt_e_sessao()
        self.assertIn('Part 1: Interview', prompt)
        self.assertIn('Part 2: My day', prompt)
        self.assertIn('Part 3: Situation', prompt)
        self.assertIn('simpler version', prompt)
        self.assertNotIn('What would you do', prompt)
        self.assertNotIn('8 to 10 minutes', prompt)
        self.assertEqual(sessao['max_segundos'], 420)
        # Uma só situação sorteada, com a frase inicial.
        presentes = [s for s in self.banco if s.nome in prompt]
        self.assertEqual(len(presentes), 1)
        self.assertIn(presentes[0].extras['frase_inicial'], prompt)
        cfg = VapiSession.objects.get(pk=ex.sessao_id).full_session_data['config']
        self.assertEqual(cfg[exame.CHAVE_GUIAO]['partes'][0]['titulo'], 'Interview')
        self.assertEqual(cfg[exame.CHAVE_SITUACOES], [presentes[0].slug])
        e = self.client.get(f'{self.v}/{self.curso.id}/exame/').data
        self.assertEqual(e['duracao_minutos'], 7)

    def test_guiao_guardado_no_curso_ganha_ao_do_nivel(self):
        from apps.courses.models import CourseGradingConfig
        CourseGradingConfig.objects.update_or_create(course=self.curso, defaults={'exam_script': {
            'duracao': '5 to 6 minutes', 'max_minutos': 6, 'situacoes': 1,
            'partes': [{'titulo': 'Past and plans', 'perguntas': [
                {'pergunta': 'Hello, {nome}. What did you do last weekend?', 'simples': 'Last Saturday?'}]}],
            'notas': ['Ask "Can you tell me more?" once if the answer is one word.']}})
        prompt, sessao, _ = self.prompt_e_sessao()
        self.assertIn('Part 1: Past and plans', prompt)
        self.assertIn('Hello, Ana. What did you do last weekend?', prompt)
        self.assertIn('Can you tell me more?', prompt)
        self.assertNotIn('Interview', prompt)
        self.assertEqual(sessao['max_segundos'], 360)

    def test_guiao_invalido_no_curso_cai_no_do_nivel(self):
        from apps.courses.models import CourseGradingConfig
        CourseGradingConfig.objects.update_or_create(course=self.curso, defaults={'exam_script': {'partes': []}})
        prompt, _, _ = self.prompt_e_sessao()
        self.assertIn('Part 1: Interview', prompt)

    def test_curso_b1_continua_com_o_exame_geral(self):
        self.curso.level = 'B1'
        self.curso.save(update_fields=['level'])
        prompt, sessao, _ = self.prompt_e_sessao()
        self.assertIn('8 to 10 minutes', prompt)
        self.assertEqual(sessao['max_segundos'], 600)
        self.assertEqual(sum(1 for s in self.banco if s.nome in prompt), 3)  # três tarefas sorteadas

    @property
    def v(self):
        from apps.courses.api.tests.test_fase6_fala import V
        return V


class ValidarGuiaoTests(Base):

    def test_limpa_chavetas_e_limita(self):
        g = exame.validar_guiao({'max_minutos': 99, 'situacoes': 9, 'partes': [
            {'titulo': 'A', 'perguntas': [{'pergunta': 'Hi {nome}, {0} {x} ok?'}]}]})
        self.assertEqual(g['partes'][0]['perguntas'][0]['pergunta'], 'Hi {nome}, (0) (x) ok?')
        self.assertEqual((g['max_minutos'], g['situacoes']), (10, 3))
        self.assertEqual(g['partes'][0]['perguntas'][0]['pergunta'].format(nome='Ana'), 'Hi Ana, (0) (x) ok?')

    def test_formas_invalidas(self):
        for dados in (None, [], {}, {'partes': []}, {'partes': [{'titulo': '', 'perguntas': [{'pergunta': 'x'}]}]},
                      {'partes': [{'titulo': 'A', 'perguntas': []}]}, {'partes': [{'titulo': 'A', 'perguntas': ['x']}]},
                      {'partes': [{'titulo': 'A', 'perguntas': [{'pergunta': 'x'}]}], 'max_minutos': 'muito'}):
            self.assertIsNone(exame.validar_guiao(dados), dados)

    def test_comando_carrega_guiao_e_situacoes(self):
        import json
        import os
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        from apps.courses.models import CourseGradingConfig
        pasta = tempfile.mkdtemp()
        guiao = os.path.join(pasta, 'g.json')
        sits = os.path.join(pasta, 's.json')
        with open(guiao, 'w') as f:
            json.dump({'formato': 'x', 'max_minutos': 6, 'partes': [
                {'titulo': 'Interview', 'perguntas': [{'pergunta': 'Hello?'}]}]}, f)
        with open(sits, 'w') as f:
            json.dump({'situacoes': [{'slug': 'nv-cmd-1', 'nome': 'Cmd', 'descricao': 'd', 'papel_tutor': 'w',
                                      'nivel': 'A1', 'extras': {'parte': 3}}]}, f)
        call_command('carregar_exame_curso', str(self.curso.pk), guiao=guiao, situacoes=sits, stdout=StringIO())
        self.assertEqual(CourseGradingConfig.objects.get(course=self.curso).exam_script['max_minutos'], 6)
        s = Situacao.objects.get(slug='nv-cmd-1')
        self.assertEqual((s.curso_id, s.estado, s.extras['exame']), (self.curso.pk, Situacao.ACTIVO, True))
        self.assertEqual(exame.situacoes_de_exame(self.curso), [s])
