"""
Chamadas do Vapi verificadas no servidor: a fonte de verdade das conversas por voz.

O browser do aluno não é de confiança: é ele que começa a chamada (com a chave pública) e podia
mandar uma transcrição inventada, saltar ligada/, mentir no id da chamada ou forjar um relatório.
Por isso, no modo de voz, a transcrição, a duração, o fim da chamada e a gravação só valem quando
vêm do próprio Vapi:

- pedido GET /call/{id} à API privada (settings.VAPI_PRIVATE_KEY, base settings.VAPI_BASE_URL);
- ou o end-of-call-report recebido no webhook com o segredo GLOBAL (X-Vapi-Secret / Bearer, que
  nunca passa pelo browser).

Uma chamada só é aceite para uma sessão quando metadata.sessao_id é o id dessa sessão e o
assistente é o nosso (o que criar_sessao mandou e ficou em config.assistant_id).

De onde vem o id da chamada: o cliente manda-o depois do call-start (ligada/ ou terminar/), e fica
como «reclamado» (dados.vapi_call_id_reclamado) até um GET o confirmar; o webhook autenticado
também o traz. Um id que o Vapi confirmou (dados.vapi_call_id) nunca é trocado pelo do cliente.
Os ids do Vapi são UUIDs: tudo o resto é recusado antes de entrar num caminho de URL.
"""
import json
import logging
import re
import uuid
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from django.conf import settings
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

TIMEOUT = 8
MAX_MENSAGENS = 600


class ErroVapi(Exception):
    def __init__(self, mensagem, status=None):
        super().__init__(mensagem)
        self.status = status


def _d(valor):
    return valor if isinstance(valor, dict) else {}


def call_id_valido(valor):
    """O id normalizado (UUID em minúsculas) ou None."""
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    if len(valor) != 36:
        return None
    try:
        return str(uuid.UUID(valor))
    except ValueError:
        return None


def configurado():
    return bool(getattr(settings, 'VAPI_PRIVATE_KEY', None))


def pedir(metodo, caminho):
    """
    (status, corpo) da API privada do Vapi. corpo é um dict (ou None se vazio / não JSON-objecto).
    Os 4xx/5xx devolvem o status (não levantam); falhas de rede levantam ErroVapi.
    Os testes substituem esta função: nunca há pedidos reais.
    """
    chave = getattr(settings, 'VAPI_PRIVATE_KEY', None)
    if not chave:
        raise ErroVapi('sem VAPI_PRIVATE_KEY')
    base = (getattr(settings, 'VAPI_BASE_URL', '') or 'https://api.vapi.ai').rstrip('/')
    pedido = urlrequest.Request(f'{base}{caminho}', method=metodo,
                                headers={'Authorization': f'Bearer {chave}', 'Accept': 'application/json'})
    try:
        with urlrequest.urlopen(pedido, timeout=TIMEOUT) as r:  # noqa: S310 (base fixa das settings)
            status, corpo = r.status, r.read()
    except urlerror.HTTPError as e:
        return e.code, None
    except Exception as e:  # rede, timeout, TLS
        raise ErroVapi(f'pedido ao Vapi falhou: {type(e).__name__}') from e
    if not corpo:
        return status, None
    try:
        dados = json.loads(corpo)
    except ValueError:
        return status, None
    return status, dados if isinstance(dados, dict) else None


def _caminho_chamada(call_id):
    return '/call/' + urlparse.quote(call_id, safe='')


def obter_chamada(call_id):
    """O objecto da chamada (dict), None se o Vapi não a conhece (404). Levanta ErroVapi."""
    call_id = call_id_valido(call_id)
    if call_id is None:
        return None
    status, corpo = pedir('GET', _caminho_chamada(call_id))
    if status == 404:
        return None
    if not 200 <= (status or 0) < 300 or corpo is None:
        raise ErroVapi(f'GET /call respondeu {status}', status)
    return corpo


def apagar_chamada(call_id):
    """True quando o Vapi apagou (2xx) ou já não a tem (404). Nunca levanta."""
    call_id = call_id_valido(call_id)
    if call_id is None:
        return False
    try:
        status, _ = pedir('DELETE', _caminho_chamada(call_id))
    except Exception as e:
        logger.warning('vapi: não foi possível apagar a chamada %s: %s', call_id, e)
        return False
    return status == 404 or 200 <= (status or 0) < 300


# ---------------------------------------------------------------------------
# Ler uma chamada (GET /call) ou um end-of-call-report autenticado
# ---------------------------------------------------------------------------

def url_gravacao(origem):
    """O URL https da gravação (artifact.recordingUrl e formatos antigos), ou None."""
    origem = _d(origem)
    artifact = _d(origem.get('artifact'))
    gravacao = _d(artifact.get('recording'))
    for valor in (artifact.get('recordingUrl'), gravacao.get('url'), _d(gravacao.get('mono')).get('combinedUrl'),
                  origem.get('recordingUrl')):
        if isinstance(valor, str) and valor.startswith('https://'):
            return valor[:1000]
    return None


def _sessao_id(call, *outros):
    overrides = _d(call.get('assistantOverrides'))
    for origem in (_d(overrides.get('metadata')), _d(call.get('metadata')), *outros):
        valor = _d(origem).get('sessao_id')
        if isinstance(valor, str) and valor:
            return valor
    return None


def _segundos(inicio, fim):
    a, b = parse_datetime(inicio or '') if isinstance(inicio, str) else None, \
        parse_datetime(fim or '') if isinstance(fim, str) else None
    if a and b and b >= a:
        return int((b - a).total_seconds())
    return None


def ler_chamada(call):
    """Objecto de GET /call -> dict normalizado (ver ler_relatorio)."""
    call = _d(call)
    artifact = _d(call.get('artifact'))
    mensagens = artifact.get('messages') if isinstance(artifact.get('messages'), list) else call.get('messages')
    estado = str(call.get('status') or '')
    duracao = _segundos(call.get('startedAt'), call.get('endedAt'))
    if duracao is None and estado == 'ended':
        duracao = 0  # terminou sem nunca ter começado (microfone recusado, erro a ligar)
    return {
        'id': call_id_valido(call.get('id')),
        'terminada': estado == 'ended',
        'motivo': str(call.get('endedReason') or '')[:120],
        'sessao_id': _sessao_id(call),
        'assistant_id': call.get('assistantId') if isinstance(call.get('assistantId'), str) else None,
        'mensagens': (mensagens if isinstance(mensagens, list) else [])[:MAX_MENSAGENS],
        'duracao': duracao,
        'inicio': call.get('startedAt') if isinstance(call.get('startedAt'), str) else None,
        'gravacao_url': url_gravacao(call),
    }


def ler_relatorio(msg):
    """end-of-call-report (webhook com o segredo global) -> o mesmo dict de ler_chamada."""
    msg = _d(msg)
    call = _d(msg.get('call'))
    artifact = _d(msg.get('artifact'))
    mensagens = artifact.get('messages') if isinstance(artifact.get('messages'), list) else msg.get('messages')
    duracao = msg.get('durationSeconds')
    if not (isinstance(duracao, (int, float)) and not isinstance(duracao, bool) and duracao >= 0):
        duracao = _segundos(msg.get('startedAt') or call.get('startedAt'), msg.get('endedAt') or call.get('endedAt'))
    assistente = call.get('assistantId') or _d(msg.get('assistant')).get('id')
    return {
        'id': call_id_valido(call.get('id')),
        'terminada': True,
        'motivo': str(msg.get('endedReason') or call.get('endedReason') or '')[:120],
        'sessao_id': _sessao_id(call, _d(msg.get('assistant')).get('metadata')),
        'assistant_id': assistente if isinstance(assistente, str) else None,
        'mensagens': (mensagens if isinstance(mensagens, list) else [])[:MAX_MENSAGENS],
        'duracao': int(duracao) if duracao is not None else 0,
        'inicio': msg.get('startedAt') or call.get('startedAt'),
        'gravacao_url': url_gravacao(msg) or url_gravacao(call),
    }


def assistente_esperado(sessao):
    dados = sessao.full_session_data if isinstance(sessao.full_session_data, dict) else {}
    cfg = _d(dados.get('config'))
    return cfg.get('assistant_id') or settings.VAPI_ENGLISH_ASSISTANT_ID or settings.VAPI_DEFAULT_ASSISTANT_ID


def motivo_recusa(chamada, sessao):
    """None se a chamada pertence à sessão; senão um código curto."""
    if not chamada.get('id'):
        return 'sem_id'
    if chamada.get('sessao_id') != sessao.session_id:
        return 'outra_sessao'
    esperado = assistente_esperado(sessao)
    if not esperado or chamada.get('assistant_id') != esperado:
        return 'outro_assistente'
    return None


def transcricao(mensagens, escritos=None):
    """
    artifact.messages do Vapi ([{role, message}]) -> [{quem, texto}] já limpa. As falas do aluno
    que ele ESCREVEU (o cliente avisou: dados.escritos) ficam com {'escrito': True}: as frases-alvo
    que tiverem contam no máximo 'com_ajuda' (perfil.servico.uso_da_frase).
    """
    from apps.perfil.servico import normalizar
    from . import analise
    marcas = {normalizar(e) for e in escritos or [] if isinstance(e, str)}
    marcas.discard('')
    turnos = []
    for m in mensagens if isinstance(mensagens, list) else []:
        if not isinstance(m, dict):
            continue
        papel = m.get('role')
        quem = 'aluno' if papel == 'user' else 'tutor' if papel in ('bot', 'assistant') else None
        texto = m.get('message') if isinstance(m.get('message'), str) else m.get('content')
        if quem and isinstance(texto, str):
            t = {'quem': quem, 'texto': texto}
            if quem == 'aluno' and marcas and normalizar(texto) in marcas:
                t['escrito'] = True
            turnos.append(t)
    return analise.limpar_transcricao(turnos)
