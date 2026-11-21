"""
Apaga as gravações dos exames orais com mais de 12 meses (RETENCAO_GRAVACOES_DIAS em
apps/practice/conversa/exame.py) e repete os pedidos de apagar que o Vapi ainda não confirmou:
pede ao Vapi que apague a chamada e esquece o URL (no exame e na sessão).
Correr uma vez por dia (cron): python manage.py apagar_gravacoes_exames
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Apaga as gravações dos exames orais com mais de 12 meses e repete os pedidos pendentes.'

    def handle(self, *args, **options):
        from apps.practice.conversa.exame import RETENCAO_GRAVACOES_DIAS, apagar_gravacoes_antigas
        n = apagar_gravacoes_antigas()
        self.stdout.write(f'{n} gravação(ões) tratada(s) (mais de {RETENCAO_GRAVACOES_DIAS} dias ou pedidos pendentes).')
