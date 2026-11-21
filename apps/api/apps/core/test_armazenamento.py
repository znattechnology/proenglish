"""Armazenamento no Cloudflare R2 (compatível com S3): cliente, URLs pré-assinados e endereços públicos."""
from urllib.parse import urlparse

from django.test import SimpleTestCase, override_settings

from apps.core import armazenamento

R2 = dict(AWS_ACCESS_KEY_ID='chave-de-teste', AWS_SECRET_ACCESS_KEY='segredo-de-teste',
          AWS_STORAGE_BUCKET_NAME='proenglish-media', AWS_S3_REGION_NAME='auto',
          AWS_S3_ENDPOINT_URL='https://conta123.r2.cloudflarestorage.com',
          AWS_S3_CUSTOM_DOMAIN='media.exemplo.test', AWS_CLOUDFRONT_DOMAIN='')


class ArmazenamentoTests(SimpleTestCase):

    @override_settings(**R2)
    def test_r2_assina_para_o_endpoint_da_conta_com_v4(self):
        url = armazenamento.cliente().generate_presigned_url(
            'put_object', Params={'Bucket': 'proenglish-media', 'Key': 'videos/a.mp4', 'ContentType': 'video/mp4'},
            ExpiresIn=600)
        partes = urlparse(url)
        self.assertTrue(partes.netloc.endswith('conta123.r2.cloudflarestorage.com'), url)
        self.assertIn('videos/a.mp4', partes.path)
        self.assertIn('X-Amz-Algorithm=AWS4-HMAC-SHA256', url)
        self.assertIn('auto', url)  # a região do R2 vai na credencial assinada

    @override_settings(**dict(R2, AWS_S3_ENDPOINT_URL='', AWS_S3_REGION_NAME='eu-west-1'))
    def test_sem_endpoint_continua_a_ser_a_amazon(self):
        url = armazenamento.cliente().generate_presigned_url(
            'put_object', Params={'Bucket': 'proenglish-media', 'Key': 'x.png'}, ExpiresIn=60)
        self.assertIn('amazonaws.com', urlparse(url).netloc)

    @override_settings(**R2)
    def test_url_publico_usa_o_dominio_do_bucket(self):
        self.assertEqual(armazenamento.url_publico('imagens/nuno.webp'), 'https://media.exemplo.test/imagens/nuno.webp')
        self.assertEqual(armazenamento.url_publico('/imagens/x.webp'), 'https://media.exemplo.test/imagens/x.webp')

    @override_settings(**dict(R2, AWS_CLOUDFRONT_DOMAIN='https://cdn.exemplo.test/'))
    def test_cdn_tem_prioridade(self):
        self.assertEqual(armazenamento.url_publico('a.mp4'), 'https://cdn.exemplo.test/a.mp4')

    @override_settings(**R2)
    def test_configurado(self):
        self.assertTrue(armazenamento.configurado())
        with self.settings(AWS_SECRET_ACCESS_KEY=''):
            self.assertFalse(armazenamento.configurado())
