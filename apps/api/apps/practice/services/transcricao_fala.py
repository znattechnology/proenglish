"""
Fala -> texto (speech-to-text) atrás de uma interface única, independente do fornecedor.

    transcrever(audio_bytes, mime='audio/webm', idioma='en', palavras=True) -> Transcricao

Transcricao: texto, palavras [{palavra, inicio, fim}] (segundos desde o início da gravação),
segmentos [{inicio, fim, texto}], duracao (segundos da gravação, ou None) e fonte (o adaptador).
Levanta ErroTranscricao quando o serviço falha (rede, chave, quota); devolve texto '' quando
não houve fala.

Todos os pontos que transcrevem a fala dos alunos passam por aqui (exercício de pronúncia,
Responder, revisão, repetir frases da aula) e as métricas de fluência (services/metricas_fala.py)
lêem os tempos das palavras daqui. Para mudar de fornecedor (Azure Speech, Whisper alojado por
nós, ...) basta outro adaptador e a variável TRANSCRICAO_FALA_PROVEDOR; nenhum chamador muda.

Adaptadores:
- 'openai': OpenAI Whisper (whisper-1) com response_format=verbose_json e
  timestamp_granularities=['word', 'segment']. Se o SDK ou o modelo não aceitarem os tempos,
  repete-se o pedido só com texto (as métricas passam a ser estimadas).
"""
import io
import logging
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Os pedidos com gravações têm de acabar antes dos 60 s do nginx (e o Claude ainda vem depois):
# um pedido ao Whisper, sem repetições automáticas.
TIMEOUT = 20
MAX_RETRIES = 0
MAX_PALAVRAS = 400
# Respostas do fornecedor que querem dizer "esta gravação não serve" (formato, ficheiro estragado,
# demasiado grande): grava-se outra vez. Tudo o resto (rede, timeout, 5xx, 401, 429, chave em
# falta) é o serviço indisponível.
ESTADOS_AUDIO_INVALIDO = (400, 413, 415, 422)


class ErroTranscricao(Exception):
    """
    A transcrição falhou. audio_invalido=False: o serviço falhou (não é culpa do aluno; 503 e pode
    saltar). audio_invalido=True: o fornecedor recusou a gravação (grava-se outra vez; 422).
    """

    def __init__(self, mensagem='', audio_invalido=False):
        super().__init__(mensagem)
        self.audio_invalido = audio_invalido


def _erro_do_fornecedor(e):
    estado = getattr(e, 'status_code', None)
    return ErroTranscricao(f'whisper: {type(e).__name__}', audio_invalido=estado in ESTADOS_AUDIO_INVALIDO)


@dataclass
class Transcricao:
    texto: str = ''
    palavras: List[dict] = field(default_factory=list)   # [{palavra, inicio, fim}]
    segmentos: List[dict] = field(default_factory=list)  # [{inicio, fim, texto}]
    duracao: Optional[float] = None
    fonte: str = ''

    def como_dict(self):
        return {'texto': self.texto, 'palavras': self.palavras, 'segmentos': self.segmentos,
                'duracao': self.duracao, 'fonte': self.fonte}


def _campo(obj, nome):
    return obj.get(nome) if isinstance(obj, dict) else getattr(obj, nome, None)


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f >= 0 else None


def limpar_palavras(lista):
    """[{palavra|word, inicio|start, fim|end}] -> lista limpa, por ordem, sem tempos impossíveis."""
    out = []
    for p in lista or []:
        texto = _campo(p, 'palavra') or _campo(p, 'word')
        ini = _num(_campo(p, 'inicio') if _campo(p, 'inicio') is not None else _campo(p, 'start'))
        fim = _num(_campo(p, 'fim') if _campo(p, 'fim') is not None else _campo(p, 'end'))
        texto = ' '.join(str(texto or '').split())
        if not texto or ini is None or fim is None or fim < ini:
            continue
        out.append({'palavra': texto[:60], 'inicio': round(ini, 2), 'fim': round(fim, 2)})
    out.sort(key=lambda p: p['inicio'])
    return out[:MAX_PALAVRAS]


def _limpar_segmentos(lista):
    out = []
    for s in lista or []:
        ini, fim = _num(_campo(s, 'start')), _num(_campo(s, 'end'))
        texto = ' '.join(str(_campo(s, 'text') or '').split())
        if ini is None or fim is None or not texto:
            continue
        out.append({'inicio': round(ini, 2), 'fim': round(max(ini, fim), 2), 'texto': texto[:500]})
    return out[:100]


def _extensao(mime, nome=None):
    if nome and '.' in str(nome):
        return str(nome).rsplit('.', 1)[-1].lower()[:5]
    m = (mime or '').lower()
    for chave, ext in (('webm', 'webm'), ('ogg', 'ogg'), ('wav', 'wav'), ('mp4', 'm4a'), ('m4a', 'm4a'),
                       ('mpeg', 'mp3'), ('mp3', 'mp3')):
        if chave in m:
            return ext
    return 'webm'


# ---------------------------------------------------------------------------
# Adaptadores
# ---------------------------------------------------------------------------

class Adaptador:
    nome = 'base'

    def transcrever(self, audio_bytes, mime, idioma, palavras):  # pragma: no cover - interface
        raise NotImplementedError


class WhisperOpenAI(Adaptador):
    """OpenAI Whisper. A chave fica em settings.OPENAI_API_KEY (nunca vai para os registos)."""
    nome = 'openai_whisper'

    def __init__(self, cliente=None):
        self._cliente = cliente

    def cliente(self):
        if self._cliente is None:
            import openai
            chave = getattr(settings, 'OPENAI_API_KEY', '')
            if not chave or chave in ('dummy', 'sk-dummy'):
                raise ErroTranscricao('transcrição sem chave configurada')
            self._cliente = openai.OpenAI(api_key=chave, timeout=TIMEOUT, max_retries=MAX_RETRIES)
        return self._cliente

    def transcrever(self, audio_bytes, mime, idioma, palavras, nome=None):
        ficheiro = io.BytesIO(audio_bytes)
        ficheiro.name = nome or f'gravacao.{_extensao(mime)}'
        modelo = getattr(settings, 'TRANSCRICAO_FALA_MODELO', None) or 'whisper-1'
        try:
            cliente = self.cliente()
        except ErroTranscricao:
            raise
        except Exception as e:
            raise ErroTranscricao(f'whisper: {type(e).__name__}') from e
        kwargs = {'model': modelo, 'file': ficheiro}
        if idioma:
            kwargs['language'] = idioma.split('-')[0]
        if palavras:
            try:
                r = cliente.audio.transcriptions.create(
                    response_format='verbose_json', timestamp_granularities=['word', 'segment'], **kwargs)
                return Transcricao(
                    texto=' '.join(str(_campo(r, 'text') or '').split())[:2000],
                    palavras=limpar_palavras(_campo(r, 'words')),
                    segmentos=_limpar_segmentos(_campo(r, 'segments')),
                    duracao=_num(_campo(r, 'duration')),
                    fonte=self.nome,
                )
            except TypeError:
                # SDK antigo sem timestamp_granularities: só texto (métricas estimadas).
                logger.info('transcrição: SDK sem tempos por palavra; a pedir só o texto')
                ficheiro.seek(0)
            except Exception as e:
                if not _pedido_invalido(e):
                    raise _erro_do_fornecedor(e) from e
                logger.info('transcrição: o modelo %s não devolve tempos; a pedir só o texto', modelo)
                ficheiro.seek(0)
        try:
            texto = cliente.audio.transcriptions.create(response_format='text', **kwargs)
        except Exception as e:
            raise _erro_do_fornecedor(e) from e
        texto = texto if isinstance(texto, str) else (_campo(texto, 'text') or '')
        return Transcricao(texto=' '.join(str(texto).split())[:2000], fonte=self.nome)


def _pedido_invalido(e):
    """400 do fornecedor (p.ex. um modelo que não aceita verbose_json): vale a pena repetir só com texto."""
    return getattr(e, 'status_code', None) == 400


ADAPTADORES = {'openai': WhisperOpenAI}


def adaptador():
    nome = (getattr(settings, 'TRANSCRICAO_FALA_PROVEDOR', None) or 'openai').strip().lower()
    classe = ADAPTADORES.get(nome)
    if classe is None:
        logger.warning('transcrição: fornecedor desconhecido %r; a usar openai', nome)
        classe = WhisperOpenAI
    return classe()


def transcrever(audio_bytes, mime='audio/webm', idioma='en', palavras=True, nome=None):
    """A fala transcrita (ver o topo do módulo). Levanta ErroTranscricao em falha técnica."""
    if isinstance(audio_bytes, io.BytesIO):
        nome = nome or getattr(audio_bytes, 'name', None)
        audio_bytes = audio_bytes.getvalue()
    a = adaptador()
    try:
        return a.transcrever(audio_bytes, mime, idioma, palavras, nome=nome)
    except TypeError:
        return a.transcrever(audio_bytes, mime, idioma, palavras)


# ---------------------------------------------------------------------------
# Duração da gravação (ffprobe), quando o fornecedor não a dá
# ---------------------------------------------------------------------------

def duracao_audio(audio_bytes, mime='audio/webm', timeout=10):
    """Segundos da gravação (ffprobe), ou None se não for possível medir."""
    if not audio_bytes:
        return None
    ffprobe = shutil.which(getattr(settings, 'FFPROBE_BIN', 'ffprobe') or 'ffprobe')
    if not ffprobe:
        return None
    caminho = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.' + _extensao(mime), delete=False) as f:
            f.write(audio_bytes)
            caminho = f.name
        r = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'default=noprint_wrappers=1:nokey=1', caminho],
                           capture_output=True, timeout=timeout, check=False)
        if r.returncode != 0:
            return None
        return _num(r.stdout.decode('utf-8', 'ignore').strip())
    except Exception:
        return None
    finally:
        if caminho:
            try:
                os.unlink(caminho)
            except OSError:
                pass
