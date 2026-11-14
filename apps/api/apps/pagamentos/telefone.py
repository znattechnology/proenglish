"""Validação e máscara de números de telemóvel angolanos (Multicaixa Express)."""

import re

_PADRAO = re.compile(r'^(?:\+?244)?(9\d{8})$')

MENSAGEM_TELEFONE_INVALIDO = (
    'Número de telemóvel inválido. Indique um número angolano com 9 dígitos '
    'começado por 9 (ex.: 923 456 789), opcionalmente com o prefixo +244.'
)


class TelefoneInvalido(ValueError):
    pass


def normalizar_telefone(valor):
    """Devolve os 9 dígitos (ex.: '923456789') ou lança TelefoneInvalido.

    Aceita prefixo opcional '+244' ou '244' e espaços; rejeita tudo o resto.
    """
    if not isinstance(valor, str):
        raise TelefoneInvalido(MENSAGEM_TELEFONE_INVALIDO)
    compacto = valor.replace(' ', '')
    if compacto.startswith('+') and not compacto.startswith('+244'):
        raise TelefoneInvalido(MENSAGEM_TELEFONE_INVALIDO)
    m = _PADRAO.match(compacto)
    if not m:
        raise TelefoneInvalido(MENSAGEM_TELEFONE_INVALIDO)
    return m.group(1)


def mascarar_telefone(numero):
    """'923456123' -> '9•• ••• 123'."""
    if not numero or len(numero) != 9:
        return ''
    return f'{numero[0]}•• ••• {numero[-3:]}'
