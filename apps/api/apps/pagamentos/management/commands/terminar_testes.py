"""
Períodos de teste grátis (cron, de hora a hora), idempotente:

    python manage.py terminar_testes [--dry-run]

1. Aviso (in-app + email) 2 dias antes do fim do teste, uma vez por teste.
2. Testes terminados sem pagamento voltam ao plano Gratuito (o progresso fica) e o
   aluno é avisado. Quem pagou durante o teste já não está em teste.
"""

from django.core.management.base import BaseCommand

from apps.pagamentos.teste import avisar_testes_a_terminar, terminar_testes


class Command(BaseCommand):
    help = 'Avisa os testes grátis que terminam em 2 dias e volta ao Gratuito os que terminaram sem pagamento.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria feito sem alterar nada.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        prefixo = '[dry-run] ' if dry else ''
        avisos = avisar_testes_a_terminar(dry_run=dry)
        terminados = terminar_testes(dry_run=dry)
        self.stdout.write(f'{prefixo}avisos de fim do teste: {len(avisos)}')
        self.stdout.write(f'{prefixo}testes terminados (voltaram ao Gratuito): {terminados}')
