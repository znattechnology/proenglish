"""
Escala única de níveis de inglês: CEFR A1, A2, B1, B2, C1, C2.

Usada em Course.level (cursos de vídeo e de prática), em user.preferences.nivel, no tutor e nas
situações de conversa. Os valores antigos (Beginner/Intermediate/Advanced) só são aceites na
leitura (dados antigos, clientes desactualizados) e traduzidos com ANTIGO_PARA_CEFR; na escrita
de cursos só se aceitam códigos CEFR.
"""

CEFR = ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')

NOMES = {
    'A1': 'Iniciante',
    'A2': 'Elementar',
    'B1': 'Intermédio',
    'B2': 'Intermédio avançado',
    'C1': 'Avançado',
    'C2': 'Proficiente',
}

DESCRICOES = {
    'A1': 'Conheço palavras e frases muito simples',
    'A2': 'Consigo falar de rotinas e tarefas simples',
    'B1': 'Consigo conversar sobre o trabalho com algum apoio',
    'B2': 'Participo em reuniões e discussões com à-vontade',
    'C1': 'Exprimo-me com fluência e precisão em contexto profissional',
    'C2': 'Uso o inglês como um falante nativo',
}

# Mapeamento usado na migração de dados e na leitura de valores antigos.
ANTIGO_PARA_CEFR = {'Beginner': 'A2', 'Intermediate': 'B1', 'Advanced': 'B2'}
# Inverso (migração para trás): A1/A2 -> Beginner, B1 -> Intermediate, B2+ -> Advanced.
CEFR_PARA_ANTIGO = {'A1': 'Beginner', 'A2': 'Beginner', 'B1': 'Intermediate',
                    'B2': 'Advanced', 'C1': 'Advanced', 'C2': 'Advanced'}

LEVEL_CHOICES = [(c, f'{c} ({NOMES[c]})') for c in CEFR]


def e_cefr(valor):
    return isinstance(valor, str) and valor in CEFR


def normalizar(valor):
    """
    Código CEFR para um valor guardado (CEFR em qualquer caixa, ou um valor antigo). None se
    não for reconhecido. Só para leitura; a escrita de cursos usa cefr_de_entrada.
    """
    if not isinstance(valor, str):
        return None
    v = valor.strip()
    if v.upper() in CEFR:
        return v.upper()
    return ANTIGO_PARA_CEFR.get(v) or ANTIGO_PARA_CEFR.get(v.capitalize())


def cefr_de_entrada(valor):
    """Código CEFR enviado por um cliente (aceita 'b1' ou 'B1'); None para tudo o resto."""
    if not isinstance(valor, str):
        return None
    v = valor.strip().upper()
    return v if v in CEFR else None


def rotulo(valor):
    """'Nível B1' para mostrar; None se não houver nível reconhecido."""
    c = normalizar(valor)
    return f'Nível {c}' if c else None


def indice(valor):
    c = normalizar(valor)
    return CEFR.index(c) if c else None


def opcoes():
    """Lista para selects: [{'valor': 'A1', 'nome': 'A1 (Iniciante)', 'descricao': ...}]."""
    return [{'valor': c, 'nome': f'{c} ({NOMES[c]})', 'descricao': DESCRICOES[c]} for c in CEFR]


# Banda que cada valor antigo cobria (só para filtros enviados por clientes antigos).
BANDA_ANTIGA = {'Beginner': ('A1', 'A2'), 'Intermediate': ('B1',), 'Advanced': ('B2', 'C1', 'C2')}


def filtro(param):
    """
    Valor do parâmetro ?level= -> lista de códigos CEFR a filtrar (vazia = sem filtro válido).
    Aceita 'B1', 'A2,B1' e, por compatibilidade, os nomes antigos (cada um vale a sua banda).
    """
    if not isinstance(param, str):
        return []
    codigos = []
    for parte in param.split(','):
        parte = parte.strip()
        if parte in BANDA_ANTIGA:
            codigos.extend(BANDA_ANTIGA[parte])
        elif parte.upper() in CEFR:
            codigos.append(parte.upper())
    return sorted(set(codigos), key=CEFR.index)
