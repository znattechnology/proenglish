"""
Métricas de fluência de uma gravação, a partir dos tempos das palavras (transcricao_fala).

Definições (todas em segundos):
- palavras: número de palavras ditas (com tempos; sem tempos, contadas no texto).
- duração da fala ("span"): do início da primeira palavra ao fim da última.
- pausa: o intervalo entre o fim mais tardio das palavras anteriores e o início da seguinte.
  Pausa longa: mais de PAUSA_LONGA (1,0 s).
- segundos_fala: o span MENOS a duração das pausas longas, i.e. o tempo em que o aluno esteve
  realmente a falar. É o que soma nos "minutos a falar" do dia (FalaDiaria).
- ppm (palavras por minuto): palavras / span, em minutos. Inclui as pausas (curtas e longas):
  quem pára muito fala menos palavras por minuto. Só se calcula com pelo menos MIN_PALAVRAS_PPM
  palavras e MIN_SPAN_PPM s de span; abaixo disso (uma palavra solta) não diz nada: None.
- pausas_longas: quantas; pausas_longas_s: soma; maior_pausa_s: o maior intervalo entre palavras.
- fonte_tempo: 'medido' (tempos por palavra) ou 'estimado'.

Sem tempos por palavra (adaptador sem tempos, modo simulado): estimado. segundos_fala =
palavras / PALAVRAS_POR_SEGUNDO (2,3), limitado à duração da gravação quando se conhece; ppm só se
a duração da gravação for conhecida (palavras / duração), e as pausas ficam None (não se inventam).
"""
import re

PAUSA_LONGA = 1.0
PALAVRAS_POR_SEGUNDO = 2.3
MIN_PALAVRAS_PPM = 3
MIN_SPAN_PPM = 1.0
MAX_TEMPOS_GUARDADOS = 120

_PALAVRA = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")


def contar_palavras(texto):
    return len(_PALAVRA.findall(str(texto or '')))


def _r(v, casas=2):
    return None if v is None else round(float(v), casas)


def metricas_de_palavras(palavras, texto='', duracao_audio=None):
    """Dicionário com os campos de TentativaPronuncia (ver o topo). Nunca levanta excepção."""
    palavras = [p for p in (palavras or []) if isinstance(p, dict)
                and isinstance(p.get('inicio'), (int, float)) and isinstance(p.get('fim'), (int, float))]
    if palavras:
        palavras = sorted(palavras, key=lambda p: p['inicio'])
        n = len(palavras)
        span = max(0.0, max(p['fim'] for p in palavras) - palavras[0]['inicio'])
        # Pausa = o silêncio antes de cada palavra: o início dela menos o fim MAIS TARDIO de todas
        # as anteriores (as palavras podem sobrepor-se; uma palavra longa cobre as seguintes).
        pausas, fim_ate_agora = [], palavras[0]['fim']
        for p in palavras[1:]:
            pausas.append(max(0.0, p['inicio'] - fim_ate_agora))
            fim_ate_agora = max(fim_ate_agora, p['fim'])
        longas = [p for p in pausas if p > PAUSA_LONGA]
        segundos = max(0.0, span - sum(longas))
        ppm = (n / (span / 60.0)) if n >= MIN_PALAVRAS_PPM and span >= MIN_SPAN_PPM else None
        return {
            'segundos_fala': _r(segundos),
            'palavras_ditas': n,
            'ppm': _r(ppm, 1),
            'pausas_longas': len(longas),
            'pausas_longas_s': _r(sum(longas)),
            'maior_pausa_s': _r(max(pausas) if pausas else 0.0),
            'fonte_tempo': 'medido',
            'tempos_palavras': [[p['palavra'][:40], _r(p['inicio']), _r(p['fim'])]
                                for p in palavras[:MAX_TEMPOS_GUARDADOS]],
        }
    n = contar_palavras(texto)
    if not n:
        return {'segundos_fala': None, 'palavras_ditas': 0 if texto is not None else None, 'ppm': None,
                'pausas_longas': None, 'pausas_longas_s': None, 'maior_pausa_s': None,
                'fonte_tempo': '', 'tempos_palavras': None}
    segundos = n / PALAVRAS_POR_SEGUNDO
    dur = duracao_audio if isinstance(duracao_audio, (int, float)) and duracao_audio > 0 else None
    if dur is not None:
        segundos = min(segundos, dur)
    ppm = (n / (dur / 60.0)) if dur is not None and n >= MIN_PALAVRAS_PPM and dur >= MIN_SPAN_PPM else None
    return {
        'segundos_fala': _r(segundos),
        'palavras_ditas': n,
        'ppm': _r(ppm, 1),
        'pausas_longas': None,
        'pausas_longas_s': None,
        'maior_pausa_s': None,
        'fonte_tempo': 'estimado',
        'tempos_palavras': None,
    }


def metricas_de_transcricao(t, texto=None):
    """Métricas a partir de um objecto Transcricao (ou de algo parecido), ou só do texto."""
    if t is None:
        return metricas_de_palavras([], texto or '')
    return metricas_de_palavras(getattr(t, 'palavras', None) or [],
                                texto if texto is not None else getattr(t, 'texto', ''),
                                getattr(t, 'duracao', None))


CAMPOS = ('segundos_fala', 'palavras_ditas', 'ppm', 'pausas_longas', 'pausas_longas_s', 'maior_pausa_s',
          'fonte_tempo', 'tempos_palavras')


def resumo_publico(m):
    """O que vai para o ecrã (sem a lista de tempos)."""
    if not m or m.get('segundos_fala') is None:
        return None
    return {k: m.get(k) for k in CAMPOS if k != 'tempos_palavras'}


# ---------------------------------------------------------------------------
# Correspondência de palavras (avaliação de pronúncia só pelo texto)
# ---------------------------------------------------------------------------
# Sem a avaliação detalhada (Azure) só temos o que a transcrição ouviu. A nota honesta é quantas
# palavras da frase esperada foram reconhecidas, por ordem (palavras em falta, trocadas ou a mais
# baixam a nota). Não mede fluência nem clareza: a transcrição normaliza o que o aluno disse.
# Formas que a transcrição escreve de outra maneira (números, contracções) contam como iguais.

_NUMEROS = {
    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven',
    '8': 'eight', '9': 'nine', '10': 'ten', '11': 'eleven', '12': 'twelve', '13': 'thirteen', '14': 'fourteen',
    '15': 'fifteen', '16': 'sixteen', '17': 'seventeen', '18': 'eighteen', '19': 'nineteen', '20': 'twenty',
    '30': 'thirty', '40': 'forty', '50': 'fifty', '60': 'sixty', '70': 'seventy', '80': 'eighty',
    '90': 'ninety', '100': 'hundred',
}
_CONTRACCOES = {
    "can't": ['can', 'not'], "won't": ['will', 'not'], "shan't": ['shall', 'not'], "let's": ['let', 'us'],
    "i'm": ['i', 'am'], "it's": ['it', 'is'], "that's": ['that', 'is'], "there's": ['there', 'is'],
    "what's": ['what', 'is'], "he's": ['he', 'is'], "she's": ['she', 'is'],
}
_SUFIXOS = (("n't", ['not']), ("'ll", ['will']), ("'re", ['are']), ("'ve", ['have']), ("'d", ['would']),
            ("'m", ['am']))
_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def palavras_normalizadas(texto):
    """Palavras em minúsculas, sem pontuação, com números por extenso e contracções abertas."""
    out = []
    for t in _TOKEN.findall(str(texto or '').lower().replace('’', "'")):
        if t in _NUMEROS:
            out.append(_NUMEROS[t])
        elif t in _CONTRACCOES:
            out.extend(_CONTRACCOES[t])
        else:
            for suf, abre in _SUFIXOS:
                if t.endswith(suf) and len(t) > len(suf):
                    out.append(t[:-len(suf)])
                    out.extend(abre)
                    break
            else:
                out.append(t)
    return out


def correspondencia_palavras(esperado, ouvido, palavras=None):
    """
    Compara a frase esperada com o que se ouviu. `palavras` (opcional) são os tempos por palavra da
    transcrição ([{palavra, inicio, fim}]): quando existem, são a fonte do que se ouviu.

    Devolve {'nota': 0-100, 'certas', 'esperadas', 'ouvidas', 'em_falta': [...], 'a_mais': [...]}.
    nota = palavras certas (por ordem) / max(esperadas, ouvidas): palavras em falta, trocadas ou a
    mais baixam a nota. Frase esperada vazia: nota 0.
    """
    from difflib import SequenceMatcher

    exp = palavras_normalizadas(esperado)
    ouv = []
    if palavras:
        ouv = palavras_normalizadas(' '.join(str(p.get('palavra') or '') for p in palavras if isinstance(p, dict)))
    if not ouv:
        ouv = palavras_normalizadas(ouvido)
    if not exp:
        return {'nota': 0, 'certas': 0, 'esperadas': 0, 'ouvidas': len(ouv), 'em_falta': [], 'a_mais': []}
    sm = SequenceMatcher(None, exp, ouv, autojunk=False)
    certas, em_falta, a_mais = 0, [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            certas += i2 - i1
        else:
            em_falta.extend(exp[i1:i2])
            a_mais.extend(ouv[j1:j2])
    nota = int(round(100 * certas / max(len(exp), len(ouv))))
    vistos = []
    for p in em_falta:
        if p not in vistos:
            vistos.append(p)
    return {'nota': nota, 'certas': certas, 'esperadas': len(exp), 'ouvidas': len(ouv),
            'em_falta': vistos, 'a_mais': a_mais}
