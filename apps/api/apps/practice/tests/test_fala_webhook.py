"""
Perfil de fala: tentativas de pronúncia guardadas e webhook do Vapi (end-of-call-report).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_fala_webhook
"""
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings

from apps.practice.conversa import webhook
from apps.practice.models import ChallengeAttempt, TentativaPronuncia, UserProgress, VapiSession
from apps.practice.study_services import pending_review_queryset
from apps.practice.tests.test_conversa import FALAS_BOAS, Base as ConversaBase
from apps.practice.tests.test_seguranca_fase1 import Base as PraticaBase

WEBHOOK = '/api/v1/practice/vapi/webhook/'
SEGREDO = 's3gredo-proprio-123'


def _resultado(aceitavel, palavras=()):
    return SimpleNamespace(
        transcribed_text='Please check the valf pressure.', expected_text='Please check the valve pressure.',
        pronunciation_score=55.6, fluency_score=70, clarity_score=60, overall_score=58 if not aceitavel else 85,
        is_acceptable=aceitavel, partial_credit=0, confidence_level=0.8,
        feedback='Atenção à palavra «valve».', problematic_words=list(palavras),
        suggestions=['Diga «valve» com v no fim.'], indisponivel=False,
    )


class TentativaPronunciaTests(PraticaBase):

    @override_settings(PRONUNCIA_SIMULADA=True, DEBUG=True)
    def test_simulada_guarda_tentativa_e_resposta(self):
        r = self.pronunciar(self.falar)
        self.assertEqual(r.status_code, 200, r.content)
        t = TentativaPronuncia.objects.get(user=self.aluno)
        self.assertEqual(r.json()['tentativa_id'], str(t.id))
        self.assertEqual(t.fonte, 'simulada')
        self.assertTrue(t.aceite)
        self.assertEqual(t.nota_geral, 82)
        self.assertEqual(t.texto_esperado, 'Please check the valve pressure.')
        self.assertEqual(t.challenge, self.falar)
        self.assertTrue(t.resposta.is_correct)
        self.assertEqual(ChallengeAttempt.objects.filter(user=self.aluno, challenge=self.falar).count(), 1)

    @override_settings(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test')
    def test_ia_errada_guarda_palavras_e_entra_na_revisao(self):
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
        analisar = mock.AsyncMock(return_value=_resultado(False, ['valve', 42, '', None]))
        with mock.patch.object(AIPronunciationAnalyzer, '__init__', lambda s: None), \
                mock.patch.object(AIPronunciationAnalyzer, 'analyze_pronunciation', analisar):
            r = self.pronunciar(self.falar)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['feedback']['problematic_words'], ['valve', '42'])
        t = TentativaPronuncia.objects.get(user=self.aluno)
        self.assertEqual(t.fonte, 'ia')
        self.assertFalse(t.aceite)
        self.assertEqual(t.nota_pronuncia, 56)
        self.assertEqual(t.transcricao, 'Please check the valf pressure.')
        self.assertEqual(t.palavras_problematicas, ['valve', '42'])
        self.assertFalse(t.resposta.is_correct)
        self.assertEqual([x['challenge_id'] for x in pending_review_queryset(self.aluno)], [self.falar.id])

    @override_settings(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test')
    def test_analise_indisponivel_nao_guarda(self):
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
        falha = _resultado(False)
        falha.indisponivel = True
        with mock.patch.object(AIPronunciationAnalyzer, '__init__', lambda s: None), \
                mock.patch.object(AIPronunciationAnalyzer, 'analyze_pronunciation',
                                  mock.AsyncMock(return_value=falha)):
            self.pronunciar(self.falar)
        self.assertFalse(TentativaPronuncia.objects.exists())
        self.assertFalse(ChallengeAttempt.objects.exists())


def _relatorio(sessao_id=None, falas=FALAS_BOAS, duracao=None, **extra):
    mensagens = [{'role': 'system', 'message': 'prompt'}]
    for f in falas:
        mensagens += [{'role': 'bot', 'message': 'Tell me more.'}, {'role': 'user', 'message': f}]
    msg = {'type': 'end-of-call-report', 'endedReason': 'customer-ended-call',
           'artifact': {'messages': mensagens}, 'call': {'id': 'call_1'}, **extra}
    if sessao_id:
        msg['call']['assistantOverrides'] = {'metadata': {'sessao_id': sessao_id}}
    if duracao is not None:
        msg['durationSeconds'] = duracao
    return {'message': msg}


@override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
                   VAPI_WEBHOOK_SECRET=SEGREDO, VAPI_WEBHOOK_URL='https://api.exemplo.ao/api/v1/practice/vapi/webhook/')
class WebhookFimChamadaTests(ConversaBase):

    def setUp(self):
        super().setUp()
        # Avaliação sem Claude (cai nas regras) e sem thread.
        for alvo, kw in (('apps.practice.conversa.analise.avaliar_claude', {'side_effect': RuntimeError('sem claude')}),
                         ('apps.practice.conversa.webhook.executar_em_fundo',
                          {'side_effect': lambda f, *a: f(*a)})):
            p = mock.patch(alvo, **kw)
            p.start()
            self.addCleanup(p.stop)

    def enviar(self, corpo, segredo=SEGREDO, query=''):
        extra = {'HTTP_X_VAPI_SECRET': segredo} if segredo else {}
        return self.client.post(WEBHOOK + query, corpo, format='json', **extra)

    def test_overrides_pedem_o_relatorio_ao_webhook(self):
        d = self.criar().data
        ov = d['vapi']['assistant_overrides']
        self.assertEqual(ov['serverMessages'], ['end-of-call-report'])
        self.assertTrue(ov['server']['url'].startswith('https://api.exemplo.ao/api/v1/practice/vapi/webhook/?sessao='))
        self.assertNotIn(SEGREDO, str(ov))  # vai pelo browser: nunca o segredo
        self.assertEqual(ov['artifactPlan'], {'recordingEnabled': False})

    @override_settings(VAPI_WEBHOOK_URL='http://localhost:8000/api/v1/practice/vapi/webhook/')
    def test_sem_url_publica_nao_ha_server(self):
        ov = self.criar().data['vapi']['assistant_overrides']
        self.assertNotIn('server', ov)
        self.assertNotIn('serverMessages', ov)

    def test_autenticacao(self):
        sid = self.criar().data['id']
        corpo = _relatorio(sid)
        self.assertEqual(self.enviar(corpo, segredo=None).status_code, 403)
        self.assertEqual(self.enviar(corpo, segredo='errado').status_code, 403)
        # token de outra sessão
        self.assertEqual(self.enviar(corpo, segredo=None,
                                     query=f'?sessao=outra&token={webhook.token_sessao("outra")}').status_code, 403)
        self.assertEqual(VapiSession.objects.get(pk=sid).status, 'em_curso')
        with override_settings(VAPI_WEBHOOK_SECRET=''):
            self.assertEqual(self.enviar(corpo).status_code, 404)

    def test_token_da_sessao_no_url(self):
        d = self.criar().data
        self.recuar_inicio(d['id'], 130)
        url = d['vapi']['assistant_overrides']['server']['url']
        r = self.client.post(url.replace('https://api.exemplo.ao', ''), _relatorio(), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'fechada')

    def test_abandonada_fecha_cobra_e_avalia_uma_vez(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 130)
        r = self.enviar(_relatorio(sid, duracao=125))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'fechada')
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.status, 'avaliada')
        self.assertEqual(s.duration_seconds, 125)  # limitado pela duração do Vapi
        self.assertEqual(s.duration_minutes, 3)
        self.assertEqual(self.usados(), 3)
        dados = s.full_session_data
        self.assertEqual([t['texto'] for t in dados['transcricao'] if t['quem'] == 'aluno'], FALAS_BOAS)
        self.assertEqual(dados['vapi_fim']['duracao_segundos'], 125)
        self.assertEqual(dados['vapi_fim']['call_id'], 'call_1')
        self.assertGreater(dados['pontos'], 0)
        pontos = UserProgress.objects.get(user=self.aluno).points

        # Repetido: nada muda (nem minutos, nem pontos).
        r = self.enviar(_relatorio(sid, duracao=125))
        self.assertEqual(r.json()['status'], 'repetido')
        self.assertEqual(self.usados(), 3)
        s2 = VapiSession.objects.get(pk=sid)
        self.assertEqual(s2.full_session_data['pontos'], dados['pontos'])
        self.assertEqual(UserProgress.objects.get(user=self.aluno).points, pontos)
        # O cliente terminar depois: devolve o resumo sem voltar a cobrar.
        r = self.terminar(sid, [{'quem': 'aluno', 'texto': 'outra coisa'}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['estado'], 'avaliada')
        self.assertEqual(self.usados(), 3)

    def test_transcricao_do_servidor_ganha_a_do_cliente(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 130)
        # O cliente já terminou com uma transcrição curta: sem avaliação.
        r = self.terminar(sid, [{'quem': 'aluno', 'texto': 'Hello.'}])
        self.assertEqual(r.data['estado'], 'sem_avaliacao')
        self.assertEqual(self.usados(), 3)
        r = self.enviar(_relatorio(sid))
        self.assertEqual(r.json()['status'], 'registada')
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.status, 'avaliada')
        self.assertIn(FALAS_BOAS[0], [t['texto'] for t in s.full_session_data['transcricao']])
        self.assertEqual(self.usados(), 3)  # minutos já cobrados: não mudam

    def test_sessao_desconhecida_ou_outro_tipo(self):
        self.assertEqual(self.enviar(_relatorio('nao-existe')).json()['status'], 'sessao_desconhecida')
        self.assertEqual(self.enviar({'message': {'type': 'status-update'}}).json()['status'], 'ignorado')
        self.assertEqual(self.enviar(_relatorio()).json()['status'], 'sem_sessao')

    def test_transcricao_vapi(self):
        t = webhook.transcricao_vapi([{'role': 'system', 'message': 'x'}, {'role': 'user', 'message': ' Hi  there '},
                                      {'role': 'assistant', 'message': 'Hello'}, {'role': 'tool_calls'}, 'lixo'])
        self.assertEqual(t, [{'quem': 'aluno', 'texto': 'Hi there'}, {'quem': 'tutor', 'texto': 'Hello'}])
