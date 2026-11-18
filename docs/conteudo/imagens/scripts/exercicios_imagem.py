"""Acrescenta aos laboratórios do A1 exercícios "Escolha a imagem" com o banco de imagens.
Uso: python3 exercicios_imagem.py <docs/conteudo> [--escrever]"""
import json, glob, os, random, re, sys
base = sys.argv[1]; escrever = '--escrever' in sys.argv
banco = json.load(open(os.path.join(base, 'imagens/banco-a1.json'), encoding='utf-8'))
grupo = {i['id']: i['uso'].split(': ')[1] for i in banco['imagens']}
for c in ('black','white','blue','red','grey','green','yellow','brown','pink','orange'):
    grupo[c] = 'cores'
SIN = {'mobile': 'mobile-phone', 'phone': 'mobile-phone', 'tv': 'watch-tv', 'football': 'play-football',
       'basketball': 'play-basketball', 'guitar': 'play-the-guitar', 'piano': 'play-the-piano',
       'teeth': 'tooth', 'feet': 'foot', 'the flu': 'cold', 'credit card': 'bank-card', 'card': 'bank-card',
       'multicaixa': 'bank-card', 'kwanza(s)': 'cash', 'a sandwich': 'sandwich', 'a cake': 'cake',
       'a croissant': 'croissant', 'the doctor': 'doctor', 'the hospital': 'hospital', 'swim': 'swim'}
def ids_de(palavra):
    w = palavra.strip().lower()
    w = re.sub(r'\(.*?\)', '', w).strip()
    if w in SIN: return [SIN[w]]
    partes = [p.strip() for p in re.split(r'\s*/\s*', w)] if '/' in w and 'play' not in w else [w]
    saida = []
    for p in partes:
        for cand in (p, re.sub(r'^(a|an|the)\s+', '', p)):
            k = re.sub(r'[^a-z0-9]+', '-', cand).strip('-')
            if k in grupo: saida.append(k); break
    return saida
def palavras_da_aula(texto, codigo):
    m = re.search(r'^## ' + re.escape(codigo) + r' — .*?(?=^## |\Z)', texto, re.M | re.S)
    if not m: return []
    p = re.search(r'Palavras-alvo:(.*?)(?=\n\S[^\n:]*:|\n```)', m.group(0), re.S)
    if not p: return []
    return [w.strip().rstrip('.') for w in re.split(r'[,;]\s*', ' '.join(p.group(1).split())) if w.strip()]
total = 0
for pasta in sorted(glob.glob(os.path.join(base, 'a1/*/'))):
    lab_p = os.path.join(pasta, 'laboratorio.json'); gui_p = os.path.join(pasta, 'guioes.md')
    if not os.path.exists(lab_p) or not os.path.exists(gui_p): continue
    lab = json.load(open(lab_p, encoding='utf-8')); guioes = open(gui_p, encoding='utf-8').read()
    mudou = False
    for licao in lab.get('licoes', []):
        if not licao.get('aula'): continue
        if any(o.get('imagem') for e in licao['exercicios'] for o in (e.get('opcoes') or []) if isinstance(o, dict)): continue
        achados = []
        for w in palavras_da_aula(guioes, licao['aula']):
            for k in ids_de(w):
                if k not in [a for a, _ in achados]: achados.append((k, w))
        if not achados: continue
        rnd = random.Random(licao['codigo'])
        quantos = 2 if len(achados) >= 4 else 1
        novos = []
        for alvo, palavra in rnd.sample(achados, quantos):
            outros = [a for a, _ in achados if a != alvo and grupo[a] == grupo[alvo]]
            if len(outros) < 2:
                outros += [k for k, g in grupo.items() if g == grupo[alvo] and k != alvo and k not in outros]
            distractores = rnd.sample(outros[:max(2, len(outros))], 2)
            MAIUSC = {'it-technician': 'IT technician', 'watch-tv': 'watch TV', 'id-card': 'ID card', 'atm': 'ATM', 't-shirt': 'T-shirt'}
            texto = lambda k: MAIUSC.get(k, k.replace('-', ' '))
            opcoes = [{'texto': texto(alvo), 'certa': True, 'imagem': alvo}] + [{'texto': texto(k), 'certa': False, 'imagem': k} for k in distractores]
            rnd.shuffle(opcoes)
            novos.append({'tipo': 'escolher', 'enunciado': f'Escolha a imagem: "{texto(alvo)}"', 'opcoes': opcoes})
        if len(licao['exercicios']) + len(novos) > 30: novos = novos[:30 - len(licao['exercicios'])]
        if not novos: continue
        licao['exercicios'][1:1] = novos
        total += len(novos); mudou = True
        print(f"{os.path.basename(pasta.rstrip('/'))} {licao['codigo']}: " + '; '.join(n['enunciado'] for n in novos))
    if mudou and escrever:
        with open(lab_p, 'w', encoding='utf-8') as f:
            json.dump(lab, f, ensure_ascii=False, indent=1); f.write('\n')
print('exercícios novos:', total, '(escritos)' if escrever else '(ensaio)')
