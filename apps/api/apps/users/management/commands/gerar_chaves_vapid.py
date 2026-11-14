"""
Gera um par de chaves VAPID (P-256) para o Web Push.

    ./venv/bin/python manage.py gerar_chaves_vapid >> .env

Escreve as linhas VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY (base64url, formato
aceite pelo pywebpush e pelo PushManager.subscribe do navegador).
Atenção: trocar as chaves invalida as subscrições push existentes.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64url(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b'=').decode('ascii')


def gerar_par():
    privada = ec.generate_private_key(ec.SECP256R1())
    bytes_privada = privada.private_numbers().private_value.to_bytes(32, 'big')
    bytes_publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64url(bytes_publica), _b64url(bytes_privada)


class Command(BaseCommand):
    help = 'Gera um par de chaves VAPID para o Web Push (linhas para o .env).'

    def handle(self, *args, **options):
        publica, privada = gerar_par()
        self.stdout.write(f'VAPID_PUBLIC_KEY={publica}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={privada}')
