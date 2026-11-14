"""
Conversas por voz à espera da chamada verificada do Vapi (apps/practice/conversa/verificacao.py):
- as que ficaram «em curso» muito depois do limite (separador fechado, sem terminar/ nem webhook)
  passam a esperar pelo Vapi;
- as que esperam pedem a chamada ao Vapi (GET /call) e, se terminou, fecham, cobram e avaliam;
- passado o prazo (ESPERA_MAXIMA_MINUTOS) sem chamada verificada, fecham sem nota.
Correr de 5 em 5 minutos (cron): python manage.py verificar_conversas_vapi
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verifica no Vapi as conversas por voz que ainda esperam pela chamada (cobra e avalia).'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=50, help='Máximo de sessões por execução.')

    def handle(self, *args, **options):
        from apps.practice.conversa import verificacao
        from apps.practice.models import VapiSession
        abandonadas = verificacao.fechar_abandonadas()
        tratadas, avaliadas, expiradas = 0, 0, 0
        for pk in list(verificacao.pendentes().order_by('created_at').values_list('pk', flat=True)[:options['limite']]):
            tratadas += 1
            try:
                s = verificacao.resolver(pk, forcar=True)
            except Exception as e:  # uma sessão com problemas não pára as outras
                self.stderr.write(f'Sessão {pk}: {type(e).__name__}')
                continue
            if s.status == VapiSession.STATUS_AVALIADA:
                avaliadas += 1
            elif (s.full_session_data or {}).get('fechada_sem_vapi') or s.status == VapiSession.STATUS_SEM_AVALIACAO:
                expiradas += 1
        self.stdout.write(f'{abandonadas} abandonada(s); {tratadas} à espera do Vapi: {avaliadas} avaliada(s), '
                          f'{expiradas} fechada(s) sem nota.')
