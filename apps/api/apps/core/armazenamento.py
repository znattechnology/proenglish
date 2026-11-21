"""
Armazenamento de ficheiros (vídeos, imagens, áudio, materiais) num bucket compatível com S3.

Em produção é o Cloudflare R2. O R2 fala a API do S3, por isso usa-se o boto3 com:
  AWS_S3_ENDPOINT_URL   https://<id da conta>.r2.cloudflarestorage.com
  AWS_S3_REGION_NAME    auto
  AWS_S3_CUSTOM_DOMAIN  o domínio público do bucket (media.<domínio>, ou pub-….r2.dev para testes)
Sem AWS_S3_ENDPOINT_URL, continua a funcionar com o S3 da Amazon.

Todos os módulos criam o cliente e os endereços públicos por aqui, para não haver um sítio
esquecido a apontar para a Amazon.
"""
from django.conf import settings


def configurado():
    """Há credenciais e bucket para enviar ficheiros?"""
    return bool(getattr(settings, 'AWS_ACCESS_KEY_ID', '') and getattr(settings, 'AWS_SECRET_ACCESS_KEY', '')
                and getattr(settings, 'AWS_STORAGE_BUCKET_NAME', ''))


def cliente():
    """Cliente S3 (boto3) para o bucket configurado: R2 se houver AWS_S3_ENDPOINT_URL."""
    import boto3
    from botocore.config import Config

    opcoes = {
        'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
        'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        'region_name': getattr(settings, 'AWS_S3_REGION_NAME', '') or 'us-east-1',
        # Os URLs pré-assinados do R2 só aceitam a assinatura v4.
        'config': Config(signature_version='s3v4'),
    }
    endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', '')
    if endpoint:
        opcoes['endpoint_url'] = endpoint
    return boto3.client('s3', **opcoes)


def dominio_publico():
    """'https://media.exemplo.ao' (sem barra no fim): CDN se houver, senão o domínio público do bucket."""
    dominio = getattr(settings, 'AWS_CLOUDFRONT_DOMAIN', '') or getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '')
    if not dominio:
        return ''
    if not dominio.startswith('http'):
        dominio = f'https://{dominio}'
    return dominio.rstrip('/')


def url_publico(chave):
    """O endereço público de um objecto do bucket."""
    return f'{dominio_publico()}/{chave.lstrip("/")}'
