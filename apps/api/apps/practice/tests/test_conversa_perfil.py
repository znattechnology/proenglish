"""
Conversa com o tutor + perfil de fala (apps/perfil): objectivos, memória do tutor, avaliação
e ecrãs (preparar, resumo, progresso).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_conversa_perfil
"""
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from apps.perfil import servico as perfil
from apps.perfil.models import ItemBanco, PadraoErro, PerfilFala
from apps.practice.models import VapiSession
from apps.practice.tests.test_conversa import C, Base
from apps.practice.tests.test_seguranca_fase1 import Base as PraticaBase

OBJECTIVOS_RELATORIO = ['Could you send me the report by Friday?', 'When is the deadline?',
                        "I'll have it ready on Thursday."]
VAPI = dict(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
            ANTHROPIC_API_KEY='x', VAPI_PRIVATE_KEY='sk_test_falsa')


class PrepararCriarTests(Base):

    def test_preparar_objectivos_e_nivel_do_perfil(self):
        d = self.client.get(f'{C}preparar/').data
        self.assertEqual(d['perfil'], {'nivel': 'B1'})  # Intermediate -> B1
        obj = d['objectivos']['pedir_relatorio']
        self.assertEqual([o['en'] for o in obj], OBJECTIVOS_RELATORIO)
        self.assertEqual(obj[0]['pt'], 'Pode enviar-me o relatório até sexta-feira?')
        self.assertTrue(all(2 <= len(v) <= 4 for v in d['objectivos'].values()))
        PerfilFala.objects.filter(user=self.aluno).update(nivel_falar='B2')
        d = self.client.get(f'{C}preparar/').data
        self.assertEqual((d['perfil']['nivel'], d['preferencias']['nivel']), ('B2', 'B2'))

    def test_criar_guarda_objectivos_e_semeia_banco(self):
        d = self.criar().data
        self.assertEqual([o['en'] for o in d['objectivos']], OBJECTIVOS_RELATORIO)
        cfg = VapiSession.objects.get(pk=d['id']).full_session_data['config']
        self.assertEqual([o['en'] for o in cfg['objectivos']], OBJECTIVOS_RELATORIO)
        banco = ItemBanco.objects.filter(user=self.aluno)
        self.assertEqual(banco.count(), 4)  # as 4 frases da situação
        self.assertEqual(set(banco.values_list('estado', flat=True)), {'vista'})
        self.assertEqual(set(banco.values_list('origem', flat=True)), {'situacao'})
        self.assertTrue(all(i.situacao_id for i in banco))

    @override_settings(**VAPI)
    def test_prompt_tem_contexto_e_objectivos(self):
        perfil._registar_padroes(self.aluno, perfil.limpar_padroes([
            {'chave': 'third_person_s', 'descricao_pt': 'Com he/she/it o verbo leva -s.', 'errado': 'it include',
             'certo': 'it includes'}]), timezone.now())
        instrucoes = self.criar().data['vapi']['assistant_overrides']['variableValues']['instrucoes']
        self.assertIn('<student_profile>', instrucoes)
        self.assertIn('third_person_s', instrucoes)
        self.assertIn('<goal_phrases>', instrucoes)
        for frase in OBJECTIVOS_RELATORIO:
            self.assertIn(frase, instrucoes)
        self.assertIn('Never ask the student to repeat a phrase', instrucoes)
        self.assertIn('Correct at most one or two errors per turn', instrucoes)
        self.assertIn('Keep the student talking', instrucoes)
        # As regras do tutor vêm depois dos blocos de dados.
        self.assertGreater(instrucoes.index('Tutor rules'), instrucoes.index('</goal_phrases>'))

    def test_falha_no_perfil_nao_impede_a_conversa(self):
        with mock.patch('apps.perfil.servico.objectivos_detalhe', side_effect=RuntimeError('x')), \
                mock.patch('apps.perfil.servico.semear_situacao', side_effect=RuntimeError('x')):
            r = self.criar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data['objectivos']), 3)


class AvaliacaoRegrasTests(Base):

    def test_fluxo_simulado_actualiza_o_perfil(self):
        sid = self.criar().data['id']
        for fala in ["I'll have it ready on Thursday because the data is almost ready.",
                     'It include the monthly figures and a short summary for the team.',
                     'I need the sales data from you, and then I finish the draft in Monday.']:
            self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': fala}, format='json')
        self.recuar_inicio(sid, 130)
        r = self.terminar(sid).data
        self.assertEqual(r['estado'], 'avaliada')
        usados = {o['en']: o['usado'] for o in r['objectivos']}
        self.assertEqual(usados, {OBJECTIVOS_RELATORIO[0]: False, OBJECTIVOS_RELATORIO[1]: False,
                                  OBJECTIVOS_RELATORIO[2]: True})
        self.assertEqual({p['chave']: p['estado'] for p in r['padroes']},
                         {'third_person_s': 'novo', 'on_with_weekdays': 'novo'})
        self.assertEqual(ItemBanco.objects.get(user=self.aluno, chave="i'll have it ready on thursday").estado,
                         'sozinho')
        self.assertEqual(ItemBanco.objects.get(user=self.aluno, chave='on monday').origem, 'conversa')
        p = PerfilFala.objects.get(user=self.aluno)
        self.assertEqual((p.nivel_falar, p.conversas_avaliadas), ('B1', 1))  # regras: sem níveis
        dados = VapiSession.objects.get(pk=sid).full_session_data
        self.assertTrue(dados['perfil_registado'])
        self.assertIsNone(dados['nivel_cefr'])

        # Idempotente: registar outra vez não conta nada de novo.
        perfil.registar_conversa(VapiSession.objects.get(pk=sid))
        self.assertEqual(PadraoErro.objects.get(user=self.aluno, chave='third_person_s').ocorrencias, 1)
        self.assertEqual(ItemBanco.objects.get(user=self.aluno, chave="i'll have it ready on thursday").vezes_sozinho, 1)
        self.assertEqual(PerfilFala.objects.get(user=self.aluno).conversas_avaliadas, 1)

        g = self.client.get(f'{C}progresso/').data
        self.assertEqual(g['frases_sozinho']['total'], 1)
        self.assertEqual(g['frases_sozinho']['recentes'][0]['texto'], "I'll have it ready on Thursday.")
        self.assertEqual({p['chave'] for p in g['padroes']}, {'third_person_s', 'on_with_weekdays'})
        self.assertEqual(set(g['padroes'][0]), {'chave', 'descricao', 'errado', 'certo', 'ocorrencias',
                                               'ultima_ocorrencia', 'superado'})
        gram = next(c for c in g['por_competencia'] if c['chave'] == 'gramatica')
        if gram['valor'] is not None and gram['valor'] < 85:
            self.assertIn('Erro a trabalhar', gram['nota'])

    def test_resumo_mostra_superado_agora(self):
        sid = self.criar().data['id']
        for fala in ['It include the monthly figures and a short summary for the team.',
                     'The final deadline is Friday morning, I will send it by email.']:
            self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': fala}, format='json')
        self.recuar_inicio(sid, 130)
        self.terminar(sid)
        PadraoErro.objects.filter(user=self.aluno, chave='third_person_s').update(superado=True)
        r = self.client.get(f'{C}sessoes/{sid}/').data
        self.assertEqual(r['padroes'][0]['estado'], 'superado')


@override_settings(**VAPI)
class AvaliacaoClaudeTests(Base):

    TRANSCRICAO = [
        {'quem': 'tutor', 'texto': 'Hi Ana! I need the monthly report. When can you send it to me?'},
        {'quem': 'aluno', 'texto': 'What is the deadline for this report?'},
        {'quem': 'tutor', 'texto': 'Friday. Is that okay?'},
        {'quem': 'aluno', 'texto': 'Yes. She have the figures, I will ask her today.'},
        {'quem': 'tutor', 'texto': 'Great. Anything else?'},
        {'quem': 'aluno', 'texto': 'No, I will send it on Friday morning by email.'},
    ]

    def _resposta(self, **extra):
        r = {'fluencia': 70, 'gramatica': 60, 'vocabulario': 65,
             'correccoes': [{'disse': 'She have', 'certo': 'She has', 'porque': 'Com she, usa-se has.'}],
             'palavras_bem_usadas': ['deadline'], 'resumo': 'Bom trabalho.',
             'padroes': [{'chave': 'third_person_s', 'descricao_pt': 'Com he/she/it o verbo leva -s.',
                          'errado': 'She have', 'certo': 'She has'},
                         {'chave': 'not a valid KEY!!', 'descricao_pt': 'x', 'errado': '', 'certo': ''}],
             'nivel_cefr': {'falar': 'C1', 'gramatica': 'A2', 'vocabulario': 'Z1'},
             'objectivos_usados': ['When is the deadline?']}
        r.update(extra)
        return r

    def _conversa(self, resposta):
        # A avaliação usa a chamada verificada no Vapi (falso), não o que o browser manda.
        from apps.practice.tests.vapi_falso import VapiFalso
        vapi = VapiFalso()
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 130)
        cid = vapi.chamada(sid, [(t['quem'], t['texto']) for t in self.TRANSCRICAO], duracao=130)
        with mock.patch('apps.practice.conversa.analise._json', return_value=resposta) as j, \
                mock.patch('apps.practice.conversa.chamada.pedir', vapi):
            r = self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': self.TRANSCRICAO, 'call_id': cid},
                                 format='json').data
        return sid, r, j

    def test_campos_novos_guardados_e_perfil_actualizado(self):
        sid, r, j = self._conversa(self._resposta())
        self.assertEqual(r['estado'], 'avaliada')
        system, user = j.call_args.args[0], j.call_args.args[1]
        self.assertIn('objectivos_usados', system)
        self.assertIn('<session_goals>', user)
        self.assertIn('When is the deadline?', user)
        self.assertIn('<known_patterns>', user)
        esquema = j.call_args.args[5]
        self.assertTrue({'padroes', 'nivel_cefr', 'objectivos_usados'} <= set(esquema['required']))

        dados = VapiSession.objects.get(pk=sid).full_session_data
        self.assertEqual(dados['fonte_avaliacao'], 'claude')
        self.assertEqual(dados['nivel_cefr'], {'falar': 'C1', 'gramatica': 'A2'})
        self.assertEqual(dados['objectivos_usados'], ['When is the deadline?'])
        self.assertEqual(len(dados['padroes']), 2)
        self.assertTrue(dados['perfil_registado'])

        usados = {o['en']: o['usado'] for o in r['objectivos']}
        self.assertTrue(usados['When is the deadline?'])          # o Claude assinalou e o texto confirma
        self.assertFalse(usados['Could you send me the report by Friday?'])
        self.assertEqual([p['chave'] for p in r['padroes']], ['third_person_s', 'not_a_valid_key'])

        p = PerfilFala.objects.get(user=self.aluno)
        self.assertEqual((p.nivel_falar, p.nivel_gramatica, p.nivel_vocabulario), ('B2', 'B1', 'B1'))
        self.assertEqual(ItemBanco.objects.get(user=self.aluno, chave='she has').estado, 'vista')

        # A segunda conversa passa os padrões abertos ao Claude e reutiliza a chave.
        _, r2, j2 = self._conversa(self._resposta(padroes=[{'chave': 'third_person_s', 'descricao_pt': 'x',
                                                            'errado': 'he go', 'certo': 'he goes'}]))
        self.assertIn('third_person_s', j2.call_args.args[1])
        self.assertEqual(r2['padroes'][0]['estado'], 'recorrente')
        padrao = PadraoErro.objects.get(user=self.aluno, chave='third_person_s')
        self.assertEqual((padrao.ocorrencias, padrao.descricao), (2, 'Com he/she/it o verbo leva -s.'))
        self.assertEqual(PerfilFala.objects.get(user=self.aluno).nivel_falar, 'B2')  # ainda não sobe para C1

    def test_resposta_antiga_sem_campos_novos(self):
        antiga = {k: v for k, v in self._resposta().items() if k not in ('padroes', 'nivel_cefr', 'objectivos_usados')}
        sid, r, _ = self._conversa(antiga)
        self.assertEqual(r['estado'], 'avaliada')
        self.assertEqual(r['padroes'], [])
        dados = VapiSession.objects.get(pk=sid).full_session_data
        self.assertIsNone(dados['objectivos_usados'])
        self.assertTrue(dados['perfil_registado'])

    def test_falha_do_perfil_nao_parte_a_avaliacao(self):
        with mock.patch('apps.perfil.servico.registar_conversa', side_effect=RuntimeError('x')):
            _, r, _ = self._conversa(self._resposta())
        self.assertEqual(r['estado'], 'avaliada')


class LicaoHookTests(PraticaBase):

    @override_settings(PRONUNCIA_SIMULADA=True, DEBUG=True)
    def test_gravacao_aceite_fica_com_ajuda(self):
        r = self.pronunciar(self.falar)
        self.assertEqual(r.status_code, 200, r.content)
        item = ItemBanco.objects.get(user=self.aluno)
        self.assertEqual((item.texto, item.estado, item.origem), ('Please check the valve pressure.', 'com_ajuda', 'licao'))
        self.assertEqual((item.licao_id, item.curso_id), (self.licao.pk, self.curso.pk))

    @override_settings(PRONUNCIA_SIMULADA=True, DEBUG=True)
    def test_falha_do_perfil_nao_parte_o_exercicio(self):
        with mock.patch('apps.perfil.servico.registar_frase_licao', side_effect=RuntimeError('x')):
            r = self.pronunciar(self.falar)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(ItemBanco.objects.exists())
