"""
Avisos aos alunos inscritos quando um curso de vídeo publicado recebe uma aula nova.

Chamado pelo post_save de Chapter (signals.py) depois do commit, quando a aula passa a estar
visível (o vídeo foi confirmado pela primeira vez). Deduplicado pelo id da aula: substituir o
vídeo ou mudar o título não volta a avisar; uma aula diferente com o mesmo título avisa.
"""

import logging

logger = logging.getLogger(__name__)


def chave_capitulo(course_id, chapter_id):
    return f'capitulo:{course_id}:{chapter_id}'


def avisar_novo_capitulo(chapter_id):
    from apps.users.models import Notification
    from .models import Chapter, CourseEnrollment

    try:
        chapter = Chapter.objects.select_related('section__course').filter(pk=chapter_id).first()
        from .ciclo import aula_visivel
        if chapter is None or not (chapter.title or '').strip() or not aula_visivel(chapter):
            return 0
        course = chapter.section.course
        if course.status != 'Published' or course.course_type != 'video':
            return 0
        alunos = (
            CourseEnrollment.objects
            .filter(course=course, is_active=True, user__is_active=True)
            .exclude(user_id=course.teacher_id)
            .select_related('user')
        )
        chave = chave_capitulo(course.pk, chapter.pk)
        total = 0
        for inscricao in alunos:
            n = Notification.notify(
                inscricao.user,
                Notification.KIND_COURSE,
                title=f'Novo capítulo em {course.title}'[:200],
                body=f'"{chapter.title}" já está disponível. Continue o curso de onde parou.',
                link=f'/user/courses/{course.pk}/chapters/{chapter.pk}',
                dedupe_key=chave,
            )
            total += 1 if n else 0
        return total
    except Exception:
        logger.exception('Falha ao avisar alunos do capítulo %s', chapter_id)
        return 0
