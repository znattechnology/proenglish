"""
Avaliações em segundo plano (conversa/webhook.executar_em_fundo): threads daemon sem fila.

- uma thread perdida (o Gunicorn recicla o worker com --max-requests) deixa a sessão 'a_avaliar';
  o comando verificar_conversas_vapi retoma-a passados 2 minutos, respeitando o bloqueio de
  servico.avaliar_pendente (AVALIACAO_BLOQUEIO_SEGUNDOS);
- no máximo AVALIACOES_EM_SIMULTANEO avaliações ao mesmo tempo por processo.

O Claude nunca é chamado (modo simulado: avaliação por regras).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_avaliacao_em_fundo
"""
import threading
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.practice.conversa import servico, webhook
from apps.practice.models import VapiSession
from apps.practice.tests import test_conversa

C = test_conversa.C


class AvaliacaoParadaTests(test_conversa.Base):

    def conversar(self):
        sid = self.criar().data['id']
        for f in test_conversa.FALAS_BOAS:
            self.assertEqual(self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': f}, format='json').status_code,
                             200)
        self.recuar_inicio(sid, 240)
        return sid

    def parada(self):
        """Uma conversa terminada cuja thread de avaliação nunca correu (worker reciclado)."""
        sid = self.conversar()
        with override_settings(AVALIACAO_EM_FUNDO=True), \
                mock.patch('apps.practice.conversa.webhook.executar_em_fundo') as fundo:
            t = self.terminar(sid)
        self.assertEqual(t.status_code, 200, t.content)
        fundo.assert_called_once()
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.status, VapiSession.STATUS_A_AVALIAR)
        return s

    def recuar(self, s, fim=None, iniciada=None):
        dados = dict(s.full_session_data or {})
        if iniciada is not None:
            dados['avaliacao_iniciada_em'] = (timezone.now() - iniciada).isoformat()
        VapiSession.objects.filter(pk=s.pk).update(ended_at=timezone.now() - (fim or timedelta(0)),
                                                   full_session_data=dados)

    def cron(self):
        out = StringIO()
        call_command('verificar_conversas_vapi', stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_cron_avalia_a_sessao_parada(self):
        s = self.parada()
        self.recuar(s, fim=timedelta(minutes=3))
        self.assertEqual(servico.avaliacoes_paradas(), [s.pk])
        saida = self.cron()
        self.assertIn('1 avaliação(ões) parada(s) retomada(s)', saida)
        s.refresh_from_db()
        self.assertEqual(s.status, VapiSession.STATUS_AVALIADA)
        self.assertNotIn('avaliacao_iniciada_em', s.full_session_data)

    def test_thread_perdida_a_meio_retomada_depois_do_bloqueio(self):
        s = self.parada()
        # A thread marcou o início e morreu com o worker há 3 minutos (bloqueio de 120 s já passou).
        self.recuar(s, fim=timedelta(minutes=4), iniciada=timedelta(minutes=3))
        self.cron()
        s.refresh_from_db()
        self.assertEqual(s.status, VapiSession.STATUS_AVALIADA)

    def test_respeita_o_bloqueio_de_uma_avaliacao_em_curso(self):
        s = self.parada()
        # Outra thread começou há 30 s (ainda dentro do bloqueio): o cron não a repete.
        self.recuar(s, fim=timedelta(minutes=5), iniciada=timedelta(seconds=30))
        self.assertEqual(servico.avaliacoes_paradas(), [])
        with mock.patch('apps.practice.conversa.servico.avaliar_pendente') as avaliar:
            self.cron()
        avaliar.assert_not_called()
        s.refresh_from_db()
        self.assertEqual(s.status, VapiSession.STATUS_A_AVALIAR)

    def test_acabada_de_fechar_nao_conta_como_parada(self):
        s = self.parada()
        self.recuar(s, fim=timedelta(seconds=30))
        self.assertEqual(servico.avaliacoes_paradas(), [])

    def test_voz_sem_chamada_verificada_fica_para_o_vapi(self):
        s = self.parada()
        dados = dict(s.full_session_data or {}, aguarda_vapi=timezone.now().isoformat())
        VapiSession.objects.filter(pk=s.pk).update(mode='vapi', full_session_data=dados,
                                                   ended_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(servico.avaliacoes_paradas(), [])
        dados['vapi_verificada'] = {'call_id': 'x', 'em': (timezone.now() - timedelta(minutes=5)).isoformat()}
        VapiSession.objects.filter(pk=s.pk).update(full_session_data=dados)
        self.assertEqual(servico.avaliacoes_paradas(), [s.pk])

    def test_cron_nao_lanca_threads(self):
        """No comando, executar_em_fundo corre de imediato (uma thread morreria com o processo)."""
        corridas = []
        with mock.patch('apps.practice.conversa.webhook.threading.Thread') as thread, \
                webhook.no_proprio_processo():
            webhook.executar_em_fundo(corridas.append, 1)
        thread.assert_not_called()
        self.assertEqual(corridas, [1])


class SemaforoTests(SimpleTestCase):

    def test_limita_as_avaliacoes_em_simultaneo(self):
        """5 avaliações pedidas de uma vez com limite 2: nunca mais de 2 a correr."""
        limite = 2
        soltar = threading.Event()
        lock = threading.Lock()
        estado = {'agora': 0, 'max': 0, 'feitas': 0}
        duas_a_correr = threading.Event()

        def avaliar(_pk):
            with lock:
                estado['agora'] += 1
                estado['max'] = max(estado['max'], estado['agora'])
                if estado['agora'] >= limite:
                    duas_a_correr.set()
            soltar.wait(5)
            with lock:
                estado['agora'] -= 1
                estado['feitas'] += 1

        with mock.patch.object(webhook, 'AVALIACOES_EM_SIMULTANEO', threading.BoundedSemaphore(limite)), \
                mock.patch.object(webhook, 'close_old_connections'):
            threads = [webhook.executar_em_fundo(avaliar, i) for i in range(5)]
            self.assertTrue(duas_a_correr.wait(5))
            # As outras 3 estão à espera da vez, sem correr.
            for t in threads:
                t.join(0.05)
            with lock:
                self.assertEqual(estado['agora'], limite)
                self.assertEqual(estado['feitas'], 0)
            soltar.set()
            for t in threads:
                t.join(5)
        self.assertEqual(estado['feitas'], 5)
        self.assertEqual(estado['max'], limite)

    def test_falha_liberta_o_lugar(self):
        sem = threading.BoundedSemaphore(1)

        def falha(_pk):
            raise RuntimeError('Claude em baixo')
        with mock.patch.object(webhook, 'AVALIACOES_EM_SIMULTANEO', sem), \
                mock.patch.object(webhook, 'close_old_connections'), webhook.no_proprio_processo():
            webhook.executar_em_fundo(falha, 1)
        self.assertTrue(sem.acquire(blocking=False))
