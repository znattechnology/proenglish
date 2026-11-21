"""
Webhook do Vapi: POST /api/v1/practice/vapi/webhook/

Só trata o `end-of-call-report` (o relatório que o Vapi envia quando a chamada acaba).

Autenticação (sem segredo próprio em VAPI_WEBHOOK_SECRET o endpoint responde 404):
- cabeçalho `X-Vapi-Secret: <segredo>` (o que o Vapi envia quando o segredo está configurado no
  servidor do assistente/organização no painel) ou `Authorization: Bearer <segredo>` (credencial
  «Bearer» do Vapi). O segredo nunca passa pelo browser: um relatório assim vem do Vapi e conta
  como chamada verificada (verificacao.aplicar), se pertencer à sessão (metadata.sessao_id e o
  nosso assistente, chamada.motivo_recusa);
- `?sessao=<id>&token=<hmac>` no URL: o formato antigo, que ia nos overrides (pelo browser). Já não
  se manda ao cliente; um pedido assim só serve de pista: o conteúdo é ignorado e a chamada é pedida
  ao Vapi (GET /call, verificacao.verificar). Um relatório forjado não muda nada.

A ordem de chegada não importa (o webhook antes ou depois de terminar/): a primeira chamada
verificada fecha, cobra e avalia; as seguintes respondem «ja_verificada».
"""
import hashlib
import hmac
import logging
import threading
from contextlib import contextmanager
from urllib.parse import urlencode

from django.conf import settings
from django.db import close_old_connections
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.practice.models import VapiSession
from apps.practice.throttling import VapiWebhookThrottle

from . import chamada, verificacao

logger = logging.getLogger(__name__)

SEGREDO_PREDEFINIDO = 'default_webhook_secret'
TIPO_FIM = 'end-of-call-report'


def _segredo():
    return (getattr(settings, 'VAPI_WEBHOOK_SECRET', None) or '').strip()


def webhook_configurado():
    """O webhook só existe com um segredo próprio (nunca o valor predefinido das settings)."""
    s = _segredo()
    return bool(s) and s != SEGREDO_PREDEFINIDO


def token_sessao(sessao_id):
    chave = _segredo().encode()
    return hmac.new(chave, f'conversa-webhook:{sessao_id}'.encode(), hashlib.sha256).hexdigest()


def url_servidor(sessao_id):
    """URL antigo com o token da sessão. Já não vai para o cliente (só para compatibilidade)."""
    base = (getattr(settings, 'VAPI_WEBHOOK_URL', None) or '').strip()
    if not webhook_configurado() or not base.startswith('https://'):
        return None
    sep = '&' if '?' in base else '?'
    return f"{base}{sep}{urlencode({'sessao': sessao_id, 'token': token_sessao(sessao_id)})}"


def _autenticar(request):
    """(ok, sessao_restrita). sessao_restrita é o id da única sessão a que o pedido tem acesso
    (token no URL, formato antigo: conteúdo não confiável) ou None (segredo global)."""
    segredo = _segredo().encode()
    cabecalho = request.headers.get('X-Vapi-Secret') or ''
    auth = request.headers.get('Authorization') or ''
    if auth.lower().startswith('bearer '):
        auth = auth[7:].strip()
    else:
        auth = ''
    for valor in (cabecalho, auth):
        if valor and hmac.compare_digest(valor.encode(), segredo):
            return True, None
    sessao, token = request.query_params.get('sessao') or '', request.query_params.get('token') or ''
    if sessao and token and hmac.compare_digest(token.encode(), token_sessao(sessao).encode()):
        return True, sessao
    return False, None


def _d(valor):
    return valor if isinstance(valor, dict) else {}


def transcricao_vapi(mensagens, escritos=None):
    """artifact.messages do Vapi -> [{quem, texto}] já limpa (chamada.transcricao)."""
    return chamada.transcricao(mensagens, escritos)


url_gravacao = chamada.url_gravacao


# Tarefas em segundo plano (avaliação das conversas, pronúncia do exame) ao mesmo tempo, por
# processo: as outras threads esperam pela vez. No VPS (2 workers do Gunicorn) são no máximo
# 2 x AVALIACOES_EM_SIMULTANEO pedidos ao Claude/Azure de uma vez, e a memória fica previsível.
AVALIACOES_EM_SIMULTANEO = threading.BoundedSemaphore(max(1, int(getattr(settings, 'AVALIACOES_EM_SIMULTANEO', 2))))
_local = threading.local()


@contextmanager
def no_proprio_processo():
    """Dentro deste bloco, executar_em_fundo corre de imediato (sem thread). Para os comandos do
    cron: uma thread daemon morreria com o processo do comando antes de acabar."""
    antes = getattr(_local, 'sincrono', False)
    _local.sincrono = True
    try:
        yield
    finally:
        _local.sincrono = antes


def _correr_limitado(funcao, *args, thread=True):
    try:
        with AVALIACOES_EM_SIMULTANEO:
            funcao(*args)
    except Exception:
        logger.exception('conversa: falha na avaliação em segundo plano')
    finally:
        if thread:  # a ligação à base é desta thread; no próprio processo é de quem chamou
            close_old_connections()


def executar_em_fundo(funcao, *args):
    """
    A avaliação (Claude) pode demorar até 60 s, mais do que o Vapi espera pela resposta: corre numa
    thread à parte, no máximo AVALIACOES_EM_SIMULTANEO de cada vez por processo.

    Sem fila de tarefas (ver o relatório da auditoria): uma thread daemon perde-se quando o Gunicorn
    recicla o worker (--max-requests) ou reinicia. Nada se perde de vez: a sessão fica 'a_avaliar'
    com avaliacao_iniciada_em e volta a ser avaliada passados AVALIACAO_BLOQUEIO_SEGUNDOS, na próxima
    consulta do cliente ou no comando verificar_conversas_vapi (cron de 5 em 5 minutos), que também
    apanha a pronúncia do exame oral por fazer.
    Os testes substituem esta função para correr de imediato.
    """
    if getattr(_local, 'sincrono', False):
        _correr_limitado(funcao, *args, thread=False)
        return None
    t = threading.Thread(target=_correr_limitado, args=(funcao, *args), name='conversa-avaliar', daemon=True)
    t.start()
    return t


def registar_relatorio(msg):
    """end-of-call-report autenticado com o segredo global: é do Vapi. Devolve um código curto."""
    v = chamada.ler_relatorio(msg)
    sessao_id = v['sessao_id']
    if not sessao_id:
        return 'sem_sessao'
    sessao = VapiSession.objects.filter(pk=sessao_id).first()
    if sessao is None or sessao.mode != 'vapi':
        return 'sessao_desconhecida'
    motivo = chamada.motivo_recusa(v, sessao)
    if motivo == 'outro_assistente' and not v['assistant_id'] and v['id'] and chamada.configurado():
        # O relatório não diz o assistente: confirma-se com GET /call.
        verificacao._actualizar_dados(sessao.pk, lambda d: verificacao.reclamar_call_id(d, v['id']))
        return verificacao.verificar(sessao.pk, forcar=True, em_fundo=True)
    if motivo:
        logger.warning('vapi webhook: relatório recusado para a sessão %s (%s)', sessao.pk, motivo)
        return 'recusada'
    return verificacao.aplicar(sessao.pk, v, 'webhook', em_fundo=True)


def registar_pista(sessao_id, msg):
    """URL antigo com token por sessão: o conteúdo não conta, só o id da chamada (pedida ao Vapi)."""
    sessao = VapiSession.objects.filter(pk=sessao_id).first()
    if sessao is None or sessao.mode != 'vapi':
        return 'sessao_desconhecida'
    cid = _d(msg.get('call')).get('id')
    verificacao._actualizar_dados(sessao.pk, lambda d: verificacao.reclamar_call_id(d, cid))
    return verificacao.verificar(sessao.pk, forcar=True, em_fundo=True)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([VapiWebhookThrottle])
def vapi_webhook(request):
    if not webhook_configurado():
        return Response({'error': 'Not found'}, status=404)
    ok, sessao_restrita = _autenticar(request)
    if not ok:
        logger.warning('vapi webhook: segredo inválido')
        return Response({'error': 'Invalid webhook secret'}, status=403)

    msg = _d(request.data.get('message') if isinstance(request.data, dict) else None)
    tipo = msg.get('type')
    if tipo != TIPO_FIM:
        return Response({'status': 'ignorado'})

    if sessao_restrita is not None:
        indicada = chamada.ler_relatorio(msg)['sessao_id']
        if indicada and indicada != sessao_restrita:
            return Response({'error': 'Invalid webhook secret'}, status=403)
    try:
        if sessao_restrita is not None:
            resultado = registar_pista(sessao_restrita, msg)
        else:
            resultado = registar_relatorio(msg)
    except Exception:
        logger.exception('vapi webhook: falha ao tratar o relatório')
        resultado = 'erro'
    return Response({'status': resultado})
