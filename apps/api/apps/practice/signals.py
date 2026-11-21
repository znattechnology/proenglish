"""
Practice app evaluation signals.

Handles automatic grade recalculation when:
- Challenge progress is completed (practice exercises)
- Vapi conversation session is saved

This module follows the established signal pattern from apps/users/signals.py
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ChallengeProgress, VapiSession

logger = logging.getLogger(__name__)


def _get_courses_for_challenge(challenge_progress):
    """
    Video course(s) a practice challenge counts towards: courses whose chapters
    (Chapter.practice_lesson) or chapter quizzes (ChapterQuiz.practice_lesson) link to the
    challenge's lesson, where the user is enrolled.

    Returns list of (User, Course) tuples.
    """
    from apps.courses.models import CourseEnrollment
    from apps.courses.services.grade_calculator import cursos_da_licao_pratica

    challenge = challenge_progress.challenge
    if not challenge or not challenge.lesson_id:
        return []

    user = challenge_progress.user
    return [(user, course) for course in cursos_da_licao_pratica(challenge.lesson_id)
            if CourseEnrollment.objects.filter(user=user, course=course).exists()]


def _get_courses_for_vapi_session(vapi_session):
    """
    The video course a conversation counts towards (only one): the course of its situation
    (practice.Situacao.curso) or full_session_data['config']['curso_id'], if the user is enrolled.
    General conversations (no course) don't change any course grade.

    Returns list of (User, Course) tuples.
    """
    from apps.courses.models import CourseEnrollment
    from apps.courses.services.grade_calculator import curso_da_sessao

    course = curso_da_sessao(vapi_session)
    if course is None:
        return []
    user = vapi_session.user
    if not CourseEnrollment.objects.filter(user=user, course=course).exists():
        return []
    return [(user, course)]


@receiver(post_save, sender=ChallengeProgress)
def on_challenge_completed(sender, instance, created, **kwargs):
    """
    Recalculate student grade when a practice challenge is completed.

    Only triggers if:
    - Challenge is marked as completed
    - Challenge's lesson is linked to a video course chapter
    - User is enrolled in that course

    The signal handler catches all exceptions to ensure challenge
    completion is never blocked by grade calculation failures.
    """
    # Skip if not completed - no point recalculating
    if not instance.completed:
        logger.debug(f"Challenge progress {instance.id} not completed, skipping")
        return

    # Skip raw mode (migrations, loaddata)
    if kwargs.get('raw', False):
        logger.debug("Skipping grade recalc - raw mode")
        return

    try:
        # Import here to avoid circular imports
        from apps.courses.services.grade_calculator import GradeCalculatorService

        courses = _get_courses_for_challenge(instance)

        if not courses:
            logger.debug(
                f"Challenge {instance.challenge_id} not linked to any enrolled courses"
            )
            return

        for user, course in courses:
            logger.info(
                f"Recalculating grade for user {user.id} ({user.email}) "
                f"in course {course.id} ({course.title}) "
                f"due to practice_completed"
            )

            calculator = GradeCalculatorService(user=user, course=course)
            result = calculator.calculate_and_save(change_reason='practice_completed')

            logger.info(
                f"Grade recalculated: {result.final_grade_percentage:.1f}% "
                f"({result.final_grade_letter})"
            )

    except Exception as e:
        # Log but don't raise - challenge completion should never fail
        logger.error(
            f"Error recalculating grade after challenge {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender=VapiSession)
def on_vapi_session_saved(sender, instance, created, **kwargs):
    """
    Recalculate student grade when a Vapi conversation session is saved.

    Only triggers if:
    - This is a new session (created=True) - avoids duplicate recalcs on updates
    - Session has an overall_score > 0 (is complete, not empty)
    - The conversation belongs to a course the user is enrolled in

    The signal handler catches all exceptions to ensure Vapi session
    saving is never blocked by grade calculation failures.
    """
    # Only trigger on creation to avoid duplicate recalculations
    if not created:
        logger.debug(f"Vapi session {instance.session_id} updated, skipping recalc")
        return

    # Skip if session doesn't have a meaningful score
    if instance.overall_score is None or instance.overall_score == 0:
        logger.debug(
            f"Vapi session {instance.session_id} has no score, skipping recalc"
        )
        return

    # Skip raw mode (migrations, loaddata)
    if kwargs.get('raw', False):
        logger.debug("Skipping grade recalc - raw mode")
        return

    # Sessões da conversa/ nascem "em curso" (nota 0): a nota é recalculada ao terminar.
    if instance.status != VapiSession.STATUS_AVALIADA:
        return

    recalcular_notas_conversa(instance)


def recalcular_notas_conversa(instance):
    """Recalcula as notas dos cursos a que esta sessão de conversa conta (nunca levanta excepções)."""
    try:
        # Import here to avoid circular imports
        from apps.courses.services.grade_calculator import GradeCalculatorService

        courses = _get_courses_for_vapi_session(instance)

        if not courses:
            logger.debug(
                f"Vapi session {instance.session_id} not tied to an enrolled course"
            )
            return

        for user, course in courses:
            logger.info(
                f"Recalculating grade for user {user.id} ({user.email}) "
                f"in course {course.id} ({course.title}) "
                f"due to conversation_session (level: {instance.level}, "
                f"score: {instance.overall_score})"
            )

            calculator = GradeCalculatorService(user=user, course=course)
            result = calculator.calculate_and_save(change_reason='conversation_session')

            logger.info(
                f"Grade recalculated: {result.final_grade_percentage:.1f}% "
                f"({result.final_grade_letter})"
            )

    except Exception as e:
        # Log but don't raise - Vapi session save should never fail
        logger.error(
            f"Error recalculating grade after Vapi session {instance.session_id}: {e}",
            exc_info=True
        )
