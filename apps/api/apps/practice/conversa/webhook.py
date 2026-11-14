"""
Webhook do Vapi: POST /api/v1/practice/vapi/webhook/

Só trata o `end-of-call-report` (o relatório que o Vapi envia quando a chamada acaba):
guarda a transcrição e a duração do lado do Vapi na VapiSession (e o URL da gravação, só no exame
oral com consentimento: config.gravar, ver conversa/exame.py) e, se o aluno fechou o
separador sem terminar (a sessão ainda está «em_curso»), fecha-a, cobra os minutos com as
regras de servico._terminar_bloqueado e manda avaliar. Idempotente: um segundo relatório da
mesma sessão não muda nada.

Autenticação (sem segredo próprio em VAPI_WEBHOOK_SECRET o endpoint responde 404):
- cabeçalho `X-Vapi-Secret: <segredo>` (o que o Vapi envia quando o segredo está configurado
  no servidor do assistente/organização no painel) ou `Authorization: Bearer <segredo>`
  (credencial «Bearer» do Vapi); dá acesso a qualquer sessão;
- `?sessao=<id>&token=<hmac>` no URL: é o que criar_sessao põe em assistant_overrides.server.url.
  Os overrides passam pelo browser do aluno, por isso não levam o segredo: levam um token que só
  vale para aquela sessão (o aluno só conseguiria mandar um relatório da própria conversa, o que
  já faz em terminar/).
"""
import hashlib
import hmac
import logging
import threading
from urllib.parse import urlencode

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.practice.models import VapiSession
from apps.practice.throttling import VapiWebhookThrottle

from . import analise, servico, tempo_fala
from .quota import obter_assinatura

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
    """URL para assistant_overrides.server.url, ou None se o webhook não pode ser usado
    (sem segredo próprio, ou VAPI_WEBHOOK_URL não é https: o Vapi não chega a localhost)."""
    base = (getattr(settings, 'VAPI_WEBHOOK_URL', None) or '').strip()
    if not webhook_configurado() or not base.startswith('https://'):
        return None
    sep = '&' if '?' in base else '?'
    return f"{base}{sep}{urlencode({'sessao': sessao_id, 'token': token_sessao(sessao_id)})}"


def _autenticar(request):
    """(ok, sessao_restrita). sessao_restrita é o id da única sessão a que o pedido tem acesso
    (token no URL) ou None (segredo global)."""
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


def sessao_da_mensagem(msg):
    """O id da VapiSession que criar_sessao mandou nos overrides (metadata e variableValues)."""
    call = _d(msg.get('call'))
    overrides = _d(call.get('assistantOverrides'))
    for origem in (
        _d(overrides.get('metadata')), _d(overrides.get('variableValues')),
        _d(_d(msg.get('artifact')).get('variableValues')),
        _d(_d(msg.get('assistant')).get('metadata')), _d(call.get('metadata')),
    ):
        valor = origem.get('sessao_id')
        if isinstance(valor, str) and valor:
            return valor
    return None


def transcricao_vapi(mensagens):
    """artifact.messages do Vapi ([{role, message}]) -> [{quem, texto}] já limpa."""
    turnos = []
    for m in mensagens if isinstance(mensagens, list) else []:
        if not isinstance(m, dict):
            continue
        papel = m.get('role')
        quem = 'aluno' if papel == 'user' else 'tutor' if papel in ('bot', 'assistant') else None
        texto = m.get('message') if isinstance(m.get('message'), str) else m.get('content')
        if quem and isinstance(texto, str):
            turnos.append({'quem': quem, 'texto': texto})
    return analise.limpar_transcricao(turnos)


def _duracao(msg):
    valor = msg.get('durationSeconds')
    if isinstance(valor, (int, float)) and valor >= 0:
        return int(valor)
    inicio, fim = parse_datetime(msg.get('startedAt') or ''), parse_datetime(msg.get('endedAt') or '')
    if inicio and fim and fim >= inicio:
        return int((fim - inicio).total_seconds())
    return None


def url_gravacao(msg):
    """O URL da gravação no end-of-call-report (artifact.recordingUrl, ou o formato antigo)."""
    artifact = _d(msg.get('artifact'))
    for valor in (artifact.get('recordingUrl'), _d(artifact.get('recording')).get('url'),
                  _d(_d(artifact.get('recording')).get('mono')).get('combinedUrl'), msg.get('recordingUrl')):
        if isinstance(valor, str) and valor.startswith('https://'):
            return valor[:1000]
    return None


def _gravacao_permitida(dados):
    """Só se guarda a gravação de uma sessão criada com gravar=True (exame oral com consentimento)."""
    cfg = dados.get('config') if isinstance(dados.get('config'), dict) else {}
    return bool(cfg.get('gravar'))


def executar_em_fundo(funcao, *args):
    """A avaliação (Claude) pode demorar até 60 s, mais do que o Vapi espera pela resposta.
    Os testes substituem esta função para correr de imediato."""
    def correr():
        try:
            funcao(*args)
        except Exception:
            logger.exception('conversa: falha na avaliação em segundo plano')
        finally:
            close_old_connections()
    t = threading.Thread(target=correr, name='conversa-avaliar', daemon=True)
    t.start()
    return t


def registar_fim_chamada(sessao_id, msg):
    """Trata um end-of-call-report. Devolve um código curto (para a resposta e os testes)."""
    sessao = VapiSession.objects.filter(pk=sessao_id).select_related('user').first()
    if sessao is None or sessao.mode != 'vapi':
        return 'sessao_desconhecida'
    artifact = _d(msg.get('artifact'))
    transcricao = transcricao_vapi(artifact.get('messages') or msg.get('messages'))
    duracao = _duracao(msg)
    fechada_agora, segundos = False, 0

    with transaction.atomic():
        # Ordem de bloqueio igual à de servico.terminar (assinatura primeiro).
        sub = obter_assinatura(sessao.user, bloquear=True)
        sessao = VapiSession.objects.select_for_update().select_related('user').get(pk=sessao_id)
        dados = servico._dados(sessao)
        if dados.get('vapi_fim'):
            return 'repetido'
        dados['transcricao_servidor'] = transcricao
        gravacao = url_gravacao(msg)
        if gravacao and _gravacao_permitida(dados):
            dados['gravacao_url'] = gravacao
        dados['vapi_fim'] = {
            'call_id': str(_d(msg.get('call')).get('id') or ''),
            'motivo': str(msg.get('endedReason') or '')[:120],
            'duracao_segundos': duracao,
            'recebido_em': timezone.now().isoformat(),
        }
        tempos = tempo_fala.segmentos_vapi(artifact.get('messages') or msg.get('messages'))
        if tempos:
            dados['tempos_vapi'] = tempos
        sessao.full_session_data = dados

        if sessao.status == VapiSession.STATUS_EM_CURSO:
            # O aluno fechou o separador (ou o relatório chegou antes de terminar/): fecha e cobra aqui.
            # A transcrição do servidor ganha à do cliente (_escolher_transcricao).
            sessao, segundos = servico._terminar_bloqueado(sessao, [], sub, segundos_max=duracao)
            fechada_agora = True
        elif (analise.tem_conteudo_suficiente(transcricao) and sessao.connected_at is not None and (
                sessao.status == VapiSession.STATUS_SEM_AVALIACAO
                or (sessao.status == VapiSession.STATUS_A_AVALIAR and not dados.get('avaliacao_iniciada_em')))):
            # Já fechada pelo cliente com uma transcrição curta/incompleta (ou ainda por avaliar):
            # avalia-se com a do servidor. Os minutos já foram cobrados e não mudam.
            m = analise.metricas(transcricao, sessao.duration_seconds)
            dados.update({'transcricao': transcricao, 'metricas': m})
            sessao.total_words = m['total_palavras']
            sessao.words_per_minute = m['palavras_por_minuto']
            sessao.status = VapiSession.STATUS_A_AVALIAR
            campos = tempo_fala.aplicar(sessao, dados, transcricao)
            sessao.save(update_fields=['full_session_data', 'total_words', 'words_per_minute', 'status'] + campos)
        elif sessao.connected_at is not None and sessao.status in VapiSession.STATUS_TERMINADAS:
            # Já fechada e avaliada: só os tempos de fala medidos (ganham à estimativa do fecho).
            campos = tempo_fala.aplicar(sessao, dados, analise.limpar_transcricao(dados.get('transcricao') or [])
                                        or transcricao)
            sessao.save(update_fields=['full_session_data'] + campos)
        else:
            sessao.save(update_fields=['full_session_data'])

    if fechada_agora:
        servico._efeitos_cobranca(sessao, segundos)
        servico.depois_de_fechar(sessao)
    if dados.get('gravacao_url'):
        try:
            from .exame import guardar_gravacao_da_sessao
            guardar_gravacao_da_sessao(sessao.pk, dados['gravacao_url'])
        except Exception:
            logger.exception('vapi webhook: falha ao guardar a gravação do exame')
    if sessao.status == VapiSession.STATUS_A_AVALIAR:
        executar_em_fundo(servico.avaliar_pendente, sessao.pk)
    return 'fechada' if fechada_agora else 'registada'


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

    sessao_id = sessao_da_mensagem(msg)
    if sessao_restrita is not None:
        if sessao_id and sessao_id != sessao_restrita:
            return Response({'error': 'Invalid webhook secret'}, status=403)
        sessao_id = sessao_restrita
    if not sessao_id:
        return Response({'status': 'sem_sessao'})
    resultado = registar_fim_chamada(sessao_id, msg)
    return Response({'status': resultado})
