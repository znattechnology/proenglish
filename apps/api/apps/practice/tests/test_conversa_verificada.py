"""
Conversas por voz: só a chamada verificada no Vapi conta (chamada.py, verificacao.py).
Regressões das revisões: transcrição do cliente avaliada, cobrança sem ligada/, webhook forjado,
id da chamada injectado, gravação que voltava depois de apagada, frases escritas/reveladas/eco,
nota mínima do exame, exame desligado.

O Vapi é o VapiFalso (apps/practice/tests/vapi_falso.py) e o Claude é simulado: nunca há pedidos reais.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_conversa_verificada
"""
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.courses.api.tests.test_fase6_fala import (
    C, EXAME_BOM, EXAME_FRACO, FALAS_EXAME, GRAVACAO, PROF, V, Base, _claude, _transcricao,
)
from apps.courses.models import CourseGradingConfig, ExameOral
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.perfil import servico as perfil
from apps.perfil.models import ItemBanco
from apps.practice.conversa import exame, verificacao, webhook
from apps.practice.models import VapiSession
from apps.practice.tests import test_conversa
from apps.practice.tests.vapi_falso import VapiFalso

FALSO = [('tutor', 'Hi'), ('aluno', 'FABRICATED perfect answer about refinery safety procedures today.'),
         ('tutor', 'ok'), ('aluno', 'Another FABRICATED long fluent answer with great vocabulary indeed.')]


class CobrancaTests(Base):

    def nova(self):
        r = self.client.post(f'{C}sessoes/', {'situacao': 'pedir_relatorio', 'nivel': 'B1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def test_sem_ligada_cobra_a_duracao_verificada(self):
        d = self.nova()
        self.assertNotIn('server', d['vapi']['assistant_overrides'])  # nada de token por sessão no browser
        self.chamada(d['id'], FALAS_EXAME, duracao=600)
        self.assertEqual(self.webhook(d['id'], recording=None).data['status'], 'fechada')
        s = VapiSession.objects.get(pk=d['id'])
        self.assertEqual((s.duration_seconds, s.duration_minutes), (600, 10))
        self.assertEqual(self.usados(), 10)

    def test_terminar_sem_chamada_nao_cobra_nem_avalia_e_expira_sem_nota(self):
        d = self.nova()
        self.ligar(d['id'], 200)
        t = self.client.post(f'{C}sessoes/{d["id"]}/terminar/', {'transcricao': _transcricao()}, format='json').data
        self.assertEqual((t['estado'], t['notas'], t['transcricao_provisoria']), ('a_avaliar', None, True))
        self.assertEqual(self.usados(), 0)
        self.claude.assert_not_called()
        # 30 minutos sem a chamada do Vapi: fecha sem nota, cobra pelo relógio do servidor.
        s = VapiSession.objects.get(pk=d['id'])
        s.full_session_data['aguarda_vapi'] = (timezone.now() - timedelta(minutes=31)).isoformat()
        s.save(update_fields=['full_session_data'])
        r = self.client.get(f'{C}sessoes/{d["id"]}/').data
        self.assertEqual(r['estado'], 'sem_avaliacao')
        self.assertIsNone(r['notas'])
        self.assertFalse(ItemBanco.objects.filter(user=self.aluno, estado=ItemBanco.SOZINHO).exists())

    def test_diagnostico_conta_os_comecados_sem_ligada(self):
        ids = []
        for _ in range(2):
            r = self.client.post(f'{C}diagnostico/comecar/', {}, format='json')
            self.assertEqual(r.status_code, 201, r.content)
            ids.append(r.data['sessao']['id'])
        # Sem ligada/ nem webhook, os dois contam.
        self.assertFalse(self.client.get(f'{C}diagnostico/').data['disponivel'])
        self.assertEqual(self.client.post(f'{C}diagnostico/comecar/', {}, format='json').status_code, 429)
        # O Vapi confirma que um nunca ligou (duração 0): esse não conta.
        self.chamada(ids[0], [], duracao=0)
        self.webhook(ids[0], recording=None)
        self.assertEqual(VapiSession.objects.get(pk=ids[0]).status, VapiSession.STATUS_NAO_LIGOU)
        self.assertTrue(self.client.get(f'{C}diagnostico/').data['disponivel'])

    def test_diagnostico_curto_sem_resultado(self):
        r = self.client.post(f'{C}diagnostico/comecar/', {}, format='json')
        sid = r.data['sessao']['id']
        self.terminar(sid, duracao=45)  # menos de 60 s confirmados pelo Vapi
        self.assertEqual(VapiSession.objects.get(pk=sid).status, VapiSession.STATUS_SEM_AVALIACAO)


class ExameVerificadoTests(Base):

    def setUp(self):
        super().setUp()
        self.concluir()

    def test_transcricao_do_cliente_nunca_avaliada(self):
        capt = []
        base = _claude(exame_dados=EXAME_BOM)

        def espia(system, user, *a, **k):
            capt.append(user)
            return base(system, user, *a, **k)
        self.claude.side_effect = espia
        r = self.comecar_exame(False)
        sid = r.data['sessao']['id']
        self.ligar(sid)
        # Sem o id da chamada: espera pelo Vapi e não avalia nada.
        t = self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': _transcricao(FALSO)}, format='json')
        self.assertEqual(t.status_code, 200, t.content)
        self.assertEqual(ExameOral.objects.get(pk=r.data['exame_id']).estado, ExameOral.A_AVALIAR)
        self.assertEqual(capt, [])
        # O relatório do Vapi chega: avalia com a transcrição verdadeira.
        self.chamada(sid, FALAS_EXAME, duracao=300)
        self.webhook(sid, recording=None)
        ex = ExameOral.objects.get(pk=r.data['exame_id'])
        self.assertEqual(ex.estado, ExameOral.AVALIADO)
        self.assertTrue(capt)
        self.assertFalse(any('FABRICATED' in u for u in capt))
        self.assertNotIn('FABRICATED', str(VapiSession.objects.get(pk=sid).full_session_data['transcricao']))

    def test_cliente_manda_outra_transcricao_com_o_id(self):
        r = self.comecar_exame(False)
        sid = r.data['sessao']['id']
        self.chamada(sid, FALAS_EXAME, duracao=300)
        self.terminar(sid, cliente=FALSO)
        s = VapiSession.objects.get(pk=sid)
        self.assertNotIn('FABRICATED', str(s.full_session_data['transcricao']))
        self.assertEqual(ExameOral.objects.get(pk=r.data['exame_id']).estado, ExameOral.AVALIADO)

    def test_exame_curto_sem_nota(self):
        r = self.comecar_exame(False)
        sid = r.data['sessao']['id']
        self.terminar(sid, duracao=90)  # < 120 s confirmados
        self.assertEqual(ExameOral.objects.get(pk=r.data['exame_id']).estado, ExameOral.INSUFICIENTE)

    def test_relatorio_forjado_com_token_antigo_nao_conta(self):
        r = self.comecar_exame(True)
        sid = r.data['sessao']['id']
        self.assertNotIn('server', r.data['sessao']['vapi']['assistant_overrides'])
        url = webhook.url_servidor(sid).replace('https://api.exemplo.ao', '')
        forjado = {'message': {'type': 'end-of-call-report', 'durationSeconds': 600,
                               'call': {'id': 'c1', 'assistantId': 'asst_1',
                                        'assistantOverrides': {'metadata': {'sessao_id': sid}}},
                               'artifact': {'recordingUrl': 'https://evil.example.com/a.wav',
                                            'messages': [{'role': 'user', 'message': 'forged answer one two three'}]}}}
        self.assertEqual(self.client.post(url, forjado, format='json').data['status'], 'sem_chamada')
        self.assertEqual(VapiSession.objects.get(pk=sid).status, VapiSession.STATUS_EM_CURSO)
        # O verdadeiro (segredo global) avalia e traz a gravação verdadeira; a ordem não importa.
        self.chamada(sid, FALAS_EXAME, duracao=300)
        self.assertEqual(self.webhook(sid).data['status'], 'fechada')
        ex = ExameOral.objects.get(pk=r.data['exame_id'])
        self.assertEqual((ex.estado, ex.gravacao_url), (ExameOral.AVALIADO, GRAVACAO))

    def test_gravacao_chega_depois_da_avaliacao(self):
        ex, r = self.fazer_exame(consentimento=True)  # avaliado por GET /call, ainda sem gravação
        self.assertEqual(ex.gravacao_url, '')
        self.assertEqual(self.webhook(ex.sessao_id).data['status'], 'ja_verificada')
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, GRAVACAO)

    def test_call_id_invalido_recusado(self):
        r = self.comecar_exame(True)
        sid = r.data['sessao']['id']
        self.client.post(f'{C}sessoes/{sid}/ligada/', {'call_id': '../assistant/asst_1'}, format='json')
        dados = VapiSession.objects.get(pk=sid).full_session_data
        self.assertNotIn('vapi_call_id', dados)
        self.assertNotIn('vapi_call_id_reclamado', dados)
        self.terminar(sid)
        self.client.delete(f"{V}/exames/{r.data['exame_id']}/gravacao/")
        for metodo, caminho in self.falso.pedidos:
            self.assertRegex(caminho, r'^/call/[0-9a-f-]{36}$')

    def test_id_de_outra_sessao_recusado(self):
        r = self.comecar_exame(False)
        sid = r.data['sessao']['id']
        alheia = self.falso.chamada('outra-sessao', FALAS_EXAME, duracao=300)
        self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': _transcricao(), 'call_id': alheia},
                         format='json')
        s = VapiSession.objects.get(pk=sid)
        self.assertIn(alheia, s.full_session_data['vapi_call_ids_recusados'])
        self.assertEqual(ExameOral.objects.get(pk=r.data['exame_id']).estado, ExameOral.A_AVALIAR)

    def test_gravacao_apagada_nao_volta(self):
        ex, _ = self.fazer_exame(consentimento=True)
        self.webhook(ex.sessao_id)
        d = self.client.delete(f'{V}/exames/{ex.pk}/gravacao/').data
        self.assertEqual((d['gravacao_url'], d['gravacao_apagada']), (None, True))
        self.assertNotIn('gravacao_url', VapiSession.objects.get(pk=ex.sessao_id).full_session_data)
        # Nada a põe de volta: a vista do exame, um novo relatório, a avaliação de novo.
        g = self.client.get(f'{V}/exames/{ex.pk}/').data
        self.assertIsNone(g['gravacao_url'])
        self.webhook(ex.sessao_id)
        exame.depois_de_avaliar(VapiSession.objects.get(pk=ex.sessao_id))
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, '')
        self.assertIsNotNone(ex.gravacao_apagada_em)

    def test_apagar_sem_confirmacao_do_vapi_fica_pendente(self):
        ex, _ = self.fazer_exame(consentimento=True)
        self.webhook(ex.sessao_id)
        self.falso.status_delete = 500
        d = self.client.delete(f'{V}/exames/{ex.pk}/gravacao/').data
        self.assertEqual((d['gravacao_url'], d['gravacao_apagada']), (None, True))
        ex.refresh_from_db()
        self.assertIsNone(ex.gravacao_apagada_em)
        self.assertTrue(VapiSession.objects.get(pk=ex.sessao_id).full_session_data['gravacao_apagar_pendente'])
        self.falso.status_delete = 404  # já não existe no Vapi: conta como apagada
        self.assertEqual(exame.apagar_gravacoes_antigas(), 1)
        ex.refresh_from_db()
        self.assertIsNotNone(ex.gravacao_apagada_em)
        self.assertNotIn('gravacao_apagar_pendente', VapiSession.objects.get(pk=ex.sessao_id).full_session_data)

    def test_erros_do_vapi_nunca_partem_as_paginas(self):
        ex, _ = self.fazer_exame(consentimento=True)
        self.vapi.side_effect = lambda m, c: (200, None)  # JSON que não é um objecto
        from django.core.cache import cache
        cache.clear()
        self.assertEqual(self.client.get(f'{V}/exames/{ex.pk}/').status_code, 200)
        self.vapi.side_effect = RuntimeError('rede')
        cache.clear()
        self.assertEqual(self.client.get(f'{V}/exames/{ex.pk}/').status_code, 200)
        self.entrar(self.prof)
        self.assertEqual(self.client.get(f'{PROF}/exames/{ex.pk}/').status_code, 200)

    def test_lista_do_professor_nao_chama_o_vapi(self):
        ex, _ = self.fazer_exame(consentimento=True)
        self.falso.chamadas[self.chamadas[ex.sessao_id]]['artifact']['recordingUrl'] = GRAVACAO
        self.falso.pedidos.clear()
        self.entrar(self.prof)
        self.client.get(f'{PROF}/exames/', {'curso': str(self.curso.id)})
        self.client.get(f'{PROF}/alunos/{self.aluno.id}/fala/')
        self.assertEqual(self.falso.pedidos, [])
        d = self.client.get(f'{PROF}/exames/{ex.pk}/').data  # só a vista de um exame
        self.assertEqual(d['gravacao_url'], GRAVACAO)

    def test_ajuste_no_exame_nao_chama_o_claude(self):
        r = self.comecar_exame(False)
        sid = r.data['sessao']['id']
        self.ligar(sid)
        with mock.patch('apps.practice.conversa.analise.ajuste_claude') as aj:
            d = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I have went to the refinery yesterday'},
                                 format='json').data
        aj.assert_not_called()
        self.assertIsNone(d['ajuste'])


class NotaMinimaTests(Base):

    def setUp(self):
        super().setUp()
        self.concluir()

    def test_passou_segue_a_nota_minima_de_agora(self):
        ex, _ = self.fazer_exame()  # 77.5 com mínimo 60: passou
        self.assertTrue(ex.aprovado)
        cfg = CourseGradingConfig.objects.get_or_create(course=self.curso)[0]
        cfg.min_exam_score = 80
        cfg.save(update_fields=['min_exam_score'])
        # Mesmo antes de sincronizar, as leituras usam a nota de agora.
        d = self.client.get(f'{V}/exames/{ex.pk}/').data
        self.assertEqual((d['aprovado'], d['nota_minima']), (False, 80))
        self.assertFalse(GradeCalculatorService(self.aluno, self.curso).calculate_exam_scores()['passed'])
        self.assertNotEqual(self.client.get(f'{V}/{self.curso.id}/exame/').data['motivo'], 'aprovado')
        self.assertEqual(exame.sincronizar_aprovacao(self.curso), 1)
        ex.refresh_from_db()
        self.assertEqual((ex.aprovado, ex.nota_minima), (False, 80))
        self.assertIsNotNone(ex.pode_repetir_em)
        # A nota do professor ganha, com a mesma regra.
        self.entrar(self.prof)
        r = self.client.post(f'{PROF}/exames/{ex.pk}/rever/', {'nota': 85}, format='json').data
        self.assertEqual((r['aprovado'], r['nota_minima']), (True, 80))

    def test_exame_desligado(self):
        cfg = CourseGradingConfig.objects.get_or_create(course=self.curso)[0]
        cfg.exam_enabled = False
        cfg.save(update_fields=['exam_enabled'])
        e = self.client.get(f'{V}/{self.curso.id}/exame/').data
        self.assertEqual((e['disponivel'], e['motivo']), (False, 'desligado'))
        r = self.comecar_exame()
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'desligado'))
        self.assertFalse(VapiSession.objects.filter(situation__startswith='exame-').exists())

    def test_data_para_repetir_em_hora_de_luanda(self):
        ex, _ = self.fazer_exame(dados=EXAME_FRACO)
        quando = timezone.now().replace(hour=23, minute=30, second=0, microsecond=0) + timedelta(days=3)
        ExameOral.objects.filter(pk=ex.pk).update(pode_repetir_em=quando)  # 23:30 UTC = 00:30 em Luanda
        m = self.client.get(f'{V}/{self.curso.id}/exame/').data['mensagem']
        self.assertIn((quando + timedelta(hours=1)).strftime('%d/%m/%Y às 00:30'), m)


# ---------------------------------------------------------------------------
# Perfil de fala: só a voz verificada marca 'sozinho'
# ---------------------------------------------------------------------------

OBJ = ['Could you send me the report by Friday?', 'When is the deadline?', "I'll have it ready on Thursday."]
VAPI = dict(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
            ANTHROPIC_API_KEY='', VAPI_PRIVATE_KEY='sk_test_falsa')


@override_settings(**VAPI)
class PerfilVozTests(test_conversa.Base):

    def setUp(self):
        super().setUp()
        self.vapi = VapiFalso()
        for alvo, kw in (('apps.practice.conversa.chamada.pedir', {'side_effect': self.vapi}),
                         ('apps.practice.conversa.analise._json', {'side_effect': RuntimeError('sem claude')})):
            p = mock.patch(alvo, **kw)
            p.start()
            self.addCleanup(p.stop)

    def estados(self):
        return dict(ItemBanco.objects.filter(user=self.aluno).values_list('texto', 'estado'))

    def falas(self):
        out = [('tutor', 'Hello, how can I help?')]
        for f in OBJ:
            out += [('aluno', f + ' And some more words to look natural here.'), ('tutor', 'Okay, great.')]
        return out

    def test_transcricao_do_cliente_nao_marca_sozinho(self):
        sid = self.criar().data['id']
        self.client.post(f'{C}sessoes/{sid}/ligada/', {}, format='json')
        self.recuar_inicio(sid, 130)
        self.terminar(sid, [{'quem': q, 'texto': t} for q, t in self.falas()])
        for f in OBJ:
            self.assertNotEqual(self.estados()[f], 'sozinho')

    def test_voz_verificada_marca_sozinho_menos_escritas_e_reveladas(self):
        sid = self.criar().data['id']
        falas = self.falas()
        cid = self.vapi.chamada(sid, falas, duracao=130)
        escrita = falas[3][1]  # a fala com OBJ[1]
        self.client.post(f'{C}sessoes/{sid}/ajuda/', {'escrito': escrita}, format='json')
        cliente = [{'quem': q, 'texto': t, **({'escrito': True} if t == escrita else {})} for q, t in falas]
        r = self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': cliente, 'call_id': cid,
                                                              'reveladas': [OBJ[2]]}, format='json')
        self.assertEqual(r.data['estado'], 'avaliada', r.data)
        e = self.estados()
        self.assertEqual(e[OBJ[0]], 'sozinho')
        self.assertEqual(e[OBJ[1]], 'com_ajuda')   # escrita, não dita
        self.assertEqual(e[OBJ[2]], 'com_ajuda')   # viu-a em inglês durante a conversa
        transcricao = VapiSession.objects.get(pk=sid).full_session_data['transcricao']
        self.assertTrue(next(t for t in transcricao if t['texto'] == escrita)['escrito'])


class UsoDaFraseTests(SimpleTestCase):
    FRASE = 'When is the deadline?'

    def t(self, *falas):
        return [{'quem': f[0], 'texto': f[1], **(f[2] if len(f) > 2 else {})} for f in falas]

    def test_eco_nos_dois_turnos_anteriores_do_tutor(self):
        dois = self.t(('tutor', 'When is the deadline? Ask me that.'), ('aluno', 'ok'), ('tutor', 'Go on.'),
                      ('aluno', 'When is the deadline?'))
        self.assertEqual(perfil.uso_da_frase(self.FRASE, dois), 'com_ajuda')
        tres = self.t(('tutor', 'When is the deadline? Ask me that.'), ('aluno', 'ok'), ('tutor', 'Hmm.'),
                      ('aluno', 'yes'), ('tutor', 'Go on.'), ('aluno', 'When is the deadline?'))
        self.assertEqual(perfil.uso_da_frase(self.FRASE, tres), 'sozinho')

    def test_escrita_so_com_ajuda(self):
        escrita = self.t(('tutor', 'Hi'), ('aluno', 'When is the deadline?', {'escrito': True}))
        self.assertEqual(perfil.uso_da_frase(self.FRASE, escrita), 'com_ajuda')
        self.assertIsNone(perfil.uso_da_frase(self.FRASE, self.t(('aluno', 'Hello there'))))


@override_settings(CONVERSA_SIMULADA=True)
class SimuladoTests(test_conversa.Base):

    def test_resposta_escrita_fica_marcada_no_historico(self):
        sid = self.criar().data['id']
        self.client.post(f'{C}sessoes/{sid}/ligada/', {}, format='json')
        self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'When is the deadline?', 'escrito': True},
                         format='json')
        self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'I can do it on Friday'}, format='json')
        hist = VapiSession.objects.get(pk=sid).full_session_data['historico']
        alunos = [t for t in hist if t['quem'] == 'aluno']
        self.assertEqual([t.get('escrito') for t in alunos], [True, None])


class ChamadaTests(SimpleTestCase):

    def test_call_id_so_uuid(self):
        from apps.practice.conversa import chamada
        self.assertIsNone(chamada.call_id_valido('../assistant/asst_1'))
        self.assertIsNone(chamada.call_id_valido('call_1'))
        self.assertEqual(chamada.call_id_valido('6F1C9A2E-1B2C-4D3E-8F90-0A1B2C3D4E5F'),
                         '6f1c9a2e-1b2c-4d3e-8f90-0a1b2c3d4e5f')
        dados = {'vapi_call_id': '6f1c9a2e-1b2c-4d3e-8f90-0a1b2c3d4e5f'}
        self.assertFalse(verificacao.reclamar_call_id(dados, '7f1c9a2e-1b2c-4d3e-8f90-0a1b2c3d4e5f'))
        self.assertNotIn('vapi_call_id_reclamado', dados)  # nunca troca um id confirmado pelo Vapi
