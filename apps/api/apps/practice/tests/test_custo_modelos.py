"""
Custo dos modelos Claude: cada tarefa usa o modelo mais barato que chega e o prompt de sistema
vai com cache_control. Tudo com o cliente Anthropic simulado (sem rede, sem gastos).
"""
import json
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

HAIKU, SONNET, OPUS = 'claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5'
CACHE = {'type': 'ephemeral'}

FALAS = ['I am sending the report to my manager today.',
         'We need the safety checklist before the shift starts.',
         'The pump was repaired yesterday and it works well now.']


def _resposta(dados):
    return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=json.dumps(dados))])


def _cliente(dados):
    c = mock.MagicMock()
    c.beta.messages.create.return_value = _resposta(dados)
    return c


class ModelosPorOmissaoTests(SimpleTestCase):
    """Os valores por omissão em core/settings.py (nenhuma variável de ambiente os muda no .env)."""

    def test_modelo_de_cada_tarefa(self):
        esperado = {
            'TRADUCAO_CLAUDE_MODELO': HAIKU,
            'PRONUNCIA_CLAUDE_MODELO': HAIKU,
            'RESPONDER_CLAUDE_MODELO': HAIKU,
            'REVISAO_CLAUDE_MODELO': HAIKU,
            'CONVERSA_CLAUDE_MODELO_AJUSTE': HAIKU,
            'CONVERSA_CLAUDE_MODELO': SONNET,
            'FRASES_AULA_CLAUDE_MODELO': SONNET,
            'PRATICA_CLAUDE_MODELO': SONNET,
            'EXAME_CLAUDE_MODELO': OPUS,
            'DIAGNOSTICO_CLAUDE_MODELO': OPUS,
        }
        self.assertEqual({k: getattr(settings, k) for k in esperado}, esperado)


@override_settings(ANTHROPIC_API_KEY='x', CONVERSA_CLAUDE_FALLBACKS=True)
class ModeloECacheTests(SimpleTestCase):

    def _kw(self, cliente):
        return cliente.beta.messages.create.call_args.kwargs

    def _cache_no_sistema(self, kw, contem):
        self.assertIsInstance(kw['system'], list)
        self.assertEqual(len(kw['system']), 1)
        bloco = kw['system'][0]
        self.assertEqual(bloco['type'], 'text')
        self.assertEqual(bloco['cache_control'], CACHE)
        self.assertIn(contem, bloco['text'])

    def test_avaliacao_da_conversa_usa_sonnet_com_cache(self):
        from apps.practice.conversa import analise
        from apps.practice.conversa.situacoes import SITUACOES
        c = _cliente({'fluencia': 70, 'gramatica': 60, 'vocabulario': 65, 'correccoes': [],
                      'palavras_bem_usadas': [], 'resumo': 'Bom.', 'padroes': [],
                      'nivel_cefr': {'falar': 'B1', 'gramatica': 'B1', 'vocabulario': 'B1'},
                      'objectivos_usados': []})
        t = [{'quem': 'aluno', 'texto': f} for f in FALAS]
        with mock.patch.object(analise, '_cliente', return_value=c):
            r = analise.avaliar(t, SITUACOES[0], 'B1', 'general', 120, simulado=False)
        self.assertEqual(r['fonte'], 'claude')
        kw = self._kw(c)
        self.assertEqual(kw['model'], SONNET)
        self.assertEqual(kw['fallbacks'], 'default')  # o Sonnet 5.5 aceita o recurso no servidor
        self.assertEqual(kw['output_config']['effort'], 'medium')
        self._cache_no_sistema(kw, 'English teacher assessing a workplace role-play')

    def test_ajuste_usa_haiku_sem_fallbacks_com_cache(self):
        from apps.practice.conversa import analise
        c = _cliente({'tem_erro': False, 'disse': '', 'certo': '', 'porque': ''})
        with mock.patch.object(analise, '_cliente', return_value=c):
            self.assertIsNone(analise.ajuste_claude('I am fine.'))
        kw = self._kw(c)
        self.assertEqual(kw['model'], HAIKU)
        self.assertNotIn('fallbacks', kw)
        self.assertNotIn('betas', kw)
        self._cache_no_sistema(kw, 'You check ONE sentence')

    def test_teste_de_nivel_usa_opus(self):
        from apps.practice.conversa import analise, diagnostico
        c = _cliente({'niveis': {'falar': 'B1', 'ouvir': 'B1', 'gramatica': 'A2', 'vocabulario': 'B1'},
                      'notas': {'fluencia': 60, 'gramatica': 55, 'vocabulario': 62},
                      'explicacoes': {'falar': '', 'ouvir': '', 'gramatica': '', 'vocabulario': ''},
                      'resumo': 'Bom.', 'padroes': []})
        t = [{'quem': 'aluno', 'texto': f} for f in FALAS]
        with mock.patch.object(analise, '_cliente', return_value=c):
            r = diagnostico.avaliar_claude(t, 200)
        self.assertEqual(r['fonte'], 'claude')
        kw = self._kw(c)
        self.assertEqual(kw['model'], OPUS)
        self.assertEqual(kw['fallbacks'], 'default')
        self._cache_no_sistema(kw, diagnostico.DIAGNOSTICO_SYSTEM[:60])

    @override_settings(DIAGNOSTICO_CLAUDE_MODELO='modelo-diagnostico', EXAME_CLAUDE_MODELO='modelo-exame',
                       CONVERSA_CLAUDE_MODELO='modelo-conversa')
    def test_exame_e_teste_de_nivel_tem_settings_proprios(self):
        from apps.practice.conversa import analise, diagnostico, exame
        vistos = []

        def falso_json(system, user, *a, modelo=None, **k):
            vistos.append(modelo)
            raise RuntimeError('pára aqui')

        sessao = SimpleNamespace(level='B1', duration_seconds=300)
        curso = SimpleNamespace(title='Curso')
        with mock.patch.object(analise, '_json', side_effect=falso_json), \
                mock.patch.object(exame, 'nivel_do_curso', return_value='B1'), \
                mock.patch.object(exame, 'situacoes_do_curso', return_value=[]):
            with self.assertRaises(RuntimeError):
                exame.avaliar_claude(sessao, [{'quem': 'aluno', 'texto': 'Hi'}], curso, [], [])
            with self.assertRaises(RuntimeError):
                diagnostico.avaliar_claude([{'quem': 'aluno', 'texto': 'Hi'}], 100)
        self.assertEqual(vistos, ['modelo-exame', 'modelo-diagnostico'])

    def test_traducao_usa_haiku_com_cache(self):
        from apps.practice.conversa import analise
        from apps.practice.services import ai_translation as t
        c = _cliente({'overall_score': 80})
        with mock.patch.object(analise, '_cliente', return_value=c):
            t._claude_json(t.SYSTEM_AVALIAR, '<source>a</source>', t.ESQUEMA_AVALIACAO)
        kw = self._kw(c)
        self.assertEqual(kw['model'], HAIKU)
        self.assertEqual(kw['output_config']['effort'], 'low')  # o Haiku 5.5 aceita effort
        self.assertNotIn('fallbacks', kw)
        self._cache_no_sistema(kw, t.SYSTEM_AVALIAR[:60])

    def test_pronuncia_usa_haiku(self):
        from apps.practice.conversa import analise
        from apps.practice.services import ai_pronunciation as p
        c = _cliente({'x': 1})
        with mock.patch.object(analise, '_cliente', return_value=c):
            p._claude_json(p.ANALISE_SYSTEM, '<expected>a</expected>', 5, 100, {'type': 'object'})
        kw = self._kw(c)
        self.assertEqual(kw['model'], HAIKU)
        self.assertNotIn('fallbacks', kw)
        self._cache_no_sistema(kw, p.ANALISE_SYSTEM[:60])

    def test_frases_da_aula_usam_sonnet_com_cache(self):
        from apps.courses import frases_aula
        c = _cliente({'frases': []})
        with mock.patch('anthropic.Anthropic', return_value=c):
            frases_aula.pedir_claude('<transcript>\n</transcript>')
        kw = self._kw(c)
        self.assertEqual(kw['model'], SONNET)
        self.assertEqual(kw['fallbacks'], 'default')
        self._cache_no_sistema(kw, frases_aula.SYSTEM[:60])

    def test_gerar_licao_usa_sonnet_com_cache(self):
        from apps.courses.api.teacher import gerar_licao
        c = _cliente({'titulo_sugerido': 'X', 'exercicios': []})
        with mock.patch.object(gerar_licao, '_cliente', return_value=c):
            gerar_licao.pedir_claude('<teacher_objective>x</teacher_objective>')
        kw = self._kw(c)
        self.assertEqual(kw['model'], SONNET)
        self.assertEqual(kw['fallbacks'], 'default')
        self._cache_no_sistema(kw, gerar_licao.SYSTEM[:60])
