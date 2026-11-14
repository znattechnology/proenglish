"""
Métricas de fluência de uma gravação, a partir dos tempos das palavras (transcricao_fala).

Definições (todas em segundos):
- palavras: número de palavras ditas (com tempos; sem tempos, contadas no texto).
- duração da fala ("span"): do início da primeira palavra ao fim da última.
- pausa: o intervalo entre o fim de uma palavra e o início da seguinte.
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
        pausas = [max(0.0, b['inicio'] - a['fim']) for a, b in zip(palavras, palavras[1:])]
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
