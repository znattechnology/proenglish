"""
Gerar as imagens do curso com o Nano Banana (API do Gemini), com registo do custo de cada uma.

O que se gera vem de um manifesto JSON (docs/conteudo/imagens/*.json):

    {
      "estilo": "o estilo comum a todas as imagens",
      "regras": "o que nenhuma imagem pode ter (texto, logótipos…)",
      "imagens": [
        {"id": "nuno-ficha", "modelo": "pro", "proporcao": "16:9", "tamanho": "2K",
         "descricao": "…", "referencias": ["estilo-escolhido"]}
      ]
    }

- modelo: "pro" (Nano Banana Pro), "2.1" (Nano Banana 2.1) ou "flash" (Nano Banana 2);
- referencias: ids de imagens já aprovadas (o ficheiro aprovado vai como imagem de referência)
  ou caminhos de ficheiros;
- cada geração fica em <saída>/<id>/<id>-<n>.png; aprovar copia uma variante para
  <saída>/aprovadas/<id>.png; publicar envia a aprovada para o bucket (R2).

O custo de cada pedido é estimado pela tabela de preços abaixo (preços por imagem da página de
preços da API do Gemini, Novembro de 2026) e registado num CSV. Antes de cada pedido verifica-se o
limite de gasto da execução: o comando pára antes de o ultrapassar.
"""
import base64
import csv
import datetime
import json
import os
import shutil
from dataclasses import dataclass

URL_INTERACOES = 'https://generativelanguage.googleapis.com/v1beta/interactions'
URL_GENERATE = 'https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent'


@dataclass(frozen=True)
class Modelo:
    codigo: str
    por_imagem: dict           # tamanho -> US$ por imagem gerada
    por_referencia: float      # US$ por imagem de referência enviada
    proporcoes: tuple
    max_referencias: int


MODELOS = {
    'pro': Modelo('gemini-3-pro-image', {'1K': 0.134, '2K': 0.134, '4K': 0.24}, 0.0011,
                  ('1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'), 14),
    '2.1': Modelo('gemini-nano-banana-2.1', {'1K': 0.0336, '2K': 0.0504, '4K': 0.113}, 0.0009,
                  ('1:1', '1:4', '1:8', '2:3', '3:2', '3:4', '4:1', '4:3', '4:5', '5:4', '8:1', '9:16', '16:9', '21:9'), 14),
    'flash': Modelo('gemini-3.1-flash-image', {'1K': 0.067, '2K': 0.101, '4K': 0.151}, 0.0003,
                    ('1:1', '1:4', '1:8', '2:3', '3:2', '3:4', '4:1', '4:3', '4:5', '5:4', '8:1', '9:16', '16:9', '21:9'), 14),
}

CAMPOS_CUSTO = ['data', 'id', 'variante', 'modelo', 'tamanho', 'proporcao', 'referencias', 'custo_usd', 'ficheiro', 'uso']


class ErroImagens(Exception):
    pass


def ler_manifesto(caminho):
    with open(caminho, encoding='utf-8') as f:
        dados = json.load(f)
    imagens = dados.get('imagens') or []
    ids = [i.get('id') for i in imagens]
    if not imagens or not all(ids) or len(set(ids)) != len(ids):
        raise ErroImagens('O manifesto precisa de "imagens", cada uma com um "id" único.')
    for i in imagens:
        modelo = MODELOS.get(i.get('modelo', 'pro'))
        if modelo is None:
            raise ErroImagens(f'{i["id"]}: modelo desconhecido ({i.get("modelo")}). Use: {", ".join(MODELOS)}.')
        if i.get('tamanho', '1K') not in modelo.por_imagem:
            raise ErroImagens(f'{i["id"]}: tamanho inválido ({i.get("tamanho")}).')
        if i.get('proporcao', '1:1') not in modelo.proporcoes:
            raise ErroImagens(f'{i["id"]}: proporção {i.get("proporcao")} não existe no modelo {i.get("modelo", "pro")}.')
        if not (i.get('descricao') or '').strip():
            raise ErroImagens(f'{i["id"]}: falta a descrição.')
        if len(i.get('referencias') or []) > modelo.max_referencias:
            raise ErroImagens(f'{i["id"]}: demasiadas referências.')
    return dados


def custo_previsto(item):
    modelo = MODELOS[item.get('modelo', 'pro')]
    return modelo.por_imagem[item.get('tamanho', '1K')] + modelo.por_referencia * len(item.get('referencias') or [])


def texto_do_pedido(manifesto, item):
    partes = [item['descricao'].strip()]
    estilo = item.get('estilo', manifesto.get('estilo'))
    if estilo:
        partes.append(f'Style: {estilo.strip()}')
    if manifesto.get('regras'):
        partes.append(manifesto['regras'].strip())
    if item.get('referencias'):
        partes.append('Keep every person exactly as in the reference images: same face, skin tone, hair, '
                      'build and age.')
    return '\n\n'.join(partes)


def ficheiro_da_referencia(saida, ref):
    """Id de uma imagem aprovada ou caminho de um ficheiro."""
    aprovada = os.path.join(saida, 'aprovadas', f'{ref}.png')
    if os.path.exists(aprovada):
        return aprovada
    if os.path.exists(ref):
        return ref
    raise ErroImagens(f'Referência sem imagem aprovada: {ref}')


def _mime(caminho):
    return 'image/jpeg' if caminho.lower().endswith(('.jpg', '.jpeg')) else (
        'image/webp' if caminho.lower().endswith('.webp') else 'image/png')


def _b64(caminho):
    with open(caminho, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def corpo_interacoes(modelo, texto, referencias, proporcao, tamanho):
    entrada = [{'type': 'text', 'text': texto}]
    entrada += [{'type': 'image', 'mime_type': _mime(r), 'data': _b64(r)} for r in referencias]
    return {'model': modelo.codigo, 'input': entrada,
            'response_format': {'type': 'image', 'mime_type': 'image/png',
                                'aspect_ratio': proporcao, 'image_size': tamanho}}


def corpo_generate(texto, referencias, proporcao, tamanho):
    partes = [{'text': texto}] + [{'inline_data': {'mime_type': _mime(r), 'data': _b64(r)}} for r in referencias]
    return {'contents': [{'parts': partes}],
            'generationConfig': {'responseModalities': ['IMAGE'],
                                 'imageConfig': {'aspectRatio': proporcao, 'imageSize': tamanho}}}


def imagens_da_resposta(dados):
    """Os bytes das imagens devolvidas (as duas formas de resposta da API)."""
    achadas = []

    def andar(no):
        if isinstance(no, dict):
            if no.get('type') == 'image' and isinstance(no.get('data'), str):
                achadas.append(no['data'])
                return
            inline = no.get('inline_data') or no.get('inlineData')
            if isinstance(inline, dict) and isinstance(inline.get('data'), str):
                achadas.append(inline['data'])
                return
            for v in no.values():
                andar(v)
        elif isinstance(no, list):
            for v in no:
                andar(v)
    andar(dados)
    return [base64.b64decode(d) for d in achadas]


def pedir(chave, modelo, texto, referencias, proporcao, tamanho, api='interacoes', sessao=None):
    """Um pedido à API. Devolve (bytes da primeira imagem, resposta sem as imagens)."""
    import requests

    sessao = sessao or requests
    cabecalhos = {'x-goog-api-key': chave, 'Content-Type': 'application/json'}
    if api == 'interacoes':
        r = sessao.post(URL_INTERACOES, headers=cabecalhos, timeout=300,
                        json=corpo_interacoes(modelo, texto, referencias, proporcao, tamanho))
    else:
        r = sessao.post(URL_GENERATE.format(modelo=modelo.codigo), headers=cabecalhos, timeout=300,
                        json=corpo_generate(texto, referencias, proporcao, tamanho))
    if r.status_code != 200:
        raise ErroImagens(f'A API respondeu {r.status_code}: {r.text[:500]}')
    dados = r.json()
    imagens = imagens_da_resposta(dados)
    if not imagens:
        raise ErroImagens('A API não devolveu nenhuma imagem: ' + json.dumps(dados)[:500])
    return imagens[0], dados


def registar_custo(caminho_csv, linha):
    novo = not os.path.exists(caminho_csv)
    os.makedirs(os.path.dirname(caminho_csv) or '.', exist_ok=True)
    with open(caminho_csv, 'a', newline='', encoding='utf-8') as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_CUSTO)
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)


def total_gasto(caminho_csv):
    if not os.path.exists(caminho_csv):
        return 0.0, 0
    with open(caminho_csv, encoding='utf-8') as f:
        linhas = list(csv.DictReader(f))
    return sum(float(l['custo_usd']) for l in linhas), len(linhas)


def proxima_variante(saida, ident):
    pasta = os.path.join(saida, ident)
    if not os.path.isdir(pasta):
        return 1
    numeros = [int(n.rsplit('-', 1)[1].split('.')[0]) for n in os.listdir(pasta)
               if n.startswith(f'{ident}-') and n.rsplit('-', 1)[1].split('.')[0].isdigit()]
    return max(numeros, default=0) + 1


def gerar(manifesto, itens, saida, csv_custos, chave, variantes=1, limite_usd=2.0, api='interacoes',
          sessao=None, escrever=print):
    """Gera as variantes pedidas, parando antes de passar o limite de gasto. Devolve o gasto."""
    gasto = 0.0
    for item in itens:
        modelo = MODELOS[item.get('modelo', 'pro')]
        referencias = [ficheiro_da_referencia(saida, r) for r in item.get('referencias') or []]
        for _ in range(variantes):
            previsto = custo_previsto(item)
            if gasto + previsto > limite_usd + 1e-9:
                escrever(f'Limite de US$ {limite_usd:.2f} atingido: {item["id"]} ficou por gerar.')
                return gasto
            imagem, _ = pedir(chave, modelo, texto_do_pedido(manifesto, item), referencias,
                              item.get('proporcao', '1:1'), item.get('tamanho', '1K'), api=api, sessao=sessao)
            n = proxima_variante(saida, item['id'])
            os.makedirs(os.path.join(saida, item['id']), exist_ok=True)
            ficheiro = os.path.join(saida, item['id'], f'{item["id"]}-{n}.png')
            with open(ficheiro, 'wb') as f:
                f.write(imagem)
            gasto += previsto
            registar_custo(csv_custos, {
                'data': datetime.datetime.now().isoformat(timespec='seconds'), 'id': item['id'], 'variante': n,
                'modelo': modelo.codigo, 'tamanho': item.get('tamanho', '1K'),
                'proporcao': item.get('proporcao', '1:1'), 'referencias': len(referencias),
                'custo_usd': f'{previsto:.4f}', 'ficheiro': os.path.relpath(ficheiro, saida),
                'uso': item.get('uso', ''),
            })
            escrever(f'{item["id"]} variante {n}: {ficheiro} (US$ {previsto:.4f})')
    return gasto


def aprovar(saida, ident, variante):
    origem = os.path.join(saida, ident, f'{ident}-{variante}.png')
    if not os.path.exists(origem):
        raise ErroImagens(f'Não existe a variante {variante} de {ident}.')
    destino = os.path.join(saida, 'aprovadas', f'{ident}.png')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copyfile(origem, destino)
    return destino


def publicar(saida, ident, prefixo='conteudo/imagens'):
    """Envia a imagem aprovada para o bucket (R2) em WebP e devolve o endereço público."""
    from io import BytesIO

    from django.conf import settings
    from PIL import Image

    from apps.core import armazenamento

    aprovada = os.path.join(saida, 'aprovadas', f'{ident}.png')
    if not os.path.exists(aprovada):
        raise ErroImagens(f'{ident} ainda não foi aprovada.')
    if not armazenamento.configurado():
        raise ErroImagens('O armazenamento (R2) não está configurado.')
    buffer = BytesIO()
    Image.open(aprovada).convert('RGB').save(buffer, 'WEBP', quality=88, method=6)
    chave = f'{prefixo.strip("/")}/{ident}.webp'
    armazenamento.cliente().put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=chave, Body=buffer.getvalue(),
                                       ContentType='image/webp', CacheControl='public, max-age=31536000')
    return armazenamento.url_publico(chave)
