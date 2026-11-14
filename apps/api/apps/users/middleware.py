"""
Autenticação JWT a partir do cookie HttpOnly ``access_token``.

Se o pedido não traz cabeçalho Authorization, o token do cookie é posto em
``Authorization: Bearer ...`` para o JWTAuthentication do DRF o validar.

Defesa contra CSRF: em produção os cookies são SameSite=None (o site e a API estão em
domínios diferentes), por isso um formulário noutro site conseguia fazer um POST com a
sessão da pessoa. Nos pedidos que alteram dados (POST, PUT, PATCH, DELETE) autenticados
pelo cookie, o cabeçalho Origin (ou, sem ele, o Referer) tem de ser uma origem aceite
(COOKIE_AUTH_ALLOWED_ORIGINS ou, por omissão, CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS
+ FRONTEND_URL, e a própria API). Caso contrário: 403.

* Pedidos com Authorization (apps, integrações) não são verificados: não há cookie em jogo.
* Pedidos sem Origin nem Referer passam (clientes que não são browsers; os browsers
  actuais enviam sempre Origin num POST vindo de outro site).
"""

import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

METODOS_INSEGUROS = {'POST', 'PUT', 'PATCH', 'DELETE'}
ORIGEM_RECUSADA = ('Este pedido não veio do site do ProEnglish e foi recusado. '
                   'Abra o ProEnglish e tente outra vez.')


def _normalizar(origem):
    """'https://Exemplo.ao:443/x' -> 'https://exemplo.ao' (esquema + anfitrião + porta não padrão)."""
    try:
        partes = urlsplit((origem or '').strip())
    except ValueError:
        return None
    if not partes.scheme or not partes.hostname:
        return None
    esquema = partes.scheme.lower()
    anfitriao = partes.hostname.lower()
    try:
        porta = partes.port
    except ValueError:
        return None
    if porta and not ((esquema == 'http' and porta == 80) or (esquema == 'https' and porta == 443)):
        return f'{esquema}://{anfitriao}:{porta}'
    return f'{esquema}://{anfitriao}'


def origens_aceites():
    lista = list(getattr(settings, 'COOKIE_AUTH_ALLOWED_ORIGINS', None) or [])
    if not lista:
        lista = (list(getattr(settings, 'CORS_ALLOWED_ORIGINS', None) or [])
                 + list(getattr(settings, 'CSRF_TRUSTED_ORIGINS', None) or [])
                 + [getattr(settings, 'FRONTEND_URL', '')])
    return {o for o in (_normalizar(x) for x in lista) if o}


def origem_do_pedido(request):
    """Origem declarada pelo browser (Origin, ou o Referer). '' se não houver nenhuma."""
    origem = request.META.get('HTTP_ORIGIN')
    if origem is not None:
        return origem.strip()
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return referer.strip()
    return ''


def origem_aceite(request):
    declarada = origem_do_pedido(request)
    if not declarada:
        return True
    origem = _normalizar(declarada)  # "null" (iframes com sandbox, data:) dá None: recusado
    if not origem:
        return False
    if origem in origens_aceites():
        return True
    # A própria API (admin do Django, páginas servidas pela API)
    try:
        propria = _normalizar(f'{request.scheme}://{request.get_host()}')
    except Exception:
        propria = None
    return origem == propria


MUDAR_SENHA = 'A administração pediu-lhe para mudar a palavra-passe. Mude-a para continuar.'

# Caminhos públicos de entrada/saída: um cookie antigo ainda no browser nunca os bloqueia.
SEM_VERIFICACAO = (
    '/api/v1/users/login/',
    '/api/v1/users/logout/',
    '/api/v1/users/refresh-token/',
    '/api/v1/users/register/',
    '/api/v1/users/password-reset/',
    '/api/v1/users/password-reset-confirm/',
    '/api/v1/users/verify-email/',
    '/api/v1/users/resend-verification/',
    '/api/v1/users/confirmar-email-novo/',
    '/api/v1/users/oauth/',
    '/api/v1/convites/',
)
# Com deve_mudar_senha=True só estes (e os de SEM_VERIFICACAO) respondem.
LIVRES_COM_MUDAR_SENHA = (
    '/api/v1/users/change-password/',
    '/api/v1/users/profile/',
)


def _bloqueio_da_conta(request):
    """
    Regras da administração que dependem do estado actual da conta (uma consulta por pedido
    autenticado da API):

    * sessões terminadas pela administração (User.sessoes_invalidas_antes): os tokens de acesso
      emitidos antes deixam de valer logo (401), sem esperar que expirem;
    * palavra-passe a mudar (User.deve_mudar_senha): 403 code "mudar_senha" em tudo menos
      LIVRES_COM_MUDAR_SENHA.

    Token inválido ou expirado: não faz nada (o DRF responde 401 como sempre).
    """
    if not request.path.startswith('/api/') or request.path.startswith(SEM_VERIFICACAO):
        return None
    cabecalho = request.META.get('HTTP_AUTHORIZATION') or ''
    partes = cabecalho.split()
    if len(partes) != 2 or partes[0] != 'Bearer':
        return None
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.settings import api_settings
        token = AccessToken(partes[1])
        user_id = token[api_settings.USER_ID_CLAIM]
        emitido = int(token.get('iat') or 0)
    except Exception:
        return None
    from apps.core.exceptions import SESSAO_TERMINOU, corpo_erro
    from .models import User
    try:
        estado = (User.objects.filter(pk=user_id)
                  .values('deve_mudar_senha', 'sessoes_invalidas_antes').first())
    except Exception:
        return None
    if not estado:
        return None
    corte = estado['sessoes_invalidas_antes']
    if corte and emitido < int(corte.timestamp()):
        return JsonResponse(corpo_erro(SESSAO_TERMINOU, 'token_not_valid'), status=401)
    if estado['deve_mudar_senha'] and not request.path.startswith(LIVRES_COM_MUDAR_SENHA):
        return JsonResponse(corpo_erro(MUDAR_SENHA, 'mudar_senha'), status=403)
    return None


class JWTCookieAuthenticationMiddleware(MiddlewareMixin):

    def process_request(self, request):
        if request.META.get('HTTP_AUTHORIZATION'):
            return _bloqueio_da_conta(request)

        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None

        if request.method in METODOS_INSEGUROS and not origem_aceite(request):
            logger.warning('Pedido %s %s com cookie de sessão recusado: origem %r não aceite',
                           request.method, request.path, origem_do_pedido(request)[:200])
            from apps.core.exceptions import corpo_erro
            return JsonResponse(corpo_erro(ORIGEM_RECUSADA, 'origem_invalida'), status=403)

        request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        return _bloqueio_da_conta(request)
