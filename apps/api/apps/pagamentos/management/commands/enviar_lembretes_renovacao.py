"""
Tarefa de renovação (cron, de hora a hora), idempotente:

    python manage.py enviar_lembretes_renovacao [--dry-run]

1. lembretes: emite o sinal ``lembrete_renovacao`` (D3 a <= 72 h, D0 a <= 24 h do
   fim), uma vez por período. Corre ANTES de expirar, para o D0 sair sempre.
2. expirar_subscricoes: subscrições pagas terminadas voltam ao plano Gratuito.
3. pagamentos pendentes fora de prazo são resolvidos (libertam códigos promocionais).
"""

from django.core.management.base import BaseCommand

from apps.pagamentos.renovacao import expirar_subscricoes, enviar_lembretes
from apps.pagamentos.services import resolver_pendentes_caducados


class Command(BaseCommand):
    help = ('Envia lembretes de renovação (D-3 e D-0), expira subscrições pagas terminadas '
            'e resolve pagamentos pendentes fora de prazo. Seguro de correr de hora a hora.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra o que seria feito sem alterar nada.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        prefixo = '[dry-run] ' if dry else ''
        lembretes = enviar_lembretes(dry_run=dry)
        expiradas = expirar_subscricoes(dry_run=dry)
        pendentes = 0 if dry else resolver_pendentes_caducados()
        self.stdout.write(f'{prefixo}lembretes: {len(lembretes)} enviado(s)')
        for sub, tipo in lembretes:
            self.stdout.write(f'  - {tipo} subscrição {sub.pk} (fim {sub.expires_at:%Y-%m-%d %H:%M} UTC)')
        self.stdout.write(f'{prefixo}expirar_subscricoes: {expiradas} subscrição(ões) voltaram ao Gratuito')
        self.stdout.write(f'{prefixo}pagamentos pendentes fora de prazo resolvidos: {pendentes}')
