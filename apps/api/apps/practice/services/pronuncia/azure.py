"""
Azure Speech: avaliação de pronúncia detalhada (nota por palavra e por som), pela REST API
"speech to text for short audio".

Verificado na documentação da Microsoft (learn.microsoft.com, rest-speech-to-text-short e
how-to-pronunciation-assessment, consultadas em 2026-11):
- POST https://<região>.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1
  ?language=en-US&format=detailed  (ou o endpoint do recurso:
  https://<recurso>.cognitiveservices.azure.com/stt/speech/recognition/conversation/cognitiveservices/v1)
- cabeçalhos: Ocp-Apim-Subscription-Key, Accept: application/json,
  Content-Type 'audio/wav; codecs=audio/pcm; samplerate=16000' (ou 'audio/ogg; codecs=opus');
  áudio WAV PCM 16 kHz mono; no máximo 30 s para avaliação de pronúncia (60 s para só transcrever).
- Pronunciation-Assessment: JSON em base64 com ReferenceText (OBRIGATÓRIO nesta API),
  GradingSystem 'HundredMark', Granularity 'Phoneme', Dimension 'Comprehensive',
  EnableProsodyAssessment 'True' (prosódia só em en-US).
- resposta: RecognitionStatus 'Success' | 'NoMatch' | 'InitialSilenceTimeout' | 'BabbleTimeout' | 'Error';
  NBest[0] com AccuracyScore, FluencyScore, CompletenessScore, ProsodyScore, PronScore e Words
  [{Word, Offset, Duration (unidades de 100 ns), AccuracyScore, ErrorType, Phonemes[...]}].
  A REST API devolve as notas directamente no objecto; os exemplos do SDK põem-nas dentro de
  'PronunciationAssessment': aceitam-se as duas formas.

Modo 'livre' (fala espontânea): a REST API para áudio curto exige ReferenceText. Sem texto, levanta
ErroProvedor (TODO: "unscripted" só pelo Speech SDK ou WebSocket) e a avaliação é a normal, pelo
texto. Com o texto do que o aluno DISSE (a transcrição confirmada da fala, como no exame oral:
conversa/exame.py) avalia-se contra esse texto, sem EnableMiscue (não há guião a cumprir: palavras
a mais ou a menos não são erros de pronúncia); a nota útil é a exactidão (AccuracyScore).

A chave nunca vai para os registos (só o código HTTP e o tipo de erro).
"""
import base64
import io
import json
import logging
import shutil
import subprocess
import wave

import requests
from django.conf import settings

from apps.practice.services.transcricao_fala import Transcricao

from .base import NOTA_ACEITE, ErroProvedor, Provedor, ResultadoPronuncia, credito_de

logger = logging.getLogger(__name__)

# Curtos: a avaliação detalhada vem antes do Whisper + Claude e o pedido todo tem de caber nos
# ~45 s do orçamento (services/pronuncia.ORCAMENTO_SEGUNDOS), abaixo dos 60 s do nginx.
TIMEOUT = 8
TIMEOUT_FFMPEG = 5
MAX_SEGUNDOS = 30
TICKS_POR_SEGUNDO = 10_000_000
MAX_BYTES_WAV = 16000 * 2 * MAX_SEGUNDOS + 44   # 16 kHz, 16 bits, mono, 30 s
ERROS_PALAVRA = ('Mispronunciation', 'Omission')

# Sons difíceis para quem fala português: dica curta em pt-PT (o som em IPA vem do Azure).
DICAS_FONEMA = {
    'θ': 'ponha a ponta da língua entre os dentes e sopre (como em "think")',
    'ð': 'língua entre os dentes, com voz (como em "this")',
    'ɪ': 'um "i" curto e relaxado (como em "ship", não "sheep")',
    'i': 'um "i" longo (como em "sheep")',
    'æ': 'abra bem a boca, entre "a" e "é" (como em "cat")',
    'ʌ': 'um "a" curto e fechado (como em "cup")',
    'ə': 'um som neutro e fraco (como no fim de "doctor")',
    'h': 'sopre o ar, o "h" inglês ouve-se (como em "house")',
    'ɹ': 'o "r" inglês: a língua não toca no céu da boca',
    'r': 'o "r" inglês: a língua não toca no céu da boca',
    'ŋ': 'o "ng" no fim, sem dizer o "g" (como em "sing")',
    'v': 'dentes de cima no lábio de baixo, com voz',
    'z': 'um "z" com voz, mesmo no fim da palavra',
    'ʃ': 'como o "ch" de "chave"',
    'tʃ': 'um "t" seguido de "ch" (como em "check")',
    'dʒ': 'um "d" seguido de "j" (como em "job")',
    'w': 'lábios em bico, como um "u" rápido',
    'oʊ': 'um "ou" que desliza (como em "go")',
    'eɪ': 'um "ei" que desliza (como em "day")',
}


def configurado():
    return bool((getattr(settings, 'AZURE_SPEECH_KEY', '') or '').strip()
                and ((getattr(settings, 'AZURE_SPEECH_REGION', '') or '').strip()
                     or (getattr(settings, 'AZURE_SPEECH_ENDPOINT', '') or '').strip()))


def url_reconhecimento(idioma='en-US'):
    endpoint = (getattr(settings, 'AZURE_SPEECH_ENDPOINT', '') or '').strip().rstrip('/')
    if endpoint:
        base = f'{endpoint}/stt/speech/recognition/conversation/cognitiveservices/v1'
    else:
        regiao = settings.AZURE_SPEECH_REGION.strip()
        base = f'https://{regiao}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1'
    return f'{base}?language={idioma}&format=detailed'


def cabecalho_avaliacao(texto_esperado, idioma='en-US', miscue=True):
    params = {
        'ReferenceText': texto_esperado,
        'GradingSystem': 'HundredMark',
        'Granularity': 'Phoneme',
        'Dimension': 'Comprehensive',
        'EnableMiscue': 'True' if miscue else 'False',
    }
    if idioma == 'en-US':  # prosódia só existe em en-US
        params['EnableProsodyAssessment'] = 'True'
    return base64.b64encode(json.dumps(params, ensure_ascii=False).encode('utf-8')).decode('ascii')


def para_wav(audio_bytes, mime=''):
    """
    Qualquer gravação do browser (webm/opus, ogg, mp4) -> WAV PCM 16 kHz mono.

    O ffmpeg dá só as amostras (s16le, sem cabeçalho) e o cabeçalho WAV é escrito aqui com os
    tamanhos certos: um WAV escrito pelo ffmpeg para um pipe não pode voltar atrás para os
    preencher (fica com tamanhos inválidos/0xFFFFFFFF) nem leva metadados que não pedimos.
    """
    if (mime or '').startswith('audio/wav') and audio_bytes[:4] == b'RIFF':
        return audio_bytes
    ffmpeg = shutil.which(getattr(settings, 'FFMPEG_BIN', 'ffmpeg') or 'ffmpeg')
    if not ffmpeg:
        raise ErroProvedor('ffmpeg em falta')
    try:
        r = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', 'pipe:0', '-t', str(MAX_SEGUNDOS + 1),
                            '-map_metadata', '-1', '-vn', '-ac', '1', '-ar', '16000', '-acodec', 'pcm_s16le',
                            '-f', 's16le', 'pipe:1'],
                           input=audio_bytes, capture_output=True, timeout=TIMEOUT_FFMPEG, check=False)
    except subprocess.TimeoutExpired as e:
        raise ErroProvedor('ffmpeg demorou demasiado') from e
    if r.returncode != 0:
        raise ErroProvedor('ffmpeg não converteu a gravação')
    return pcm_para_wav(r.stdout or b'')


def pcm_para_wav(pcm):
    """Amostras s16le, 16 kHz, mono (saída do ffmpeg) -> WAV com o cabeçalho certo."""
    if len(pcm) < 320:  # menos de 10 ms de som
        raise ErroProvedor('ffmpeg não converteu a gravação')
    if len(pcm) % 2:
        pcm = pcm[:-1]
    saida = io.BytesIO()
    with wave.open(saida, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return saida.getvalue()


def _pa(obj, chave):
    """Nota na forma da REST API (no próprio objecto) ou do SDK (dentro de PronunciationAssessment)."""
    if not isinstance(obj, dict):
        return None
    v = obj.get(chave)
    if v is None and isinstance(obj.get('PronunciationAssessment'), dict):
        v = obj['PronunciationAssessment'].get(chave)
    return v


def _nota(v):
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


def dica_de(palavra):
    """'think: o som /θ/ — ponha a ponta da língua...' para a palavra com o pior som, ou None."""
    fonemas = [f for f in palavra.get('fonemas') or [] if f.get('nota') is not None]
    if not fonemas:
        return None
    pior = min(fonemas, key=lambda f: f['nota'])
    if pior['nota'] >= NOTA_ACEITE:
        return None
    som = pior['fonema']
    dica = DICAS_FONEMA.get(som)
    base = f'«{palavra["palavra"]}»: o som /{som}/'
    return f'{base} — {dica}.' if dica else f'{base} ainda não sai bem. Ouça o modelo e repita devagar.'


def interpretar(dados, texto_esperado):
    """Resposta JSON do Azure -> ResultadoPronuncia. Levanta ErroProvedor se não houve reconhecimento."""
    if not isinstance(dados, dict):
        raise ErroProvedor('resposta inválida')
    estado = dados.get('RecognitionStatus')
    if estado not in ('Success', 0):
        raise ErroProvedor(f'reconhecimento: {estado}')
    nbest = dados.get('NBest') if isinstance(dados.get('NBest'), list) else []
    if not nbest or not isinstance(nbest[0], dict):
        raise ErroProvedor('resposta sem NBest')
    nb = nbest[0]
    exactidao = _nota(_pa(nb, 'AccuracyScore'))
    fluencia = _nota(_pa(nb, 'FluencyScore'))
    completude = _nota(_pa(nb, 'CompletenessScore'))
    prosodia = _nota(_pa(nb, 'ProsodyScore'))
    geral = _nota(_pa(nb, 'PronScore'))
    if geral is None:
        valores = [v for v in (exactidao, fluencia, completude) if v is not None]
        geral = round(sum(valores) / len(valores)) if valores else None
    if geral is None:
        raise ErroProvedor('resposta sem notas')

    palavras, tempos = [], []
    for w in nb.get('Words') or []:
        if not isinstance(w, dict) or not w.get('Word'):
            continue
        erro = str(_pa(w, 'ErrorType') or 'None')
        fonemas = [{'fonema': str(f.get('Phoneme') or '')[:10], 'nota': _nota(_pa(f, 'AccuracyScore'))}
                   for f in w.get('Phonemes') or [] if isinstance(f, dict) and f.get('Phoneme')]
        nota = _nota(_pa(w, 'AccuracyScore'))
        if erro == 'Omission':
            nota = 0
        palavras.append({'palavra': str(w['Word'])[:40], 'nota': nota, 'erro_tipo': erro, 'fonemas': fonemas[:20]})
        ini, dur = w.get('Offset'), w.get('Duration')
        if erro != 'Omission' and isinstance(ini, (int, float)) and isinstance(dur, (int, float)):
            tempos.append({'palavra': str(w['Word'])[:60], 'inicio': round(ini / TICKS_POR_SEGUNDO, 2),
                           'fim': round((ini + dur) / TICKS_POR_SEGUNDO, 2)})
    palavras = palavras[:80]
    problematicas = [p['palavra'] for p in palavras
                     if (p['nota'] is not None and p['nota'] < NOTA_ACEITE) or p['erro_tipo'] in ERROS_PALAVRA]
    pior = min((p for p in palavras if p['nota'] is not None and p['erro_tipo'] != 'Omission'),
               key=lambda p: p['nota'], default=None)
    dica = dica_de(pior) if pior else None
    aceite = geral >= NOTA_ACEITE
    if aceite and not problematicas:
        mensagem = 'Muito bem: todas as palavras saíram claras.' if geral >= 80 else 'Bem dito. Continue a treinar o ritmo.'
    elif aceite:
        mensagem = f'Bem dito. Ainda pode melhorar: {", ".join(problematicas[:3])}.'
    else:
        mensagem = (f'Ainda não. Treine: {", ".join(problematicas[:3])}.' if problematicas
                    else 'Ainda não. Ouça o modelo e repita mais devagar.')
    texto = str(nb.get('Display') or nb.get('Lexical') or dados.get('DisplayText') or '')[:2000]
    duracao = dados.get('Duration')
    return ResultadoPronuncia(
        nota=geral, fluencia=fluencia, completude=completude, prosodia=prosodia, palavras=palavras,
        fonte='azure', transcricao=texto, texto_esperado=texto_esperado, aceite=aceite, mensagem=mensagem,
        sugestoes=[dica] if dica else [], palavras_problematicas=problematicas[:10],
        nota_pronuncia=exactidao if exactidao is not None else geral,
        nota_clareza=exactidao if exactidao is not None else geral,
        credito=credito_de(geral), confianca=nb.get('Confidence') if isinstance(nb.get('Confidence'), (int, float)) else 0.9,
        tempos=Transcricao(texto=texto, palavras=tempos,
                           duracao=(duracao / TICKS_POR_SEGUNDO) if isinstance(duracao, (int, float)) else None,
                           fonte='azure'),
        detalhada=True,
    )


class ProvedorAzure(Provedor):
    nome = 'azure'

    def avaliar(self, audio_bytes, mime, texto_esperado=None, idioma='en-US', modo='lido', nivel='intermediate',
                nome=None):
        if not configurado():
            raise ErroProvedor('Azure Speech não configurado')
        if not (texto_esperado or '').strip():
            # TODO(fase 3, etapa 2): avaliação livre ("unscripted") pelo Speech SDK; a REST API exige ReferenceText.
            raise ErroProvedor('avaliação livre não suportada pela REST API para áudio curto')
        wav = para_wav(audio_bytes, mime)
        if len(wav) > MAX_BYTES_WAV:
            raise ErroProvedor('gravação com mais de 30 s')
        try:
            r = requests.post(
                url_reconhecimento(idioma), data=wav, timeout=TIMEOUT,
                headers={
                    'Ocp-Apim-Subscription-Key': settings.AZURE_SPEECH_KEY.strip(),
                    'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
                    'Accept': 'application/json',
                    'Pronunciation-Assessment': cabecalho_avaliacao(texto_esperado.strip()[:1000], idioma,
                                                                    miscue=(modo != 'livre')),
                })
        except requests.RequestException as e:
            raise ErroProvedor(f'rede: {type(e).__name__}') from e
        if r.status_code != 200:
            raise ErroProvedor(f'HTTP {r.status_code}')
        try:
            dados = r.json()
        except ValueError as e:
            raise ErroProvedor('resposta não é JSON') from e
        return interpretar(dados, texto_esperado)
