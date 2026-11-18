"""
Carrega num curso em vídeo (e no curso de laboratório que o acompanha) as unidades escritas em
docs/conteudo: aulas, questionário, lições de laboratório e conversas com o tutor.

    ./venv/bin/python manage.py carregar_unidades_curso <id do curso em vídeo> \
        --laboratorio <id do curso de laboratório> \
        docs/conteudo/c1/unidade-01 docs/conteudo/c1/unidade-02 … docs/conteudo/c1/revisao-1

As pastas são carregadas pela ordem em que são dadas (é a ordem das secções no curso). Os dois
cursos têm de existir (criam-se na área do professor) e ser do mesmo professor. Sem --laboratorio,
carrega só as aulas, o questionário e as conversas.

  --verificar   lê e valida as pastas e diz o que carregaria, sem escrever nada (não precisa de curso:
                use "-" no lugar do id);
  --forcar      substitui também as lições com respostas de alunos e os questionários com tentativas.

Pode correr várias vezes: actualiza o que já existe (ver apps/courses/carregar_unidades.py).
O exame oral de cada curso carrega-se à parte, com carregar_exame_curso.
"""
import io

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses import carregar_unidades as cu
from apps.courses.models import Course


class Command(BaseCommand):
    help = 'Carrega as unidades de docs/conteudo num curso: aulas, questionário, laboratório e conversas.'

    def add_arguments(self, parser):
        parser.add_argument('curso')
        parser.add_argument('pastas', nargs='+')
        parser.add_argument('--laboratorio')
        parser.add_argument('--verificar', action='store_true')
        parser.add_argument('--forcar', action='store_true')

    def handle(self, *args, **o):
        try:
            unidades = [(pasta, cu.ler_pasta(pasta)) for pasta in o['pastas']]
        except cu.ErroDeConteudo as e:
            raise CommandError(str(e))
        codigos = [a['codigo'] for _, d in unidades for a in d['aulas']]
        repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
        if repetidos:
            raise CommandError('Códigos de aula repetidos entre as pastas: ' + ', '.join(repetidos))
        if o['verificar']:
            for _, d in unidades:
                self.stdout.write(self._linha(d, sum(len(l['exercicios']) for l in d['licoes'])))
            self.stdout.write(self.style.SUCCESS(f'{len(unidades)} pastas válidas. Nada foi escrito.'))
            return

        curso = Course.objects.filter(pk=o['curso'], course_type='video').first()
        if curso is None:
            raise CommandError('Curso em vídeo não encontrado.')
        laboratorio = None
        if o['laboratorio']:
            laboratorio = Course.objects.filter(pk=o['laboratorio'], course_type='practice').first()
            if laboratorio is None:
                raise CommandError('Curso de laboratório não encontrado.')
            if laboratorio.teacher_id != curso.teacher_id:
                raise CommandError('Os dois cursos têm de ser do mesmo professor.')

        avisos, sem_audio = [], 0
        try:
            with transaction.atomic():
                for pasta, d in unidades:
                    aulas, aula_quiz, a = cu.carregar_video(curso, d, forcar=o['forcar'])
                    avisos += a
                    exercicios = 0
                    if laboratorio is not None:
                        exercicios, s, a = cu.carregar_laboratorio(laboratorio, d, aulas, aula_quiz, forcar=o['forcar'])
                        sem_audio += s
                        avisos += a
                    if d['tutor']:
                        call_command('carregar_conversas_curso', str(curso.pk), d['tutor'], exigir_aulas=True,
                                     stdout=io.StringIO())
                    self.stdout.write(self._linha(d, exercicios if laboratorio is not None else None))
        except cu.ErroDeConteudo as e:
            raise CommandError(str(e))
        for aviso in avisos:
            self.stdout.write(self.style.WARNING(aviso))
        if sem_audio:
            self.stdout.write(self.style.WARNING(
                f'{sem_audio} exercícios de escuta e de pronúncia ainda não têm áudio.'))
        self.stdout.write(self.style.SUCCESS(f'{len(unidades)} pastas carregadas em "{curso.title}".'))

    @staticmethod
    def _linha(d, exercicios):
        partes = [f'{len(d["aulas"])} aulas', 'questionário' if d['questionario'] else 'sem questionário']
        if exercicios is not None:
            partes.append(f'{len(d["licoes"])} lições ({exercicios} exercícios)')
        partes.append('conversas' if d['tutor'] else 'sem conversas')
        return f'{d["titulo"]}: ' + ', '.join(partes)

