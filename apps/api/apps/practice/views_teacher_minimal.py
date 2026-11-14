"""
Minimal views for teacher dashboard - only what's needed to fix the 404 errors.
Created to avoid import issues with views.py being shadowed by views/ directory.
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from apps.courses.models import Course
from apps.courses.serializers import CourseListSerializer


class CoursesListView(generics.ListAPIView):
    """
    GET /api/v1/practice/courses/

    List all available courses for practice selection and teacher management.
    Supports include_stats=true to return units_count, lessons_count, challenges_count.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        # Get query parameters
        include_drafts = self.request.query_params.get('include_drafts', 'true').lower() == 'true'
        course_type = self.request.query_params.get('course_type', 'practice')
        include_stats = self.request.query_params.get('include_stats', 'false').lower() == 'true'

        from apps.courses import ciclo
        user = self.request.user
        queryset = Course.objects.filter(course_type=course_type)
        if ciclo.e_staff(user):
            pass  # administradores vêem todos
        elif ciclo.e_professor(user):
            # O professor só gere os seus cursos (antes via os rascunhos de todos).
            queryset = queryset.filter(teacher=user)
        else:
            # Os alunos têm o seu próprio catálogo; aqui só vêem o que está no catálogo.
            queryset = queryset.filter(ciclo.q_catalogo())

        if not include_drafts:
            queryset = queryset.filter(status=ciclo.PUBLICADO)

        # Annotate with stats if requested
        if include_stats:
            queryset = queryset.annotate(
                units_count=Count('practice_units', distinct=True),
                lessons_count=Count('practice_units__lessons', distinct=True),
                challenges_count=Count('practice_units__lessons__challenges', distinct=True)
            )

        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """Override list to include stats in response."""
        queryset = self.get_queryset()
        include_stats = request.query_params.get('include_stats', 'false').lower() == 'true'

        # Serialize normally first
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        from apps.courses import ciclo
        estados = {str(c.id): ciclo.estado(c) for c in queryset}
        for item in data:
            item['estado'] = estados.get(str(item.get('courseId') or item.get('id') or ''))

        # If stats requested, add them to each course
        if include_stats:
            # Create a map of course stats from annotated queryset
            stats_map = {}
            for course in queryset:
                course_id = str(course.id)
                stats_map[course_id] = {
                    'units_count': getattr(course, 'units_count', 0),
                    'lessons_count': getattr(course, 'lessons_count', 0),
                    'challenges_count': getattr(course, 'challenges_count', 0),
                }

            # Add stats to serialized data
            for item in data:
                # CourseListSerializer uses 'courseId' field (which is a property that returns id)
                course_id = str(item.get('courseId') or item.get('id') or '')
                if course_id in stats_map:
                    item['units_count'] = stats_map[course_id]['units_count']
                    item['lessons_count'] = stats_map[course_id]['lessons_count']
                    item['challenges_count'] = stats_map[course_id]['challenges_count']
                else:
                    item['units_count'] = 0
                    item['lessons_count'] = 0
                    item['challenges_count'] = 0

                # Also add 'id' field for frontend compatibility (it expects both id and courseId)
                if 'id' not in item and 'courseId' in item:
                    item['id'] = item['courseId']

        return Response(data)


def _uuid_valido(valor):
    import uuid
    try:
        uuid.UUID(str(valor))
        return True
    except ValueError:
        return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_practice_analytics(request):
    """
    GET /api/v1/practice/analytics/

    Get analytics data for teacher dashboard.
    Só professores; com ?course=, só o dono do curso (ou um administrador).
    """
    course_id = request.GET.get('course')
    from apps.courses import ciclo
    if not (ciclo.e_professor(request.user) or ciclo.e_staff(request.user)):
        return Response({'error': 'Apenas professores podem ver estas estatísticas.',
                         'message': 'Apenas professores podem ver estas estatísticas.',
                         'code': 'permission_denied', 'details': {}}, status=status.HTTP_403_FORBIDDEN)
    if course_id:
        curso = Course.objects.filter(id=course_id).first() if _uuid_valido(course_id) else None
        if curso is None or not ciclo.e_dono_ou_staff(request.user, curso):
            return Response({'error': 'Curso não encontrado.', 'message': 'Curso não encontrado.',
                             'code': 'not_found', 'details': {}}, status=status.HTTP_404_NOT_FOUND)

    try:
        from apps.practice.models import PracticeSession
    except ImportError:
        # If PracticeSession doesn't exist, return empty analytics
        return Response({
            'total_sessions': 0,
            'completed_sessions': 0,
            'recent_activity': 0,
            'average_score': 0,
            'completion_rate': 0
        })

    # Get course filter if provided
    course_id = request.GET.get('course')
    # Base query
    sessions = PracticeSession.objects.all()
    if course_id:
        sessions = sessions.filter(course_id=course_id)
    elif not ciclo.e_staff(request.user):
        sessions = sessions.filter(course__teacher=request.user)

    # Calculate basic analytics
    total_sessions = sessions.count()
    completed_sessions = sessions.filter(status='completed').count()

    # Get recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_sessions = sessions.filter(created_at__gte=thirty_days_ago).count()

    # Calculate average scores if available
    avg_score = sessions.filter(
        final_score__isnull=False
    ).aggregate(Avg('final_score'))['final_score__avg'] or 0

    analytics_data = {
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'recent_activity': recent_sessions,
        'average_score': round(avg_score, 2),
        'completion_rate': round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2)
    }

    return Response(analytics_data)
