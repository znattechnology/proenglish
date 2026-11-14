"""
Seleção do provedor de pagamentos.

``PAGAMENTOS_PROVEDOR`` (settings) escolhe o provedor usado em novos
pagamentos. Cada pagamento guarda o código do provedor com que foi criado,
para que pagamentos antigos continuem a ser consultados no provedor certo.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import ProvedorPagamento, ResultadoInicio, ResultadoConsulta
from .simulado import MulticaixaSimulado
from .emis import MulticaixaEMIS

PROVEDORES = {
    MulticaixaSimulado.codigo: MulticaixaSimulado,
    MulticaixaEMIS.codigo: MulticaixaEMIS,
}


def obter_provedor(codigo=None) -> ProvedorPagamento:
    codigo = codigo or getattr(settings, 'PAGAMENTOS_PROVEDOR', 'simulado')
    try:
        return PROVEDORES[codigo]()
    except KeyError:
        raise ImproperlyConfigured(f'PAGAMENTOS_PROVEDOR desconhecido: {codigo!r}')


def simulacao_permitida() -> bool:
    return bool(getattr(settings, 'PAGAMENTOS_SIMULADOS', False))


def provedor_disponivel(provedor: ProvedorPagamento) -> bool:
    """O simulador só pode ser usado com PAGAMENTOS_SIMULADOS=True."""
    return not provedor.simulado or simulacao_permitida()


__all__ = [
    'ProvedorPagamento', 'ResultadoInicio', 'ResultadoConsulta',
    'MulticaixaSimulado', 'MulticaixaEMIS',
    'obter_provedor', 'simulacao_permitida', 'provedor_disponivel',
]
