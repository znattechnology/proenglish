"""
Cria/actualiza o ChapterQuiz de todos os capítulos de questionário a partir do quiz_data
(os capítulos criados antes do signal não tinham ChapterQuiz e davam 404 ao aluno).

    ./venv/bin/python manage.py sincronizar_questionarios [--dry-run]

Idempotente: pode correr várias vezes.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.courses.models import Chapter, ChapterQuiz
from apps.courses.questionarios import perguntas_validas, sincronizar_questionario


class Command(BaseCommand):
    help = 'Cria/actualiza o ChapterQuiz dos capítulos de questionário a partir do quiz_data.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Só mostra o que faria.')

    def handle(self, *args, **opts):
        capitulos = (Chapter.objects.filter(Q(type='Quiz') | Q(quiz_enabled=True) | Q(quiz__isnull=False))
                     .select_related('section__course__teacher').distinct())
        criados = actualizados = sem_perguntas = 0
        for cap in capitulos:
            tinha = ChapterQuiz.objects.filter(chapter=cap).exists()
            if not perguntas_validas(cap.quiz_data):
                sem_perguntas += 1
            if opts['dry_run']:
                self.stdout.write(f'{cap.pk} {cap.title!r}: {"actualizar" if tinha else "criar"}')
                continue
            with transaction.atomic():
                quiz = sincronizar_questionario(cap)
            if quiz is not None and not tinha:
                criados += 1
            elif tinha:
                actualizados += 1
        self.stdout.write(self.style.SUCCESS(
            f'Capítulos: {capitulos.count()} | ChapterQuiz criados: {criados} | '
            f'verificados/actualizados: {actualizados} | sem perguntas: {sem_perguntas}'))
