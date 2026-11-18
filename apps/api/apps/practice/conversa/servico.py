"""
Regras de negócio da conversa com o tutor (independentes do HTTP).
"""
import hashlib
import logging
import math
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import DateTimeField, Value
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from django.db.models import Avg, Count, Q, Sum
from django.db.models import F
from django.utils import timezone

from apps.practice.models import DailyProgressSummary, DailyStudyLog, UserProgress, VapiSession
from apps.subscriptions.models import UserSubscription

from . import analise, regras
from apps.perfil import servico as perfil_servico

from .quota import MENSAGENS, estado_quota, obter_assinatura
from .situacoes import (
    AREA_IDS, CORRECOES, NIVEIS, SITUACOES_POR_ID, instrucoes_tutor, nome_aluno, obter_situacao,
    _limpar_prompt, primeira_fala, resumo_aluno, situacao_dict, situacoes_visiveis,
)

logger = logging.getLogger(__name__)

VERSAO = 'conversa-1'
PONTOS_POR_MINUTO = 2
MAX_PONTOS_SESSAO = 20
JANELA_ACTIVIDADE_SEGUNDOS = 30   # conta-se até 30 s depois do último sinal de vida
TOLERANCIA_SEGUNDOS = 20          # menos do que isto ligada: 0 minutos
MIN_PALAVRAS_AJUSTE = 3
AVALIACAO_BLOQUEIO_SEGUNDOS = 120  # outro pedido não repete a avaliação durante este tempo
TITULO_LEGADO = 'Conversa com o tutor'


class ErroConversa(Exception):
    def __init__(self, status, codigo, mensagem, campos=None, oferta=None):
        super().__init__(mensagem)
        self.status, self.codigo, self.mensagem, self.campos = status, codigo, mensagem, campos
        self.oferta = oferta


def _erro_quota(user, motivo):
    from apps.subscriptions.oferta import CONVERSA, oferta_segura
    return ErroConversa(403, motivo, MENSAGENS[motivo], oferta=oferta_segura(user, CONVERSA))


def modo_simulado():
    return bool(settings.CONVERSA_SIMULADA)


def config_vapi():
    if modo_simulado():
        return None
    assistant = settings.VAPI_ENGLISH_ASSISTANT_ID or settings.VAPI_DEFAULT_ASSISTANT_ID
    if not (settings.VAPI_PUBLIC_KEY and assistant):
        return None
    return {'public_key': settings.VAPI_PUBLIC_KEY, 'assistant_id': assistant}


def modo():
    return 'vapi' if config_vapi() else 'simulado'


def _situacao_de(sessao):
    return obter_situacao(sessao.situation)


def _dados(sessao):
    return sessao.full_session_data if isinstance(sessao.full_session_data, dict) else {}


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

def validar_pedido(data, user=None, situacao=None):
    erros = {}
    slug = data.get('situacao') if situacao is None else None
    if isinstance(slug, str) and slug:
        if user is None:
            situacao = obter_situacao(slug)
        else:
            obj = situacoes_visiveis(user).filter(slug=slug).first()
            situacao = situacao_dict(obj) if obj else None
    if not situacao:
        erros['situacao'] = 'Escolha uma situação válida.'
    if data.get('nivel') not in NIVEIS:
        erros['nivel'] = 'Nível inválido (A1 a C2).'
    if data.get('correcao') not in CORRECOES:
        erros['correcao'] = 'Escolha «suave» ou «directa».'
    if data.get('area') not in AREA_IDS:
        erros['area'] = 'Área inválida.'
    if erros:
        raise ErroConversa(400, 'dados_invalidos', 'Verifique os dados da conversa.', campos=erros)
    return situacao


def criar_sessao(user, data, situacao=None, objectivos=None, max_segundos=None, config_extra=None,
                 isenta_quota=False, gravar=False, instrucoes=None):
    """
    Opcionais (conversa curta de uma lição, conversa/licao.py): `situacao` já montada (em vez do
    slug em data), `objectivos` explícitos [{en, pt}], `max_segundos` (nunca acima da quota) e
    `config_extra` (guardado em full_session_data.config).

    Fase 6 (teste de nível falado, conversa/diagnostico.py, e exame oral, conversa/exame.py):
    - `isenta_quota`: não precisa de minutos do dia, não gasta minutos (minutos_cobrados = 0) e o
      limite é só `max_segundos`; fica em config.isenta_quota;
    - `gravar`: liga a gravação do áudio no Vapi (artifactPlan.recordingEnabled). SÓ o exame oral
      com o consentimento do aluno usa isto; em qualquer outra conversa nunca se grava;
    - `instrucoes`: o prompt do tutor já montado (o examinador e o diagnóstico têm o seu).
    """
    situacao = validar_pedido(data, user, situacao=situacao)
    nivel, correcao, area = data['nivel'], data['correcao'], data['area']

    fechadas = []
    with transaction.atomic():
        sub = obter_assinatura(user, bloquear=True)
        # Uma conversa de cada vez: as que ficaram abertas são fechadas (e cobradas) agora.
        for antiga in VapiSession.objects.select_for_update().filter(user=user, status=VapiSession.STATUS_EM_CURSO):
            fechadas.append(_terminar_bloqueado(antiga, [], sub))
            sub.refresh_from_db()
        quota = estado_quota(user, sub)
    for antiga, segundos in fechadas:
        _efeitos_cobranca(antiga, segundos)
        depois_de_fechar(antiga)
    # As que ainda esperam pela chamada do Vapi (esta e as que ficaram para trás): verificadas
    # agora, para os minutos delas contarem antes de se decidir a quota desta conversa.
    # (O exame e o teste de nível não gastam minutos: ficam para o ecrã deles e para o comando.)
    pendentes = list(VapiSession.objects.filter(user=user, status=VapiSession.STATUS_A_AVALIAR)
                     .exclude(situation__startswith='exame-').exclude(situation__startswith='diagnostico-')
                     .order_by('-created_at').values_list('pk', flat=True)[:3])
    for pk in pendentes:
        # Sem esperar pelo Claude: avaliação por regras (rápida).
        try:
            avaliar_pendente(pk, so_regras=True)
        except Exception:
            logger.exception('conversa: falha ao avaliar a sessão pendente %s', pk)
    if not quota['pode_comecar'] and not isenta_quota:
        raise _erro_quota(user, quota['motivo'])

    with transaction.atomic():
        sub = obter_assinatura(user, bloquear=True)
        quota = estado_quota(user, sub)
        if not quota['pode_comecar'] and not isenta_quota:
            raise _erro_quota(user, quota['motivo'])

        nome = nome_aluno(user)
        fala = primeira_fala(situacao, nivel, nome)
        if objectivos is None:
            objectivos = _objectivos(user, situacao)
        vapi = config_vapi()
        if isenta_quota and max_segundos:
            pass  # fora da quota: só o limite da própria sessão
        else:
            limite_quota = quota['max_minutos_sessao'] * 60
            max_segundos = min(limite_quota, max_segundos) if max_segundos else limite_quota
        agora = timezone.now()
        sessao = VapiSession.objects.create(
            session_id=str(uuid.uuid4()), user=user, level=nivel, domain=area, duration_minutes=0,
            overall_score=0, fluency_score=0, grammar_score=0, vocabulary_score=0, pronunciation_score=None,
            status=VapiSession.STATUS_EM_CURSO, situation=situacao['id'],
            mode='vapi' if vapi else 'simulado', started_at=agora, max_seconds=max_segundos,
            full_session_data={
                'versao': VERSAO,
                'config': {'situacao': situacao['id'], 'nivel': nivel, 'correcao': correcao, 'area': area,
                           'curso_id': str(situacao['curso_id']) if situacao.get('curso_id') else None,
                           'objectivos': objectivos, **(config_extra or {}),
                           **({'isenta_quota': True} if isenta_quota else {}),
                           # O assistente a que a chamada tem de pertencer (chamada.motivo_recusa).
                           **({'assistant_id': vapi['assistant_id']} if vapi else {}),
                           'gravar': bool(gravar and vapi)},
                'historico': [{'quem': 'tutor', 'texto': fala}],
            },
        )

    try:
        perfil_servico.semear_situacao(user, situacao)
    except Exception:
        logger.exception('conversa: falha ao semear as frases da situação no banco do aluno')

    resposta = {
        'id': sessao.session_id,
        'situacao': {'id': situacao['id'], 'titulo': situacao['titulo']},
        'max_segundos': max_segundos,
        'frases': situacao['frases'],
        'objectivos': objectivos,
        'primeira_fala': fala,
        'vapi': None,
    }
    if vapi:
        if instrucoes is None:
            instrucoes = instrucoes_tutor(situacao, nivel, correcao, area, nome,
                                          contexto=_contexto(user, situacao), objectivos=objectivos)
        resposta['vapi'] = {
            'assistant_id': vapi['assistant_id'],
            'assistant_overrides': {
                'variableValues': {
                    'nome': nome, 'nivel': nivel, 'area': area, 'correcao': correcao,
                    'situacao': _limpar_prompt(situacao['titulo'], 80), 'objectivo': situacao['brief'],
                    'instrucoes': instrucoes, 'sessao_id': sessao.session_id,
                },
                # O prompt vai em cada chamada, para não depender do prompt guardado no painel do Vapi.
                'model': modelo_vapi(instrucoes),
                'firstMessage': fala,
                'firstMessageMode': 'assistant-speaks-first',
                'maxDurationSeconds': max_segundos,
                # Sem gravação do áudio no Vapi (vem ligada por omissão): só precisamos da transcrição.
                # A única excepção é o exame oral com o consentimento do aluno (conversa/exame.py).
                'artifactPlan': {'recordingEnabled': bool(gravar)},
                'metadata': {'sessao_id': sessao.session_id},
            },
        }
        # O end-of-call-report vai para o URL do servidor configurado no painel do Vapi (assistente
        # ou organização), com o segredo global (webhook.py). Nada de URL nem token por sessão aqui:
        # os overrides passam pelo browser do aluno. A transcrição, a duração e a gravação só valem
        # quando vêm do Vapi (chamada.py, verificacao.py).
        from .webhook import webhook_configurado
        if webhook_configurado():
            resposta['vapi']['assistant_overrides']['serverMessages'] = ['end-of-call-report']
    return resposta


def _objectivos(user, situacao):
    """2 a 4 frases-alvo [{en, pt}] (perfil de fala). Uma falha no perfil não impede a conversa."""
    try:
        return perfil_servico.objectivos_detalhe(user, situacao)
    except Exception:
        logger.exception('conversa: falha ao escolher os objectivos')
        return [{'en': f['en'], 'pt': f.get('pt') or ''} for f in (situacao.get('frases') or [])[:3]
                if isinstance(f, dict) and f.get('en')]


def _contexto(user, situacao):
    try:
        return perfil_servico.contexto_do_aluno(user, situacao=situacao)
    except Exception:
        logger.exception('conversa: falha ao montar o contexto do aluno')
        return None


def modelo_vapi(instrucoes):
    """O modelo que o Vapi usa na chamada, com o prompt desta sessão."""
    modelo = {
        'provider': settings.CONVERSA_VAPI_PROVEDOR,
        'model': settings.CONVERSA_VAPI_MODELO,
        'maxTokens': 250,
        'messages': [{'role': 'system', 'content': instrucoes}],
    }
    if settings.CONVERSA_VAPI_PROVEDOR == 'openai':
        modelo['temperature'] = 0.6  # os modelos Claude actuais não aceitam temperature
    return modelo


# ---------------------------------------------------------------------------
# Durante a conversa
# ---------------------------------------------------------------------------

def obter_sessao(user, sessao_id, bloquear=False):
    qs = VapiSession.objects.filter(user=user, session_id=str(sessao_id))
    if bloquear:
        qs = qs.select_for_update()
    sessao = qs.first()
    if sessao is None:
        raise ErroConversa(404, 'nao_encontrada', 'Conversa não encontrada.')
    return sessao


def _inicio_relogio(sessao):
    """O tempo conta desde que a chamada ligou (ou, sem ligada/, desde a criação)."""
    return sessao.connected_at or sessao.started_at


def _exigir_em_curso(sessao):
    if sessao.status != VapiSession.STATUS_EM_CURSO:
        raise ErroConversa(409, 'conversa_terminada', 'Esta conversa já terminou.')
    inicio = _inicio_relogio(sessao)
    if inicio and sessao.max_seconds and timezone.now() > inicio + timedelta(seconds=sessao.max_seconds):
        raise ErroConversa(409, 'tempo_esgotado', 'O tempo desta conversa acabou. Termine para ver o resultado.')


def _registar_actividade(sessao, agora=None):
    """Sinal de vida do aluno. Sem ligada/ antes (cliente antigo ou falha), a ligação conta a partir daqui."""
    agora = agora or timezone.now()
    VapiSession.objects.filter(pk=sessao.pk).update(
        last_activity_at=agora, connected_at=Coalesce('connected_at', Value(agora, output_field=DateTimeField())))
    sessao.last_activity_at = agora
    sessao.connected_at = sessao.connected_at or agora


def ligada(user, sessao_id, call_id=None):
    """A chamada ligou (Vapi call-start; no simulado, ao começar). Idempotente.
    No modo de voz NÃO conta para cobrar: os minutos vêm da duração que o Vapi confirma
    (verificacao.py). call_id (opcional): o id da chamada no Vapi, guardado como «reclamado»
    até um GET /call o confirmar (chamada.py); um id que o Vapi já confirmou nunca muda."""
    from . import verificacao
    with transaction.atomic():
        sessao = obter_sessao(user, sessao_id, bloquear=True)
        if sessao.status != VapiSession.STATUS_EM_CURSO:
            raise ErroConversa(409, 'conversa_terminada', 'Esta conversa já terminou.')
        campos = []
        if sessao.connected_at is None:
            agora = timezone.now()
            sessao.connected_at = agora
            sessao.last_activity_at = agora
            campos += ['connected_at', 'last_activity_at']
        dados = _dados(sessao)
        if sessao.mode == 'vapi' and verificacao.reclamar_call_id(dados, call_id):
            sessao.full_session_data = dados
            campos.append('full_session_data')
        if campos:
            sessao.save(update_fields=campos)
    termina = sessao.connected_at + timedelta(seconds=sessao.max_seconds) if sessao.max_seconds else None
    return {
        'id': sessao.session_id,
        'ligada_em': sessao.connected_at.isoformat(),
        'max_segundos': sessao.max_seconds,
        'termina_em': termina.isoformat() if termina else None,
    }


def responder(user, sessao_id, texto, escrito=False):
    """Resposta do tutor no modo simulado. escrito=True: o aluno escreveu em vez de falar (a fala fica
    marcada e as frases-alvo que tiver só contam 'com_ajuda')."""
    texto = (texto or '').strip()
    if not texto:
        raise ErroConversa(400, 'texto_vazio', 'Escreva uma frase.')
    texto = ' '.join(texto.split())[:500]
    with transaction.atomic():
        sessao = obter_sessao(user, sessao_id, bloquear=True)
        _exigir_em_curso(sessao)
        if sessao.mode == 'vapi':
            # Na chamada de voz o texto escrito vai pelo próprio Vapi (add-message); aqui só no simulado.
            raise ErroConversa(409, 'so_simulado', 'Na chamada de voz, o texto escrito vai directo ao tutor.')
        situacao = _situacao_de(sessao)
        if situacao is None:
            raise ErroConversa(409, 'conversa_antiga', 'Esta conversa não suporta respostas escritas.')
        _registar_actividade(sessao)
        dados = _dados(sessao)
        cfg = dados.get('config', {})
        historico = list(dados.get('historico') or [])
        indice = sum(1 for t in historico if t.get('quem') == 'aluno')
        historico.append({'quem': 'aluno', 'texto': texto, **({'escrito': True} if escrito is True else {})})
        tutor = regras.resposta_simulada(situacao, cfg.get('correcao', 'suave'), nome_aluno(user), texto, indice)
        historico.append({'quem': 'tutor', 'texto': tutor})
        dados['historico'] = historico[-200:]
        sessao.full_session_data = dados
        sessao.save(update_fields=['full_session_data'])
    return {'tutor': tutor}


def sessao_sem_ajuda(sessao):
    """Exame oral e teste de nível: sem ajustes (Claude) durante a conversa nem texto escrito."""
    return (sessao.situation or '').startswith(('exame-', 'diagnostico-'))


def ajuste(user, sessao_id, frase):
    frase = ' '.join((frase or '').split())[:300]
    sessao = obter_sessao(user, sessao_id)
    _exigir_em_curso(sessao)  # 409 também quando o tempo acabou: não se chama o Claude depois disso
    _registar_actividade(sessao)
    # No exame e no teste de nível não há ajustes: o pedido só serve de sinal de vida.
    if sessao_sem_ajuda(sessao):
        return {'ajuste': None}
    # O cliente manda um pedido por cada fragmento final do reconhecimento de voz: os muito curtos
    # ("Yes.", "OK, sure") não têm o que corrigir e não vão ao Claude.
    if len(regras.palavras(frase)) < MIN_PALAVRAS_AJUSTE:
        return {'ajuste': None}
    if sessao.mode == 'simulado' or modo_simulado():
        return {'ajuste': regras.primeiro_ajuste(frase)}
    chave = 'conversa:ajuste:%s:%s' % (sessao.session_id, hashlib.sha1(frase.lower().encode()).hexdigest())
    if chave in cache:  # o mesmo fragmento repetido (o cliente reenviou): mesma resposta, sem novo pedido
        return {'ajuste': cache.get(chave)}
    resultado = analise.ajuste_claude(frase)
    cache.set(chave, resultado, 15 * 60)
    return {'ajuste': resultado}


MAX_AJUDAS = 60


def _juntar_lista(dados, chave, texto):
    """Junta um texto a dados[chave] (sem repetidos, no máximo MAX_AJUDAS). True se mudou."""
    if not isinstance(texto, str):
        return False
    texto = ' '.join(texto.split())[:500]
    if not perfil_servico.normalizar(texto):
        return False
    lista = [t for t in dados.get(chave) or [] if isinstance(t, str)]
    chaves = {perfil_servico.normalizar(t) for t in lista}
    if perfil_servico.normalizar(texto) in chaves or len(lista) >= MAX_AJUDAS:
        return False
    dados[chave] = lista + [texto]
    return True


def juntar_ajudas(dados, escritos=(), reveladas=()):
    """O cliente diz o que o aluno ESCREVEU (em vez de falar) e que frases-alvo REVELOU em inglês.
    Só pode baixar o resultado (essas frases ficam no máximo 'com_ajuda'), nunca subir. True se mudou."""
    if dados.get('perfil_registado'):
        return False
    mudou = False
    for t in list(escritos or [])[:MAX_AJUDAS]:
        mudou = _juntar_lista(dados, 'escritos', t) or mudou
    for t in list(reveladas or [])[:MAX_AJUDAS]:
        mudou = _juntar_lista(dados, 'reveladas', t) or mudou
    return mudou


def registar_ajuda(user, sessao_id, escrito=None, revelada=None):
    """POST sessoes/<id>/ajuda/ durante a conversa: {escrito: texto} ou {revelada: frase em inglês}."""
    with transaction.atomic():
        sessao = obter_sessao(user, sessao_id, bloquear=True)
        dados = _dados(sessao)
        if juntar_ajudas(dados, [escrito] if escrito else (), [revelada] if revelada else ()):
            sessao.full_session_data = dados
            sessao.save(update_fields=['full_session_data'])
    return {'ok': True}


# ---------------------------------------------------------------------------
# Terminar
# ---------------------------------------------------------------------------

def segundos_ligada(sessao, agora=None):
    """
    Segundos que contam no modo simulado (e, no modo de voz, só quando o Vapi nunca confirmou a
    chamada: verificacao.expirar): desde connected_at até ao fim, que é o mais cedo entre agora e
    30 s depois do último sinal de vida, e nunca mais do que max_seconds. Sem ligação: 0.
    """
    if sessao.connected_at is None:
        return 0
    agora = agora or timezone.now()
    fim = agora
    if sessao.last_activity_at:
        fim = min(agora, sessao.last_activity_at + timedelta(seconds=JANELA_ACTIVIDADE_SEGUNDOS))
    segundos = max(0, int((fim - sessao.connected_at).total_seconds()))
    if sessao.max_seconds:
        segundos = min(segundos, sessao.max_seconds)
    return segundos


def minutos_a_cobrar(segundos):
    """Menos de 20 s ligada: 0. A partir daí, cada minuto começado conta (ceil(segundos / 60))."""
    if segundos < TOLERANCIA_SEGUNDOS:
        return 0
    return math.ceil(segundos / 60)


def dia_da_sessao(sessao):
    from apps.practice.limite_licoes import hoje_luanda
    return hoje_luanda(sessao.connected_at or sessao.started_at or sessao.created_at)


def minimo_segundos(sessao):
    """No modo de voz, o exame e o teste de nível só têm nota com uma duração mínima confirmada pelo Vapi."""
    if sessao.mode != 'vapi':
        return 0
    slug = sessao.situation or ''
    if slug.startswith('exame-'):
        from .exame import MIN_SEGUNDOS_VERIFICADOS
        return MIN_SEGUNDOS_VERIFICADOS
    if slug.startswith('diagnostico-'):
        from .diagnostico import MIN_SEGUNDOS_VERIFICADOS
        return MIN_SEGUNDOS_VERIFICADOS
    return 0


def fechar(sessao, sub, segundos, transcricao, ligou, agora=None, avaliavel=True, ja_cobrados=0):
    """
    Fecha e cobra uma sessão com uma duração e uma transcrição em que se confia (simulado: relógio
    e histórico do servidor; voz: a chamada verificada do Vapi). SEM avaliar.
    Chamar dentro de transaction.atomic com a sessão e a assinatura bloqueadas.
    avaliavel=False: fecha sem avaliação (o Vapi nunca confirmou a chamada).
    ja_cobrados: minutos já descontados antes (fecho sem o Vapi corrigido depois): só se cobra a diferença.
    """
    from apps.practice.limite_licoes import hoje_luanda
    agora = agora or timezone.now()
    segundos = max(0, int(segundos or 0))
    if sessao.max_seconds:
        segundos = min(segundos, sessao.max_seconds)
    do_dia = dia_da_sessao(sessao) == hoje_luanda(agora)

    isenta = sessao_isenta(sessao)
    quota = estado_quota(sessao.user, sub)
    restantes = quota['minutos_restantes'] if do_dia and not isenta else None  # dia passado: não gasta a quota de hoje
    if restantes is not None:
        restantes += ja_cobrados
        segundos_cobrar = min(segundos, restantes * 60)
    else:
        segundos_cobrar = segundos
    minutos = minutos_a_cobrar(segundos_cobrar)
    if restantes is not None:
        minutos = min(minutos, restantes)

    dados = _dados(sessao)
    dados.pop('aguarda_vapi', None)
    dados['transcricao'] = transcricao
    dados['minutos_cobrados'] = 0 if isenta else minutos
    m = analise.metricas(transcricao, segundos_cobrar)
    dados.update({'notas': None, 'correccoes': [], 'palavras_bem_usadas': [], 'resumo': None, 'metricas': m})

    if not ligou:
        sessao.status = VapiSession.STATUS_NAO_LIGOU
    elif avaliavel and analise.tem_conteudo_suficiente(transcricao) and segundos >= minimo_segundos(sessao):
        sessao.status = VapiSession.STATUS_A_AVALIAR
    else:
        sessao.status = VapiSession.STATUS_SEM_AVALIACAO

    sessao.total_words = m['total_palavras']
    sessao.words_per_minute = m['palavras_por_minuto']
    sessao.duration_seconds = segundos_cobrar
    sessao.duration_minutes = minutos
    sessao.ended_at = sessao.ended_at or agora
    if ligou:  # fase 3: tempo de fala do aluno (medido com os tempos do Vapi, ou estimado)
        from . import tempo_fala
        tempo_fala.aplicar(sessao, dados, transcricao)
    sessao.full_session_data = dados
    sessao.save()

    a_cobrar = minutos - ja_cobrados
    if a_cobrar > 0 and do_dia and not isenta:
        UserSubscription.objects.filter(pk=sub.pk).update(
            daily_speaking_minutes_used=F('daily_speaking_minutes_used') + a_cobrar)
    return sessao, segundos_cobrar


def _suspender(sessao, transcricao_enviada, agora):
    """Modo de voz sem chamada verificada: a sessão fica 'a_avaliar' à espera do Vapi (aguarda_vapi),
    sem cobrar nem avaliar. A transcrição do cliente fica só como provisória, para mostrar."""
    dados = _dados(sessao)
    dados['aguarda_vapi'] = agora.isoformat()
    dados['transcricao_provisoria'] = transcricao_enviada
    juntar_ajudas(dados, escritos=[t['texto'] for t in transcricao_enviada if t.get('escrito')])
    sessao.status = VapiSession.STATUS_A_AVALIAR
    sessao.ended_at = agora
    sessao.full_session_data = dados
    sessao.save(update_fields=['status', 'ended_at', 'full_session_data'])
    return sessao


def _terminar_bloqueado(sessao, transcricao_enviada, sub):
    """
    Fecha uma sessão em curso, SEM avaliar (a avaliação é depois, fora da transacção).
    Chamar dentro de transaction.atomic com a sessão e a assinatura bloqueadas.
    - simulado (e sessões antigas): duração do relógio do servidor e o histórico do servidor;
    - voz: nunca se confia no cliente. Fica à espera da chamada verificada (verificacao.py), que
      fecha, cobra e manda avaliar com a duração e a transcrição do Vapi.
    """
    agora = timezone.now()
    if sessao.mode == 'vapi':
        return _suspender(sessao, transcricao_enviada, agora), 0
    historico = analise.limpar_transcricao(_dados(sessao).get('historico') or [])
    return fechar(sessao, sub, segundos_ligada(sessao, agora), historico, sessao.connected_at is not None, agora)


def sessao_isenta(sessao):
    """Teste de nível falado e exame oral: fora da quota diária de minutos."""
    cfg = _dados(sessao).get('config')
    return bool(isinstance(cfg, dict) and cfg.get('isenta_quota'))


def _efeitos_cobranca(sessao, segundos):
    """Minutos no registo diário (do dia da sessão) e sequência. Fora da transacção principal."""
    if segundos > 0 and sessao.duration_minutes > 0:
        DailyStudyLog.add_minutes(sessao.user, DailyStudyLog.KIND_CONVERSATION, segundos / 60.0,
                                  day=dia_da_sessao(sessao))


def _efeitos_avaliacao(sessao):
    """Pontos, resumo diário e notas dos cursos de uma sessão acabada de avaliar."""
    user = sessao.user
    pontos = 0
    if sessao.duration_minutes > 0 and not sessao_isenta(sessao):  # 0 minutos cobrados: sem pontos
        pontos = min(MAX_PONTOS_SESSAO, PONTOS_POR_MINUTO * sessao.duration_minutes)
        progresso, _ = UserProgress.objects.get_or_create(user=user, defaults={'points': 0})
        curso_id = (_dados(sessao).get('config') or {}).get('curso_id')
        progresso.add_points(pontos, reason='conversa', curso_id=curso_id or None)
    DailyProgressSummary.update_for_user_date(user, sessao.date or timezone.localdate())
    try:
        from apps.practice.signals import recalcular_notas_conversa
        recalcular_notas_conversa(sessao)
    except Exception:
        logger.exception('conversa: falha ao recalcular notas dos cursos')
    dados = _dados(sessao)
    dados['pontos'] = pontos
    VapiSession.objects.filter(pk=sessao.pk).update(full_session_data=dados)


def precisa_do_vapi(sessao):
    """Sessão de voz cuja chamada o Vapi ainda não confirmou: não se avalia nem conta para nada."""
    return sessao.mode == 'vapi' and not _dados(sessao).get('vapi_verificada')


def avaliar_pendente(sessao_pk, so_regras=False):
    """
    Avalia uma sessão 'a_avaliar' FORA de qualquer transacção (o Claude pode demorar até 60 s).
    Um pedido de cada vez: marca 'avaliacao_iniciada_em' antes; outro pedido nesse intervalo
    devolve a sessão ainda 'a_avaliar'. Devolve a sessão actualizada.
    """
    agora = timezone.now()
    sessao = VapiSession.objects.get(pk=sessao_pk)
    if sessao.status == VapiSession.STATUS_A_AVALIAR and precisa_do_vapi(sessao):
        # Voz sem chamada verificada: nunca se avalia a transcrição do cliente. Pede-se a chamada
        # ao Vapi (que avalia, se já terminou); passado o prazo, fecha sem nota (verificacao.py).
        from . import verificacao
        return verificacao.resolver(sessao_pk, so_regras=so_regras)
    with transaction.atomic():
        sessao = VapiSession.objects.select_for_update().select_related('user').get(pk=sessao_pk)
        if sessao.status != VapiSession.STATUS_A_AVALIAR or precisa_do_vapi(sessao):
            return sessao
        dados = _dados(sessao)
        iniciada = parse_datetime(dados.get('avaliacao_iniciada_em') or '')
        if iniciada and agora - iniciada < timedelta(seconds=AVALIACAO_BLOQUEIO_SEGUNDOS):
            return sessao
        dados['avaliacao_iniciada_em'] = agora.isoformat()
        VapiSession.objects.filter(pk=sessao.pk).update(full_session_data=dados)

    situacao = _situacao_de(sessao) or obter_situacao('conversa_livre') or SITUACOES_POR_ID['conversa_livre']
    transcricao = dados.get('transcricao') or []
    objectivos = (dados.get('config') or {}).get('objectivos') or []
    try:
        conhecidos = [{'chave': p.chave, 'descricao': p.descricao}
                      for p in perfil_servico.padroes_abertos(sessao.user, limite=10)]
    except Exception:
        logger.exception('conversa: falha ao ler os padrões de erro do aluno')
        conhecidos = []
    especial = _avaliacao_especial(sessao)
    simulado = so_regras or sessao.mode == 'simulado' or modo_simulado()
    if especial is not None:
        resultado = especial.avaliar(sessao, transcricao, situacao, simulado=simulado,
                                     objectivos=objectivos, padroes_conhecidos=conhecidos)
    else:
        resultado = analise.avaliar(transcricao, situacao, sessao.level, sessao.domain, sessao.duration_seconds,
                                    simulado=simulado, objectivos=objectivos, padroes_conhecidos=conhecidos)

    with transaction.atomic():
        sessao = VapiSession.objects.select_for_update().select_related('user').get(pk=sessao_pk)
        if sessao.status != VapiSession.STATUS_A_AVALIAR:
            return sessao
        notas = resultado['notas']
        dados = _dados(sessao)
        dados.pop('avaliacao_iniciada_em', None)
        dados.update({
            'notas': notas, 'correccoes': resultado['correccoes'],
            'palavras_bem_usadas': resultado['palavras_bem_usadas'], 'resumo': resultado['resumo'],
            'summary': resultado['resumo'], 'metricas': resultado['metricas'], 'fonte_avaliacao': resultado['fonte'],
            'padroes': resultado.get('padroes') or [], 'nivel_cefr': resultado.get('nivel_cefr'),
            'objectivos_usados': resultado.get('objectivos_usados'),
        })
        if especial is not None and resultado.get('extra') is not None:
            dados[especial.CHAVE] = resultado['extra']
        sessao.status = VapiSession.STATUS_AVALIADA
        sessao.fluency_score = notas['fluencia']
        sessao.grammar_score = notas['gramatica']
        sessao.vocabulary_score = notas['vocabulario']
        sessao.pronunciation_score = notas['pronuncia']
        sessao.overall_score = notas['geral'] or 0
        sessao.corrections_count = len(resultado['correccoes'])
        sessao.full_session_data = dados
        sessao.calculate_improvement()
        sessao.save()
    _efeitos_avaliacao(sessao)
    try:
        perfil_servico.registar_conversa(sessao)
    except Exception:
        logger.exception('conversa: falha ao actualizar o perfil de fala (sessão %s)', sessao.pk)
    if especial is not None:
        try:
            sessao.refresh_from_db()  # registar_conversa guardou full_session_data['perfil']
            especial.depois_de_avaliar(sessao)
        except Exception:
            logger.exception('conversa: falha no registo depois da avaliação (sessão %s)', sessao.pk)
    sessao.refresh_from_db()
    return sessao


PARADA_SEGUNDOS = 120  # 'a_avaliar' há mais do que isto sem avaliação em curso: a thread perdeu-se


def avaliacoes_paradas(agora=None, limite=20):
    """
    Sessões 'a_avaliar' que já podiam estar avaliadas e não estão: a thread da avaliação perdeu-se
    (o Gunicorn reciclou ou reiniciou o worker) ou nunca chegou a correr. Só as que não precisam do
    Vapi (as que precisam são de verificacao.pendentes) e:
    - com avaliacao_iniciada_em há mais de AVALIACAO_BLOQUEIO_SEGUNDOS (o bloqueio já não vale), ou
    - sem avaliação iniciada, fechadas (ou verificadas pelo Vapi) há mais de PARADA_SEGUNDOS.
    Devolve os ids, das mais antigas para as mais recentes.
    """
    agora = agora or timezone.now()
    corte = agora - timedelta(seconds=PARADA_SEGUNDOS)
    qs = (VapiSession.objects.filter(status=VapiSession.STATUS_A_AVALIAR)
          .filter(~Q(mode='vapi') | Q(full_session_data__has_key='vapi_verificada'))
          .filter(Q(ended_at__lte=corte) | Q(ended_at__isnull=True, created_at__lte=corte))
          .order_by('ended_at', 'created_at'))
    out = []
    for pk, dados in qs.values_list('pk', 'full_session_data').iterator():
        dados = dados if isinstance(dados, dict) else {}
        iniciada = parse_datetime(dados.get('avaliacao_iniciada_em') or '')
        if iniciada is not None:
            if agora - iniciada < timedelta(seconds=AVALIACAO_BLOQUEIO_SEGUNDOS):
                continue  # avaliação em curso noutro processo
        else:
            verificada = dados.get('vapi_verificada') if isinstance(dados.get('vapi_verificada'), dict) else {}
            em = parse_datetime(verificada.get('em') or '') if isinstance(verificada.get('em'), str) else None
            if em is not None and em > corte:
                continue  # o Vapi acabou de confirmar: a avaliação deve estar a começar
        out.append(pk)
        if len(out) >= limite:
            break
    return out


def avaliar_sem_bloquear(sessao):
    """
    Avalia uma sessão 'a_avaliar' sem prender o pedido HTTP: a avaliação (Claude) pode demorar até
    60 s e em produção há poucos lugares no Gunicorn (2 workers x 2 threads no VPS); umas quantas
    conversas a terminar ao mesmo tempo deixavam a API inteira (entrada, lições, site) à espera.
    O cliente já sonda enquanto o estado é 'a_avaliar' (resumo da conversa, exame, teste de nível).
    AVALIACAO_EM_FUNDO=False (testes) avalia no próprio pedido, como antes.
    Devolve a sessão relida (já avaliada quando corre no pedido).
    """
    if sessao.status != VapiSession.STATUS_A_AVALIAR:
        return sessao
    if getattr(settings, 'AVALIACAO_EM_FUNDO', True):
        from .webhook import executar_em_fundo
        executar_em_fundo(avaliar_pendente, sessao.pk)
        sessao.refresh_from_db()
        return sessao
    return avaliar_pendente(sessao.pk)


def _avaliacao_especial(sessao):
    """O módulo que avalia o teste de nível (diagnostico) ou o exame oral (exame); None nas outras."""
    slug = sessao.situation or ''
    if slug.startswith('diagnostico-'):
        from . import diagnostico
        return diagnostico
    if slug.startswith('exame-'):
        from . import exame
        return exame
    return None


def depois_de_fechar(sessao):
    """Uma sessão especial acabou de fechar: não ligou, falou pouco ou vai ser avaliada."""
    especial = _avaliacao_especial(sessao)
    if especial is not None and sessao.status != VapiSession.STATUS_EM_CURSO:
        try:
            especial.depois_de_avaliar(sessao)
        except Exception:
            logger.exception('conversa: falha ao fechar a sessão especial %s', sessao.pk)


def terminar(user, sessao_id, transcricao_bruta, call_id=None, reveladas=None):
    """
    O aluno terminou (ou fechou o separador). No simulado fecha, cobra e avalia já. Na voz, a
    transcrição do cliente é só provisória (para mostrar): a sessão espera pela chamada verificada
    do Vapi, pedida aqui mesmo (call_id reclamado) e, se ainda não terminou lá, pelo webhook ou por
    uma nova tentativa (resumo, comando verificar_conversas_vapi).
    """
    from . import verificacao
    transcricao = analise.limpar_transcricao(transcricao_bruta)
    with transaction.atomic():
        # Ordem de bloqueio igual à de criar_sessao (assinatura primeiro) para evitar deadlocks.
        sub = obter_assinatura(user, bloquear=True)
        sessao = obter_sessao(user, sessao_id, bloquear=True)
        dados = _dados(sessao)
        mudou = juntar_ajudas(dados, escritos=[t['texto'] for t in transcricao if t.get('escrito')],
                              reveladas=reveladas if isinstance(reveladas, list) else ())
        if sessao.mode == 'vapi':
            mudou = verificacao.reclamar_call_id(dados, call_id) or mudou
        if mudou:
            sessao.full_session_data = dados
        if sessao.status != VapiSession.STATUS_EM_CURSO:
            fechada_agora = False
            if mudou:
                sessao.save(update_fields=['full_session_data'])
        else:
            sessao, segundos = _terminar_bloqueado(sessao, transcricao, sub)
            fechada_agora = True
    # Cobrança já gravada (commit): o resto corre sem bloqueios.
    if fechada_agora:
        _efeitos_cobranca(sessao, segundos)
        depois_de_fechar(sessao)
    sessao = avaliar_sem_bloquear(sessao)
    return resumo(sessao)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _titulo(sessao):
    s = _situacao_de(sessao)
    return s['titulo'] if s else TITULO_LEGADO


def _transcricao_legada(dados):
    out = []
    for t in dados.get('conversation_history') or []:
        if isinstance(t, dict) and t.get('text'):
            out.append({'quem': 'aluno' if t.get('who') == 'student' else 'tutor', 'texto': str(t['text'])})
    return out


def _correccoes_legadas(dados):
    out = []
    for c in dados.get('corrections') or []:
        if isinstance(c, dict) and c.get('original_phrase'):
            out.append({'disse': c.get('original_phrase'), 'certo': c.get('corrected_phrase') or '',
                        'porque': c.get('explanation_pt') or c.get('short_explanation_pt') or ''})
    return out


def obter_resumo(user, sessao_id):
    """GET da sessão. Uma sessão que ficou 'a_avaliar' (p.ex. o pedido de terminar caiu a meio)
    é avaliada aqui, se ninguém a estiver a avaliar."""
    sessao = obter_sessao(user, sessao_id)
    sessao = avaliar_sem_bloquear(sessao)
    return resumo(sessao)


def resumo(sessao):
    """
    estado: em_curso | a_avaliar | avaliada | sem_avaliacao | nao_ligou.
    situacao.id é null nas sessões do fluxo antigo (sem situação).
    minutos == minutos_cobrados: os minutos que contaram (para a quota do dia da sessão).
    """
    dados = _dados(sessao)
    estado = sessao.status
    notas = None
    if estado == VapiSession.STATUS_AVALIADA:
        notas = {
            'geral': sessao.overall_score, 'fluencia': sessao.fluency_score,
            'gramatica': sessao.grammar_score, 'pronuncia': sessao.pronunciation_score,
            'vocabulario': sessao.vocabulary_score,
        }
    provisoria = False
    if 'versao' in dados:
        transcricao = dados.get('transcricao')
        if not transcricao and dados.get('transcricao_provisoria'):
            # Voz ainda sem a chamada verificada (ou fechada sem ela): o que o browser mostrou, sem valor de nota.
            transcricao, provisoria = dados['transcricao_provisoria'], True
        transcricao = transcricao or analise.limpar_transcricao(dados.get('historico') or [])
        correccoes = dados.get('correccoes') or []
        bem = dados.get('palavras_bem_usadas') or []
        texto_resumo = dados.get('resumo')
    else:  # sessões do fluxo antigo
        transcricao = _transcricao_legada(dados) or dados.get('transcricao') or []
        correccoes = _correccoes_legadas(dados) or dados.get('correccoes') or []
        bem = dados.get('palavras_bem_usadas') or []
        texto_resumo = dados.get('resumo') or dados.get('summary')
    situacao = _situacao_de(sessao)
    objectivos, padroes = _perfil_da_sessao(sessao, dados)
    return {
        'id': sessao.session_id,
        'situacao': {'id': situacao['id'] if situacao else None, 'titulo': _titulo(sessao)},
        'iniciada_em': (sessao.started_at or sessao.created_at).isoformat(),
        'minutos': sessao.duration_minutes,
        'minutos_cobrados': dados.get('minutos_cobrados', sessao.duration_minutes),
        'segundos': sessao.duration_seconds or sessao.duration_minutes * 60,
        'estado': estado,
        'notas': notas,
        'transcricao': transcricao,
        'transcricao_provisoria': provisoria,
        'correccoes': correccoes,
        'palavras_bem_usadas': bem,
        'resumo': texto_resumo or None,
        'objectivos': objectivos,
        'padroes': padroes,
        'fala': _tempo_fala(sessao),
    }


def _tempo_fala(sessao):
    from . import tempo_fala
    try:
        return tempo_fala.resumo(sessao)
    except Exception:
        logger.exception('conversa: falha no resumo do tempo de fala')
        return None


def _perfil_da_sessao(sessao, dados):
    """
    Objectivos [{en, pt, usado, com_ajuda}] e padrões [{chave, descricao, errado, certo, estado}]
    desta conversa. estado: novo | recorrente | superado (superado é o estado de agora).
    """
    registo = dados.get('perfil') if isinstance(dados.get('perfil'), dict) else {}
    objectivos = registo.get('objectivos')
    if objectivos is None:
        objectivos = [{'en': o['en'], 'pt': o.get('pt') or '', 'usado': False, 'com_ajuda': False}
                      for o in (dados.get('config') or {}).get('objectivos') or [] if isinstance(o, dict) and o.get('en')]
    padroes = [dict(p) for p in registo.get('padroes') or [] if isinstance(p, dict)]
    if padroes:
        try:
            superados = perfil_servico.padroes_superados(sessao.user_id, [p['chave'] for p in padroes])
        except Exception:
            superados = set()
        for p in padroes:
            if p['chave'] in superados:
                p['estado'] = 'superado'
    return objectivos, padroes


def preparar(user):
    from .situacoes import AREAS, preferencias_padrao
    situacoes, dicts = [], []
    for obj in situacoes_visiveis(user):
        s = situacao_dict(obj)
        item = {k: s[k] for k in ('id', 'titulo', 'minutos_sugeridos', 'area')}
        # Para o aluno: só a primeira frase (o texto completo orienta o tutor).
        item['descricao'] = resumo_aluno(s['descricao'])
        # Nível e correcção sugeridos pelo professor (o aluno pode mudar antes de começar);
        # nas situações da plataforma não há sugestão: ficam as preferências do aluno.
        do_professor = obj.criado_por_id is not None
        item['nivel'] = s['nivel'] if do_professor and s['nivel'] in NIVEIS else None
        item['correcao'] = s['correcao'] if do_professor and s['correcao'] in CORRECOES else None
        item['curso'] = {'id': str(obj.curso_id), 'titulo': obj.curso.title} if obj.curso_id else None
        # Lugar no percurso do curso (courses/percurso.py): a aula depois da qual se faz, e o tipo.
        item['aula'] = ({'id': str(obj.aula_id), 'titulo': obj.aula.title, 'unidade': obj.aula.section.sectionTitle}
                        if obj.aula_id else None)
        item['tipo_conversa'] = obj.tipo_conversa or None
        situacoes.append(item)
        dicts.append(s)
    preferencias = preferencias_padrao(user)
    perfil = {'nivel': None}
    objectivos = {}
    try:
        p = perfil_servico.obter_perfil(user)
        perfil['nivel'] = p.nivel_falar
        if p.nivel_falar in NIVEIS:
            preferencias['nivel'] = p.nivel_falar  # «O seu nível» (o aluno pode mudar)
        # As mesmas consultas para todas as situações.
        banco = perfil_servico.banco_a_aprender(user)
        from apps.perfil.models import ItemBanco
        chaves = {perfil_servico.normalizar(f['en']) for s in dicts for f in perfil_servico._frases_situacao(s)}
        estados = dict(ItemBanco.objects.filter(user=user, chave__in=chaves).values_list('chave', 'estado'))
        for s in dicts:
            objectivos[s['id']] = perfil_servico.objectivos_detalhe(user, s, banco=banco, estados=estados)
    except Exception:
        logger.exception('conversa: falha ao ler o perfil de fala no preparar')
    return {
        'situacoes': situacoes,
        'objectivos': objectivos,
        'perfil': perfil,
        'niveis': NIVEIS,
        'areas': AREAS,
        'preferencias': preferencias,
        'quota': estado_quota(user),
        'modo': modo(),
        'vapi': config_vapi(),
    }


COMPETENCIAS = [
    ('fluencia', 'Fluência', 'fluency_score'),
    ('gramatica', 'Gramática', 'grammar_score'),
    ('pronuncia', 'Pronúncia', 'pronunciation_score'),
    ('vocabulario', 'Vocabulário', 'vocabulary_score'),
]


def _erro_mais_frequente(sessoes):
    contagem = {}
    for dados in sessoes.values_list('full_session_data', flat=True)[:20]:
        for c in (dados or {}).get('correccoes') or []:
            if isinstance(c, dict) and c.get('disse'):
                k = (c['disse'].lower(), c.get('certo', ''))
                contagem[k] = contagem.get(k, 0) + 1
    if not contagem:
        return None
    (disse, certo), n = max(contagem.items(), key=lambda kv: kv[1])
    return disse, certo, n


def _nota_competencia(chave, valor, mais_fraca, erro_freq, padrao=None):
    if valor is None:
        if chave == 'pronuncia':
            return 'Ainda não medimos a pronúncia nas conversas (só o texto).'
        return 'Ainda sem dados.'
    if chave == 'gramatica' and padrao and valor < 85:
        if padrao['errado'] and padrao['certo']:
            return f'Erro a trabalhar: {padrao["descricao"]} («{padrao["errado"]}» → «{padrao["certo"]}»).'
        return f'Erro a trabalhar: {padrao["descricao"]}'
    if chave == 'gramatica' and erro_freq and valor < 85:
        disse, certo, _ = erro_freq
        return f'Erro mais frequente: «{disse}» → «{certo}».'
    dicas = {
        'fluencia': ('Responda com frases completas, sem parar a meio.',
                     'Ligue ideias com «because», «so» e «then».',
                     'Boa fluidez. Tente falar mais tempo em cada turno.'),
        'gramatica': ('Reveja as correcções das últimas conversas antes de começar.',
                      'Atenção aos tempos verbais e ao -s do presente.',
                      'Gramática sólida. Experimente frases mais longas.'),
        'vocabulario': ('Leia as frases úteis da situação antes de começar.',
                        'Use mais termos da sua área de trabalho.',
                        'Bom vocabulário. Varie as expressões.'),
    }[chave]
    texto = dicas[0] if valor < 60 else dicas[1] if valor < 80 else dicas[2]
    if chave == mais_fraca and valor < 80:
        texto = 'A sua competência mais fraca. ' + texto
    return texto


def progresso(user):
    hoje = timezone.localdate()
    terminadas = VapiSession.objects.filter(user=user, status__in=VapiSession.STATUS_TERMINADAS)
    avaliadas = terminadas.filter(status=VapiSession.STATUS_AVALIADA)

    agg = terminadas.aggregate(n=Count('session_id'), minutos=Sum('duration_minutes'))
    medias = avaliadas.aggregate(
        geral=Avg('overall_score'),
        mes=Avg('overall_score', filter=Q(date__gt=hoje - timedelta(days=30))),
        mes_ant=Avg('overall_score', filter=Q(date__lte=hoje - timedelta(days=30),
                                              date__gt=hoje - timedelta(days=60))),
        **{chave: Avg(campo) for chave, _, campo in COMPETENCIAS},
    )

    def _r(v):
        return round(v) if v is not None else None

    variacao = None
    if medias['mes'] is not None and medias['mes_ant'] is not None:
        variacao = round(medias['mes'] - medias['mes_ant'])

    valores = {chave: _r(medias[chave]) for chave, _, _ in COMPETENCIAS}
    medidos = {k: v for k, v in valores.items() if v is not None}
    mais_fraca = min(medidos, key=medidos.get) if medidos else None
    erro_freq = _erro_mais_frequente(avaliadas.order_by('-created_at'))
    try:
        perfil = perfil_servico.resumo_progresso(user)
    except Exception:
        logger.exception('conversa: falha ao ler o perfil de fala no progresso')
        perfil = {'padroes': [], 'frases_sozinho': {'total': 0, 'recentes': []}}
    padrao = next((p for p in perfil['padroes'] if not p['superado']), None)

    ultimas = []
    for s in terminadas.order_by('-created_at')[:10]:
        ultimas.append({
            'id': s.session_id, 'titulo': _titulo(s),
            'iniciada_em': (s.started_at or s.created_at).isoformat(),
            'minutos': s.duration_minutes,
            'geral': s.overall_score if s.status == VapiSession.STATUS_AVALIADA else None,
        })

    return {
        'media': _r(medias['geral']),
        'variacao_mes': variacao,
        'sessoes': agg['n'] or 0,
        'minutos': agg['minutos'] or 0,
        'por_competencia': [
            {'chave': chave, 'nome': nome, 'valor': valores[chave],
             'nota': _nota_competencia(chave, valores[chave], mais_fraca, erro_freq, padrao)}
            for chave, nome, _ in COMPETENCIAS
        ],
        'ultimas': ultimas,
        'padroes': perfil['padroes'],
        'frases_sozinho': perfil['frases_sozinho'],
    }
