"""
Regressões do laboratório (exercícios falados das lições) — correcções da revisão de código:

- Whisper em baixo no SPEAKING: 503 com token para saltar, sem tirar vidas, sem chamar o Claude;
- silêncio: 422 sem_fala (sem Claude e sem custos); gravação recusada (HTTP 400/413): 422;
- gravações grandes: 413; os exercícios falados das lições não contam para o limite de análises;
- RESPONDER incompleto salta sem token; +10 pontos só uma vez; vidas ilimitadas no SPEAKING;
- métricas de pausas com palavras sobrepostas; orçamento de tempo; gerar lição com < 3 exercícios.

    ./venv/bin/python manage.py test apps.practice.tests.test_correccoes_lab
"""
from types import SimpleNamespace
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.courses import ciclo
from apps.courses.api.tests.test_fase4b_laboratorio import AUDIO_BOM, VEREDICTO_BOM, Fase4BBase
from apps.courses.api.tests.test_pratica_professor import ALUNO, EXEMPLOS, P, _resposta_claude
from apps.courses.models import Course
from apps.practice.models import ChallengeProgress, PracticeChallenge, PointsEntry, TentativaPronuncia, UserProgress
from apps.practice.services.transcricao_fala import ErroTranscricao, Transcricao

PRON = '/api/v1/practice/analyze-ai-pronunciation/'
NOTA_BAIXA = {'pronunciation_score': 5, 'fluency_score': 5, 'clarity_score': 5, 'overall_score': 5,
              'is_acceptable': False, 'feedback': 'Não disse nada.', 'problematic_words': [], 'suggestions': [],
              'partial_credit': 0, 'confidence_level': 0.9}
NOTA_BOA = {**NOTA_BAIXA, 'pronunciation_score': 90, 'fluency_score': 90, 'clarity_score': 90, 'overall_score': 90,
            'is_acceptable': True, 'feedback': 'Muito bem.', 'partial_credit': 10}
IA = dict(PRONUNCIA_SIMULADA=False, OPENAI_API_KEY='sk-test-x', ANTHROPIC_API_KEY='x', AZURE_SPEECH_KEY='',
          PRONUNCIA_PROVEDOR='auto')


class _ErroHttp(Exception):
    def __init__(self, status_code):
        super().__init__(f'HTTP {status_code}')
        self.status_code = status_code


@override_settings(**IA)
class FalarNaLicao(Fase4BBase):
    def setUp(self):
        super().setUp()
        self.entrar(self.prof)
        Course.objects.filter(pk=self.curso.pk).update(status=ciclo.RASCUNHO)
        self.fala = self.novo_exercicio(self.l1['id'], EXEMPLOS['pronuncia'])
        Course.objects.filter(pk=self.curso.pk).update(status=ciclo.PUBLICADO)
        self.como_aluno()

    def _claude(self, dados):
        cliente = mock.MagicMock()
        cliente.beta.messages.create.return_value = _resposta_claude(dados)
        return mock.patch('apps.practice.conversa.analise._cliente', return_value=cliente), cliente

    def _pron(self, audio=AUDIO_BOM):
        return self.client.post(PRON, {'audio': SimpleUploadedFile('g.webm', audio, 'audio/webm'),
                                       'challenge_id': self.fala['id']}, format='multipart')

    def _resp(self, audio=AUDIO_BOM):
        return self.client.post(f'{ALUNO}challenges/{self.resp["id"]}/responder/',
                                {'audio': SimpleUploadedFile('r.webm', audio, 'audio/webm')}, format='multipart')

    def test_whisper_em_baixo_503_sem_tirar_vida_nem_chamar_o_claude(self):
        patch, cliente = self._claude(NOTA_BAIXA)
        with patch, mock.patch('apps.practice.services.transcricao_fala.transcrever',
                               side_effect=ErroTranscricao('whisper: APIConnectionError')):
            r = self._pron()
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.json()['pode_saltar'])
        self.assertTrue(r.json()['token_saltar'])
        self.assertEqual(cliente.beta.messages.create.call_count, 0)
        self.assertEqual(self.progresso(), (3, 0))
        self.assertFalse(TentativaPronuncia.objects.exists())
        s = self.client.post(f'{ALUNO}challenge-progress/', {'challenge_id': self.fala['id'], 'saltar': True,
                                                             'token_saltar': r.json()['token_saltar']}, format='json')
        self.assertEqual(s.status_code, 200, s.content)
        self.assertTrue(ChallengeProgress.objects.get(user=self.aluno, challenge_id=self.fala['id']).skipped)

    def test_silencio_422_sem_claude(self):
        patch, cliente = self._claude(NOTA_BAIXA)
        with patch, mock.patch('apps.practice.services.transcricao_fala.transcrever', return_value=Transcricao(texto='  ')):
            r = self._pron()
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()['codigo'], 'sem_fala')
        self.assertEqual(cliente.beta.messages.create.call_count, 0)
        self.assertEqual(self.progresso(), (3, 0))

    def test_gravacao_recusada_pelo_fornecedor_422(self):
        for estado in (400, 413):
            with mock.patch('apps.practice.services.transcricao_fala.transcrever',
                            side_effect=ErroTranscricao('whisper: BadRequestError', audio_invalido=True)):
                r = self._pron()
                r2 = self._resp(b'x')
            self.assertEqual((r.status_code, r.json()['codigo']), (422, 'gravacao_invalida'), estado)
            self.assertEqual((r2.status_code, r2.json()['codigo']), (422, 'gravacao_invalida'), estado)
            self.assertNotIn('token_saltar', r2.json())
        self.assertEqual(self.progresso(), (3, 0))

    def test_gravacao_grande_413(self):
        grande = b'\x1a' * (5 * 1024 * 1024 + 1)
        with mock.patch('apps.practice.services.transcricao_fala.transcrever') as whisper:
            self.assertEqual(self._pron(grande).status_code, 413)
            self.assertEqual(self._resp(grande).status_code, 413)
        whisper.assert_not_called()

    def test_licao_nao_conta_para_o_limite_de_analises(self):
        """Decisão do dono: SPEAKING e RESPONDER das lições não gastam nem são bloqueados pelo limite."""
        from apps.practice.limite_licoes import hoje_luanda
        from apps.subscriptions.models import UserSubscription
        from apps.practice.tests.test_conversa import _plano
        plano = _plano('FREE', 'Gratuito', 0)
        plano.daily_ai_analyses_limit = 5
        plano.save()
        UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=plano, status='ACTIVE', daily_ai_analyses_used=5, last_reset_date=hoje_luanda()))
        patch, _ = self._claude(VEREDICTO_BOM)
        with patch, mock.patch('apps.practice.responder.transcrever', return_value="I'll have it ready by five."):
            r = self._resp()
        self.assertEqual(r.status_code, 200, r.content)
        patch, _ = self._claude(NOTA_BOA)
        with patch, mock.patch('apps.practice.services.transcricao_fala.transcrever',
                               return_value=Transcricao(texto=PracticeChallenge.objects.get(id=self.fala['id']).question)):
            r = self._pron()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(UserSubscription.objects.get(user=self.aluno).daily_ai_analyses_used, 5)

    def test_responder_incompleto_salta_sem_token(self):
        ch = PracticeChallenge.objects.get(id=self.resp['id'])
        ch.conversation_context = {}
        ch.save()
        r = self.client.post(f'{ALUNO}challenge-progress/', {'challenge_id': self.resp['id'], 'saltar': True},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['saltado'])

    def test_responder_mais_10_so_uma_vez(self):
        patch, _ = self._claude(VEREDICTO_BOM)
        with patch, mock.patch('apps.practice.responder.transcrever', return_value="I'll have it ready by five."):
            for _ in range(2):
                self.assertEqual(self._resp().status_code, 200)
        self.assertEqual(self.progresso(), (3, 10))
        self.assertEqual(ChallengeProgress.objects.filter(user=self.aluno, challenge_id=self.resp['id']).count(), 1)

    def test_speaking_vidas_ilimitadas(self):
        p = UserProgress.objects.get(user=self.aluno)
        p.hearts = 0
        p.save()
        patch, _ = self._claude(NOTA_BAIXA)
        with patch, mock.patch('apps.courses.api.student.practice_courses.views.has_unlimited_hearts', return_value=True), \
                mock.patch('apps.practice.services.transcricao_fala.transcrever', return_value=Transcricao(texto='hello')):
            r = self._pron()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['heartsUsed'], r.json()['user_progress']['hearts']), (0, 999))
        self.assertEqual(UserProgress.objects.get(user=self.aluno).hearts, 0)

    def test_speaking_perde_vida_e_diz_quantas(self):
        patch, _ = self._claude(NOTA_BAIXA)
        with patch, mock.patch('apps.practice.services.transcricao_fala.transcrever', return_value=Transcricao(texto='hello')):
            r = self._pron()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['heartsUsed'], 1)

    def test_speaking_pontos_com_curso(self):
        patch, _ = self._claude(NOTA_BOA)
        frase = PracticeChallenge.objects.get(id=self.fala['id']).question
        with patch, mock.patch('apps.practice.services.transcricao_fala.transcrever', return_value=Transcricao(texto=frase)):
            r = self._pron()
            r2 = self._pron()
        self.assertEqual((r.status_code, r.json()['points_earned'], r2.json()['points_earned']), (200, 10, 0))
        self.assertEqual(list(PointsEntry.objects.filter(user=self.aluno).values_list('curso_id', flat=True)),
                         [self.curso.pk])


class Transcricao_(SimpleTestCase):
    @override_settings(OPENAI_API_KEY='sk-test-x')
    def test_cliente_sem_repeticoes_e_timeout_curto(self):
        from apps.practice.services import transcricao_fala as tf
        with mock.patch('openai.OpenAI') as cls:
            tf.WhisperOpenAI().cliente()
        self.assertEqual(cls.call_args.kwargs['max_retries'], 0)
        self.assertLessEqual(cls.call_args.kwargs['timeout'], 20)

    def test_classificacao_dos_erros(self):
        from apps.practice.services import transcricao_fala as tf
        for estado, invalido in ((400, True), (413, True), (401, False), (429, False), (500, False), (None, False)):
            cli = mock.MagicMock()
            cli.audio.transcriptions.create.side_effect = _ErroHttp(estado) if estado else ConnectionError('x')
            with self.assertRaises(ErroTranscricao) as e:
                tf.WhisperOpenAI(cliente=cli).transcrever(b'abc', 'audio/webm', 'en', True)
            self.assertEqual(e.exception.audio_invalido, invalido, estado)


class Metricas(SimpleTestCase):
    def test_pausa_usa_o_fim_mais_tardio(self):
        from apps.practice.services.metricas_fala import metricas_de_palavras
        p = [{'palavra': 'a', 'inicio': 0.0, 'fim': 5.0}, {'palavra': 'b', 'inicio': 1.0, 'fim': 1.5},
             {'palavra': 'c', 'inicio': 4.0, 'fim': 4.5}]
        m = metricas_de_palavras(p)
        self.assertEqual((m['pausas_longas'], m['maior_pausa_s']), (0, 0.0))
        p.append({'palavra': 'd', 'inicio': 7.0, 'fim': 7.5})
        m = metricas_de_palavras(p)
        self.assertEqual((m['pausas_longas'], m['maior_pausa_s']), (1, 2.0))


class Orcamento(SimpleTestCase):
    @override_settings(PRONUNCIA_SIMULADA=False, PRONUNCIA_PROVEDOR='azure')
    def test_sem_tempo_depois_da_detalhada_fica_indisponivel(self):
        from apps.practice.services import pronuncia
        from apps.practice.services.pronuncia import ErroProvedor
        lento = mock.MagicMock()
        lento.nome = 'azure'
        lento.avaliar.side_effect = ErroProvedor('timeout')
        tempos = iter([0.0, 30.0])
        with mock.patch.object(pronuncia, '_detalhado', return_value=lento), \
                mock.patch.object(pronuncia, 'reservar', return_value=True), \
                mock.patch.object(pronuncia, 'devolver'), \
                mock.patch.object(pronuncia.time, 'monotonic', side_effect=lambda: next(tempos)), \
                mock.patch.object(pronuncia, 'ProvedorTexto') as texto:
            r = pronuncia.avaliar(b'x', 'audio/webm', 'Hello there.', user=SimpleNamespace(pk=1))
        self.assertTrue(r.indisponivel)
        texto.assert_not_called()


class GerarLicaoPequena(Fase4BBase):
    def test_menos_de_3_exercicios_503(self):
        base = {'enunciado': '', 'frase': '', 'opcoes': [], 'pares': [], 'resposta': '', 'contexto': '',
                'explicacao': ''}
        gerado = {'titulo_sugerido': 'Turno', 'exercicios': [
            {**base, **{k: v for k, v in EXEMPLOS[t].items() if k != 'audio_url'}}
            for t in ('escolher', 'completar', 'traduzir', 'pronuncia')]}
        cliente = mock.MagicMock()
        cliente.beta.messages.create.return_value = _resposta_claude(gerado)
        self.entrar(self.prof)
        u = self.nova_unidade('Gerada')
        with mock.patch('apps.courses.api.teacher.gerar_licao._cliente', return_value=cliente):
            r = self.client.post(f'{P}{self.curso.id}/gerar-licao/',
                                 {'unidade': u['id'], 'objectivo': 'Relatórios de turno', 'quantos': 6}, format='json')
        self.assertEqual(r.status_code, 503, r.content)

