"""
Matrícula de um utilizador num curso (enrollment + progresso inicial).

Usado por ``create_transaction`` (video_courses). O acesso ao curso vem do plano
(Course.user_has_access); a inscrição não tem custo próprio.
"""

from django.db import transaction
from django.utils import timezone

from .models import CourseEnrollment, UserCourseProgress, ChapterProgress


@transaction.atomic
def matricular_em_curso(user, course):
    """Cria (idempotentemente) enrollment, progresso do curso e dos capítulos.

    Returns:
        (enrollment, progress)
    """
    enrollment, _ = CourseEnrollment.objects.get_or_create(user=user, course=course)

    progress, _ = UserCourseProgress.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            'enrollmentDate': timezone.now(),
            'overallProgress': 0.0,
        },
    )

    for section in course.sections.all():
        for chapter in section.chapters.all():
            ChapterProgress.objects.get_or_create(
                user_progress=progress,
                chapter=chapter,
                defaults={'completed': False},
            )

    return enrollment, progress
