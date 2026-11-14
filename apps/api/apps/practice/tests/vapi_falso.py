"""
Vapi falso para os testes (nunca há pedidos reais): substitui apps.practice.conversa.chamada.pedir.

    vapi = VapiFalso()
    mock.patch('apps.practice.conversa.chamada.pedir', vapi)
    cid = vapi.chamada(sessao_id, [('tutor', 'Hi'), ('aluno', 'Hello')], duracao=300)
    GET /call/<cid> -> o objecto da chamada (formato da API do Vapi)
"""
import uuid
from datetime import timedelta

from django.utils import timezone


class VapiFalso:
    def __init__(self, assistente='asst_1'):
        self.assistente = assistente
        self.chamadas = {}
        self.apagadas = {}
        self.pedidos = []
        self.status_delete = 200

    def chamada(self, sessao_id, falas, duracao=300, gravacao=None, estado='ended', assistente=None,
                call_id=None, tempos=False):
        cid = call_id or str(uuid.uuid4())
        fim = timezone.now()
        inicio = fim - timedelta(seconds=duracao)
        mensagens = [{'role': 'system', 'message': 'prompt'}]
        t0 = int(inicio.timestamp() * 1000)
        for i, (quem, texto) in enumerate(falas):
            m = {'role': 'user' if quem == 'aluno' else 'bot', 'message': texto}
            if tempos:
                m.update({'time': t0 + i * 10_000, 'endTime': t0 + i * 10_000 + (6000 if quem == 'aluno' else 3000),
                          'secondsFromStart': i * 10})
            mensagens.append(m)
        call = {
            'id': cid, 'type': 'webCall', 'status': estado,
            'assistantId': assistente if assistente is not None else self.assistente,
            'assistantOverrides': {'metadata': {'sessao_id': sessao_id}},
            'endedReason': 'customer-ended-call' if estado == 'ended' else None,
            'artifact': {'messages': mensagens},
        }
        if duracao:
            call['startedAt'] = inicio.isoformat().replace('+00:00', 'Z')
        if estado == 'ended':
            call['endedAt'] = fim.isoformat().replace('+00:00', 'Z')
        if gravacao:
            call['artifact']['recordingUrl'] = gravacao
        self.chamadas[cid] = call
        return cid

    def relatorio(self, cid, gravacao=None, **extra):
        """O end-of-call-report do webhook para uma chamada registada."""
        call = self.chamadas.get(cid) or self.apagadas[cid]
        msg = {'type': 'end-of-call-report', 'endedReason': call.get('endedReason') or 'customer-ended-call',
               'call': {k: call[k] for k in ('id', 'assistantId', 'assistantOverrides', 'type') if k in call},
               'artifact': dict(call['artifact']), 'startedAt': call.get('startedAt'), 'endedAt': call.get('endedAt'),
               **extra}
        if gravacao:
            msg['artifact']['recordingUrl'] = gravacao
        return {'message': msg}

    def __call__(self, metodo, caminho):
        self.pedidos.append((metodo, caminho))
        cid = caminho.rsplit('/', 1)[-1]
        if metodo == 'GET':
            call = self.chamadas.get(cid)
            return (200, call) if call is not None else (404, None)
        if metodo == 'DELETE':
            if self.status_delete < 300 and cid in self.chamadas:
                self.apagadas[cid] = self.chamadas.pop(cid)
            return self.status_delete, None
        return 405, None

    def pedidos_de(self, metodo):
        return [c for m, c in self.pedidos if m == metodo]
