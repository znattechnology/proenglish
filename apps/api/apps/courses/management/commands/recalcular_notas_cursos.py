"""
Recalcula as notas guardadas (StudentCourseGrade) com as regras actuais (fase 6: exame oral,
frases do curso, conversas, estudo). As notas também se recalculam sozinhas quando o aluno abre
a página das notas ou faz algo que conta; isto é para actualizar tudo de uma vez.

  python manage.py recalcular_notas_cursos [--curso <id>] [--so-antigas]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Recalcula as notas dos cursos em vídeo com as regras actuais.'

    def add_arguments(self, parser):
        parser.add_argument('--curso', help='Só este curso (id)')
        parser.add_argument('--so-antigas', action='store_true',
                            help='Só as notas calculadas com uma versão anterior do cálculo')

    def handle(self, *args, **options):
        from apps.courses.models import CourseEnrollment, StudentCourseGrade
        from apps.courses.services.grade_calculator import GradeCalculatorService

        inscricoes = CourseEnrollment.objects.filter(course__course_type='video').select_related('user', 'course')
        if options.get('curso'):
            inscricoes = inscricoes.filter(course_id=options['curso'])
        if options.get('so_antigas'):
            actuais = StudentCourseGrade.objects.filter(
                calculation_version=GradeCalculatorService.CALCULATION_VERSION).values_list('user_id', 'course_id')
            actuais = set(actuais)
        else:
            actuais = set()
        n = falhas = 0
        for insc in inscricoes.iterator():
            if (insc.user_id, insc.course_id) in actuais:
                continue
            try:
                GradeCalculatorService(insc.user, insc.course).calculate_and_save(change_reason='recalculation')
                n += 1
            except Exception as e:  # um aluno com dados estranhos não pára o resto
                falhas += 1
                self.stderr.write(f'Falhou {insc.user_id} / {insc.course_id}: {e}')
        self.stdout.write(f'{n} nota(s) recalculada(s), {falhas} falha(s).')
