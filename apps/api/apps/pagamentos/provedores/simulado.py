"""
Provedor Multicaixa Express simulado (desenvolvimento / testes).

Comportamento determinístico pelo número de telefone, para o frontend
conseguir exercitar todos os estados:

* termina em ``0000`` -> ``recusado`` ("Pagamento recusado no telemóvel.")
  ao fim de ``ATRASO_CONFIRMACAO``;
* termina em ``1111`` -> fica ``pendente`` e passa a ``expirado`` em ``expira_em``;
* qualquer outro número -> ``pago`` ao fim de ``ATRASO_CONFIRMACAO`` desde a criação.

A resolução é feita "lazy" quando o pagamento é lido (sem worker).
"""

import uuid
from datetime import timedelta

from django.utils import timezone

from .base import ProvedorPagamento, ResultadoInicio, ResultadoConsulta

ATRASO_CONFIRMACAO = timedelta(seconds=6)
MOTIVO_RECUSADO = 'Pagamento recusado no telemóvel.'


class MulticaixaSimulado(ProvedorPagamento):
    codigo = 'simulado'
    simulado = True

    def iniciar(self, pagamento):
        return ResultadoInicio(referencia_externa=f'SIM-{uuid.uuid4().hex[:16].upper()}')

    def consultar(self, pagamento):
        telefone = pagamento.telefone or ''
        if telefone.endswith('1111'):
            return ResultadoConsulta(estado='pendente')
        if timezone.now() < pagamento.created_at + ATRASO_CONFIRMACAO:
            return ResultadoConsulta(estado='pendente')
        if telefone.endswith('0000'):
            return ResultadoConsulta(estado='recusado', motivo=MOTIVO_RECUSADO)
        return ResultadoConsulta(estado='pago')
