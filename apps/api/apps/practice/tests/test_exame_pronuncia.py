"""
Nota de pronúncia do exame oral (conversa/exame.avaliar_pronuncia): com gravação consentida e o
Azure Speech configurado, uma amostra de falas do aluno (tempos da chamada verificada) é cortada
com o ffmpeg e avaliada pelo Azure em modo livre, em segundo plano; a nota entra na nota do exame.

O Vapi, o Claude, o download da gravação, o ffmpeg e o Azure são sempre simulados.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_exame_pronuncia
"""
import base64
import json
import os
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.courses.api.tests.test_fase6_fala import EXAME_BOM, FALAS_EXAME, GRAVACAO, Base, _claude
from apps.courses.models import ExameOral
from apps.practice.conversa import exame
from apps.practice.models import VapiSession

AZURE = dict(PRONUNCIA_EXAME=True, PRONUNCIA_PROVEDOR='auto', AZURE_SPEECH_KEY='chave-falsa',
             AZURE_SPEECH_REGION='westeurope', AZURE_SPEECH_ENDPOINT='', PRONUNCIA_SIMULADA=False)
PCM = b'\x01\x00' * 16000  # 1 s de "som"


def resposta_azure(exactidao):
    corpo = {'RecognitionStatus': 'Success', 'Duration': 50_000_000,
             'NBest': [{'Display': 'x', 'AccuracyScore': exactidao, 'FluencyScore': 80, 'CompletenessScore': 100,
                        'ProsodyScore': 75, 'PronScore': exactidao, 'Words': []}]}
    return SimpleNamespace(status_code=200, json=lambda: corpo)


@override_settings(**AZURE)
class PronunciaExameTests(Base):

    def setUp(self):
        super().setUp()
        self.concluir()
        self.descarregados = []
        self.cortes = []
        self.ficheiros = []

        def descarregar(url, destino):
            self.descarregados.append(url)
            self.ficheiros.append(destino.name)
            destino.write(b'audio-falso')

        def ffmpeg(args, **kw):
            self.cortes.append((float(args[args.index('-ss') + 1]), float(args[args.index('-t') + 1])))
            return SimpleNamespace(returncode=0, stdout=PCM, stderr=b'')

        for alvo, kw in (('apps.practice.conversa.exame._descarregar', {'side_effect': descarregar}),
                         ('apps.practice.conversa.exame._ffmpeg', {'return_value': '/usr/bin/ffmpeg'}),
                         ('apps.practice.conversa.exame.subprocess.run', {'side_effect': ffmpeg})):
            p = mock.patch(alvo, **kw)
            self.addCleanup(p.stop)
            p.start()
        p = mock.patch('apps.practice.services.pronuncia.azure.requests.post',
                       side_effect=[resposta_azure(n) for n in (90, 80, 70, 60, 50)])
        self.addCleanup(p.stop)
        self.azure = p.start()

    def exame_gravado(self, consentimento=True, gravacao=GRAVACAO):
        """Exame avaliado; a chamada do Vapi tem tempos e (por omissão) a gravação."""
        self.claude.side_effect = _claude(exame_dados=EXAME_BOM)
        r = self.comecar_exame(consentimento)
        self.assertEqual(r.status_code, 201, r.content)
        sid = r.data['sessao']['id']
        self.ligar(sid)
        self.chamada(sid, FALAS_EXAME, duracao=300, gravacao=gravacao, tempos=True)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.terminar(sid).status_code, 200)
        return ExameOral.objects.get(pk=r.data['exame_id']), sid

    def test_avalia_a_pronuncia_e_entra_na_nota(self):
        ex, sid = self.exame_gravado()
        self.assertEqual(ex.estado, ExameOral.AVALIADO)
        falas = VapiSession.objects.get(pk=sid).full_session_data[exame.CHAVE_FALAS]
        self.assertEqual([f['inicio'] for f in falas], [10, 30, 50])  # as 3 falas do aluno, com tempos do Vapi
        self.assertEqual(self.descarregados, [GRAVACAO])
        # Cada fala cortada com margem: -ss início - 0,3 s, -t duração (6 s) + 0,6 s.
        self.assertEqual(self.cortes, [(9.7, 6.6), (29.7, 6.6), (49.7, 6.6)])
        self.assertEqual(self.azure.call_count, 3)
        cab = json.loads(base64.b64decode(self.azure.call_args.kwargs['headers']['Pronunciation-Assessment']))
        self.assertEqual(cab['EnableMiscue'], 'False')       # modo livre: sem guião
        self.assertEqual(cab['ReferenceText'], falas[-1]['texto'])  # contra o que o aluno disse
        pesos = [f['palavras'] for f in falas]
        esperada = round((90 * pesos[0] + 80 * pesos[1] + 70 * pesos[2]) / sum(pesos), 1)
        self.assertEqual(ex.nota_pronuncia, esperada)
        notas = [EXAME_BOM['fluencia'], EXAME_BOM['gramatica'], EXAME_BOM['vocabulario'], EXAME_BOM['tarefa'],
                 esperada]
        self.assertEqual(ex.nota_final, round(sum(notas) / 5, 1))
        reg = VapiSession.objects.get(pk=sid).full_session_data[exame.CHAVE_PRONUNCIA]
        self.assertEqual((reg['estado'], reg['tentativas'], len(reg['amostras'])), ('feita', 1, 3))
        self.assertFalse(any(os.path.exists(f) for f in self.ficheiros))  # a cópia temporária foi apagada
        # No exame_dict: notas.pronuncia e a nota da IA com ela.
        d = exame.exame_dict(ex)
        self.assertEqual((d['notas']['pronuncia'], d['nota_ia']), (esperada, ex.nota_final))
        # Idempotente: outra chamada não volta a avaliar.
        self.assertEqual(exame.avaliar_pronuncia(ex.pk), 'ignorada')
        self.assertEqual(self.azure.call_count, 3)

    def test_corre_em_segundo_plano(self):
        with mock.patch('apps.practice.conversa.webhook.executar_em_fundo') as fundo:
            ex, _ = self.exame_gravado()
        chamadas = [c for c in fundo.call_args_list if c.args[0] is exame.avaliar_pronuncia]
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0].args[1], ex.pk)
        self.assertIsNone(ExameOral.objects.get(pk=ex.pk).nota_pronuncia)  # não correu no pedido
        self.assertEqual(self.azure.call_count, 0)

    def test_sem_azure_fica_como_estava(self):
        with override_settings(AZURE_SPEECH_KEY=''):
            ex, _ = self.exame_gravado()
            self.assertEqual(exame.pronuncias_por_fazer(), 0)
        self.assertIsNone(ex.nota_pronuncia)
        self.assertEqual(ex.nota_final, round(sum(EXAME_BOM[k] for k in ('fluencia', 'gramatica', 'vocabulario',
                                                                         'tarefa')) / 4, 1))
        self.assertEqual((self.descarregados, self.azure.call_count), ([], 0))

    def test_sem_consentimento_nao_grava_nem_avalia(self):
        ex, sid = self.exame_gravado(consentimento=False)
        self.assertEqual(ex.estado, ExameOral.AVALIADO)
        self.assertIsNone(ex.nota_pronuncia)
        self.assertNotIn(exame.CHAVE_FALAS, VapiSession.objects.get(pk=sid).full_session_data)
        self.assertEqual(self.azure.call_count, 0)

    def test_gravacao_que_chega_depois(self):
        ex, sid = self.exame_gravado(gravacao=None)
        self.assertEqual(ex.estado, ExameOral.AVALIADO)
        self.assertIsNone(ex.nota_pronuncia)
        self.assertEqual(self.descarregados, [])
        # O relatório do Vapi traz a gravação mais tarde: guarda-a e avalia a pronúncia.
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(sid, recording=GRAVACAO)
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, GRAVACAO)
        self.assertIsNotNone(ex.nota_pronuncia)
        self.assertEqual(self.descarregados, [GRAVACAO])

    def test_falha_do_azure_e_o_cron_repete(self):
        self.azure.side_effect = [SimpleNamespace(status_code=503, json=lambda: {})] * 3 + \
            [resposta_azure(n) for n in (85, 85, 85)]
        ex, sid = self.exame_gravado()
        self.assertIsNone(ex.nota_pronuncia)
        reg = VapiSession.objects.get(pk=sid).full_session_data[exame.CHAVE_PRONUNCIA]
        self.assertEqual((reg['estado'], reg['tentativas']), ('erro', 1))
        # O comando (cron) tenta outra vez passados 2 minutos.
        ExameOral.objects.filter(pk=ex.pk).update(avaliado_em=timezone.now() - timedelta(minutes=5))
        out = StringIO()
        call_command('verificar_conversas_vapi', stdout=out, stderr=StringIO())
        self.assertIn('1 pronúncia(s) de exame avaliada(s)', out.getvalue())
        ex.refresh_from_db()
        self.assertEqual(ex.nota_pronuncia, 85)
        reg = VapiSession.objects.get(pk=sid).full_session_data[exame.CHAVE_PRONUNCIA]
        self.assertEqual((reg['estado'], reg['tentativas']), ('feita', 2))

    def test_bloqueio_e_tentativas(self):
        self.azure.side_effect = [SimpleNamespace(status_code=500, json=lambda: {})] * 30
        ex, sid = self.exame_gravado()
        # Uma tentativa a correr (há menos de 10 min) não deixa começar outra.
        s = VapiSession.objects.get(pk=sid)
        dados = dict(s.full_session_data)
        dados[exame.CHAVE_PRONUNCIA] = {'estado': 'a_avaliar', 'em': timezone.now().isoformat(), 'tentativas': 1}
        VapiSession.objects.filter(pk=sid).update(full_session_data=dados)
        self.assertEqual(exame.avaliar_pronuncia(ex.pk), 'ignorada')
        # Esgotadas as tentativas, desiste (a nota fica sem pronúncia, como sem Azure).
        dados[exame.CHAVE_PRONUNCIA] = {'estado': 'erro', 'em': timezone.now().isoformat(),
                                        'tentativas': exame.PRONUNCIA_MAX_TENTATIVAS}
        VapiSession.objects.filter(pk=sid).update(full_session_data=dados)
        n = self.azure.call_count
        self.assertEqual(exame.avaliar_pronuncia(ex.pk), 'ignorada')
        self.assertEqual(self.azure.call_count, n)

    def test_poucas_falas_sem_nota(self):
        falas = [('tutor', 'Hello, introduce yourself.'), ('aluno', 'My name is Ana and I am an engineer.'),
                 ('tutor', 'Thanks.'), ('aluno', 'Yes.')]
        self.claude.side_effect = _claude(exame_dados=EXAME_BOM)
        r = self.comecar_exame(True)
        sid = r.data['sessao']['id']
        self.ligar(sid)
        self.chamada(sid, falas, duracao=300, gravacao=GRAVACAO, tempos=True)
        with self.captureOnCommitCallbacks(execute=True):
            self.terminar(sid, falas=falas)
        ex = ExameOral.objects.get(pk=r.data['exame_id'])
        self.assertIsNone(ex.nota_pronuncia)
        self.assertEqual(self.azure.call_count, 0)
        self.assertEqual(self.descarregados, [])

    def test_aluno_apagou_a_gravacao_antes(self):
        with mock.patch('apps.practice.conversa.webhook.executar_em_fundo'):
            ex, _ = self.exame_gravado()
        exame.apagar_gravacao(ex)
        self.assertEqual(exame.avaliar_pronuncia(ex.pk), 'ignorada')
        self.assertEqual(self.descarregados, [])


class FalasParaPronunciaTests(SimpleTestCase):

    def m(self, papel, texto, inicio, segundos):
        return {'role': papel, 'message': texto, 'secondsFromStart': inicio, 'time': 1_700_000_000_000 + inicio * 1000,
                'endTime': 1_700_000_000_000 + (inicio + segundos) * 1000}

    def test_escolhe_as_falas_mais_longas_pela_ordem(self):
        msgs = [self.m('bot', 'Tell me about your work and your team, please.', 0, 4)]
        for i in range(8):
            palavras = ' '.join(['word'] * (4 + i))
            msgs.append(self.m('user', palavras, 10 + i * 10, 5))
        msgs += [self.m('user', 'Too short.', 100, 1),                       # poucas palavras
                 self.m('user', 'This one is far too long to send', 110, 40),  # mais de 25 s
                 {'role': 'user', 'message': 'no times at all in this message'}]
        falas = exame.falas_para_pronuncia(msgs)
        self.assertEqual(len(falas), exame.PRONUNCIA_MAX_AMOSTRAS)
        self.assertEqual([f['palavras'] for f in falas], [7, 8, 9, 10, 11])
        self.assertEqual([f['inicio'] for f in falas], sorted(f['inicio'] for f in falas))
        self.assertTrue(all(f['segundos'] == 5 for f in falas))

    def test_entrada_invalida(self):
        self.assertEqual(exame.falas_para_pronuncia(None), [])
        self.assertEqual(exame.falas_para_pronuncia([{'role': 'user', 'message': 'a b c d e',
                                                      'secondsFromStart': 'x', 'duration': 3}]), [])
