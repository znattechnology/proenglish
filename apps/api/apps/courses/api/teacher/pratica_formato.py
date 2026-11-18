"""
Formato único dos exercícios na área do professor (cursos de prática) e a tradução de/para
PracticeChallenge + ChallengeOption, tal como o ecrã da lição do aluno os lê
(apps/courses/api/student/practice_courses/jogar.py e a validação em challenge-progress/).

  exercicio = {id, tipo, ordem, enunciado, frase, opcoes:[{id?, texto, certa, imagem?}], pares:[{a, b}],
               resposta, explicacao, audio_url, contexto, frases_alvo:[str], acerto, tentativas}

Tipos (normalizado -> modelo) e onde fica cada campo:

  escolher (SELECT) / assistir (ASSIST)
      question = enunciado; opções = opcoes (exactamente uma certa).
  verdadeiro_falso (TRUE_FALSE)
      question = enunciado (a afirmação); opções "Verdadeiro"/"Falso"; resposta = verdadeiro|falso.
  completar (FILL_BLANK)
      frase "Could you [send] me..." -> question "Could you ___ me..."; as palavras entre [ ] são
      as opções certas (pela ordem dos espaços); opcoes com certa=false são as alternativas
      (banco de palavras). Sem alternativas o aluno escreve. instruction = enunciado.
  traduzir (TRANSLATION)
      question = enunciado (frase em português); resposta = 1.ª opção certa; opcoes = outras
      traduções aceites (certa=true) ou, se houver erradas, o exercício passa a ser de escolha.
  ordenar (SENTENCE_ORDER)
      question = enunciado (frase em português, o aluno vê-a); resposta = frase em inglês;
      cada palavra é uma opção, pela ordem certa.
  pares (MATCH_PAIRS)
      question = enunciado (ou "Ligue cada palavra à tradução."); cada par é uma opção "a - b".
  escuta (LISTENING)
      frase = o texto lido em voz alta (guardado também em conversation_context.frase);
      com opcoes: question = enunciado (pergunta sobre o que se ouve) e escolha;
      sem opcoes: ditado, a opção certa é a frase e question = enunciado ou "Escreva o que ouve.".
      audio_url = reference_audio_url.
  pronuncia (SPEAKING)
      question = frase (o que o aluno diz); instruction = enunciado; audio_url = reference_audio_url.
  responder (RESPONDER)
      o aluno ouve/lê uma pergunta de trabalho e responde em voz alta, livremente.
      question = enunciado (a pergunta, em inglês); instruction = contexto (curto, opcional);
      conversation_context = {frase_alvo: frase, exemplo: resposta}. Sem opções.
  conversa (VAPI_CONVERSATION)
      conversa curta (1-2 min) com o tutor no fim da lição.
      question = enunciado (a situação); conversation_context = {scenario: enunciado,
      frases: frases_alvo (2 a 3), goal: as frases juntas (exercícios antigos tinham só goal)}.

O texto de explicação vai para `explanation`. Campos que um tipo não usa saem "" / [] / null.

Imagens nas opções (`imagem`, endereço https, opcional): nos tipos escolher, assistir e escuta com
opções ("Escolha a imagem: a receipt"); vai para ChallengeOption.image_url. O texto da opção
continua obrigatório (é o que o leitor de ecrã lê e o que se compara). Nos outros tipos, ignora-se.
"""
import re

TIPOS = {
    'escolher': 'SELECT',
    'assistir': 'ASSIST',
    'completar': 'FILL_BLANK',
    'traduzir': 'TRANSLATION',
    'ordenar': 'SENTENCE_ORDER',
    'pares': 'MATCH_PAIRS',
    'verdadeiro_falso': 'TRUE_FALSE',
    'escuta': 'LISTENING',
    'pronuncia': 'SPEAKING',
    'responder': 'RESPONDER',
    'conversa': 'VAPI_CONVERSATION',
}
TIPO_API = {v: k for k, v in TIPOS.items()}
TIPOS_CRIAVEIS = list(TIPOS)
# Exercícios em que o aluno fala (a regra "pelo menos metade da lição falada" do gerador).
TIPOS_FALADOS = ('pronuncia', 'responder')

NOMES = {
    'escolher': 'Escolher',
    'assistir': 'Escolha assistida',
    'completar': 'Completar',
    'traduzir': 'Traduzir',
    'ordenar': 'Ordenar',
    'pares': 'Pares',
    'verdadeiro_falso': 'Verdadeiro ou falso',
    'escuta': 'Escuta',
    'pronuncia': 'Pronúncia',
    'responder': 'Responder',
    'conversa': 'Conversa curta',
}

ESPACO = re.compile(r'_{2,}|\[\s*\]')  # o mesmo que o ecrã da lição usa para os espaços
PARENTESES = re.compile(r'\[([^\[\]]*)\]')
SEPARADORES_PAR = [' - ', ' – ', ' = ', ' : ']
PARES_PERGUNTA = 'Ligue cada palavra à tradução.'
DITADO_PERGUNTA = 'Escreva o que ouve.'
VERDADEIRO, FALSO = 'Verdadeiro', 'Falso'

MAX_ENUNCIADO = 1000
MAX_FRASE = 500
MAX_OPCAO = 300  # ChallengeOption.text
MAX_EXPLICACAO = 2000
MAX_OPCOES = 6
MAX_PARES = 8
MAX_ESPACOS = 3
MIN_PALAVRAS_ORDENAR, MAX_PALAVRAS_ORDENAR = 3, 15
MAX_CONTEXTO = 300
MAX_FRASE_ALVO = 160
MAX_SITUACAO = 600
MIN_FRASES_CONVERSA, MAX_FRASES_CONVERSA = 2, 3


def _texto(v):
    return ' '.join(v.split()) if isinstance(v, str) else ''


def _texto_longo(v):
    return v.strip() if isinstance(v, str) else ''


def _normal(v):
    return ' '.join((v or '').lower().split())


def _vazio(tipo='', ordem=None):
    return {'tipo': tipo, 'ordem': ordem, 'enunciado': '', 'frase': '', 'opcoes': [], 'pares': [],
            'resposta': '', 'explicacao': '', 'audio_url': None, 'contexto': '', 'frases_alvo': []}


# ---------------------------------------------------------------------------
# Validação (entrada da API e saída do Claude)
# ---------------------------------------------------------------------------

TIPOS_COM_IMAGEM = ('escolher', 'assistir', 'escuta')
MAX_URL = 200  # URLField


def _imagem(valor, erros, campo='opcoes'):
    """Endereço https da imagem de uma opção, ou None."""
    url = _texto(valor)
    if not url:
        return None
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator
    try:
        URLValidator(schemes=['https'])(url)
    except ValidationError:
        erros.setdefault(campo, []).append('A imagem de uma opção tem de ser um endereço https válido.')
        return None
    if len(url) > MAX_URL:
        erros.setdefault(campo, []).append('O endereço de uma imagem é demasiado longo.')
        return None
    return url


def _opcoes_entrada(valor, erros, campo='opcoes'):
    """[{texto, certa, imagem?}] -> lista limpa; regista erros de forma."""
    if valor in (None, ''):
        return []
    if not isinstance(valor, list):
        erros.setdefault(campo, []).append('As opções têm de ser uma lista.')
        return []
    limpas = []
    for o in valor:
        if isinstance(o, str):
            o = {'texto': o, 'certa': False}
        if not isinstance(o, dict):
            erros.setdefault(campo, []).append('Cada opção tem de ter texto e certa.')
            return []
        texto = _texto(o.get('texto'))
        if not texto:
            erros.setdefault(campo, []).append('Há opções sem texto.')
            return []
        if len(texto) > MAX_OPCAO:
            erros.setdefault(campo, []).append(f'Cada opção pode ter no máximo {MAX_OPCAO} caracteres.')
            return []
        certa = o.get('certa')
        limpas.append({'texto': texto, 'certa': bool(certa) if isinstance(certa, bool) else certa in ('true', 1, '1'),
                       'imagem': _imagem(o.get('imagem'), erros, campo)})
    return limpas


def _repetidas(textos):
    vistos = set()
    for t in textos:
        n = _normal(t)
        if n in vistos:
            return True
        vistos.add(n)
    return False


def _validar_escolha(opcoes, erros, minimo=2):
    if len(opcoes) < minimo:
        erros.setdefault('opcoes', []).append(f'Indique pelo menos {minimo} opções.')
    elif len(opcoes) > MAX_OPCOES:
        erros.setdefault('opcoes', []).append(f'Indique no máximo {MAX_OPCOES} opções.')
    elif _repetidas([o['texto'] for o in opcoes]):
        erros.setdefault('opcoes', []).append('Há opções repetidas.')
    elif sum(1 for o in opcoes if o['certa']) != 1:
        erros.setdefault('opcoes', []).append('Marque exactamente uma opção certa.')


def _url(valor, erros):
    url = _texto(valor)
    if not url:
        return None
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator
    try:
        URLValidator()(url)
    except ValidationError:
        erros.setdefault('audio_url', []).append('Indique um endereço (URL) válido para o áudio.')
        return None
    if len(url) > 200:  # URLField
        erros.setdefault('audio_url', []).append('O endereço do áudio é demasiado longo.')
        return None
    return url


def palavras_de(frase):
    return frase.split()


def usa_frase(frase, texto, limiar=0.8):
    """O texto usa a frase-alvo? (palavras da frase, pela ordem; "..." numa estrutura não conta)."""
    from apps.perfil.servico import cobertura
    return cobertura(frase, texto) >= limiar


def validar(dados):
    """
    dados (dict vindo do cliente ou do Claude) -> (limpo, erros).
    `limpo` tem o formato normalizado (sem id/acerto/tentativas); `erros` é {campo: [mensagens]}.
    """
    erros = {}
    if not isinstance(dados, dict):
        return None, {'tipo': ['Envie o exercício como um objecto.']}
    tipo = dados.get('tipo')
    if tipo not in TIPOS_CRIAVEIS:
        return None, {'tipo': ['Tipo inválido. Use: ' + ', '.join(TIPOS_CRIAVEIS) + '.']}

    limpo = _vazio(tipo)
    enunciado = _texto_longo(dados.get('enunciado'))
    frase = _texto(dados.get('frase'))
    resposta = _texto(dados.get('resposta'))
    explicacao = _texto_longo(dados.get('explicacao'))
    if len(enunciado) > MAX_ENUNCIADO:
        erros['enunciado'] = [f'O enunciado pode ter no máximo {MAX_ENUNCIADO} caracteres.']
    if len(frase) > MAX_FRASE:
        erros['frase'] = [f'A frase pode ter no máximo {MAX_FRASE} caracteres.']
    if len(explicacao) > MAX_EXPLICACAO:
        erros['explicacao'] = [f'A explicação pode ter no máximo {MAX_EXPLICACAO} caracteres.']
    limpo['explicacao'] = explicacao
    opcoes = _opcoes_entrada(dados.get('opcoes'), erros)

    if tipo in ('escolher', 'assistir'):
        if not enunciado:
            erros.setdefault('enunciado', []).append('Escreva a pergunta.')
        _validar_escolha(opcoes, erros)
        limpo.update(enunciado=enunciado, opcoes=opcoes)

    elif tipo == 'verdadeiro_falso':
        if not enunciado:
            erros.setdefault('enunciado', []).append('Escreva a afirmação que o aluno vai julgar.')
        valor = _normal(resposta)
        if valor not in ('verdadeiro', 'falso'):
            certas = [_normal(o['texto']) for o in opcoes if o['certa']]
            valor = certas[0] if len(certas) == 1 and certas[0] in ('verdadeiro', 'falso') else ''
        if not valor:
            erros.setdefault('resposta', []).append('Indique se a afirmação é verdadeira ou falsa.')
        limpo.update(enunciado=enunciado, resposta=valor,
                     opcoes=[{'texto': VERDADEIRO, 'certa': valor == 'verdadeiro'},
                             {'texto': FALSO, 'certa': valor == 'falso'}])

    elif tipo == 'completar':
        certas = [_texto(p) for p in PARENTESES.findall(frase)]
        if not frase:
            erros.setdefault('frase', []).append('Escreva a frase a completar.')
        elif ESPACO.search(PARENTESES.sub('x', frase)):
            erros.setdefault('frase', []).append(
                'Não use ___ na frase: ponha entre parênteses rectos a palavra que o aluno tem de escolher.')
        elif not certas:
            erros.setdefault('frase', []).append(
                'Ponha entre parênteses rectos a palavra que o aluno tem de escolher.')
        elif any(not c for c in certas):
            erros.setdefault('frase', []).append('Há parênteses rectos vazios: escreva a palavra certa lá dentro.')
        elif len(certas) > MAX_ESPACOS:
            erros.setdefault('frase', []).append(f'Use no máximo {MAX_ESPACOS} espaços por frase.')
        elif '[' in PARENTESES.sub('', frase) or ']' in PARENTESES.sub('', frase):
            erros.setdefault('frase', []).append('Há um parêntese recto por fechar.')
        elif any(len(c) > MAX_OPCAO for c in certas):
            erros.setdefault('frase', []).append(f'A palavra entre parênteses pode ter no máximo {MAX_OPCAO} caracteres.')
        certas_n = {_normal(c) for c in certas}
        erradas = [o for o in opcoes if not o['certa'] and _normal(o['texto']) not in certas_n]
        if any(o['certa'] and _normal(o['texto']) not in certas_n for o in opcoes):
            erros.setdefault('opcoes', []).append(
                'A opção certa tem de ser a palavra entre parênteses rectos na frase.')
        elif len(erradas) > MAX_OPCOES - 1:
            erros.setdefault('opcoes', []).append(f'Indique no máximo {MAX_OPCOES - 1} alternativas erradas.')
        elif _repetidas([o['texto'] for o in erradas]):
            erros.setdefault('opcoes', []).append('Há alternativas repetidas.')
        limpo.update(enunciado=enunciado, frase=frase,
                     opcoes=[{'texto': c, 'certa': True} for c in certas]
                     + [{'texto': o['texto'], 'certa': False} for o in erradas])

    elif tipo == 'traduzir':
        if not enunciado:
            erros.setdefault('enunciado', []).append('Escreva a frase em português que o aluno vai traduzir.')
        if not resposta:
            erros.setdefault('resposta', []).append('Escreva a tradução certa em inglês.')
        elif len(resposta) > MAX_OPCAO:
            erros.setdefault('resposta', []).append(f'A tradução pode ter no máximo {MAX_OPCAO} caracteres.')
        outras = [o for o in opcoes if _normal(o['texto']) != _normal(resposta)]
        if len(outras) > MAX_OPCOES - 1:
            erros.setdefault('opcoes', []).append(f'Indique no máximo {MAX_OPCOES - 1} traduções alternativas.')
        elif _repetidas([o['texto'] for o in outras]):
            erros.setdefault('opcoes', []).append('Há traduções repetidas.')
        limpo.update(enunciado=enunciado, resposta=resposta, opcoes=outras)

    elif tipo == 'ordenar':
        if not enunciado:
            erros.setdefault('enunciado', []).append('Escreva a frase em português (é o que o aluno vê).')
        n = len(palavras_de(resposta))
        if not resposta:
            erros.setdefault('resposta', []).append('Escreva a frase em inglês pela ordem certa.')
        elif not MIN_PALAVRAS_ORDENAR <= n <= MAX_PALAVRAS_ORDENAR:
            erros.setdefault('resposta', []).append(
                f'A frase tem de ter entre {MIN_PALAVRAS_ORDENAR} e {MAX_PALAVRAS_ORDENAR} palavras.')
        limpo.update(enunciado=enunciado, resposta=resposta)

    elif tipo == 'pares':
        bruto = dados.get('pares')
        pares = []
        if not isinstance(bruto, list):
            erros.setdefault('pares', []).append('Indique pelo menos 3 pares.')
        else:
            for p in bruto:
                a = _texto(p.get('a')) if isinstance(p, dict) else ''
                b = _texto(p.get('b')) if isinstance(p, dict) else ''
                if not a or not b:
                    erros.setdefault('pares', []).append('Cada par precisa das duas partes.')
                    break
                if ' - ' in a:
                    erros.setdefault('pares', []).append(f'Não use " - " (hífen entre espaços) na primeira parte ("{a}").')
                    break
                if len(a) + len(b) + 3 > MAX_OPCAO:
                    erros.setdefault('pares', []).append('Cada par pode ter no máximo 300 caracteres.')
                    break
                pares.append({'a': a, 'b': b})
            if 'pares' not in erros:
                if len(pares) < 3:
                    erros['pares'] = ['Indique pelo menos 3 pares.']
                elif len(pares) > MAX_PARES:
                    erros['pares'] = [f'Indique no máximo {MAX_PARES} pares.']
                elif _repetidas([p['a'] for p in pares]) or _repetidas([p['b'] for p in pares]):
                    erros['pares'] = ['Há pares repetidos: cada palavra só pode aparecer uma vez.']
        limpo.update(enunciado=enunciado, pares=pares)

    elif tipo == 'escuta':
        if not frase:
            erros.setdefault('frase', []).append('Escreva a frase que o aluno vai ouvir.')
        elif len(frase) > MAX_OPCAO:
            erros.setdefault('frase', []).append(f'A frase pode ter no máximo {MAX_OPCAO} caracteres.')
        if opcoes:
            if not enunciado:
                erros.setdefault('enunciado', []).append('Escreva a pergunta sobre o que o aluno ouve.')
            _validar_escolha(opcoes, erros)
        limpo.update(enunciado=enunciado, frase=frase, opcoes=opcoes, audio_url=_url(dados.get('audio_url'), erros))

    elif tipo == 'pronuncia':
        if not frase:
            erros.setdefault('frase', []).append('Escreva a frase que o aluno tem de dizer.')
        elif len(frase) > MAX_OPCAO:
            erros.setdefault('frase', []).append(f'A frase pode ter no máximo {MAX_OPCAO} caracteres.')
        limpo.update(enunciado=enunciado, frase=frase, audio_url=_url(dados.get('audio_url'), erros))

    elif tipo == 'responder':
        contexto = _texto(dados.get('contexto'))
        if not enunciado:
            erros.setdefault('enunciado', []).append('Escreva a pergunta, em inglês, a que o aluno responde.')
        elif len(enunciado) > MAX_OPCAO:
            erros.setdefault('enunciado', []).append(f'A pergunta pode ter no máximo {MAX_OPCAO} caracteres.')
        if not frase:
            erros.setdefault('frase', []).append('Indique a frase ou estrutura que a resposta deve usar.')
        elif len(frase) > MAX_FRASE_ALVO:
            erros.setdefault('frase', []).append(f'A frase-alvo pode ter no máximo {MAX_FRASE_ALVO} caracteres.')
        if not resposta:
            erros.setdefault('resposta', []).append('Escreva um exemplo de resposta, em inglês.')
        elif len(resposta) > MAX_OPCAO:
            erros.setdefault('resposta', []).append(f'O exemplo pode ter no máximo {MAX_OPCAO} caracteres.')
        elif frase and not usa_frase(frase, resposta):
            erros.setdefault('resposta', []).append('O exemplo de resposta tem de usar a frase-alvo.')
        if len(contexto) > MAX_CONTEXTO:
            erros.setdefault('contexto', []).append(f'O contexto pode ter no máximo {MAX_CONTEXTO} caracteres.')
        limpo.update(enunciado=enunciado, frase=frase, resposta=resposta, contexto=contexto)

    elif tipo == 'conversa':
        if not enunciado:
            erros.setdefault('enunciado', []).append('Descreva a situação da conversa.')
        elif len(enunciado) > MAX_SITUACAO:
            erros.setdefault('enunciado', []).append(f'A situação pode ter no máximo {MAX_SITUACAO} caracteres.')
        bruto = dados.get('frases_alvo')
        if bruto in (None, '') and frase:
            bruto = [frase]  # cliente antigo: um só objectivo
        frases = [_texto(f) for f in bruto] if isinstance(bruto, list) else []
        if not isinstance(bruto, list) or any(not isinstance(f, str) for f in bruto):
            erros.setdefault('frases_alvo', []).append('Envie as frases como uma lista de texto.')
        elif any(not f for f in frases):
            erros.setdefault('frases_alvo', []).append('Há frases vazias.')
        elif not MIN_FRASES_CONVERSA <= len(frases) <= MAX_FRASES_CONVERSA:
            erros.setdefault('frases_alvo', []).append(
                f'Indique entre {MIN_FRASES_CONVERSA} e {MAX_FRASES_CONVERSA} frases da lição para o aluno usar.')
        elif any(len(f) > MAX_FRASE_ALVO for f in frases):
            erros.setdefault('frases_alvo', []).append(f'Cada frase pode ter no máximo {MAX_FRASE_ALVO} caracteres.')
        elif _repetidas(frases):
            erros.setdefault('frases_alvo', []).append('Há frases repetidas.')
        limpo.update(enunciado=enunciado, frases_alvo=frases)

    # Todas as opções levam a chave `imagem` (só os tipos com imagem a guardam).
    com_imagem = tipo in TIPOS_COM_IMAGEM
    limpo['opcoes'] = [{**o, 'imagem': o.get('imagem') if com_imagem else None} for o in limpo.get('opcoes') or []]
    return limpo, erros


# ---------------------------------------------------------------------------
# Normalizado -> modelo
# ---------------------------------------------------------------------------

def guardar(challenge, limpo):
    """Escreve `limpo` no PracticeChallenge (já com lesson e order) e recria as opções."""
    from apps.practice.models import ChallengeOption

    tipo = limpo['tipo']
    # Áudio de uma frase que mudou: o áudio antigo já não corresponde (só se o pedido trouxer o
    # mesmo endereço; um endereço novo enviado com a frase nova fica).
    if challenge.pk and tipo in ('escuta', 'pronuncia') and limpo.get('audio_url'):
        antigo = para_normalizado(challenge) if challenge.type in ('LISTENING', 'SPEAKING') else None
        if (antigo and _normal(antigo['frase']) != _normal(limpo['frase'])
                and limpo['audio_url'] == (challenge.reference_audio_url or None)):
            limpo = dict(limpo, audio_url=None)
    challenge.type = TIPOS[tipo]
    challenge.explanation = limpo['explicacao'] or None
    challenge.instruction = None
    challenge.reference_audio_url = None
    contexto = challenge.conversation_context if isinstance(challenge.conversation_context, dict) else {}
    contexto = {k: v for k, v in contexto.items()
                if k not in ('frase', 'scenario', 'goal', 'frases', 'frase_alvo', 'exemplo')}
    opcoes = []  # (texto, certa) ou (texto, certa, imagem)

    if tipo in ('escolher', 'assistir', 'verdadeiro_falso'):
        challenge.question = limpo['enunciado']
        opcoes = [(o['texto'], o['certa'], o.get('imagem')) for o in limpo['opcoes']]
    elif tipo == 'completar':
        challenge.question = PARENTESES.sub('___', limpo['frase'])
        challenge.instruction = limpo['enunciado'] or None
        opcoes = [(o['texto'], o['certa']) for o in limpo['opcoes']]
    elif tipo == 'traduzir':
        challenge.question = limpo['enunciado']
        opcoes = [(limpo['resposta'], True)] + [(o['texto'], o['certa']) for o in limpo['opcoes']]
    elif tipo == 'ordenar':
        challenge.question = limpo['enunciado']
        opcoes = [(p, True) for p in palavras_de(limpo['resposta'])]
    elif tipo == 'pares':
        challenge.question = limpo['enunciado'] or PARES_PERGUNTA
        opcoes = [(f"{p['a']} - {p['b']}", True) for p in limpo['pares']]
    elif tipo == 'escuta':
        contexto['frase'] = limpo['frase']
        challenge.reference_audio_url = limpo['audio_url']
        if limpo['opcoes']:
            challenge.question = limpo['enunciado']
            opcoes = [(o['texto'], o['certa'], o.get('imagem')) for o in limpo['opcoes']]
        else:
            challenge.question = limpo['enunciado'] or DITADO_PERGUNTA
            opcoes = [(limpo['frase'], True)]
    elif tipo == 'pronuncia':
        challenge.question = limpo['frase']
        challenge.instruction = limpo['enunciado'] or None
        challenge.reference_audio_url = limpo['audio_url']
    elif tipo == 'responder':
        challenge.question = limpo['enunciado']
        challenge.instruction = limpo['contexto'] or None
        contexto['frase_alvo'] = limpo['frase']
        contexto['exemplo'] = limpo['resposta']
    elif tipo == 'conversa':
        challenge.question = limpo['enunciado']
        contexto['scenario'] = limpo['enunciado']
        contexto['frases'] = list(limpo['frases_alvo'])
        contexto['goal'] = '; '.join(limpo['frases_alvo'])

    challenge.conversation_context = contexto
    challenge.save()
    challenge.options.all().delete()
    ChallengeOption.objects.bulk_create([
        ChallengeOption(challenge=challenge, text=o[0][:MAX_OPCAO], is_correct=o[1],
                        image_url=(o[2] if len(o) > 2 else None) or None, order=i)
        for i, o in enumerate(opcoes, start=1)
    ])
    return challenge


# ---------------------------------------------------------------------------
# Modelo -> normalizado
# ---------------------------------------------------------------------------

def _opcao_dict(o):
    return {'id': str(o.id), 'texto': o.text, 'certa': bool(o.is_correct), 'imagem': o.image_url or None}


def para_normalizado(ch, opcoes=None):
    """PracticeChallenge (+ opções por ordem) -> exercício normalizado (sem acerto/tentativas)."""
    if opcoes is None:
        opcoes = sorted(ch.options.all(), key=lambda o: (o.order, str(o.id)))
    tipo = TIPO_API.get(ch.type, 'escolher')
    ex = _vazio(tipo, ch.order)
    ex['id'] = str(ch.id)
    ex['explicacao'] = ch.explanation or ''
    contexto = ch.conversation_context if isinstance(ch.conversation_context, dict) else {}
    pergunta = ch.question or ''
    certas = [o for o in opcoes if o.is_correct]

    if tipo in ('escolher', 'assistir'):
        ex['enunciado'] = pergunta
        ex['opcoes'] = [_opcao_dict(o) for o in opcoes]
    elif tipo == 'verdadeiro_falso':
        ex['enunciado'] = pergunta
        ex['opcoes'] = [_opcao_dict(o) for o in opcoes]
        certa = _normal(certas[0].text) if certas else ''
        ex['resposta'] = 'verdadeiro' if certa in ('verdadeiro', 'true', 'v') else ('falso' if certa else '')
    elif tipo == 'completar':
        fila = [o.text for o in certas]

        def _encher(_m):
            return f'[{fila.pop(0)}]' if fila else '[ ]'
        ex['frase'] = ESPACO.sub(_encher, pergunta)
        ex['enunciado'] = ch.instruction or ''
        ex['opcoes'] = [_opcao_dict(o) for o in opcoes]
    elif tipo == 'traduzir':
        ex['enunciado'] = pergunta
        ex['resposta'] = certas[0].text if certas else ''
        ex['opcoes'] = [_opcao_dict(o) for o in opcoes if not certas or o.id != certas[0].id]
    elif tipo == 'ordenar':
        ex['enunciado'] = pergunta
        ex['resposta'] = ' '.join(o.text for o in opcoes)
    elif tipo == 'pares':
        ex['enunciado'] = pergunta
        for o in opcoes:
            for sep in SEPARADORES_PAR:
                if sep in (o.text or ''):
                    a, b = o.text.split(sep, 1)
                    ex['pares'].append({'a': a.strip(), 'b': b.strip()})
                    break
    elif tipo == 'escuta':
        erradas = [o for o in opcoes if not o.is_correct]
        ex['audio_url'] = ch.reference_audio_url or None
        if erradas:
            ex['enunciado'] = pergunta
            ex['opcoes'] = [_opcao_dict(o) for o in opcoes]
            ex['frase'] = contexto.get('frase') or ''
        else:
            ex['frase'] = contexto.get('frase') or (certas[0].text if certas else '')
            ex['enunciado'] = '' if _normal(pergunta) == _normal(ex['frase']) else pergunta
    elif tipo == 'pronuncia':
        ex['frase'] = pergunta.strip() or (opcoes[0].text if opcoes else '')
        ex['enunciado'] = ch.instruction or ''
        ex['audio_url'] = ch.reference_audio_url or None
    elif tipo == 'responder':
        ex['enunciado'] = pergunta
        ex['contexto'] = ch.instruction or ''
        ex['frase'] = contexto.get('frase_alvo') or ''
        ex['resposta'] = contexto.get('exemplo') or ''
    elif tipo == 'conversa':
        ex['enunciado'] = pergunta or contexto.get('scenario') or ''
        ex['frases_alvo'] = frases_da_conversa(contexto)
    return ex


def frases_da_conversa(contexto):
    """As frases-alvo de uma conversa curta (as antigas só tinham um objectivo em goal)."""
    contexto = contexto if isinstance(contexto, dict) else {}
    frases = contexto.get('frases')
    if isinstance(frases, list):
        return [_texto(f) for f in frases if isinstance(f, str) and _texto(f)][:MAX_FRASES_CONVERSA]
    goal = _texto(contexto.get('goal') or contexto.get('objectivo'))
    return [goal] if goal else []
