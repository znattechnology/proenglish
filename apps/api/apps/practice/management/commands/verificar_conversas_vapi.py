"""
Conversas por voz à espera da chamada verificada do Vapi (apps/practice/conversa/verificacao.py):
- as que ficaram «em curso» muito depois do limite (separador fechado, sem terminar/ nem webhook)
  passam a esperar pelo Vapi;
- as que esperam pedem a chamada ao Vapi (GET /call) e, se terminou, fecham, cobram e avaliam;
- passado o prazo (ESPERA_MAXIMA_MINUTOS) sem chamada verificada, fecham sem nota;
- as que já podiam ser avaliadas e ficaram 'a_avaliar' há mais de 2 minutos (a thread da avaliação
  perdeu-se num reinício do worker do Gunicorn: servico.avaliacoes_paradas) são avaliadas agora,
  respeitando o bloqueio de servico.avaliar_pendente;
- os exames orais gravados ainda sem nota de pronúncia (exame.pronuncias_por_fazer): pede a gravação
  em falta ao Vapi e avalia a pronúncia (só com o Azure configurado).
Correr de 5 em 5 minutos (cron): python manage.py verificar_conversas_vapi
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verifica no Vapi as conversas por voz que ainda esperam pela chamada (cobra e avalia).'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=50, help='Máximo de sessões por execução.')
        parser.add_argument('--limite-paradas', type=int, default=10,
                            help='Máximo de avaliações paradas retomadas por execução (cada uma pode levar 60 s).')

    def handle(self, *args, **options):
        from apps.practice.conversa import webhook
        # Aqui nada vai para threads: morreriam com o processo do comando antes de acabar.
        with webhook.no_proprio_processo():
            self._handle(options)

    def _handle(self, options):
        from apps.practice.conversa import servico, verificacao
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
        retomadas = 0
        for pk in servico.avaliacoes_paradas(limite=options['limite_paradas']):
            try:
                s = servico.avaliar_pendente(pk)
            except Exception as e:
                self.stderr.write(f'Sessão {pk}: {type(e).__name__}')
                continue
            if s.status != VapiSession.STATUS_A_AVALIAR:
                retomadas += 1
        from apps.practice.conversa import exame
        try:
            pronuncias = exame.pronuncias_por_fazer(limite=options['limite_paradas'])
        except Exception as e:
            self.stderr.write(f'Pronúncia dos exames: {type(e).__name__}')
            pronuncias = 0
        self.stdout.write(f'{abandonadas} abandonada(s); {tratadas} à espera do Vapi: {avaliadas} avaliada(s), '
                          f'{expiradas} fechada(s) sem nota; {retomadas} avaliação(ões) parada(s) retomada(s); '
                          f'{pronuncias} pronúncia(s) de exame avaliada(s).')
