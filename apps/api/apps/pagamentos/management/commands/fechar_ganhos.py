"""
Fecho mensal dos ganhos dos professores (cron, dia 1 às 03:00 de Luanda), idempotente:

    python manage.py fechar_ganhos [--mes AAAA-MM] [--sem-avisos]

Por omissão fecha o mês anterior (hora de Luanda). Cria/actualiza um GanhoMensal por
professor; nunca altera linhas já pagas. Avisa cada professor (in-app, uma vez por mês).
Regras em apps/pagamentos/ganhos.py.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.pagamentos import ganhos


class Command(BaseCommand):
    help = 'Calcula os ganhos dos professores de um mês (por omissão o anterior). Idempotente.'

    def add_arguments(self, parser):
        parser.add_argument('--mes', help='Mês a fechar, AAAA-MM (por omissão o mês anterior).')
        parser.add_argument('--sem-avisos', action='store_true',
                            help='Não envia o aviso in-app aos professores.')

    def handle(self, *args, **options):
        try:
            mes = ganhos.ler_mes(options['mes']) if options.get('mes') else ganhos.mes_anterior(ganhos.hoje())
        except ValueError as e:
            raise CommandError(str(e))
        if mes >= ganhos.primeiro_dia(ganhos.hoje()):
            raise CommandError('Só é possível fechar meses já terminados.')
        r = ganhos.fechar_mes(mes, notificar=not options['sem_avisos'])
        c = r.calculo
        self.stdout.write(
            f'{ganhos.nome_mes(mes)}: receita {ganhos.formatar_kz(c.receita_kz)}, '
            f'bolo {ganhos.percentagem()}% = {ganhos.formatar_kz(c.bolo_kz)}, '
            f'{len(c.professores)} professor(es), {c.segundos_total // 60} min de alunos pagantes')
        for prof_id, t in sorted(c.professores.items(), key=lambda kv: -c.valores[kv[0]]):
            self.stdout.write(f'  - {prof_id}: {t.segundos // 60} min, {len(t.alunos)} aluno(s), '
                              f'quota {c.quotas[prof_id]}, {ganhos.formatar_kz(c.valores[prof_id])}')
        self.stdout.write(f'criados {r.criados}, actualizados {r.actualizados}, removidos {r.removidos}, '
                          f'já pagos (inalterados) {r.ja_pagos}, avisos {r.notificados}')
