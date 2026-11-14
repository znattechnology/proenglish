"""
Fecho, cobrança e avaliação das conversas por voz a partir da chamada VERIFICADA do Vapi.

Modelo de confiança (ver chamada.py):
- o browser só dá pistas: o id da chamada («reclamado»), a transcrição provisória (para mostrar),
  e o que pode BAIXAR o resultado (falas escritas, frases reveladas em inglês);
- a duração (cobrança), a transcrição (avaliação, perfil de fala, notas do curso), o fim da
  chamada e a gravação vêm só do Vapi: GET /call/{id} com a chave privada, ou o end-of-call-report
  com o segredo global do webhook. A ordem de chegada não importa: a primeira chamada verificada
  fecha e avalia; as seguintes não mudam nada (dados.vapi_verificada).

Estados de uma sessão de voz:
  em_curso -> (terminar/) a_avaliar + aguarda_vapi -> (chamada verificada) fechar(): cobra a
  duração do Vapi -> a_avaliar -> avaliada | sem_avaliacao | nao_ligou.
  Sem chamada verificada ao fim de ESPERA_MAXIMA_MINUTOS: fecha sem nota (expirar), cobrando pelo
  relógio do servidor (ligada/ + sinais de vida), como no simulado. Uma chamada verificada que
  chegue depois ainda fecha e avalia uma vez (corrige os minutos).
"""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.practice.models import VapiSession

from . import analise, chamada

logger = logging.getLogger(__name__)

ESPERA_MAXIMA_MINUTOS = 30
INTERVALO_SEGUNDOS = 10   # no máximo um GET /call por sessão neste intervalo (resumo, exame, terminar)
MAX_RECUSADOS = 10


def _dados(sessao):
    return sessao.full_session_data if isinstance(sessao.full_session_data, dict) else {}


def reclamar_call_id(dados, valor):
    """Guarda o id que o cliente diz ser o da chamada (só um UUID; nunca troca um id já confirmado
    pelo Vapi nem repete um recusado). True se mudou."""
    cid = chamada.call_id_valido(valor)
    if cid is None or dados.get('vapi_call_id') or cid in (dados.get('vapi_call_ids_recusados') or []):
        return False
    if dados.get('vapi_call_id_reclamado') == cid:
        return False
    dados['vapi_call_id_reclamado'] = cid
    return True


def _candidatos(dados):
    out = []
    for valor in (dados.get('vapi_call_id'), dados.get('vapi_call_id_reclamado')):
        cid = chamada.call_id_valido(valor)
        if cid and cid not in out:
            out.append(cid)
    return out


def _actualizar_dados(sessao_pk, funcao):
    with transaction.atomic():
        s = VapiSession.objects.select_for_update().get(pk=sessao_pk)
        dados = dict(_dados(s))
        funcao(dados)
        VapiSession.objects.filter(pk=s.pk).update(full_session_data=dados)


def _recusar(sessao_pk, cid, motivo):
    logger.warning('conversa: chamada %s recusada para a sessão %s (%s)', cid, sessao_pk, motivo)

    def f(dados):
        if dados.get('vapi_call_id_reclamado') == cid:
            dados.pop('vapi_call_id_reclamado')
        if dados.get('vapi_call_id') == cid and not dados.get('vapi_verificada'):
            dados.pop('vapi_call_id')
        recusados = [c for c in dados.get('vapi_call_ids_recusados') or [] if c != cid]
        dados['vapi_call_ids_recusados'] = (recusados + [cid])[-MAX_RECUSADOS:]
    _actualizar_dados(sessao_pk, f)


def _confirmar_id(sessao_pk, cid):
    def f(dados):
        dados['vapi_call_id'] = cid
        if dados.get('vapi_call_id_reclamado') == cid:
            dados.pop('vapi_call_id_reclamado')
    _actualizar_dados(sessao_pk, f)


def verificar(sessao_pk, so_regras=False, forcar=False, em_fundo=False):
    """
    Pede ao Vapi a chamada da sessão (GET /call) e, se pertence à sessão e já terminou, aplica-a.
    Devolve um código: fechada | registada | ja_verificada | pendente | sem_chamada | sem_chave |
    recusada | erro | sem_sessao. Nunca levanta (falhas do Vapi ficam no log).
    """
    s = VapiSession.objects.filter(pk=sessao_pk).first()
    if s is None or s.mode != 'vapi':
        return 'sem_sessao'
    dados = _dados(s)
    if dados.get('vapi_verificada'):
        return 'ja_verificada'
    if not chamada.configurado():
        return 'sem_chave'
    ids = _candidatos(dados)
    if not ids:
        return 'sem_chamada'
    if not forcar and not cache.add(f'conversa:verificar:{s.pk}', 1, INTERVALO_SEGUNDOS):
        return 'pendente'
    for cid in ids:
        try:
            call = chamada.obter_chamada(cid)
        except chamada.ErroVapi as e:
            logger.warning('conversa: não foi possível pedir a chamada %s ao Vapi: %s', cid, e)
            return 'erro'
        except Exception:
            logger.exception('conversa: resposta inesperada do Vapi para a chamada %s', cid)
            return 'erro'
        if call is None:
            _recusar(s.pk, cid, 'desconhecida')
            continue
        v = chamada.ler_chamada(call)
        motivo = 'outro_id' if v['id'] != cid else chamada.motivo_recusa(v, s)
        if motivo:
            _recusar(s.pk, cid, motivo)
            continue
        if not v['terminada']:
            _confirmar_id(s.pk, cid)
            return 'pendente'
        return aplicar(s.pk, v, 'api', so_regras=so_regras, em_fundo=em_fundo)
    return 'recusada'


def aplicar(sessao_pk, v, origem, so_regras=False, em_fundo=False):
    """
    Aplica uma chamada verificada (chamada.ler_chamada / ler_relatorio, já conferida com
    chamada.motivo_recusa): transcrição e tempos do Vapi, gravação (só exame com consentimento),
    fecho e cobrança com a duração do Vapi, e avaliação. Idempotente.
    """
    from apps.practice.conversa import servico, tempo_fala
    from .quota import obter_assinatura

    s0 = VapiSession.objects.select_related('user').filter(pk=sessao_pk).first()
    if s0 is None or s0.mode != 'vapi':
        return 'sem_sessao'
    if _dados(s0).get('vapi_verificada'):
        return _gravacao_tardia(sessao_pk, v)
    agora = timezone.now()
    fechada_agora, refecho, segundos = False, False, 0
    try:
        with transaction.atomic():
            sub = obter_assinatura(s0.user, bloquear=True)  # ordem de bloqueio de servico.terminar
            s = VapiSession.objects.select_for_update().select_related('user').get(pk=sessao_pk)
            dados = _dados(s)
            if dados.get('vapi_verificada'):
                raise _JaVerificada()  # outro pedido verificou entretanto
            transcricao = chamada.transcricao(v['mensagens'], escritos=dados.get('escritos'))
            duracao = max(0, int(v.get('duracao') or 0))
            dados['vapi_call_id'] = v['id']
            dados.pop('vapi_call_id_reclamado', None)
            dados.pop('vapi_fim', None)
            dados['transcricao_servidor'] = transcricao
            from .tempo_fala import segmentos_vapi
            tempos = segmentos_vapi(v['mensagens'])
            if tempos:
                dados['tempos_vapi'] = tempos
            dados['vapi_verificada'] = {'call_id': v['id'], 'duracao_segundos': duracao, 'motivo': v.get('motivo') or '',
                                        'origem': origem, 'em': agora.isoformat()}
            cfg = dados.get('config') if isinstance(dados.get('config'), dict) else {}
            if v.get('gravacao_url') and cfg.get('gravar') and not dados.get('gravacao_apagada'):
                dados['gravacao_url'] = v['gravacao_url']
            if cfg.get('gravar'):
                # Exame oral gravado: as falas (com os tempos do Vapi) para a nota de pronúncia.
                from .exame import CHAVE_FALAS, falas_para_pronuncia
                falas = falas_para_pronuncia(v['mensagens'])
                if falas:
                    dados[CHAVE_FALAS] = falas
            s.full_session_data = dados
            if duracao > 0 and s.connected_at is None:
                inicio = parse_datetime(v['inicio']) if isinstance(v.get('inicio'), str) else None
                s.connected_at = inicio or s.started_at or agora

            if s.status == VapiSession.STATUS_EM_CURSO or dados.get('aguarda_vapi'):
                s, segundos = servico.fechar(s, sub, duracao, transcricao, duracao > 0, agora)
                fechada_agora = True
            elif dados.get('fechada_sem_vapi') and s.status != VapiSession.STATUS_AVALIADA:
                # Fechada sem o Vapi (expirar): corrige os minutos e avalia, uma vez.
                ja = int(dados.get('minutos_cobrados') or 0)
                dados.pop('fechada_sem_vapi', None)
                s, segundos = servico.fechar(s, sub, duracao, transcricao, duracao > 0, agora, ja_cobrados=ja)
                fechada_agora, refecho = True, True
            elif s.status in (VapiSession.STATUS_A_AVALIAR, VapiSession.STATUS_SEM_AVALIACAO) and duracao > 0:
                # Sessão antiga, fechada pelo cliente antes desta verificação: avalia com a do Vapi
                # (os minutos já cobrados não mudam).
                m = analise.metricas(transcricao, s.duration_seconds)
                dados.update({'transcricao': transcricao, 'metricas': m})
                s.total_words, s.words_per_minute = m['total_palavras'], m['palavras_por_minuto']
                ok = analise.tem_conteudo_suficiente(transcricao) and duracao >= servico.minimo_segundos(s)
                s.status = VapiSession.STATUS_A_AVALIAR if ok else VapiSession.STATUS_SEM_AVALIACAO
                dados.pop('avaliacao_iniciada_em', None)
                tempo_fala.aplicar(s, dados, transcricao)
                s.full_session_data = dados
                s.save()
            else:
                # Já avaliada (antes desta verificação): só os tempos de fala medidos.
                if s.connected_at is not None:
                    tempo_fala.aplicar(s, dados, analise.limpar_transcricao(dados.get('transcricao') or []) or transcricao)
                s.save()

    except _JaVerificada:
        return _gravacao_tardia(sessao_pk, v)

    if fechada_agora:
        if not refecho:
            servico._efeitos_cobranca(s, segundos)
        servico.depois_de_fechar(s)
    if dados.get('gravacao_url'):
        _guardar_gravacao(s.pk, dados['gravacao_url'])
    if s.status == VapiSession.STATUS_A_AVALIAR:
        if em_fundo:
            from .webhook import executar_em_fundo
            executar_em_fundo(servico.avaliar_pendente, s.pk)
        else:
            servico.avaliar_pendente(s.pk, so_regras=so_regras)
    return 'fechada' if fechada_agora else 'registada'


class _JaVerificada(Exception):
    pass


def _gravacao_tardia(sessao_pk, v):
    """Já fechada com a chamada verificada. A gravação (exame com consentimento) pode só vir num
    relatório/GET posterior da MESMA chamada: só isso se aproveita."""
    url = v.get('gravacao_url')
    if not url:
        return 'ja_verificada'
    with transaction.atomic():
        s = VapiSession.objects.select_for_update().get(pk=sessao_pk)
        dados = dict(_dados(s))
        cfg = dados.get('config') if isinstance(dados.get('config'), dict) else {}
        if (v.get('id') != dados.get('vapi_call_id') or not cfg.get('gravar') or dados.get('gravacao_apagada')
                or dados.get('gravacao_url')):
            return 'ja_verificada'
        dados['gravacao_url'] = url
        VapiSession.objects.filter(pk=s.pk).update(full_session_data=dados)
    _guardar_gravacao(sessao_pk, url)
    return 'ja_verificada'


def _guardar_gravacao(sessao_pk, url):
    try:
        from .exame import guardar_gravacao_da_sessao
        guardar_gravacao_da_sessao(sessao_pk, url)
    except Exception:
        logger.exception('conversa: falha ao guardar a gravação do exame (sessão %s)', sessao_pk)


def _inicio_da_espera(sessao):
    dados = _dados(sessao)
    return parse_datetime(dados.get('aguarda_vapi') or '') or sessao.ended_at or sessao.created_at


def expirada(sessao, agora=None):
    agora = agora or timezone.now()
    inicio = _inicio_da_espera(sessao)
    return inicio is not None and agora - inicio >= timedelta(minutes=ESPERA_MAXIMA_MINUTOS)


def expirar(sessao_pk):
    """O Vapi nunca confirmou a chamada: fecha sem nota. Cobra pelo relógio do servidor (como no
    simulado); a transcrição do cliente fica só para mostrar."""
    from apps.practice.conversa import servico
    from .quota import obter_assinatura
    s0 = VapiSession.objects.select_related('user').filter(pk=sessao_pk).first()
    if s0 is None:
        return None
    segundos, fechada = 0, False
    with transaction.atomic():
        sub = obter_assinatura(s0.user, bloquear=True)
        s = VapiSession.objects.select_for_update().select_related('user').get(pk=sessao_pk)
        dados = _dados(s)
        if s.status != VapiSession.STATUS_A_AVALIAR or dados.get('vapi_verificada'):
            return s
        if dados.get('aguarda_vapi'):
            dados['fechada_sem_vapi'] = timezone.now().isoformat()
            s.full_session_data = dados
            s, segundos = servico.fechar(s, sub, servico.segundos_ligada(s, s.ended_at), [],
                                         s.connected_at is not None, avaliavel=False)
            fechada = True
        else:  # sessão antiga já cobrada, à espera de avaliação: sem nota
            s.status = VapiSession.STATUS_SEM_AVALIACAO
            dados.pop('avaliacao_iniciada_em', None)
            s.full_session_data = dados
            s.save(update_fields=['status', 'full_session_data'])
            fechada = True
    if fechada:
        if dados.get('fechada_sem_vapi'):
            servico._efeitos_cobranca(s, segundos)
        servico.depois_de_fechar(s)
    return s


def resolver(sessao_pk, so_regras=False, forcar=False):
    """Sessão de voz à espera do Vapi: tenta verificar; passado o prazo, expira. Devolve a sessão."""
    try:
        verificar(sessao_pk, so_regras=so_regras, forcar=forcar)
    except Exception:
        logger.exception('conversa: falha ao verificar a sessão %s', sessao_pk)
    s = VapiSession.objects.select_related('user').get(pk=sessao_pk)
    if s.status == VapiSession.STATUS_A_AVALIAR and not _dados(s).get('vapi_verificada') and expirada(s):
        s = expirar(sessao_pk) or s
        s.refresh_from_db()
    return s


def fechar_abandonadas(agora=None, margem_minutos=10):
    """Sessões de voz ainda 'em_curso' muito depois do limite (separador fechado sem terminar/ e sem
    webhook): passam a esperar pelo Vapi. Devolve quantas."""
    from apps.practice.conversa import servico
    from .quota import obter_assinatura
    agora = agora or timezone.now()
    n = 0
    for s in VapiSession.objects.select_related('user').filter(mode='vapi', status=VapiSession.STATUS_EM_CURSO):
        fim = (s.started_at or s.created_at) + timedelta(seconds=(s.max_seconds or 0) + margem_minutos * 60)
        if fim > agora:
            continue
        with transaction.atomic():
            sub = obter_assinatura(s.user, bloquear=True)
            s = VapiSession.objects.select_for_update().select_related('user').get(pk=s.pk)
            if s.status != VapiSession.STATUS_EM_CURSO:
                continue
            servico._terminar_bloqueado(s, [], sub)
        servico.depois_de_fechar(s)
        n += 1
    return n


def pendentes():
    """Sessões de voz à espera da chamada verificada."""
    return (VapiSession.objects.filter(mode='vapi', status=VapiSession.STATUS_A_AVALIAR)
            .exclude(full_session_data__has_key='vapi_verificada'))
