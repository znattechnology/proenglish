"""
Fase 3 (medir a fala): métricas por gravação, tempo de fala nas conversas, fala -> texto,
fornecedores de avaliação de pronúncia (texto / Azure) e limite do plano.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_fase3_fala
"""
import base64
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.practice.conversa import tempo_fala
from apps.practice.models import AvaliacaoDetalhadaDia, TentativaPronuncia, VapiSession
from apps.practice.services import metricas_fala, pronuncia, transcricao_fala
from apps.practice.services.pronuncia import azure
from apps.practice.services.pronuncia.base import ErroProvedor, ResultadoPronuncia
from apps.practice.tests.test_conversa import FALAS_BOAS, Base as ConversaBase, _plano
from apps.practice.tests.test_fala_webhook import SEGREDO, WEBHOOK, _relatorio
from apps.practice.tests.test_seguranca_fase1 import Base as PraticaBase
from apps.subscriptions.models import SubscriptionPlan, UserSubscription
from apps.users.models import User


def _p(palavra, ini, fim):
    return {'palavra': palavra, 'inicio': ini, 'fim': fim}


# Resposta gravada do Azure (formato da REST API para áudio curto, notas no próprio objecto).
AZURE_JSON = {
    'RecognitionStatus': 'Success', 'Offset': 5000000, 'Duration': 21000000, 'DisplayText': 'Please check the valve pressure.',
    'NBest': [{
        'Confidence': 0.93, 'Lexical': 'please check the valve pressure', 'Display': 'Please check the valve pressure.',
        'AccuracyScore': 78.0, 'FluencyScore': 85.0, 'CompletenessScore': 100.0, 'ProsodyScore': 71.4, 'PronScore': 80.2,
        'Words': [
            {'Word': 'please', 'Offset': 5000000, 'Duration': 3000000, 'AccuracyScore': 95.0, 'ErrorType': 'None',
             'Phonemes': [{'Phoneme': 'p', 'AccuracyScore': 98.0}, {'Phoneme': 'l', 'AccuracyScore': 94.0}]},
            {'Word': 'check', 'Offset': 8200000, 'Duration': 3000000, 'AccuracyScore': 90.0, 'ErrorType': 'None',
             'Phonemes': [{'Phoneme': 'tʃ', 'AccuracyScore': 88.0}]},
            {'Word': 'the', 'Offset': 11300000, 'Duration': 1000000, 'AccuracyScore': 41.0, 'ErrorType': 'Mispronunciation',
             'Phonemes': [{'Phoneme': 'ð', 'AccuracyScore': 20.0}, {'Phoneme': 'ə', 'AccuracyScore': 70.0}]},
            {'Word': 'valve', 'Offset': 12500000, 'Duration': 4000000, 'AccuracyScore': 66.0, 'ErrorType': 'None',
             'Phonemes': [{'Phoneme': 'v', 'AccuracyScore': 60.0}]},
            {'Word': 'pressure', 'Offset': 27000000, 'Duration': 5000000, 'AccuracyScore': 88.0, 'ErrorType': 'None'},
        ],
    }],
}


# ---------------------------------------------------------------------------
# Métricas de uma gravação
# ---------------------------------------------------------------------------

class MetricasPalavrasTests(SimpleTestCase):

    def test_pausas_ppm_e_segundos(self):
        palavras = [_p('please', 0.5, 0.8), _p('check', 0.9, 1.2), _p('the', 1.25, 1.35),
                    _p('valve', 2.85, 3.3), _p('pressure', 3.4, 4.0)]
        m = metricas_fala.metricas_de_palavras(palavras)
        self.assertEqual(m['fonte_tempo'], 'medido')
        self.assertEqual(m['palavras_ditas'], 5)
        self.assertEqual(m['pausas_longas'], 1)           # 1.35 -> 2.85 = 1.5 s
        self.assertEqual(m['pausas_longas_s'], 1.5)
        self.assertEqual(m['maior_pausa_s'], 1.5)
        self.assertEqual(m['segundos_fala'], 2.0)         # span 3.5 s - 1.5 s de pausa longa
        self.assertEqual(m['ppm'], round(5 / (3.5 / 60), 1))  # inclui as pausas
        self.assertEqual(m['tempos_palavras'][0], ['please', 0.5, 0.8])

    def test_pausa_de_um_segundo_nao_e_longa(self):
        m = metricas_fala.metricas_de_palavras([_p('a', 0, 0.5), _p('b', 1.5, 2.0), _p('c', 2.1, 2.5)])
        self.assertEqual(m['pausas_longas'], 0)
        self.assertEqual(m['maior_pausa_s'], 1.0)

    def test_uma_palavra_sem_ppm(self):
        m = metricas_fala.metricas_de_palavras([_p('valve', 0.2, 0.7)])
        self.assertIsNone(m['ppm'])
        self.assertEqual(m['segundos_fala'], 0.5)
        self.assertEqual(m['pausas_longas'], 0)

    def test_sem_tempos_estima(self):
        m = metricas_fala.metricas_de_palavras([], 'Please check the valve pressure now')
        self.assertEqual(m['fonte_tempo'], 'estimado')
        self.assertEqual(m['palavras_ditas'], 6)
        self.assertAlmostEqual(m['segundos_fala'], round(6 / 2.3, 2))
        self.assertIsNone(m['ppm'])
        self.assertIsNone(m['pausas_longas'])
        # com a duração da gravação: ppm e limite dos segundos
        m = metricas_fala.metricas_de_palavras([], 'Please check the valve pressure now', duracao_audio=2.0)
        self.assertEqual(m['segundos_fala'], 2.0)
        self.assertEqual(m['ppm'], 180.0)

    def test_sem_nada(self):
        m = metricas_fala.metricas_de_palavras(None, '')
        self.assertIsNone(m['segundos_fala'])
        self.assertIsNone(metricas_fala.resumo_publico(m))

    def test_tempos_invalidos_ignorados(self):
        m = metricas_fala.metricas_de_palavras([{'palavra': 'x', 'inicio': 'a', 'fim': 1}, 'lixo'], 'two words')
        self.assertEqual(m['fonte_tempo'], 'estimado')


# ---------------------------------------------------------------------------
# Fala -> texto (interface única; Whisper como adaptador)
# ---------------------------------------------------------------------------

@override_settings(TRANSCRICAO_FALA_PROVEDOR='openai', OPENAI_API_KEY='sk-test')
class TranscricaoFalaTests(SimpleTestCase):

    def test_whisper_com_tempos_por_palavra(self):
        cliente = mock.MagicMock()
        cliente.audio.transcriptions.create.return_value = SimpleNamespace(
            text=' Please check the valve. ', duration=3.2,
            words=[SimpleNamespace(word='Please', start=0.1, end=0.4), {'word': 'check', 'start': 0.5, 'end': 0.8},
                   {'word': 'bad', 'start': 2, 'end': 1}],
            segments=[{'start': 0.1, 'end': 1.5, 'text': 'Please check the valve.'}])
        t = transcricao_fala.WhisperOpenAI(cliente).transcrever(b'abc', 'audio/webm', 'en', True)
        kwargs = cliente.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kwargs['response_format'], 'verbose_json')
        self.assertEqual(kwargs['timestamp_granularities'], ['word', 'segment'])
        self.assertEqual(kwargs['language'], 'en')
        self.assertEqual(t.texto, 'Please check the valve.')
        self.assertEqual(t.palavras, [_p('Please', 0.1, 0.4), _p('check', 0.5, 0.8)])
        self.assertEqual(t.duracao, 3.2)
        self.assertEqual(t.segmentos[0]['texto'], 'Please check the valve.')

    def test_sdk_sem_tempos_pede_so_texto(self):
        cliente = mock.MagicMock()
        cliente.audio.transcriptions.create.side_effect = [TypeError('timestamp_granularities'), 'Hello there']
        t = transcricao_fala.WhisperOpenAI(cliente).transcrever(b'abc', 'audio/webm', 'en', True)
        self.assertEqual(t.texto, 'Hello there')
        self.assertEqual(t.palavras, [])
        self.assertEqual(cliente.audio.transcriptions.create.call_args.kwargs['response_format'], 'text')

    def test_falha_do_servico(self):
        cliente = mock.MagicMock()
        cliente.audio.transcriptions.create.side_effect = RuntimeError('429')
        with self.assertRaises(transcricao_fala.ErroTranscricao):
            transcricao_fala.WhisperOpenAI(cliente).transcrever(b'abc', 'audio/webm', 'en', True)

    def test_interface_usa_o_adaptador_configurado(self):
        falso = mock.MagicMock()
        falso.transcrever.return_value = transcricao_fala.Transcricao(texto='ok', fonte='falso')
        with mock.patch.object(transcricao_fala, 'adaptador', return_value=falso):
            self.assertEqual(transcricao_fala.transcrever(b'x').texto, 'ok')


# ---------------------------------------------------------------------------
# Conversas: tempo de fala do aluno
# ---------------------------------------------------------------------------

class TempoFalaTests(SimpleTestCase):
    TRANSCRICAO = [{'quem': 'tutor', 'texto': 'How was your week at the plant?'},
                   {'quem': 'aluno', 'texto': 'It was busy, we checked all the valves.'},
                   {'quem': 'tutor', 'texto': 'Great.'},
                   {'quem': 'aluno', 'texto': 'Yes, and the pressure is fine now.'}]

    def test_medido_com_tempos_do_vapi(self):
        t0 = 1_763_000_000_000
        msgs = [{'role': 'system', 'message': 'x', 'time': t0, 'endTime': t0},
                {'role': 'bot', 'message': 'How was your week at the plant?', 'time': t0, 'endTime': t0 + 4000,
                 'secondsFromStart': 0.5},
                {'role': 'user', 'message': 'It was busy, we checked all the valves.', 'time': t0 + 5000,
                 'endTime': t0 + 11000, 'secondsFromStart': 5.5},
                {'role': 'bot', 'message': 'Great.', 'time': t0 + 12000, 'duration': 1000},  # sem endTime: duration (ms)
                {'role': 'user', 'message': 'Yes, and the pressure is fine now.', 'secondsFromStart': 14, 'duration': 4}]
        segs = tempo_fala.segmentos_vapi(msgs)
        self.assertEqual([s['segundos'] for s in segs], [4.0, 6.0, 1.0, 4.0])
        r = tempo_fala.calcular(self.TRANSCRICAO, segs, 120)
        self.assertEqual(r['fonte_tempo'], 'medido')
        self.assertEqual(r['segundos_aluno'], 10.0)
        self.assertEqual(r['segundos_tutor'], 5.0)
        self.assertEqual(r['quota_fala_aluno'], 0.67)
        self.assertEqual(r['ppm_aluno'], round(15 / (10 / 60), 1))   # 8 + 7 palavras em 10 s
        self.assertEqual(r['palavras_por_turno'], 7.5)

    def test_estimado_sem_tempos(self):
        r = tempo_fala.calcular(self.TRANSCRICAO, None, 120)
        self.assertEqual(r['fonte_tempo'], 'estimado')
        self.assertAlmostEqual(r['segundos_aluno'], round(15 / 2.3, 1))
        self.assertIsNone(r['ppm_aluno'])
        self.assertEqual(r['palavras_por_turno'], 7.5)
        # tempos sem duração utilizável: também estimado
        segs = tempo_fala.segmentos_vapi([{'role': 'user', 'message': 'hi', 'time': 5, 'endTime': 2}])
        self.assertEqual(segs, [])

    def test_limitado_a_duracao_da_sessao(self):
        r = tempo_fala.calcular([{'quem': 'aluno', 'texto': ' '.join(['word'] * 300)}], None, 60)
        self.assertEqual(r['segundos_aluno'], 60)

    def test_frase_do_resumo(self):
        s = VapiSession(segundos_aluno=190, ppm_aluno=82.4, palavras_por_turno=9.2, quota_fala_aluno=0.55,
                        fonte_tempo='medido')
        self.assertEqual(tempo_fala.resumo(s)['frase'],
                         'Falou 3 min 10 s, 82 palavras por minuto, respostas de 9 palavras em média. '
                         'Falou 55% do tempo; o tutor o resto.')
        s = VapiSession(segundos_aluno=45, ppm_aluno=None, palavras_por_turno=6, quota_fala_aluno=None,
                        fonte_tempo='estimado')
        self.assertEqual(tempo_fala.resumo(s)['frase'], 'Falou cerca de 45 s, respostas de 6 palavras em média.')
        self.assertIsNone(tempo_fala.resumo(VapiSession(segundos_aluno=None)))


@override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
                   VAPI_WEBHOOK_SECRET=SEGREDO, VAPI_WEBHOOK_URL='https://api.exemplo.ao/api/v1/practice/vapi/webhook/',
                   VAPI_PRIVATE_KEY=None)
class WebhookTempoFalaTests(ConversaBase):
    """O end-of-call-report com tempos grava o tempo de fala medido e os minutos do dia."""

    def setUp(self):
        super().setUp()
        for alvo, kw in (('apps.practice.conversa.analise.avaliar_claude', {'side_effect': RuntimeError('sem claude')}),
                         ('apps.practice.conversa.webhook.executar_em_fundo',
                          {'side_effect': lambda f, *a: f(*a)})):
            p = mock.patch(alvo, **kw)
            p.start()
            self.addCleanup(p.stop)

    def enviar_com_tempos(self, sid):
        corpo = _relatorio(sid, duracao=125)
        t0 = 1_763_000_000_000
        for i, m in enumerate(corpo['message']['artifact']['messages']):
            m['time'] = t0 + i * 10_000
            m['endTime'] = t0 + i * 10_000 + (6000 if m['role'] == 'user' else 3000)
            m['secondsFromStart'] = i * 10
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(WEBHOOK, corpo, format='json', HTTP_X_VAPI_SECRET=SEGREDO)

    def test_abandonada_com_tempos_medidos(self):
        from apps.perfil.models import FalaDiaria
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 130)
        r = self.enviar_com_tempos(sid)
        self.assertEqual(r.json()['status'], 'fechada')
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.fonte_tempo, 'medido')
        self.assertEqual(s.segundos_aluno, 6.0 * len(FALAS_BOAS))
        self.assertEqual(s.segundos_tutor, 3.0 * len(FALAS_BOAS))
        self.assertIsNotNone(s.ppm_aluno)
        dia = FalaDiaria.objects.get(user=self.aluno)
        self.assertEqual(dia.segundos, 24.0)
        self.assertEqual(dia.fontes, {'conversa': 24.0})
        resumo = self.client.get(f'/api/v1/practice/conversa/sessoes/{sid}/').data
        self.assertEqual(resumo['fala']['fonte'], 'medido')
        self.assertTrue(resumo['fala']['frase'].startswith('Falou 24 s, '))

    def test_cliente_fecha_primeiro_e_o_relatorio_mede_depois(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 130)
        r = self.terminar(sid, [{'quem': 'aluno', 'texto': t} for t in FALAS_BOAS])
        # A transcrição do browser é só provisória: sem tempo de fala até à chamada verificada.
        self.assertEqual(r.data['estado'], 'a_avaliar')
        self.assertIsNone(r.data['fala'])
        self.enviar_com_tempos(sid)
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual((s.fonte_tempo, s.segundos_aluno), ('medido', 24.0))


# ---------------------------------------------------------------------------
# Fornecedores de avaliação de pronúncia
# ---------------------------------------------------------------------------

def _texto_ok(**kw):
    return ResultadoPronuncia(nota=70, fonte='texto', transcricao='Please check the valve pressure.',
                              texto_esperado='Please check the valve pressure.', aceite=True, **kw)


class AzureInterpretarTests(SimpleTestCase):

    def test_resposta_gravada(self):
        r = azure.interpretar(AZURE_JSON, 'Please check the valve pressure.')
        self.assertEqual((r.nota, r.fluencia, r.completude, r.prosodia), (80, 85, 100, 71))
        self.assertEqual(r.fonte, 'azure')
        self.assertTrue(r.aceite and r.detalhada)
        self.assertEqual(r.palavras_problematicas, ['the'])
        self.assertEqual(r.palavras[2], {'palavra': 'the', 'nota': 41, 'erro_tipo': 'Mispronunciation',
                                         'fonemas': [{'fonema': 'ð', 'nota': 20}, {'fonema': 'ə', 'nota': 70}]})
        self.assertIn('/ð/', r.sugestoes[0])
        self.assertEqual(r.credito, 8)
        # tempos das palavras (100 ns) -> segundos, e as métricas medidas
        self.assertEqual(r.tempos.palavras[0], _p('please', 0.5, 0.8))
        m = pronuncia.campos_tentativa(r)
        self.assertEqual(m['fonte_tempo'], 'medido')
        self.assertEqual(m['pausas_longas'], 1)        # valve acaba em 1.65 s, pressure começa em 2.7 s
        self.assertEqual(m['avaliacao'], 'azure')
        self.assertEqual(m['nota_prosodia'], 71)
        d = pronuncia.detalhe_publico(r)
        self.assertEqual(d['palavras'][2]['nota'], 41)
        self.assertIn('ð', d['dica'])

    def test_forma_do_sdk_aninhada(self):
        dados = {'RecognitionStatus': 'Success', 'NBest': [{
            'Display': 'Hello.', 'PronunciationAssessment': {'AccuracyScore': 100, 'FluencyScore': 100,
                                                             'CompletenessScore': 100, 'PronScore': 100},
            'Words': [{'Word': 'hello', 'Offset': 7500000, 'Duration': 13800000,
                       'PronunciationAssessment': {'AccuracyScore': 99.0, 'ErrorType': 'None'}}]}]}
        r = azure.interpretar(dados, 'Hello.')
        self.assertEqual(r.nota, 100)
        self.assertEqual(r.palavras[0]['nota'], 99)
        self.assertEqual(r.palavras_problematicas, [])

    def test_sem_fala_e_erro(self):
        for estado in ('NoMatch', 'InitialSilenceTimeout'):
            with self.assertRaises(ErroProvedor):
                azure.interpretar({'RecognitionStatus': estado}, 'x')
        with self.assertRaises(ErroProvedor):
            azure.interpretar({'RecognitionStatus': 'Success', 'NBest': []}, 'x')

    def test_cabecalho(self):
        params = json.loads(base64.b64decode(azure.cabecalho_avaliacao('Good morning.')))
        self.assertEqual(params, {'ReferenceText': 'Good morning.', 'GradingSystem': 'HundredMark',
                                  'Granularity': 'Phoneme', 'Dimension': 'Comprehensive', 'EnableMiscue': 'True',
                                  'EnableProsodyAssessment': 'True'})
        self.assertNotIn('EnableProsodyAssessment', json.loads(base64.b64decode(azure.cabecalho_avaliacao('x', 'en-GB'))))

    @override_settings(AZURE_SPEECH_KEY='chave-secreta', AZURE_SPEECH_REGION='westeurope', AZURE_SPEECH_ENDPOINT='')
    def test_pedido_rest(self):
        resposta = mock.MagicMock(status_code=200)
        resposta.json.return_value = AZURE_JSON
        with mock.patch.object(azure, 'para_wav', return_value=b'RIFF' + b'\x00' * 100) as wav, \
                mock.patch.object(azure.requests, 'post', return_value=resposta) as post:
            r = azure.ProvedorAzure().avaliar(b'webm', 'audio/webm', 'Please check the valve pressure.')
        wav.assert_called_once()
        url = post.call_args.args[0]
        self.assertEqual(url, 'https://westeurope.stt.speech.microsoft.com/speech/recognition/conversation/'
                              'cognitiveservices/v1?language=en-US&format=detailed')
        h = post.call_args.kwargs['headers']
        self.assertEqual(h['Ocp-Apim-Subscription-Key'], 'chave-secreta')
        self.assertEqual(h['Content-Type'], 'audio/wav; codecs=audio/pcm; samplerate=16000')
        self.assertEqual(post.call_args.kwargs['timeout'], azure.TIMEOUT)
        self.assertEqual(r.nota, 80)

    @override_settings(AZURE_SPEECH_KEY='chave-secreta', AZURE_SPEECH_REGION='westeurope')
    def test_http_erro_e_modo_livre(self):
        with mock.patch.object(azure, 'para_wav', return_value=b'RIFF'), \
                mock.patch.object(azure.requests, 'post', return_value=mock.MagicMock(status_code=401)):
            with self.assertRaises(ErroProvedor) as e:
                azure.ProvedorAzure().avaliar(b'x', 'audio/webm', 'Hello.')
        self.assertNotIn('chave-secreta', str(e.exception))
        with self.assertRaises(ErroProvedor):
            azure.ProvedorAzure().avaliar(b'x', 'audio/webm', None, modo='livre')

    def test_ffmpeg_converte(self):
        import io
        import wave
        feito = SimpleNamespace(returncode=0, stdout=b'\x01\x00' * 800)  # PCM s16le, sem cabeçalho
        with mock.patch.object(azure.shutil, 'which', return_value='/usr/bin/ffmpeg'), \
                mock.patch.object(azure.subprocess, 'run', return_value=feito) as run:
            wav = azure.para_wav(b'webm', 'audio/webm')
        args = run.call_args.args[0]
        self.assertIn('16000', args)
        self.assertIn('pcm_s16le', args)
        self.assertEqual(args[args.index('-f') + 1], 's16le')
        self.assertIn('-map_metadata', args)
        # Cabeçalho WAV verdadeiro, com os tamanhos certos (o ffmpeg num pipe não os consegue escrever).
        self.assertEqual(wav[:4], b'RIFF')
        self.assertEqual(int.from_bytes(wav[4:8], 'little'), len(wav) - 8)
        with wave.open(io.BytesIO(wav)) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 2, 16000, 800))
        with mock.patch.object(azure.shutil, 'which', return_value='/usr/bin/ffmpeg'), \
                mock.patch.object(azure.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout=b'')):
            with self.assertRaises(ErroProvedor):
                azure.para_wav(b'webm', 'audio/webm')


@override_settings(PRONUNCIA_SIMULADA=False, PRONUNCIA_PROVEDOR='auto', AZURE_SPEECH_KEY='k', AZURE_SPEECH_REGION='westeurope')
class EscolhaDoFornecedorTests(TestCase):

    def setUp(self):
        self.aluno = User.objects.create_user(email='f3-forn@example.com', name='F3 Aluno', password='x', role='student')
        self.plano = _plano('PREMIUM', 'F3 Premium', 10)
        self.plano.daily_detailed_pronunciation_limit = 2
        self.plano.save()
        UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=self.plano, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30)))
        self.texto = mock.patch.object(pronuncia.ProvedorTexto, 'avaliar', return_value=_texto_ok())
        self.texto_mock = self.texto.start()
        self.addCleanup(self.texto.stop)

    def avaliar(self):
        return pronuncia.avaliar(b'audio', 'audio/webm', 'Please check the valve pressure.', user=self.aluno)

    def test_azure_dentro_do_limite_depois_texto(self):
        detalhado = azure.interpretar(AZURE_JSON, 'Please check the valve pressure.')
        with mock.patch.object(azure.ProvedorAzure, 'avaliar', return_value=detalhado) as az:
            self.assertEqual(self.avaliar().fonte, 'azure')
            self.assertEqual(self.avaliar().fonte, 'azure')
            self.assertEqual(self.avaliar().fonte, 'texto')   # limite de 2 por dia
        self.assertEqual(az.call_count, 2)
        self.assertEqual(AvaliacaoDetalhadaDia.objects.get(user=self.aluno).usadas, 2)
        self.assertEqual(pronuncia.estado_detalhada(self.aluno)['restantes'], 0)

    def test_falha_do_azure_cai_no_texto_e_nao_gasta(self):
        with mock.patch.object(azure.ProvedorAzure, 'avaliar', side_effect=ErroProvedor('HTTP 500')):
            self.assertEqual(self.avaliar().fonte, 'texto')
        with mock.patch.object(azure.ProvedorAzure, 'avaliar', side_effect=RuntimeError('rede')):
            self.assertEqual(self.avaliar().fonte, 'texto')
        self.assertEqual(AvaliacaoDetalhadaDia.objects.get(user=self.aluno).usadas, 0)

    @override_settings(AZURE_SPEECH_KEY='')
    def test_desligado_sem_chave(self):
        with mock.patch.object(azure.ProvedorAzure, 'avaliar') as az:
            self.assertEqual(self.avaliar().fonte, 'texto')
        az.assert_not_called()
        self.assertFalse(pronuncia.estado_detalhada(self.aluno)['disponivel'])

    @override_settings(PRONUNCIA_PROVEDOR='texto')
    def test_desligado_por_configuracao(self):
        with mock.patch.object(azure.ProvedorAzure, 'avaliar') as az:
            self.assertEqual(self.avaliar().fonte, 'texto')
        az.assert_not_called()

    def test_plano_sem_detalhadas(self):
        self.plano.daily_detailed_pronunciation_limit = 0
        self.plano.save()
        with mock.patch.object(azure.ProvedorAzure, 'avaliar') as az:
            self.assertEqual(self.avaliar().fonte, 'texto')
        az.assert_not_called()

    def test_sem_texto_esperado_ou_modo_livre(self):
        with mock.patch.object(azure.ProvedorAzure, 'avaliar') as az:
            pronuncia.avaliar(b'audio', 'audio/webm', 'Hi', modo='livre', user=self.aluno)
            pronuncia.avaliar(b'audio', 'audio/webm', 'Hi')  # sem aluno
        az.assert_not_called()


@override_settings(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test')
class ExercicioPronunciaTests(PraticaBase):
    """POST analyze-ai-pronunciation/: métricas guardadas e notas por palavra na resposta."""

    def test_texto_com_tempos_guarda_metricas(self):
        t = transcricao_fala.Transcricao(texto='Please check the valve pressure.', fonte='openai_whisper',
                                         palavras=[_p('Please', 0.2, 0.5), _p('check', 0.6, 0.9), _p('the', 1.0, 1.1),
                                                   _p('valve', 2.4, 2.8), _p('pressure', 2.9, 3.4)])
        r = _texto_ok(palavras_problematicas=['valve'], tempos=t)
        with mock.patch.object(pronuncia.ProvedorTexto, 'avaliar', return_value=r), \
                self.captureOnCommitCallbacks(execute=True):
            resp = self.pronunciar(self.falar)
        self.assertEqual(resp.status_code, 200, resp.content)
        d = resp.json()
        self.assertIsNone(d['detalhe'])
        self.assertEqual(d['fala']['pausas_longas'], 1)
        tp = TentativaPronuncia.objects.get(user=self.aluno)
        self.assertEqual((tp.origem, tp.fonte_tempo, tp.palavras_ditas, tp.avaliacao), ('licao', 'medido', 5, 'texto'))
        self.assertEqual(tp.segundos_fala, 1.9)
        from apps.perfil.models import FalaDiaria, PalavraDificil
        self.assertEqual(FalaDiaria.objects.get(user=self.aluno).fontes, {'licao': 1.9})
        self.assertEqual(PalavraDificil.objects.get(user=self.aluno).palavra, 'valve')

    @override_settings(AZURE_SPEECH_KEY='k', AZURE_SPEECH_REGION='westeurope')
    def test_detalhada_na_resposta(self):
        SubscriptionPlan.objects.filter(plan_type='FREE').update(daily_detailed_pronunciation_limit=1)
        detalhado = azure.interpretar(AZURE_JSON, 'Please check the valve pressure.')
        with mock.patch.object(azure.ProvedorAzure, 'avaliar', return_value=detalhado):
            resp = self.pronunciar(self.falar)
        self.assertEqual(resp.status_code, 200, resp.content)
        d = resp.json()
        self.assertEqual(d['detalhe']['palavras'][2], {'palavra': 'the', 'nota': 41, 'erro_tipo': 'Mispronunciation'})
        self.assertIn('/ð/', d['detalhe']['dica'])
        self.assertEqual(d['ai_analysis']['overall_score'], 80)
        tp = TentativaPronuncia.objects.get(user=self.aluno)
        self.assertEqual((tp.avaliacao, tp.nota_completude), ('azure', 100))
        self.assertEqual(len(tp.palavras_detalhe), 5)


# ---------------------------------------------------------------------------
# Limite do plano (administração)
# ---------------------------------------------------------------------------

class LimitePlanoAdminTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        self.admin = User.objects.create_user(email='f3-admin@example.com', name='F3 Admin', password='x', role='admin',
                                              is_staff=True)
        self.plano = _plano('PREMIUM_PLUS', 'F3 Plus', 20)
        SubscriptionPlan.objects.filter(pk=self.plano.pk).update(monthly_price=2000, yearly_price=None)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.admin).access_token}')

    def test_editar_limite(self):
        url = f'/api/v1/admin/planos/{self.plano.id}/'
        r = self.client.patch(url, {'limites': {'pronuncia_detalhada_dia': 20}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['limites']['pronuncia_detalhada_dia'], 20)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.daily_detailed_pronunciation_limit, 20)
        for mau in (-1, 'x', None, 501):
            r = self.client.patch(url, {'limites': {'pronuncia_detalhada_dia': mau}}, format='json')
            self.assertEqual(r.status_code, 400, (mau, r.content))
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.daily_detailed_pronunciation_limit, 20)


# ---------------------------------------------------------------------------
# Análise pelo texto e geração de exercícios: Claude (sem chamadas de texto à OpenAI)
# ---------------------------------------------------------------------------

@override_settings(PRONUNCIA_CLAUDE_MODELO='claude-opus-5-5')
class AnaliseClaudeTests(SimpleTestCase):

    def test_analise_estruturada_e_limitada(self):
        import asyncio
        from apps.practice.services import ai_pronunciation as ap
        dados = {'pronunciation_score': 140, 'fluency_score': 70.4, 'clarity_score': -3, 'overall_score': 72,
                 'is_acceptable': True, 'feedback': 'Muito bem.', 'problematic_words': ['valve'] * 9,
                 'suggestions': ['a', 'b', 'c', 'd'], 'partial_credit': 15, 'confidence_level': 3}
        a = ap.AIPronunciationAnalyzer()
        with mock.patch('apps.practice.conversa.analise._json', return_value=dados) as pedido:
            r = asyncio.run(a._analyze_with_gpt4('please check the valf', 'Please check the valve.', 'beginner'))
        system, mensagem, timeout, max_tokens, esforco, esquema = pedido.call_args.args
        self.assertEqual(pedido.call_args.kwargs['modelo'], 'claude-opus-5-5')
        self.assertEqual(esforco, 'low')
        self.assertIs(esquema, ap.ANALISE_ESQUEMA)
        self.assertIn('"correcto"', system)
        self.assertIn('<heard>\nplease check the valf\n</heard>', mensagem)
        self.assertEqual((r.pronunciation_score, r.fluency_score, r.clarity_score, r.partial_credit), (100, 70, 0, 10))
        self.assertEqual(len(r.problematic_words), 6)
        self.assertEqual(r.confidence_level, 1.0)
        self.assertFalse(r.indisponivel)

    def test_sem_cliente_openai_para_o_texto(self):
        from apps.practice.services import ai_pronunciation as ap
        with mock.patch('openai.Client') as cliente:
            ap.AIPronunciationAnalyzer()
        cliente.assert_not_called()  # só o áudio de referência (tts-1) cria o cliente OpenAI

    def test_gerar_exercicio(self):
        import asyncio
        from apps.practice.services import ai_pronunciation as ap
        dados = {'text_to_speak': 'Check the pressure gauge.', 'difficulty_notes': ['x'], 'pronunciation_tips': ['y'],
                 'focus_points': ['z'], 'phonetic_guide': ''}
        with mock.patch('apps.practice.conversa.analise._json', return_value=dados) as pedido:
            r = asyncio.run(ap.AIPronunciationAnalyzer().generate_pronunciation_exercise('oil rig', 'beginner', 'sentence'))
        self.assertEqual(r, dados)
        self.assertIn('<topic>\noil rig\n</topic>', pedido.call_args.args[1])
        with mock.patch('apps.practice.conversa.analise._json', side_effect=RuntimeError('x')):
            r = asyncio.run(ap.AIPronunciationAnalyzer().generate_pronunciation_exercise('oil rig'))
        self.assertEqual(r['text_to_speak'], 'Practice pronunciation with oil rig')
