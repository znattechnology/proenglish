"""
Tratamento de erros da API: todas as respostas de erro têm o mesmo formato.

    {
        "error":   "<mensagem para a pessoa, em pt-PT>",
        "message": "<a mesma mensagem>",
        "code":    "<código para o programa>",
        "details": {"campo": ["erro", ...], ...}
    }

* Erros de validação (400): a mensagem é o primeiro erro de campo (ex.: "Já existe uma conta
  com este email."); ``details`` guarda todos os erros, campo a campo; code "validation_error".
* 401 "A sessão terminou. Entre outra vez." (a não ser que a vista dê uma mensagem própria,
  como "Email não verificado...").
* 403 "Não tem permissão para isto.", 404 "Não encontrámos o que procura." (ou a mensagem
  própria da vista, se houver).
* 429 (throttles do DRF e django_ratelimit): "Fez muitos pedidos seguidos. Tente outra vez
  daqui a N segundos.", com "aguardar_segundos" e o cabeçalho Retry-After.

As vistas que devolvem o seu próprio Response({"error": ...}) não passam por aqui.
"""

import logging
import math

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, JsonResponse
from django_ratelimit.exceptions import Ratelimited
from rest_framework import exceptions as drf_exc
from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

SESSAO_TERMINOU = 'A sessão terminou. Entre outra vez.'
SEM_PERMISSAO = 'Não tem permissão para isto.'
NAO_ENCONTRADO = 'Não encontrámos o que procura.'
LOGIN_ERRADO = 'O email ou a palavra-passe não estão certos.'
DADOS_INVALIDOS = 'Verifique os dados e tente outra vez.'
ESPERA_RATELIMIT = 60  # os limites do django_ratelimit são todos por minuto

# Nomes dos campos para as mensagens genéricas ("Preencha o campo «palavra-passe».").
ROTULOS = {
    'email': 'email',
    'password': 'palavra-passe',
    'password_confirm': 'confirmação da palavra-passe',
    'current_password': 'palavra-passe actual',
    'new_password': 'nova palavra-passe',
    'new_password_confirm': 'confirmação da nova palavra-passe',
    'newPassword': 'nova palavra-passe',
    'name': 'nome',
    'phone': 'telefone',
    'telefone': 'número de telemóvel',
    'code': 'código',
    'codigo': 'código',
    'comment': 'comentário',
    'rating': 'nota',
    'refresh': 'sessão',
    'plan': 'plano',
    'plan_id': 'plano',
    'periodo': 'período',
}
CODIGOS_PREENCHER = {'required', 'blank', 'null'}


def mensagem_espera(segundos):
    if segundos is None:
        return 'Fez muitos pedidos seguidos. Tente outra vez daqui a pouco.'
    n = max(1, int(math.ceil(segundos)))
    if n >= 120:
        minutos = int(math.ceil(n / 60))
        return f'Fez muitos pedidos seguidos. Tente outra vez daqui a {minutos} minutos.'
    unidade = 'segundo' if n == 1 else 'segundos'
    return f'Fez muitos pedidos seguidos. Tente outra vez daqui a {n} {unidade}.'


def _rotulo(campo):
    if not campo or campo == 'non_field_errors':
        return None
    return ROTULOS.get(campo, str(campo).replace('_', ' '))


def _primeiro_erro(dados, campo=None):
    """(campo, ErrorDetail/str) do primeiro erro encontrado (percorre dicts e listas)."""
    if isinstance(dados, dict):
        # non_field_errors primeiro: costuma ser a mensagem mais útil
        chaves = sorted(dados.keys(), key=lambda k: k != 'non_field_errors')
        for chave in chaves:
            r = _primeiro_erro(dados[chave], chave if campo is None else campo)
            if r:
                return r
        return None
    if isinstance(dados, (list, tuple)):
        for item in dados:
            r = _primeiro_erro(item, campo)
            if r:
                return r
        return None
    if dados in (None, ''):
        return None
    return campo, dados


def _mensagem_validacao(dados):
    r = _primeiro_erro(dados)
    if not r:
        return DADOS_INVALIDOS
    campo, erro = r
    codigo = getattr(erro, 'code', None)
    rotulo = _rotulo(campo)
    if codigo in CODIGOS_PREENCHER and rotulo:
        return f'Preencha o campo «{rotulo}».'
    return str(erro)


def _simples(dados):
    """ErrorDetail -> str, recursivamente (o JSON fica igual, mas os testes comparam melhor)."""
    if isinstance(dados, dict):
        return {str(k): _simples(v) for k, v in dados.items()}
    if isinstance(dados, (list, tuple)):
        return [_simples(v) for v in dados]
    if isinstance(dados, ErrorDetail):
        return str(dados)
    return dados


def _detalhe_e_padrao(exc):
    """Mensagem da excepção, ou None se for a mensagem por omissão do DRF."""
    detalhe = getattr(exc, 'detail', None)
    if isinstance(detalhe, (dict, list)) or detalhe is None:
        return None
    texto = str(detalhe).strip()
    if not texto or texto == str(getattr(exc, 'default_detail', '')):
        return None
    return texto


def corpo_erro(mensagem, code, details=None, **extra):
    corpo = {'error': mensagem, 'message': mensagem, 'code': code, 'details': details or {}}
    corpo.update(extra)
    return corpo


def custom_exception_handler(exc, context):
    request = context.get('request') if context else None
    path = getattr(request, 'path', '') or ''

    # django_ratelimit (block=True) lança Ratelimited, que é um PermissionDenied: é um 429.
    if isinstance(exc, Ratelimited):
        exc = drf_exc.Throttled(wait=ESPERA_RATELIMIT)

    original = exc
    response = exception_handler(exc, context)
    if response is None:
        return None

    code = 'error'
    details = {}
    extra = {}
    mensagem = None
    estado = response.status_code

    if isinstance(original, Http404):
        code, mensagem = 'not_found', NAO_ENCONTRADO
    elif isinstance(original, DjangoPermissionDenied):
        code = 'permission_denied'
        mensagem = (str(original.args[0]) if original.args and isinstance(original.args[0], str)
                    else SEM_PERMISSAO)
    elif isinstance(original, drf_exc.Throttled):
        code = 'throttled'
        espera = original.wait
        mensagem = mensagem_espera(espera)
        if espera is not None:
            extra['aguardar_segundos'] = max(1, int(math.ceil(espera)))
            response['Retry-After'] = str(extra['aguardar_segundos'])
    elif isinstance(original, drf_exc.ValidationError):
        details = _simples(original.detail)
        if isinstance(details, list):
            details = {'non_field_errors': details}
        elif not isinstance(details, dict):
            details = {'non_field_errors': [details]}
        code = 'validation_error'
        mensagem = _mensagem_validacao(original.detail)
        if path.endswith('/login/'):
            # Login: qualquer erro de dados (campos vazios, formato) é um 401, como credenciais
            # erradas, para não dar pistas.
            estado = status.HTTP_401_UNAUTHORIZED
            code, mensagem, details = 'authentication_failed', LOGIN_ERRADO, {}
    elif isinstance(original, (drf_exc.NotAuthenticated, drf_exc.AuthenticationFailed)):
        estado = status.HTTP_401_UNAUTHORIZED
        codigos = original.get_codes()
        code = codigos if isinstance(codigos, str) else (
            codigos.get('code') if isinstance(codigos, dict) and isinstance(codigos.get('code'), str)
            else 'not_authenticated')
        # Token inválido/expirado (o detalhe vem como dict do simplejwt) ou mensagem por omissão:
        # "A sessão terminou". Mensagens próprias (ex.: "Email não verificado...") ficam.
        if isinstance(original.detail, dict) or code == 'token_not_valid':
            mensagem = SESSAO_TERMINOU
            code = 'token_not_valid'
        else:
            mensagem = _detalhe_e_padrao(original) or SESSAO_TERMINOU
    elif isinstance(original, drf_exc.PermissionDenied):
        code = 'permission_denied'
        mensagem = _detalhe_e_padrao(original) or SEM_PERMISSAO
        if isinstance(original.detail, dict):
            details = _simples(original.detail)
    elif isinstance(original, drf_exc.NotFound):
        code = 'not_found'
        mensagem = _detalhe_e_padrao(original) or NAO_ENCONTRADO
    else:
        codigos = original.get_codes() if hasattr(original, 'get_codes') else None
        code = codigos if isinstance(codigos, str) else getattr(original, 'default_code', 'error')
        detalhe = getattr(original, 'detail', None)
        if isinstance(detalhe, (dict, list)):
            details = _simples(detalhe)
            mensagem = _mensagem_validacao(detalhe)
        else:
            mensagem = str(detalhe) if detalhe else 'Ocorreu um erro. Tente outra vez.'

    response.status_code = estado
    response.data = corpo_erro(mensagem, code, details, **extra)

    nivel = logging.WARNING if estado < 500 else logging.ERROR
    logger.log(nivel, 'Erro da API %s (%s) em %s: %s', estado, code, path or '?', mensagem)
    return response


def ratelimit_view(request, exception=None):
    """Vista do RatelimitMiddleware (vistas Django fora do DRF): 429 em JSON."""
    resposta = JsonResponse(
        corpo_erro(mensagem_espera(ESPERA_RATELIMIT), 'throttled', aguardar_segundos=ESPERA_RATELIMIT),
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    resposta['Retry-After'] = str(ESPERA_RATELIMIT)
    return resposta


class APIException(Exception):
    """Base API exception class."""

    def __init__(self, message="Ocorreu um erro.", status_code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(APIException):
    """Custom validation error."""

    def __init__(self, message="Dados inválidos.", status_code=status.HTTP_400_BAD_REQUEST):
        super().__init__(message, status_code)


class NotFoundError(APIException):
    """Custom not found error."""

    def __init__(self, message=NAO_ENCONTRADO, status_code=status.HTTP_404_NOT_FOUND):
        super().__init__(message, status_code)


class PermissionError(APIException):
    """Custom permission error."""

    def __init__(self, message=SEM_PERMISSAO, status_code=status.HTTP_403_FORBIDDEN):
        super().__init__(message, status_code)
