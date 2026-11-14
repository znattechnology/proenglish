"""
Regras determinísticas (sem rede): ajustes de frases, guião do tutor simulado e
métricas de texto usadas na avaliação simulada.
"""
import re

from .situacoes import ENCERRAMENTO_EN

DIAS = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
TERCEIRA_PESSOA = {
    'include': 'includes', 'need': 'needs', 'have': 'has', 'go': 'goes', 'do': 'does',
    'want': 'wants', 'work': 'works', 'make': 'makes', 'take': 'takes', 'know': 'knows',
    'like': 'likes', 'say': 'says', 'come': 'comes', 'start': 'starts', 'finish': 'finishes',
}
PASSADO_PARA_BASE = {'went': 'go', 'saw': 'see', 'came': 'come', 'did': 'do', 'had': 'have',
                     'sent': 'send', 'made': 'make', 'took': 'take', 'told': 'tell', 'finished': 'finish'}


def _preservar(original, novo):
    return novo[0].upper() + novo[1:] if original[:1].isupper() else novo


def _r_dia(m):
    return f'{_preservar(m.group(1), "on")} {m.group(2)}'


def _r_terceira(m):
    return f'{m.group(1)} {TERCEIRA_PESSOA[m.group(2).lower()]}'


def _r_passado(m):
    return f"{m.group(1)} {PASSADO_PARA_BASE[m.group(2).lower()]}"


# (padrão, substituição, porquê). A substituição pode ser texto ou função.
REGRAS = [
    (re.compile(r'\b(in|at)\s+' + DIAS + r'\b', re.I), _r_dia,
     'Com dias da semana usa-se «on».'),
    (re.compile(r'\b(it|he|she|this|that)\s+(' + '|'.join(TERCEIRA_PESSOA) + r')\b', re.I), _r_terceira,
     'Com he/she/it, o verbo no presente leva -s.'),
    (re.compile(r"\b(didn't|did not|doesn't|does not|don't|do not)\s+(" + '|'.join(PASSADO_PARA_BASE) + r')\b',
                re.I), _r_passado,
     'Depois de do/does/did usa-se o verbo na forma base.'),
    (re.compile(r'\b(I|we|they|you)\s+(am|are)\s+agree\b', re.I), lambda m: f'{m.group(1)} agree',
     '«Agree» é um verbo: não leva «am/are».'),
    (re.compile(r'\bI\s+have\s+(\d+)\s+years\b(?!\s+(?:of|experience))', re.I), lambda m: f'I am {m.group(1)} years old',
     'Para a idade usa-se «to be»: I am ... years old.'),
    (re.compile(r'\bdepends?\s+of\b', re.I), lambda m: m.group(0).rsplit(' ', 1)[0] + ' on',
     'Diz-se «depend on», não «depend of».'),
    (re.compile(r'\bexplain\s+me\b', re.I), lambda m: _preservar(m.group(0), 'explain to me'),
     '«Explain» pede «to» antes da pessoa.'),
    (re.compile(r'\binformations\b', re.I), lambda m: _preservar(m.group(0), 'information'),
     '«Information» não tem plural em inglês.'),
    (re.compile(r'\bpeoples\b', re.I), lambda m: _preservar(m.group(0), 'people'),
     '«People» já é plural.'),
    (re.compile(r'\bmore\s+(better|worse|easier|faster)\b', re.I), lambda m: m.group(1),
     'O comparativo já está em «better/worse...»: não leva «more».'),
    (re.compile(r'\bdiscuss\s+about\b', re.I), lambda m: _preservar(m.group(0), 'discuss'),
     '«Discuss» não leva «about».'),
    (re.compile(r'\bsince\s+(\d+|two|three|four|five|six|ten)\s+(years?|months?|weeks?|days?|hours?)\b', re.I),
     lambda m: f'{_preservar(m.group(0), "for")} {m.group(1)} {m.group(2)}',
     'Para duração usa-se «for»; «since» é para o ponto de início.'),
    (re.compile(r'\b(I|we|they)\s+was\b', re.I), lambda m: f'{m.group(1)} were' if m.group(1).lower() != 'i' else None,
     'Com we/they usa-se «were».'),
]


def ajustes_frase(frase):
    """Lista de ajustes {disse, certo, porque} encontrados numa frase."""
    resultado = []
    for padrao, subst, porque in REGRAS:
        for m in padrao.finditer(frase or ''):
            certo = subst(m) if callable(subst) else m.expand(subst)
            if not certo or certo == m.group(0):
                continue
            resultado.append({'disse': m.group(0), 'certo': certo, 'porque': porque})
    return resultado


def primeiro_ajuste(frase):
    lista = ajustes_frase(frase)
    return lista[0] if lista else None


# ---------------------------------------------------------------------------
# Métricas de texto
# ---------------------------------------------------------------------------

PALAVRA = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
HESITACOES = {'um', 'uh', 'er', 'erm', 'hmm', 'ah', 'eh'}
PALAVRAS_PT = {'não', 'nao', 'você', 'voce', 'obrigado', 'obrigada', 'eu', 'é', 'está', 'então',
               'porque', 'sim', 'também', 'tambem', 'que', 'mas', 'muito', 'isso'}
PALAVRAS_EN_FUNCAO = {
    'the', 'a', 'an', 'and', 'or', 'but', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'is', 'are', 'was',
    'were', 'be', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'our', 'their', 'this', 'that',
    'do', 'does', 'did', 'have', 'has', 'had', 'will', 'can', 'so', 'yes', 'no', 'ok', 'okay', 'me', 'us',
}


def palavras(texto):
    return PALAVRA.findall(texto or '')


def parece_portugues(texto):
    tokens = re.findall(r'[\wÀ-ÿ]+', (texto or '').lower())
    if not tokens:
        return False
    pt = sum(1 for t in tokens if t in PALAVRAS_PT or re.search(r'[ãõçáéíóúâêô]', t))
    return pt >= max(1, len(tokens) // 3)


# ---------------------------------------------------------------------------
# Tutor simulado
# ---------------------------------------------------------------------------

def resposta_simulada(situacao, correcao, nome, texto, indice):
    """
    Resposta determinística do tutor ao turno `indice` (0 = primeira resposta do aluno).
    """
    texto = (texto or '').strip()
    if parece_portugues(texto):
        frases = situacao.get('frases') or [{'en': 'In my opinion, ...'}]
        return f'Let\'s try that in English. You can start with: "{frases[0]["en"]}"'
    if len(palavras(texto)) < 2:
        return 'Could you say a little more? Try a full sentence.'

    guiao = situacao['guiao']
    if indice < len(guiao):
        linha = guiao[indice].format(nome=nome)
    else:
        linha = ENCERRAMENTO_EN

    ajuste = primeiro_ajuste(texto)
    if ajuste:
        if correcao == 'directa':
            prefixo = f'Quick correction: we say "{ajuste["certo"]}", not "{ajuste["disse"]}". '
        else:
            prefixo = f'Got it: "{ajuste["certo"]}". '
        return prefixo + linha
    return linha
