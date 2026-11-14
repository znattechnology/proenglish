"""
Tempo de fala do aluno numa conversa (fase 3).

Fonte 'medido': o end-of-call-report do Vapi traz, em artifact.messages, cada fala com tempos.
Segundo a especificação da API do Vapi (UserMessage/BotMessage): `time` e `endTime` (instantes,
em milissegundos desde 1970 nas chamadas reais), `secondsFromStart` (segundos desde o início) e
`duration` (opcional; a especificação diz segundos, mas há relatórios com milissegundos).
A duração de cada fala é endTime - time; sem isso usa-se `duration` (> 600 lê-se como ms).

Fonte 'estimado' (sem tempos: modo simulado, relatório que não chegou, sessões antigas):
segundos = palavras / 2,3 (ritmo de conversa de um aprendente). Nesse caso NÃO se calcula
palavras por minuto (seria só a constante ao contrário).

Resultado (campos de VapiSession):
  segundos_aluno, segundos_tutor, ppm_aluno (só medido), palavras_por_turno,
  quota_fala_aluno (0-1: parte do tempo de fala que foi do aluno), fonte_tempo.
"""
from . import analise, regras

PALAVRAS_POR_SEGUNDO = 2.3
MIN_SEGUNDOS_PPM = 5.0
MAX_DURACAO_FALA = 300.0  # uma fala com mais de 5 min é um erro de tempos: ignora-se


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v >= 0 else None


def duracao_mensagem(m):
    """Segundos de uma mensagem do Vapi, ou None."""
    ini, fim = _num(m.get('time')), _num(m.get('endTime'))
    if ini is not None and fim is not None and fim >= ini:
        d = (fim - ini) / 1000.0 if ini > 1e11 else fim - ini
        if d <= MAX_DURACAO_FALA:
            return d
    d = _num(m.get('duration'))
    if d is not None:
        d = d / 1000.0 if d > 600 else d
        if d <= MAX_DURACAO_FALA:
            return d
    return None


def segmentos_vapi(mensagens):
    """artifact.messages -> [{quem, inicio, segundos, palavras}] com tempos (só aluno/tutor)."""
    out = []
    for m in mensagens if isinstance(mensagens, list) else []:
        if not isinstance(m, dict):
            continue
        papel = m.get('role')
        quem = 'aluno' if papel == 'user' else 'tutor' if papel in ('bot', 'assistant') else None
        texto = m.get('message') if isinstance(m.get('message'), str) else m.get('content')
        if not quem or not isinstance(texto, str) or not texto.strip():
            continue
        d = duracao_mensagem(m)
        if d is None:
            continue
        out.append({'quem': quem, 'inicio': _num(m.get('secondsFromStart')), 'segundos': round(d, 2),
                    'palavras': len(regras.palavras(texto))})
    return out[:500]


def calcular(transcricao, segmentos=None, segundos_sessao=None):
    """Os campos de tempo de fala (ver o topo). transcricao: [{quem, texto}] limpa."""
    falas = analise.textos_aluno(transcricao or [])
    palavras = sum(len(regras.palavras(f)) for f in falas)
    por_turno = round(palavras / len(falas), 1) if falas else None
    segs = [s for s in segmentos or [] if isinstance(s, dict)]
    aluno = [s for s in segs if s.get('quem') == 'aluno' and (s.get('segundos') or 0) > 0]
    tetos = [segundos_sessao] if isinstance(segundos_sessao, (int, float)) and segundos_sessao > 0 else []

    if aluno:
        seg_aluno = sum(s['segundos'] for s in aluno)
        seg_tutor = sum(s['segundos'] for s in segs if s.get('quem') == 'tutor')
        palavras_medidas = sum(s.get('palavras') or 0 for s in aluno)
        ppm = (palavras_medidas / (seg_aluno / 60.0)) if seg_aluno >= MIN_SEGUNDOS_PPM and palavras_medidas else None
        fonte = 'medido'
    else:
        if not palavras:
            return {'segundos_aluno': 0.0 if transcricao is not None else None, 'segundos_tutor': None,
                    'ppm_aluno': None, 'palavras_por_turno': por_turno, 'quota_fala_aluno': None,
                    'fonte_tempo': 'estimado'}
        tutor = sum(len(regras.palavras(t['texto'])) for t in transcricao or [] if t.get('quem') == 'tutor')
        seg_aluno = palavras / PALAVRAS_POR_SEGUNDO
        seg_tutor = tutor / PALAVRAS_POR_SEGUNDO
        ppm = None
        fonte = 'estimado'
    if tetos:
        seg_aluno = min(seg_aluno, tetos[0])
        seg_tutor = min(seg_tutor, tetos[0])
    total = seg_aluno + seg_tutor
    return {
        'segundos_aluno': round(seg_aluno, 1),
        'segundos_tutor': round(seg_tutor, 1),
        'ppm_aluno': round(ppm, 1) if ppm is not None else None,
        'palavras_por_turno': por_turno,
        'quota_fala_aluno': round(seg_aluno / total, 2) if total > 0 else None,
        'fonte_tempo': fonte,
    }


CAMPOS = ('segundos_aluno', 'segundos_tutor', 'ppm_aluno', 'palavras_por_turno', 'quota_fala_aluno', 'fonte_tempo')


def aplicar(sessao, dados, transcricao=None):
    """Põe os campos na sessão (sem gravar). Devolve a lista de campos para update_fields."""
    if transcricao is None:
        transcricao = dados.get('transcricao') or analise.limpar_transcricao(dados.get('transcricao_servidor') or [])
    r = calcular(transcricao, dados.get('tempos_vapi'), sessao.duration_seconds or None)
    for k in CAMPOS:
        setattr(sessao, k, r[k])
    return list(CAMPOS)


def _min_seg(segundos):
    s = int(round(segundos or 0))
    if s < 60:
        return f'{s} s'
    m, r = divmod(s, 60)
    return f'{m} min {r} s' if r else f'{m} min'


def resumo(sessao):
    """{segundos, ppm, palavras_por_turno, quota, fonte, frase} para o resumo da conversa, ou None."""
    if sessao.segundos_aluno is None or sessao.segundos_aluno < 1:
        return None
    medido = sessao.fonte_tempo == 'medido'
    partes = [f'Falou {"" if medido else "cerca de "}{_min_seg(sessao.segundos_aluno)}']
    if sessao.ppm_aluno:
        partes.append(f'{round(sessao.ppm_aluno)} palavras por minuto')
    if sessao.palavras_por_turno:
        n = round(sessao.palavras_por_turno)
        partes.append(f'respostas de {n} {"palavra" if n == 1 else "palavras"} em média')
    frase = ', '.join(partes) + '.'
    if sessao.quota_fala_aluno is not None and sessao.segundos_aluno >= 1:
        frase += f' Falou {round(sessao.quota_fala_aluno * 100)}% do tempo; o tutor o resto.'
    return {
        'segundos': round(sessao.segundos_aluno), 'ppm': round(sessao.ppm_aluno) if sessao.ppm_aluno else None,
        'palavras_por_turno': sessao.palavras_por_turno, 'quota': sessao.quota_fala_aluno,
        'fonte': sessao.fonte_tempo or 'estimado', 'frase': frase,
    }
