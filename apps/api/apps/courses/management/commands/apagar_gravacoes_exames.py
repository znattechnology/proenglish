"""
Apaga as gravações dos exames orais com mais de 12 meses (RETENCAO_GRAVACOES_DIAS em
apps/practice/conversa/exame.py): pede ao Vapi que apague a chamada e esquece o URL.
Correr uma vez por dia (cron): python manage.py apagar_gravacoes_exames
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Apaga as gravações dos exames orais com mais de 12 meses.'

    def handle(self, *args, **options):
        from apps.practice.conversa.exame import RETENCAO_GRAVACOES_DIAS, apagar_gravacoes_antigas
        n = apagar_gravacoes_antigas()
        self.stdout.write(f'{n} gravação(ões) com mais de {RETENCAO_GRAVACOES_DIAS} dias apagada(s).')
