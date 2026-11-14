"""
Lembrete diário da meta de estudo. Correr a cada 15 minutos via cron:

    */15 * * * * cd /caminho/apps/api && ./venv/bin/python manage.py enviar_lembretes_meta

Idempotente: no máximo um lembrete por aluno e por dia (hora de Angola).
"""
from django.core.management.base import BaseCommand

from apps.practice.lembretes_meta import enviar_lembretes_meta, janela


class Command(BaseCommand):
    help = 'Envia o lembrete da meta diária aos alunos cuja hora de lembrete chegou (Africa/Luanda).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria enviado sem criar avisos.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        inicio, fim = janela()
        r = enviar_lembretes_meta(dry_run=dry)
        prefixo = '[dry-run] ' if dry else ''
        for user_id, title, body in r['enviados']:
            self.stdout.write(f'{prefixo}{user_id}: {title} / {body}')
        self.stdout.write(self.style.SUCCESS(
            f'{prefixo}Janela {inicio:%H:%M}-{fim:%H:%M} (Luanda): {len(r["enviados"])} lembrete(s), '
            f'{r["meta_cumprida"]} com a meta cumprida, {r["ja_enviados"]} já enviado(s) hoje.'
        ))
