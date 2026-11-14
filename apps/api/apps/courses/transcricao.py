"""
Transcrição automática do vídeo de uma aula (ffmpeg + Whisper).

Quando o professor carrega o vídeo (envios.confirmar) a aula fica 'pendente' e a transcrição corre
numa thread à parte (executar_em_fundo, como a avaliação da conversa no webhook do Vapi). O comando
`manage.py transcrever_aulas` (cron) apanha as que ficaram por fazer (processo reiniciado, erro).

Passos:
1. o ficheiro do vídeo: em MEDIA_ROOT (envios locais) ou descarregado do S3/CloudFront para um
   ficheiro temporário (no máximo TRANSCRICAO_MAX_BYTES); outros endereços não são descarregados;
2. ffprobe: a duração (preenche Chapter.duracao_s quando falta);
3. ffmpeg: só o áudio, mono, 16 kHz, MP3 a 32 kb/s, em pedaços de TRANSCRICAO_PEDACO_SEGUNDOS
   (10 min ~ 2.4 MB: sempre abaixo dos 25 MB que a OpenAI aceita);
4. Whisper (verbose_json, segmentos com tempos): os tempos de cada pedaço somam o início do pedaço;
5. Chapter.transcript = JSON [{start, end, text}] (o formato que o ecrã do aluno lê).

O estado fica em Chapter.metadata['transcricao']:
  {estado: pendente|a_processar|pronta|erro|manual, erro?, origem: whisper|professor|existente,
   video: URL transcrito, desde?, em?, segmentos?}
Uma transcrição escrita pelo professor ('manual') nunca é substituída sem ele pedir (forcar=True).
Se o vídeo mudar ou o professor escrever a transcrição durante o processamento, o resultado é
deitado fora.
Depois de uma transcrição nova, se a aula ainda não tem frases, o Claude propõe-nas
(frases_aula.propor); as frases que já existem ganham os tempos onde aparecem no vídeo.
"""
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PENDENTE, A_PROCESSAR, PRONTA, ERRO, MANUAL = 'pendente', 'a_processar', 'pronta', 'erro', 'manual'
ESTADOS = (PENDENTE, A_PROCESSAR, PRONTA, ERRO, MANUAL)
CHAVE = 'transcricao'
PRESA_DEPOIS = timedelta(hours=2)  # 'a_processar' há mais do que isto: o processo morreu a meio
TIMEOUT_FFMPEG = 1800
TIMEOUT_WHISPER = 300
BITRATE = '32k'
MAX_LINHAS = 3000
MAX_TEXTO_LINHA = 500


class ErroTranscricao(Exception):
    """Falha com uma mensagem para o professor (pt-PT, curta)."""


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

def _meta(chapter):
    return chapter.metadata if isinstance(chapter.metadata, dict) else {}


def estado_de(chapter):
    """O registo do estado (dict). Aulas antigas sem registo: 'manual' se já têm transcrição."""
    reg = _meta(chapter).get(CHAVE)
    if isinstance(reg, dict) and reg.get('estado') in ESTADOS:
        return reg
    if (chapter.transcript or '').strip():
        return {'estado': MANUAL, 'origem': 'existente'}
    return {'estado': PENDENTE if chapter.video else None}


def _gravar_estado(chapter_id, **campos):
    """Actualiza metadata['transcricao'] (com bloqueio da linha). Devolve o registo novo."""
    from apps.courses.models import Chapter
    with transaction.atomic():
        ch = Chapter.objects.select_for_update().get(pk=chapter_id)
        meta = dict(_meta(ch))
        reg = {k: v for k, v in campos.items() if v is not None}
        meta[CHAVE] = reg
        ch.metadata = meta
        ch.save(update_fields=['metadata'])
    return reg


def linhas(chapter):
    """As linhas da transcrição [{start, end, text}] (lista vazia se não há ou não é JSON)."""
    try:
        dados = json.loads(chapter.transcript or '[]')
    except (TypeError, ValueError):
        return []
    if not isinstance(dados, list):
        return []
    out = []
    for l in dados:
        if not isinstance(l, dict) or not isinstance(l.get('text'), str):
            continue
        try:
            start, end = float(l.get('start') or 0), float(l.get('end') or 0)
        except (TypeError, ValueError):
            continue
        out.append({'start': start, 'end': end, 'text': l['text']})
    return out


def limpar_linhas(brutas):
    """Valida as linhas que o professor envia. Devolve (linhas, erro)."""
    if not isinstance(brutas, list):
        return None, 'Envie as linhas da transcrição como uma lista.'
    if len(brutas) > MAX_LINHAS:
        return None, f'A transcrição pode ter no máximo {MAX_LINHAS} linhas.'
    out = []
    for i, l in enumerate(brutas, start=1):
        if not isinstance(l, dict):
            return None, f'Linha {i}: formato inválido.'
        texto = ' '.join(str(l.get('text') or '').split())[:MAX_TEXTO_LINHA]
        try:
            start = float(l.get('start'))
            end = float(l.get('end')) if l.get('end') not in (None, '') else start
        except (TypeError, ValueError):
            return None, f'Linha {i}: indique o tempo em segundos.'
        if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or start > 24 * 3600:
            return None, f'Linha {i}: tempo inválido.'
        if not texto:
            continue  # linhas vazias são tiradas
        out.append({'start': round(start, 2), 'end': round(max(end, start), 2), 'text': texto})
    out.sort(key=lambda l: l['start'])
    # Sem fim indicado (ou fim igual ao início): acaba onde começa a seguinte.
    for a, b in zip(out, out[1:]):
        if a['end'] <= a['start']:
            a['end'] = b['start']
    return out, None


def guardar_manual(chapter, linhas_limpas):
    """O professor escreveu/editou a transcrição: fica 'manual' (nunca é substituída sem ele pedir)."""
    chapter.transcript = json.dumps(linhas_limpas, ensure_ascii=False) if linhas_limpas else ''
    meta = dict(_meta(chapter))
    meta[CHAVE] = {'estado': MANUAL, 'origem': 'professor', 'video': chapter.video or None,
                   'em': timezone.now().isoformat()}
    chapter.metadata = meta
    chapter.save(update_fields=['transcript', 'metadata', 'updated_at'])
    relocalizar_frases(chapter)


# ---------------------------------------------------------------------------
# Agendar (pedido do professor / vídeo novo)
# ---------------------------------------------------------------------------

def executar_em_fundo(funcao, *args):
    """Corre numa thread à parte (sem fila de tarefas; o comando transcrever_aulas apanha o que se
    perder num reinício). Os testes substituem esta função para correr de imediato."""
    def correr():
        try:
            funcao(*args)
        except Exception:
            logger.exception('transcrição: falha em segundo plano')
        finally:
            close_old_connections()
    t = threading.Thread(target=correr, name='aula-transcrever', daemon=True)
    t.start()
    return t


def agendar(chapter, forcar=False, origem_pedido='video'):
    """
    Marca a aula como 'pendente' e, se TRANSCRICAO_AUTOMATICA (ou o professor pediu), corre a
    transcrição em segundo plano depois do commit. Uma transcrição manual só é substituída com forcar.
    Devolve o registo do estado.
    """
    actual = estado_de(chapter)
    if not chapter.video:
        return actual
    if actual.get('estado') == MANUAL and not forcar:
        return actual
    reg = _gravar_estado(chapter.pk, estado=PENDENTE, origem=actual.get('origem'), video=chapter.video,
                         desde=timezone.now().isoformat(), forcar=True if forcar else None)
    chapter.refresh_from_db(fields=['metadata'])
    if getattr(settings, 'TRANSCRICAO_AUTOMATICA', True) or origem_pedido == 'professor':
        pk = chapter.pk
        transaction.on_commit(lambda: executar_em_fundo(transcrever, pk, forcar))
    return reg


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe
# ---------------------------------------------------------------------------

def _binario(nome_setting, omissao):
    caminho = shutil.which(getattr(settings, nome_setting, omissao) or omissao)
    if not caminho:
        raise ErroTranscricao('O servidor não tem o ffmpeg instalado. Avise o suporte.')
    return caminho


def _correr(args, timeout=TIMEOUT_FFMPEG):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise ErroTranscricao('O vídeo demorou demasiado a processar.') from e
    if r.returncode != 0:
        logger.warning('transcrição: %s falhou: %s', os.path.basename(args[0]),
                       r.stderr.decode('utf-8', 'ignore')[-600:])
        raise ErroTranscricao('Não conseguimos ler o áudio deste vídeo. Confirme que o ficheiro abre e tem som.')
    return r.stdout.decode('utf-8', 'ignore')


def duracao(caminho):
    """Duração em segundos (ffprobe), ou None."""
    saida = _correr([_binario('FFPROBE_BIN', 'ffprobe'), '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', str(caminho)], timeout=120)
    try:
        d = float(saida.strip())
    except ValueError:
        return None
    return d if math.isfinite(d) and d > 0 else None


def extrair_audio(video, pasta, total, pedaco=None):
    """
    Áudio mono 16 kHz MP3 a 32 kb/s, em pedaços de `pedaco` segundos.
    Devolve [(caminho, inicio_em_segundos)].
    """
    ffmpeg = _binario('FFMPEG_BIN', 'ffmpeg')
    pedaco = pedaco or getattr(settings, 'TRANSCRICAO_PEDACO_SEGUNDOS', 600)
    n = max(1, math.ceil((total or pedaco) / pedaco))
    pedacos = []
    for i in range(n):
        inicio = i * pedaco
        destino = Path(pasta) / f'audio-{i:03d}.mp3'
        _correr([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(inicio), '-t', str(pedaco),
                 '-i', str(video), '-vn', '-ac', '1', '-ar', '16000', '-b:a', BITRATE, '-f', 'mp3', str(destino)])
        if destino.is_file() and destino.stat().st_size > 1024:
            pedacos.append((destino, float(inicio)))
    if not pedacos:
        raise ErroTranscricao('Este vídeo não tem som que se possa transcrever.')
    return pedacos


# ---------------------------------------------------------------------------
# O ficheiro do vídeo
# ---------------------------------------------------------------------------

def _caminho_media(url):
    """Ficheiro em MEDIA_ROOT para um URL de /media/... (envios locais), ou None."""
    caminho = unquote(urlparse(url).path)
    prefixo = settings.MEDIA_URL if settings.MEDIA_URL.startswith('/') else urlparse(settings.MEDIA_URL).path
    if not prefixo or not caminho.startswith(prefixo):
        return None
    raiz = Path(settings.MEDIA_ROOT).resolve()
    alvo = (raiz / caminho[len(prefixo):]).resolve()
    if raiz not in alvo.parents or not alvo.is_file():
        return None
    return alvo


def _url_permitido(url):
    """Só se descarrega do nosso armazenamento (S3/CloudFront): nada de URLs arbitrários."""
    from apps.courses.api.teacher.envios import _bases_s3
    return any(url.startswith(b) for b in _bases_s3())


def descarregar(url, pasta, maximo=None):
    import requests
    maximo = maximo or getattr(settings, 'TRANSCRICAO_MAX_BYTES', 2200 * 1024 * 1024)
    destino = Path(pasta) / 'video'
    recebidos = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120), allow_redirects=False) as r:
            if r.status_code != 200:
                raise ErroTranscricao('Não conseguimos descarregar o vídeo do armazenamento.')
            if int(r.headers.get('Content-Length') or 0) > maximo:
                raise ErroTranscricao('O vídeo é demasiado grande para transcrever automaticamente.')
            with open(destino, 'wb') as f:
                for bloco in r.iter_content(1024 * 1024):
                    recebidos += len(bloco)
                    if recebidos > maximo:
                        raise ErroTranscricao('O vídeo é demasiado grande para transcrever automaticamente.')
                    f.write(bloco)
    except requests.RequestException as e:
        raise ErroTranscricao('Não conseguimos descarregar o vídeo do armazenamento.') from e
    return destino


def ficheiro_do_video(url, pasta):
    local = _caminho_media(url)
    if local is not None:
        return local
    if url.startswith(('http://', 'https://')) and _url_permitido(url):
        return descarregar(url, pasta)
    raise ErroTranscricao('Este vídeo não está no armazenamento da ProEnglish: escreva a transcrição à mão.')


# ---------------------------------------------------------------------------
# Whisper
# ---------------------------------------------------------------------------

def _campo(obj, nome):
    return obj.get(nome) if isinstance(obj, dict) else getattr(obj, nome, None)


def whisper(caminho):
    """Segmentos [{start, end, text}] de um pedaço de áudio (tempos relativos ao pedaço)."""
    import openai
    chave = getattr(settings, 'OPENAI_API_KEY', '')
    if not chave or chave in ('dummy', 'sk-dummy'):
        raise ErroTranscricao('A transcrição automática não está configurada neste servidor.')
    cliente = openai.OpenAI(api_key=chave, timeout=TIMEOUT_WHISPER, max_retries=1)
    try:
        with open(caminho, 'rb') as f:
            r = cliente.audio.transcriptions.create(
                model=getattr(settings, 'TRANSCRICAO_MODELO', 'whisper-1'), file=f, language='en',
                response_format='verbose_json', timestamp_granularities=['segment'])
    except openai.OpenAIError as e:
        logger.warning('transcrição: Whisper falhou: %s', e)
        raise ErroTranscricao('O serviço de transcrição não respondeu. Tente outra vez daqui a pouco.') from e
    return [{'start': _campo(s, 'start'), 'end': _campo(s, 'end'), 'text': _campo(s, 'text')}
            for s in (_campo(r, 'segments') or [])]


def juntar_segmentos(por_pedaco):
    """[(inicio_do_pedaço, [segmentos])] -> linhas com os tempos do vídeo inteiro."""
    out = []
    for inicio, segmentos in por_pedaco:
        for s in segmentos:
            texto = ' '.join(str(s.get('text') or '').split())[:MAX_TEXTO_LINHA]
            try:
                a, b = float(s.get('start') or 0), float(s.get('end') or 0)
            except (TypeError, ValueError):
                continue
            if not texto:
                continue
            out.append({'start': round(inicio + a, 2), 'end': round(inicio + max(a, b), 2), 'text': texto})
    out.sort(key=lambda l: l['start'])
    return out[:MAX_LINHAS]


# ---------------------------------------------------------------------------
# Transcrever
# ---------------------------------------------------------------------------

def _reservar(chapter_id, forcar):
    """Passa a 'a_processar' se se pode transcrever agora. Devolve (chapter, video) ou (None, motivo)."""
    from apps.courses.models import Chapter
    with transaction.atomic():
        ch = Chapter.objects.select_for_update().filter(pk=chapter_id).first()
        if ch is None:
            return None, 'nao_existe'
        if not ch.video:
            return None, 'sem_video'
        reg = estado_de(ch)
        estado = reg.get('estado')
        forcar = forcar or bool(reg.get('forcar'))
        if estado == MANUAL and not forcar:
            return None, 'manual'
        if estado == PRONTA and reg.get('video') == ch.video and not forcar:
            return None, 'pronta'
        if estado == A_PROCESSAR:
            from django.utils.dateparse import parse_datetime
            desde = parse_datetime(str(reg.get('desde') or ''))
            if desde is not None and timezone.now() - desde < PRESA_DEPOIS:
                return None, 'a_processar'
        meta = dict(_meta(ch))
        meta[CHAVE] = {'estado': A_PROCESSAR, 'origem': 'whisper', 'video': ch.video,
                       'desde': timezone.now().isoformat()}
        ch.metadata = meta
        ch.save(update_fields=['metadata'])
        return ch, ch.video


def transcrever(chapter_id, forcar=False):
    """
    Transcreve o vídeo da aula (síncrono). Devolve o estado final ('pronta', 'erro') ou o motivo
    por que não fez nada ('manual', 'pronta', 'a_processar', 'sem_video', 'nao_existe', 'mudou').
    """
    from apps.courses.models import Chapter

    ch, video = _reservar(chapter_id, forcar)
    if ch is None:
        return video
    try:
        with tempfile.TemporaryDirectory(prefix='aula-') as pasta:
            ficheiro = ficheiro_do_video(video, pasta)
            total = duracao(ficheiro)
            pedacos = extrair_audio(ficheiro, pasta, total)
            por_pedaco = [(inicio, whisper(caminho)) for caminho, inicio in pedacos]
        resultado = juntar_segmentos(por_pedaco)
        if not resultado:
            raise ErroTranscricao('Não ouvimos fala neste vídeo.')
    except ErroTranscricao as e:
        _falhou(chapter_id, video, str(e))
        return ERRO
    except Exception:
        logger.exception('transcrição: falha inesperada na aula %s', chapter_id)
        _falhou(chapter_id, video, 'Não foi possível transcrever o vídeo. Tente outra vez.')
        return ERRO

    with transaction.atomic():
        ch = Chapter.objects.select_for_update().get(pk=chapter_id)
        reg = estado_de(ch)
        if ch.video != video or reg.get('estado') != A_PROCESSAR:
            # O professor trocou o vídeo ou escreveu a transcrição entretanto: este resultado já não vale.
            return 'mudou'
        ch.transcript = json.dumps(resultado, ensure_ascii=False)
        campos = ['transcript', 'metadata']
        if not ch.duracao_s and total:
            ch.duracao_s = int(round(total))
            campos.append('duracao_s')
        meta = dict(_meta(ch))
        meta[CHAVE] = {'estado': PRONTA, 'origem': 'whisper', 'video': video, 'em': timezone.now().isoformat(),
                       'segmentos': len(resultado),
                       'modelo': getattr(settings, 'TRANSCRICAO_MODELO', 'whisper-1')}
        ch.metadata = meta
        ch.save(update_fields=campos + ['updated_at'])
    depois_da_transcricao(ch)
    return PRONTA


def _falhou(chapter_id, video, mensagem):
    from apps.courses.models import Chapter
    with transaction.atomic():
        ch = Chapter.objects.select_for_update().filter(pk=chapter_id).first()
        if ch is None or ch.video != video or estado_de(ch).get('estado') != A_PROCESSAR:
            return
        meta = dict(_meta(ch))
        meta[CHAVE] = {'estado': ERRO, 'origem': 'whisper', 'video': video, 'erro': mensagem[:300],
                       'em': timezone.now().isoformat()}
        ch.metadata = meta
        ch.save(update_fields=['metadata'])


def depois_da_transcricao(chapter):
    """Frases que já existem ganham os tempos; sem frases nenhumas, o Claude propõe-nas."""
    from apps.courses import frases_aula
    try:
        relocalizar_frases(chapter)
        if not chapter.frases_aula.exists():
            frases_aula.propor_e_registar(chapter)
    except Exception:
        logger.exception('transcrição: falha nas frases da aula %s', chapter.pk)


def relocalizar_frases(chapter):
    """Procura cada frase da aula na transcrição e actualiza inicio/fim (sem transcrição: não mexe)."""
    from apps.courses import frases_aula
    segs = linhas(chapter)
    if not segs:
        return 0
    n = 0
    for f in chapter.frases_aula.all():
        inicio, fim = frases_aula.localizar(f.texto, segs)
        if inicio is not None and (inicio, fim) != (f.inicio, f.fim):
            f.inicio, f.fim = inicio, fim
            f.save(update_fields=['inicio', 'fim', 'actualizada_em'])
            n += 1
    return n


def pendentes(incluir_erros=False):
    """Aulas com vídeo à espera de transcrição (para o comando transcrever_aulas)."""
    from apps.courses.models import Chapter
    from django.utils.dateparse import parse_datetime
    agora = timezone.now()
    out = []
    for ch in Chapter.objects.exclude(video='').only('id', 'video', 'transcript', 'metadata').iterator():
        reg = estado_de(ch)
        estado = reg.get('estado')
        if estado == PENDENTE or (estado == ERRO and incluir_erros):
            out.append(ch.pk)
        elif estado == PRONTA and reg.get('video') != ch.video:
            out.append(ch.pk)  # vídeo trocado sem passar pelo envio (admin, scripts)
        elif estado == A_PROCESSAR:
            desde = parse_datetime(str(reg.get('desde') or ''))
            if desde is None or agora - desde >= PRESA_DEPOIS:
                out.append(ch.pk)
    return out


def estado_para_ecra(chapter):
    """O que o editor do professor mostra."""
    reg = estado_de(chapter)
    return {
        'estado': reg.get('estado'),
        'erro': reg.get('erro') or None,
        'origem': reg.get('origem') or None,
        'em': reg.get('em') or None,
        'desde': reg.get('desde') or None,
        'video_mudou': bool(reg.get('estado') == MANUAL and reg.get('video') and chapter.video
                            and reg.get('video') != chapter.video),
    }
