"""Geração de imagens com o Nano Banana: manifesto, pedidos, limite de gasto, registo do custo, aprovar e publicar."""
import base64
import csv
import io
import json
import os
import tempfile
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.courses import imagens_ia as ia


def png(cor=(200, 30, 30)):
    b = io.BytesIO()
    Image.new('RGB', (8, 8), cor).save(b, 'PNG')
    return b.getvalue()


class Resposta:
    def __init__(self, dados, estado=200):
        self.dados, self.status_code, self.text = dados, estado, json.dumps(dados)

    def json(self):
        return self.dados


class Sessao:
    """Imita requests: guarda os pedidos e responde com uma imagem."""
    def __init__(self, forma='interacoes', estado=200):
        self.pedidos, self.forma, self.estado = [], forma, estado

    def post(self, url, headers=None, json=None, timeout=None):
        self.pedidos.append({'url': url, 'headers': headers, 'json': json})
        dados = base64.b64encode(png()).decode()
        if self.estado != 200:
            return Resposta({'error': {'message': 'quota'}}, self.estado)
        if self.forma == 'interacoes':
            return Resposta({'steps': [{'type': 'model_output', 'content': [{'type': 'image', 'data': dados}]}]})
        return Resposta({'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/png', 'data': dados}}]}}]})


MANIFESTO = {
    'estilo': 'Flat vector illustration.',
    'regras': 'No text.',
    'imagens': [
        {'id': 'ficha-a', 'modelo': 'pro', 'proporcao': '16:9', 'tamanho': '2K', 'descricao': 'A man.'},
        {'id': 'cena', 'modelo': 'pro', 'proporcao': '16:9', 'tamanho': '2K', 'descricao': 'Two people.',
         'referencias': ['ficha-a']},
        {'id': 'objecto', 'modelo': '2.1', 'proporcao': '1:1', 'tamanho': '1K', 'descricao': 'A receipt.'},
    ],
}


class ImagensTests(SimpleTestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.saida = os.path.join(self.dir, 'saida')
        self.csv = os.path.join(self.dir, 'custos.csv')
        self.manifesto = os.path.join(self.dir, 'm.json')
        with open(self.manifesto, 'w') as f:
            json.dump(MANIFESTO, f)

    def test_manifesto_invalido(self):
        casos = [
            {'imagens': [{'id': 'a', 'descricao': 'x', 'modelo': 'dalle'}]},
            {'imagens': [{'id': 'a', 'descricao': 'x', 'modelo': 'pro', 'proporcao': '8:1'}]},
            {'imagens': [{'id': 'a', 'descricao': ''}]},
            {'imagens': [{'id': 'a', 'descricao': 'x'}, {'id': 'a', 'descricao': 'y'}]},
        ]
        for caso in casos:
            with open(self.manifesto, 'w') as f:
                json.dump(caso, f)
            with self.assertRaises(ia.ErroImagens, msg=caso):
                ia.ler_manifesto(self.manifesto)

    def test_custo_previsto(self):
        pro, cena, obj = MANIFESTO['imagens']
        self.assertAlmostEqual(ia.custo_previsto(pro), 0.134)
        self.assertAlmostEqual(ia.custo_previsto(cena), 0.134 + 0.0011)
        self.assertAlmostEqual(ia.custo_previsto(obj), 0.0336)

    def test_gera_regista_e_usa_a_aprovada_como_referencia(self):
        sessao = Sessao()
        m = ia.ler_manifesto(self.manifesto)
        ia.gerar(m, [m['imagens'][0]], self.saida, self.csv, 'chave-x', variantes=2, sessao=sessao, escrever=lambda s: None)
        self.assertTrue(os.path.exists(os.path.join(self.saida, 'ficha-a', 'ficha-a-1.png')))
        self.assertTrue(os.path.exists(os.path.join(self.saida, 'ficha-a', 'ficha-a-2.png')))
        pedido = sessao.pedidos[0]
        self.assertEqual(pedido['url'], ia.URL_INTERACOES)
        self.assertEqual(pedido['headers']['x-goog-api-key'], 'chave-x')
        self.assertEqual(pedido['json']['model'], 'gemini-3-pro-image')
        self.assertEqual(pedido['json']['response_format'], {'type': 'image', 'mime_type': 'image/png',
                                                             'aspect_ratio': '16:9', 'image_size': '2K'})
        texto = pedido['json']['input'][0]['text']
        self.assertIn('A man.', texto)
        self.assertIn('Flat vector illustration.', texto)
        self.assertIn('No text.', texto)
        # A cena sem a ficha aprovada não se gera; aprovada a variante 2, vai como referência.
        with self.assertRaisesMessage(ia.ErroImagens, 'Referência sem imagem aprovada: ficha-a'):
            ia.gerar(m, [m['imagens'][1]], self.saida, self.csv, 'k', sessao=sessao, escrever=lambda s: None)
        ia.aprovar(self.saida, 'ficha-a', 2)
        ia.gerar(m, [m['imagens'][1]], self.saida, self.csv, 'k', sessao=sessao, escrever=lambda s: None)
        entrada = sessao.pedidos[-1]['json']['input']
        self.assertEqual([p['type'] for p in entrada], ['text', 'image'])
        self.assertIn('same face', entrada[0]['text'])
        with open(self.csv) as f:
            linhas = list(csv.DictReader(f))
        self.assertEqual([(l['id'], l['variante'], l['custo_usd']) for l in linhas],
                         [('ficha-a', '1', '0.1340'), ('ficha-a', '2', '0.1340'), ('cena', '1', '0.1351')])
        self.assertEqual(ia.total_gasto(self.csv), (0.1340 * 2 + 0.1351, 3))

    def test_para_antes_do_limite(self):
        sessao, mensagens = Sessao(), []
        m = ia.ler_manifesto(self.manifesto)
        gasto = ia.gerar(m, [m['imagens'][0]], self.saida, self.csv, 'k', variantes=5, limite_usd=0.30,
                         sessao=sessao, escrever=mensagens.append)
        self.assertEqual(len(sessao.pedidos), 2)
        self.assertAlmostEqual(gasto, 0.268)
        self.assertIn('Limite de US$ 0.30 atingido', mensagens[-1])

    def test_resposta_generate_content_e_erros(self):
        m = ia.ler_manifesto(self.manifesto)
        sessao = Sessao(forma='generate')
        ia.gerar(m, [m['imagens'][2]], self.saida, self.csv, 'k', api='generate', sessao=sessao, escrever=lambda s: None)
        pedido = sessao.pedidos[0]
        self.assertIn('gemini-nano-banana-2.1:generateContent', pedido['url'])
        self.assertEqual(pedido['json']['generationConfig']['imageConfig'], {'aspectRatio': '1:1', 'imageSize': '1K'})
        self.assertTrue(os.path.exists(os.path.join(self.saida, 'objecto', 'objecto-1.png')))
        # Um erro da API não grava nada nem conta no custo.
        with self.assertRaisesMessage(ia.ErroImagens, 'A API respondeu 429'):
            ia.gerar(m, [m['imagens'][2]], self.saida, self.csv, 'k', sessao=Sessao(estado=429), escrever=lambda s: None)
        self.assertEqual(ia.total_gasto(self.csv)[1], 1)

    @override_settings(AWS_ACCESS_KEY_ID='a', AWS_SECRET_ACCESS_KEY='b', AWS_STORAGE_BUCKET_NAME='proenglish-media',
                       AWS_S3_CUSTOM_DOMAIN='media.exemplo.test', AWS_CLOUDFRONT_DOMAIN='')
    def test_publicar_envia_webp_para_o_bucket(self):
        os.makedirs(os.path.join(self.saida, 'aprovadas'))
        with open(os.path.join(self.saida, 'aprovadas', 'ficha-a.png'), 'wb') as f:
            f.write(png())
        cliente = mock.Mock()
        with mock.patch('apps.core.armazenamento.cliente', return_value=cliente):
            url = ia.publicar(self.saida, 'ficha-a')
        self.assertEqual(url, 'https://media.exemplo.test/conteudo/imagens/ficha-a.webp')
        args = cliente.put_object.call_args.kwargs
        self.assertEqual((args['Bucket'], args['Key'], args['ContentType']),
                         ('proenglish-media', 'conteudo/imagens/ficha-a.webp', 'image/webp'))
        self.assertEqual(Image.open(io.BytesIO(args['Body'])).format, 'WEBP')
        with self.assertRaisesMessage(ia.ErroImagens, 'ainda não foi aprovada'):
            ia.publicar(self.saida, 'cena')

    def test_comando_simular_e_sem_chave(self):
        saida = io.StringIO()
        call_command('gerar_imagens', self.manifesto, simular=True, variantes=2, stdout=saida)
        self.assertIn('3 imagens × 2 variantes: cerca de US$ 0.61', saida.getvalue())
        with mock.patch('apps.courses.management.commands.gerar_imagens.config', return_value=''):
            with self.assertRaisesMessage(CommandError, 'Falta GEMINI_API_KEY'):
                call_command('gerar_imagens', self.manifesto, saida=self.saida, registo=self.csv)
        with self.assertRaisesMessage(CommandError, 'não estão no manifesto: nada'):
            call_command('gerar_imagens', self.manifesto, ids='nada', simular=True)
