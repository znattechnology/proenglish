"""
Verificações de posse para as vistas de gestão de cursos em vídeo (teacher/video-courses/ e
o legado courses/): só o professor dono do curso (ou um administrador) lê ou altera secções,
capítulos, comentários, recursos e questionários por aqui. Para os outros, não existem (404).
Os alunos usam student/video-courses/, que exige inscrição e esconde as respostas.
"""
from rest_framework.exceptions import NotFound

from apps.courses import ciclo


def _exigir(request, course, mensagem):
    if course is None or not ciclo.e_dono_ou_staff(request.user, course):
        raise NotFound(mensagem)
    return course


def exigir_dono_curso(request, course_id):
    from apps.courses.models import Course
    return _exigir(request, Course.objects.filter(id=course_id).first(), 'Curso não encontrado.')


def exigir_dono_seccao(request, section_id):
    from apps.courses.models import CourseSection
    seccao = CourseSection.objects.select_related('course').filter(id=section_id).first()
    return _exigir(request, seccao.course if seccao else None, 'Secção não encontrada.')


def exigir_dono_capitulo(request, chapter_id):
    from apps.courses.models import Chapter
    capitulo = Chapter.objects.select_related('section__course').filter(id=chapter_id).first()
    return _exigir(request, capitulo.section.course if capitulo else None, 'Capítulo não encontrado.')
