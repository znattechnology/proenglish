"""
Course evaluation signals.

Handles automatic grade recalculation when evaluation events occur:
- Quiz attempt completed
- Automatic certificate generation when eligible

This module follows the established signal pattern from apps/users/signals.py
"""

import logging
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import StudentQuizAttempt, StudentCourseGrade, UserCourseProgress, CourseCertificate, Chapter

logger = logging.getLogger(__name__)


@receiver(post_save, sender=StudentQuizAttempt)
def on_quiz_attempt_saved(sender, instance, created, **kwargs):
    """
    Recalculate student grade when a quiz attempt is saved.

    Triggers:
    - New quiz attempt created (created=True)
    - Quiz attempt updated (e.g., completed)

    Only recalculates if:
    - Attempt is completed (is_completed=True)
    - Student and course can be determined

    The signal handler catches all exceptions to ensure quiz submission
    is never blocked by grade calculation failures.
    """
    # Skip if not completed - no point recalculating for incomplete attempts
    if not instance.is_completed:
        logger.debug(f"Quiz attempt {instance.id} not completed, skipping grade recalc")
        return

    # Skip if in raw mode (bulk inserts, migrations, loaddata)
    if kwargs.get('raw', False):
        logger.debug("Skipping grade recalc - raw mode")
        return

    try:
        # Get course from quiz -> chapter -> section -> course
        quiz = instance.chapter_quiz
        if not quiz:
            logger.warning(f"Quiz attempt {instance.id} has no chapter_quiz")
            return

        chapter = quiz.chapter
        if not chapter:
            logger.warning(f"Quiz {quiz.id} has no chapter")
            return

        section = chapter.section
        if not section:
            logger.warning(f"Chapter {chapter.id} has no section")
            return

        course = section.course
        if not course:
            logger.warning(f"Section {section.id} has no course")
            return

        user = instance.student
        if not user:
            logger.warning(f"Quiz attempt {instance.id} has no student")
            return

        # Determine change reason based on whether this is a new or updated attempt
        change_reason = 'quiz_completed' if created else 'quiz_retake'

        # Import here to avoid circular imports
        from .services.grade_calculator import GradeCalculatorService

        logger.info(
            f"Recalculating grade for user {user.id} ({user.email}) "
            f"in course {course.id} ({course.title}) "
            f"due to {change_reason}"
        )

        # Instantiate calculator and recalculate
        calculator = GradeCalculatorService(user=user, course=course)
        result = calculator.calculate_and_save(change_reason=change_reason)

        logger.info(
            f"Grade recalculated successfully: "
            f"{result.final_grade_percentage:.1f}% ({result.final_grade_letter})"
        )

    except Exception as e:
        # Log the error but DON'T raise - we don't want to break quiz submission
        # The grade will be calculated on-demand when user views grades page
        logger.error(
            f"Error recalculating grade after quiz attempt {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender=StudentCourseGrade)
def on_grade_saved_check_certificate(sender, instance, created, **kwargs):
    """
    Emite o certificado automaticamente quando a nota guardada fica elegível (o resto das regras,
    incluindo progresso a 100% e plano, está em apps.courses.certificados). A elegibilidade
    guardada só serve de filtro barato: emitir_certificado recalcula a nota com as regras actuais
    (sem gravar, para não disparar este signal outra vez) antes de emitir.
    """
    if not instance.is_eligible_for_certificate or kwargs.get('raw', False):
        return
    try:
        if CourseCertificate.objects.filter(user=instance.user, course=instance.course).exists():
            return
        from .certificados import emitir_se_elegivel
        emitir_se_elegivel(instance.user, instance.course, grade=instance)
    except Exception as e:
        # Nunca partir quem guardou a nota; o aluno pode pedir o certificado depois.
        logger.error(f"Error auto-generating certificate for grade {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender=UserCourseProgress)
def on_progress_complete_check_certificate(sender, instance, **kwargs):
    """
    Quando o progresso chega a 100%, recalcula a nota com as regras actuais e emite o certificado
    se o aluno cumprir tudo. Não se confia na elegibilidade guardada (podia vir de uma versão
    antiga do cálculo, sem o exame oral): só se salta o recálculo quando a nota guardada é da
    versão actual e não é elegível.
    """
    if instance.overallProgress < 100.0 or kwargs.get('raw', False):
        return
    try:
        if CourseCertificate.objects.filter(user=instance.user, course=instance.course).exists():
            return
        from .services.grade_calculator import GradeCalculatorService
        grade = StudentCourseGrade.objects.filter(user=instance.user, course=instance.course).first()
        if (grade is not None and not grade.is_eligible_for_certificate
                and (grade.calculation_version or 0) >= GradeCalculatorService.CALCULATION_VERSION):
            return
        from .certificados import emitir_se_elegivel
        emitir_se_elegivel(instance.user, instance.course)
    except Exception as e:
        logger.error(f"Error checking certificate on progress completion: {e}", exc_info=True)


@receiver(pre_save, sender=Chapter, dispatch_uid='visibilidade_capitulo_antes')
def on_chapter_pre_save_remember_visibility(sender, instance, **kwargs):
    """Guarda se a aula já era visível aos alunos (tinha vídeo) antes desta gravação."""
    if kwargs.get('raw', False):
        return
    from .ciclo import aula_visivel
    anterior = None
    if instance.pk and not instance._state.adding:
        anterior = Chapter.objects.filter(pk=instance.pk).only('type', 'video').first()
    instance._era_visivel = aula_visivel(anterior) if anterior is not None else None


@receiver(post_save, sender=Chapter, dispatch_uid='avisar_novo_capitulo')
def on_chapter_visible_notify_students(sender, instance, created, **kwargs):
    """
    Uma aula passa a estar visível (o vídeo foi confirmado pela primeira vez, ou foi criada já
    completa) num curso de vídeo publicado: avisa os alunos inscritos, depois do commit.
    Uma aula nova ainda sem vídeo não avisa ninguém (os alunos ainda não a vêem).
    """
    if kwargs.get('raw', False):
        return
    from .ciclo import aula_visivel
    if not aula_visivel(instance) or getattr(instance, '_era_visivel', None):
        return
    from django.db import transaction
    from .avisos import avisar_novo_capitulo

    chapter_id = instance.pk
    transaction.on_commit(lambda: avisar_novo_capitulo(chapter_id))


@receiver(post_save, sender=Chapter, dispatch_uid='sincronizar_questionario_do_capitulo')
def on_chapter_saved_sync_quiz(sender, instance, created, **kwargs):
    """
    O professor guarda o questionário em Chapter.quiz_data; as tentativas usam ChapterQuiz.
    Cria/actualiza/desactiva o ChapterQuiz depois do commit (ver apps.courses.questionarios).
    """
    if kwargs.get('raw', False):
        return
    if instance.type != 'Quiz' and not instance.quiz_enabled:
        from .models import ChapterQuiz
        if not ChapterQuiz.objects.filter(chapter_id=instance.pk, is_active=True).exists():
            return
    from django.db import transaction

    chapter_id = instance.pk

    def _sincronizar():
        try:
            from .questionarios import sincronizar_questionario
            chapter = Chapter.objects.select_related('section__course__teacher').filter(pk=chapter_id).first()
            if chapter is not None:
                sincronizar_questionario(chapter)
        except Exception:
            logger.exception('Falha ao sincronizar o questionário do capítulo %s', chapter_id)

    transaction.on_commit(_sincronizar)


def _recalcular_progresso_do_curso(course_id):
    """
    overallProgress guardado = capítulos concluídos / capítulos do curso. Quando o professor
    acrescenta ou apaga capítulos o total muda: recalcula para todos os alunos do curso.
    """
    from django.db.models import Count, Q
    from .models import Course

    if not Course.objects.filter(pk=course_id).exists():
        return
    from .ciclo import q_aula_visivel

    # Só as aulas que os alunos vêem contam (uma aula sem vídeo está escondida).
    total = Chapter.objects.filter(q_aula_visivel(), section__course_id=course_id).count()
    progressos = (UserCourseProgress.objects.filter(course_id=course_id)
                  .annotate(feitos=Count('chapter_progress', filter=Q(chapter_progress__completed=True,
                                                                     chapter_progress__chapter__section__course_id=course_id)
                                                                   & q_aula_visivel('chapter_progress__chapter__'))))
    for p in progressos:
        novo = min(100.0, (p.feitos / total) * 100) if total else 0.0
        if abs((p.overallProgress or 0.0) - novo) < 1e-9:
            continue
        p.overallProgress = novo
        if novo >= 100.0 and not p.completion_date:
            from django.utils import timezone
            p.completion_date = timezone.now()
        elif novo < 100.0 and p.completion_date:
            p.completion_date = None
        # save() (não update) para o signal do certificado correr quando chega a 100%.
        p.save(update_fields=['overallProgress', 'completion_date'])


def _agendar_recalculo_progresso(instance, **kwargs):
    if kwargs.get('raw', False):
        return
    from django.db import transaction
    try:
        course_id = instance.section.course_id
    except Exception:
        return
    transaction.on_commit(lambda: _recalcular_seguro(course_id))


def _recalcular_seguro(course_id):
    try:
        _recalcular_progresso_do_curso(course_id)
    except Exception:
        logger.exception('Falha ao recalcular o progresso do curso %s', course_id)


@receiver(post_save, sender=Chapter, dispatch_uid='progresso_capitulo_criado')
def on_chapter_created_recalc_progress(sender, instance, created, **kwargs):
    """O total de aulas visíveis muda quando se cria uma aula ou quando ela ganha/perde o vídeo."""
    from .ciclo import aula_visivel
    era = getattr(instance, '_era_visivel', None)
    if created or (era is not None and era != aula_visivel(instance)):
        _agendar_recalculo_progresso(instance, **kwargs)


@receiver(post_delete, sender=Chapter, dispatch_uid='progresso_capitulo_apagado')
def on_chapter_deleted_recalc_progress(sender, instance, **kwargs):
    _agendar_recalculo_progresso(instance, **kwargs)
