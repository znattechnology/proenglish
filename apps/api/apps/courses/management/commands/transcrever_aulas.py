"""
Transcreve os vídeos das aulas que estão à espera (ffmpeg + Whisper) e propõe as frases da aula.

    python manage.py transcrever_aulas                 # pendentes (e presas há mais de 2 h), até 20
    python manage.py transcrever_aulas --limite 5
    python manage.py transcrever_aulas --incluir-erros # tenta outra vez as que deram erro
    python manage.py transcrever_aulas --aula <id> [--forcar]
    python manage.py transcrever_aulas --listar        # só mostra o que faria

Idempotente: as aulas já transcritas (do mesmo vídeo) e as transcrições escritas à mão ficam como
estão (excepto --aula <id> --forcar). Pode correr de hora a hora no cron:
    0 * * * * cd /app && python manage.py transcrever_aulas --limite 20
Custo: o Whisper cobra por minuto de áudio (~0,006 USD/min: ~0,36 USD por hora de vídeo).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.courses import transcricao


class Command(BaseCommand):
    help = 'Transcreve os vídeos das aulas pendentes (ffmpeg + Whisper) e propõe as frases da aula.'

    def add_arguments(self, parser):
        parser.add_argument('--aula', help='Só esta aula (id)')
        parser.add_argument('--forcar', action='store_true', help='Com --aula: transcreve mesmo que já esteja feita ou seja manual')
        parser.add_argument('--incluir-erros', action='store_true', help='Tenta outra vez as que deram erro')
        parser.add_argument('--limite', type=int, default=20, help='Máximo de aulas nesta execução (20)')
        parser.add_argument('--listar', action='store_true', help='Só lista as aulas, sem transcrever')

    def handle(self, *args, **opts):
        if opts['forcar'] and not opts['aula']:
            raise CommandError('--forcar só com --aula <id>.')
        ids = [opts['aula']] if opts['aula'] else transcricao.pendentes(incluir_erros=opts['incluir_erros'])
        ids = ids[:max(0, opts['limite'])]
        if not ids:
            self.stdout.write('Nada para transcrever.')
            return
        if opts['listar']:
            for pk in ids:
                self.stdout.write(str(pk))
            self.stdout.write(f'{len(ids)} aula(s).')
            return
        contagem = {}
        for pk in ids:
            if opts['aula'] and opts['forcar']:
                from apps.courses.models import Chapter
                ch = Chapter.objects.filter(pk=pk).first()
                if ch is None:
                    raise CommandError('Aula não encontrada.')
                transcricao._gravar_estado(ch.pk, estado=transcricao.PENDENTE, video=ch.video, forcar=True)
            resultado = transcricao.transcrever(pk, forcar=bool(opts['forcar']))
            contagem[resultado] = contagem.get(resultado, 0) + 1
            self.stdout.write(f'{pk}: {resultado}')
        self.stdout.write(self.style.SUCCESS(', '.join(f'{k}: {v}' for k, v in sorted(contagem.items()))))
