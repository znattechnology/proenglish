"""
Practice Course Management Views
Endpoints específicos para gerenciar practice courses (deletar e publicar/despublicar)
"""

import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class PracticeCourseManagementView(APIView):
    """
    DELETE /api/v1/practice/courses/{course_id}/
    PUT /api/v1/practice/courses/{course_id}/
    
    Gerenciamento específico de practice courses (deletar e publicar/despublicar)
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, course_id):
        """Get practice course and verify ownership"""
        # Check if user has teacher role
        if getattr(self.request.user, 'role', None) != 'teacher':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas professores podem gerenciar cursos")
        
        try:
            from apps.courses.models import Course
            course = Course.objects.get(id=course_id, course_type='practice')
            
            # Verify if user is the teacher
            if course.teacher != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Apenas o professor proprietário pode gerenciar este curso")
                
            return course
        except Course.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Practice course não encontrado")
    
    def delete(self, request, course_id):
        """Delete practice course"""
        course = self.get_object(course_id)
        
        logger.info(f"🗑️ Deleting practice course: {course.title} (ID: {course.id})")
        
        # Store course info for response
        course_title = course.title
        
        # Delete the course
        course.delete()
        
        logger.info(f"✅ Practice course deleted successfully: {course_title}")
        
        return Response({
            'message': f'Curso "{course_title}" excluído com sucesso',
            'success': True
        }, status=status.HTTP_200_OK)
    
    def put(self, request, course_id):
        """Publish/Unpublish practice course"""
        course = self.get_object(course_id)
        
        # Get action from request data
        action = request.data.get('action')  # 'publish' or 'unpublish'
        
        from django.utils import timezone
        from apps.courses import ciclo

        if action == 'publish':
            # Publicar passa pela revisão do administrador: isto submete o curso.
            if course.status in (ciclo.PUBLICADO, ciclo.EM_REVISAO):
                return Response({
                    'message': 'Curso já está publicado' if course.status == ciclo.PUBLICADO
                    else 'Curso já está em revisão',
                    'success': False,
                    'status': course.status,
                    'estado': ciclo.estado(course),
                }, status=status.HTTP_400_BAD_REQUEST)
            verificacao = ciclo.verificar(course)
            if not verificacao['pode_submeter']:
                return Response({
                    'message': 'O curso ainda não está pronto para revisão. Veja o que falta na lista.',
                    'success': False,
                    **verificacao,
                }, status=status.HTTP_400_BAD_REQUEST)
            course.status = ciclo.EM_REVISAO
            course.submetido_em = timezone.now()
            course.motivo_recusa = ''
            course.save(update_fields=['status', 'submetido_em', 'motivo_recusa', 'updated_at'])
            return Response({
                'message': f'Curso "{course.title}" enviado para revisão. Fica publicado quando o administrador aprovar.',
                'success': True,
                'status': course.status,
                'estado': ciclo.estado(course),
            }, status=status.HTTP_200_OK)

        elif action == 'unpublish':
            if course.status == ciclo.EM_REVISAO:
                course.status = ciclo.RASCUNHO
                course.submetido_em = None
                course.save(update_fields=['status', 'submetido_em', 'updated_at'])
                return Response({
                    'message': 'Revisão cancelada. O curso voltou a rascunho.',
                    'success': True,
                    'status': course.status,
                    'estado': ciclo.estado(course),
                }, status=status.HTTP_200_OK)
            if course.status == ciclo.PUBLICADO:
                return Response({
                    'message': 'Para retirar um curso publicado do catálogo, arquive-o.',
                    'success': False,
                    'status': course.status,
                    'estado': ciclo.estado(course),
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response({
                'message': 'Curso já está em rascunho',
                'success': False,
                'status': course.status,
                'estado': ciclo.estado(course),
            }, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({
                'message': 'Ação inválida. Use "publish" ou "unpublish"',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)