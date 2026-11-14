"""
Competições: avisa os participantes quando começam e, quando terminam, grava a
classificação final e atribui os prémios (ver apps/practice/competicoes.py). De hora a hora:

    7 * * * * cd /caminho/apps/api && ./venv/bin/python manage.py fechar_competicoes

Idempotente: cada competição é avisada uma vez e fechada uma vez.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.practice import competicoes
from apps.practice.models import Competition


class Command(BaseCommand):
    help = 'Avisa o início das competições e fecha as que terminaram (prémios e avisos aos vencedores).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria feito sem alterar nada.')

    def handle(self, *args, **options):
        agora = timezone.now()
        if options['dry_run']:
            a = Competition.objects.filter(inicio_notificado=False, start_date__lte=agora, end_date__gt=agora)
            f = Competition.objects.filter(fechada_em__isnull=True, end_date__lte=agora)
            for c in a:
                self.stdout.write(f'[dry-run] começa: {c.pk} {c.title}')
            for c in f:
                self.stdout.write(f'[dry-run] fecha: {c.pk} {c.title}')
            self.stdout.write(self.style.SUCCESS(f'[dry-run] {a.count()} a avisar, {f.count()} a fechar.'))
            return
        avisadas, fechadas = competicoes.processar(agora)
        self.stdout.write(self.style.SUCCESS(f'{avisadas} competição(ões) avisada(s), {fechadas} fechada(s).'))
