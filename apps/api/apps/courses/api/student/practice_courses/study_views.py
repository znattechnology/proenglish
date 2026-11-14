"""
Student study-tracking endpoints for the practice lab.

Mounted under /api/v1/student/practice-courses/ (see urls.py):
- study-streak/, study-goal/, hearts-status/, courses/<uuid>/,
  complete-lesson/, review-words/, notifications/..., student-analytics/

Business logic lives in apps.practice.study_services.
"""

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course
from apps.practice import study_services
from apps.practice.models import PracticeLesson, UserProgress
from apps.practice.throttling import LessonCompletionThrottle
from apps.users.models import Notification

from .serializers import CompleteLessonSerializer, NotificationSerializer, StudyGoalSerializer

logger = logging.getLogger(__name__)


def _first_error(errors):
    """Flatten DRF errors into a single Portuguese message for the UI."""
    for value in errors.values():
        if isinstance(value, (list, tuple)) and value:
            return str(value[0])
        return str(value)
    return 'Pedido inválido.'


# ---------------------------------------------------------------------------
# Streak & daily goal
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_study_streak(request):
    """GET study-streak/ — streak, today's minutes vs goal and the last 7 days."""
    return Response(study_services.build_streak_payload(request.user))


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def study_goal(request):
    """GET|PATCH study-goal/ — daily goal in minutes (5, 10, 15 or 20)."""
    streak = study_services.get_or_create_streak(request.user)
    if request.method == 'PATCH':
        serializer = StudyGoalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'validation_error', 'message': _first_error(serializer.errors),
                 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        streak.daily_goal_minutes = serializer.validated_data['daily_goal_minutes']
        streak.save(update_fields=['daily_goal_minutes', 'updated_at'])
        logger.info("User %s set daily goal to %s min", request.user.pk, streak.daily_goal_minutes)
    return Response({'daily_goal_minutes': streak.daily_goal_minutes})


# ---------------------------------------------------------------------------
# Hearts
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_hearts_status(request):
    """GET hearts-status/ — current/max hearts, recharge timing and refill cost."""
    return Response(study_services.build_hearts_status(request.user))


# ---------------------------------------------------------------------------
# Course detail
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_practice_course_detail(request, course_id):
    """GET courses/<uuid>/ — published practice course detail with the user's progress."""
    from apps.courses.ciclo import bloqueio_pratica
    course = Course.objects.filter(id=course_id, course_type='practice').first()
    bloqueio = bloqueio_pratica(request.user, course) if course is not None else None
    if bloqueio and bloqueio[0] != 'curso_indisponivel':
        return Response({'error': bloqueio[0], 'message': bloqueio[1], 'code': bloqueio[0], 'details': {}},
                        status=status.HTTP_403_FORBIDDEN)
    if course is None or bloqueio:
        return Response(
            {'error': 'not_found', 'message': 'Curso de prática não encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    completed, total_lessons, challenges_count = study_services.course_lesson_progress(request.user, course)
    percentage = round(completed * 100 / total_lessons) if total_lessons else 0
    active_course_id = (
        UserProgress.objects.filter(user=request.user).values_list('active_course_id', flat=True).first()
    )
    progress = {
        'completed_lessons': completed,
        'total_lessons': total_lessons,
        'percentage': percentage,
    }
    return Response({
        'id': str(course.id),
        'title': course.title,
        'description': course.description,
        'category': course.category,
        'level': course.level,
        'image': course.image,
        'type': 'practice',
        'units_count': course.practice_units.count(),
        'lessons_count': total_lessons,
        'challenges_count': challenges_count,
        'is_active_course': active_course_id == course.id,
        'progress': progress,
        # Alias matching StudentPracticeCourse.user_progress in the web types
        'user_progress': {'completed_lessons': completed, 'percentage': percentage},
    })


# ---------------------------------------------------------------------------
# Lesson completion
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LessonCompletionThrottle])
def complete_lesson(request):
    """
    POST complete-lesson/ {lesson_id, duration_seconds}

    First completion: +10 bonus points (idempotent). Repeat practice: +5 points
    and +1 heart (capped, no-op for unlimited). Adds study minutes and updates
    the streak.
    """
    serializer = CompleteLessonSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'validation_error', 'message': _first_error(serializer.errors),
             'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = serializer.validated_data
    duration = data.get('duration_seconds')
    if duration is None:
        duration = data.get('time_spent') or 0

    lesson = PracticeLesson.objects.select_related('unit__course').filter(id=data['lesson_id']).first()
    if lesson is None:
        return Response(
            {'error': 'not_found', 'message': 'Lição não encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = study_services.complete_lesson(request.user, lesson, duration)
    except study_services.LessonLimitReached as exc:
        return Response(exc.payload, status=status.HTTP_403_FORBIDDEN)
    except study_services.LessonNotCompleted as exc:
        message = (
            'Esta lição ainda não tem exercícios.' if exc.total == 0
            else f'Ainda não concluíste todos os exercícios desta lição ({exc.completed}/{exc.total}).'
        )
        return Response(
            {'error': 'lesson_not_completed', 'message': message,
             'completed_challenges': exc.completed, 'total_challenges': exc.total},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info(
        "Lesson %s completed by %s (first=%s, points=%s)",
        lesson.id, request.user.pk, result['first_completion'], result['points_awarded'],
    )
    return Response(result)


# ---------------------------------------------------------------------------
# Review words
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_review_words(request):
    """GET review-words/ — challenges answered wrong in the last 14 days and not yet fixed."""
    return Response(study_services.build_review_words(request.user))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


def _unread(user):
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    """
    GET notifications/?page=&unread=1 — paginated, newest first (owner only).

    Contract: {results: [{id, kind, title, body, link, created_at, read}], count, next, unread}.
    ``previous``, ``unread_count`` and per-item ``read_at``/``is_read`` are kept for older clients.
    """
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_only = request.query_params.get('unread', '').lower() in ('1', 'true', 'yes')
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    paginator = NotificationPagination()
    page = paginator.paginate_queryset(qs, request)
    unread = _unread(request.user)
    return Response({
        'results': NotificationSerializer(page, many=True).data,
        'count': paginator.page.paginator.count,
        'next': paginator.get_next_link(),
        'previous': paginator.get_previous_link(),
        'unread': unread,
        'unread_count': unread,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_unread_count(request):
    """GET notifications/unread-count/ — {unread} for the bell (one COUNT query)."""
    return Response({'unread': _unread(request.user)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """POST notifications/<uuid>/read/ — owner only (404 for someone else's)."""
    notification = Notification.objects.filter(id=notification_id, user=request.user).first()
    if notification is None:
        return Response(
            {'error': 'not_found', 'message': 'Notificação não encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    unread = _unread(request.user)
    return Response({
        'notification': NotificationSerializer(notification).data,
        'unread': unread,
        'unread_count': unread,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """POST notifications/read-all/"""
    updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return Response({'marked_read': updated, 'unread': 0, 'unread_count': 0})


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_analytics(request):
    """GET student-analytics/ — data for the student analytics page."""
    return Response(study_services.build_student_analytics(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_estatisticas(request):
    """GET estatisticas/?periodo=7|30|tudo — página Estatísticas (por omissão: 7)."""
    from apps.practice.estatisticas import PERIODO_PADRAO, PERIODOS, construir_estatisticas

    periodo = request.query_params.get('periodo', PERIODO_PADRAO).strip().lower()
    if periodo not in PERIODOS:
        return Response(
            {'error': 'validation_error', 'message': 'Período inválido. Use 7, 30 ou tudo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(construir_estatisticas(request.user, periodo))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_liga_semanal(request):
    """GET liga/semana/ — a minha liga e o ranking semanal à minha volta."""
    from apps.practice.liga import construir_liga_semanal

    return Response(construir_liga_semanal(request.user))
