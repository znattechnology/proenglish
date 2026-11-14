"""Interface comum dos provedores de pagamento."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResultadoInicio:
    """Resposta do provedor ao iniciar um pagamento (push enviado ao telemóvel)."""
    referencia_externa: str


@dataclass
class ResultadoConsulta:
    """Estado atual do pagamento no provedor.

    estado: 'pendente' | 'pago' | 'recusado' | 'expirado'
    """
    estado: str
    motivo: str = ''


class ProvedorPagamento(ABC):
    """
    Contrato que qualquer provedor Multicaixa Express tem de cumprir.

    O resto do sistema (serviços, views, ativação de planos/cursos) só fala
    com esta interface, por isso trocar o simulador pelo provedor real
    (EMIS) é uma questão de configuração (``PAGAMENTOS_PROVEDOR``).
    """

    codigo = ''
    simulado = False

    @abstractmethod
    def iniciar(self, pagamento) -> ResultadoInicio:
        """Envia o pedido de pagamento (push) para o telemóvel do aluno."""

    @abstractmethod
    def consultar(self, pagamento) -> ResultadoConsulta:
        """Consulta o estado do pagamento no provedor."""

    def cancelar(self, pagamento) -> None:
        """Cancela o pedido no provedor, se suportado (por omissão nada a fazer)."""
        return None
