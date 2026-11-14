"""
Regras comuns às rotas antigas de gestão de cursos em vídeo (courses/ e teacher/video-courses/).

O editor novo (teacher/cursos, teacher/seccoes, teacher/aulas, teacher/envios) valida os
ficheiros, o questionário e a lista de verificação. As rotas antigas que escreviam secções,
capítulos, recursos, questionários e ficheiros sem essas validações respondem 410.
Apagar um curso só é possível em rascunho, sem inscritos nem certificados.
"""
from django.db import transaction
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro

EDITOR_NOVO = '/api/v1/teacher/cursos/'
MENSAGEM_REMOVIDA = ('Esta operação foi substituída pelo novo editor de cursos. '
                     'Use a Área do professor › Cursos para editar o curso.')


def resposta_removida():
    return Response(corpo_erro(MENSAGEM_REMOVIDA, 'rota_removida', {'substituto': EDITOR_NOVO}), status=410)


class SemEscritaMixin:
    """Vistas antigas só de leitura: POST/PUT/PATCH/DELETE respondem 410 (depois da autenticação)."""

    def post(self, request, *args, **kwargs):
        return resposta_removida()

    def put(self, request, *args, **kwargs):
        return resposta_removida()

    def patch(self, request, *args, **kwargs):
        return resposta_removida()

    def delete(self, request, *args, **kwargs):
        return resposta_removida()


def motivo_nao_apagar(course):
    """None se o curso pode ser apagado; senão a mensagem a mostrar."""
    from apps.courses import ciclo
    from apps.courses.models import CourseCertificate, CourseEnrollment

    if course.status != ciclo.RASCUNHO:
        return ('Só se apagam cursos em rascunho. Um curso publicado, em revisão ou arquivado '
                'arquiva-se em vez de se apagar.')
    if CourseEnrollment.objects.filter(course=course).exists():
        return 'Este curso tem alunos inscritos e não pode ser apagado. Arquive-o em vez de o apagar.'
    if CourseCertificate.objects.filter(course=course).exists():
        return 'Este curso tem certificados emitidos e não pode ser apagado. Arquive-o em vez de o apagar.'
    return None


def apagar_curso(course):
    """Apaga um curso em rascunho sem alunos (e os ficheiros dele); senão 409."""
    from apps.courses.api.teacher.envios import apagar_depois_do_commit, ficheiros_da_aula
    from apps.courses.models import Chapter

    motivo = motivo_nao_apagar(course)
    if motivo:
        return Response(corpo_erro(motivo, 'curso_nao_apagavel', {'estado': course.status}), status=409)
    titulo = course.title
    with transaction.atomic():
        ficheiros = [course.image] + [u for a in Chapter.objects.filter(section__course=course)
                                      for u in ficheiros_da_aula(a)]
        course.delete()
        apagar_depois_do_commit(ficheiros)
    return Response({'message': f'Curso "{titulo}" apagado.'}, status=200)


def _vista_removida():
    from rest_framework import permissions
    from rest_framework.decorators import api_view, permission_classes

    @api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    @permission_classes([permissions.IsAuthenticated])
    def rota_removida(request, *args, **kwargs):
        """Envios antigos (vídeo, recursos e capa): substituídos por teacher/aulas|cursos/.../envios."""
        return resposta_removida()
    return rota_removida


rota_removida = _vista_removida()
