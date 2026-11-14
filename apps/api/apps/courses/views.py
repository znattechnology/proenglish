"""
Views for the ProEnglish course management system.

This module contains all API views for course-related operations,
maintaining the same endpoints and response format as the Express API.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from apps.core.permissions import e_administrador as _e_admin
from rest_framework.views import APIView
from apps.courses.legado import SemEscritaMixin, apagar_curso, resposta_removida
from apps.courses.api.teacher.posse import exigir_dono_curso, exigir_dono_seccao, exigir_dono_capitulo
from django.db import transaction
from django.db.models import Q

from .models import (
    Course, CourseSection, Chapter, ChapterComment,
    CourseEnrollment, Transaction, UserCourseProgress, ChapterProgress,
    ChapterResource, ChapterQuiz, StudentQuizAttempt
)
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateSerializer, CourseUpdateSerializer,
    CourseSectionSerializer, CourseSectionCreateSerializer,
    ChapterSerializer, ChapterCreateSerializer, ChapterCommentSerializer,
    TransactionSerializer, TransactionCreateSerializer,
    UserCourseProgressSerializer,
    ChapterProgressSerializer, CourseEnrollmentSerializer,
    ChapterResourceSerializer, ChapterResourceCreateSerializer,
    ChapterQuizSerializer, ChapterQuizCreateSerializer,
    StudentQuizAttemptSerializer, StudentQuizAttemptCreateSerializer
)
from .pagination import (
    CourseListPagination, TransactionListPagination, CommentListPagination,
    QuizAttemptPagination, StandardResultsSetPagination, optimize_paginated_queryset
)


class CourseListCreateView(generics.ListCreateAPIView):
    """
    List courses or create new course.
    
    GET /api/v1/courses/ - List all published courses (public)
    POST /api/v1/courses/ - Create new course (teachers only)
    
    Maps to Express: GET /courses and POST /courses
    
    Query Parameters for GET:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 12, max: 100)
    - category: Filter by category ('all' for no filter)
    - ordering: Sort order (-created_at, title, price, level)
    - include_description: Include description field (default: true)
    - include_enrollment_count: Include enrollment count (default: false)
    """
    serializer_class = CourseListSerializer
    pagination_class = CourseListPagination
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]
    
    def get_queryset(self):
        if self.request.method == 'POST':
            return Course.objects.all()
        
        # Check if this is for teacher's own course management or public exploration
        view_mode = self.request.query_params.get('view_mode', 'public')
        
        if view_mode == 'teacher_courses' and self.request.user.is_authenticated and getattr(self.request.user, 'role', None) == 'teacher':
            # Teachers managing their own VIDEO courses (Draft + Published)
            queryset = Course.objects.filter(teacher=self.request.user, course_type='video')
        else:
            # Public exploration - everyone sees only published VIDEO courses
            # Só o catálogo: publicados e visíveis (os escondidos abrem-se por ligação, não aparecem aqui).
            from apps.courses import ciclo
            queryset = Course.objects.filter(ciclo.q_catalogo(), course_type='video')
        
        # Apply category filter
        category = self.request.query_params.get('category')
        if category and category != 'all':
            queryset = queryset.filter(category=category)
        
        # Use optimized queryset from serializer
        include_enrollment_count = self.request.query_params.get('include_enrollment_count', 'false').lower() == 'true'
        queryset = CourseListSerializer.optimize_queryset(
            queryset, 
            include_enrollment_count=include_enrollment_count
        )
        
        return optimize_paginated_queryset(queryset, self.request, '-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CourseCreateSerializer
        return CourseListSerializer
    
    def perform_create(self, serializer):
        # Check if user is a teacher
        if self.request.user.role != 'teacher':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas professores podem criar cursos")
        
        # Ensure video courses are created with course_type='video'
        serializer.save(teacher=self.request.user, course_type='video')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.save()
        
        # Return course with full details
        response_serializer = CourseDetailSerializer(course, context={'request': request})
        
        return Response({
            'message': 'Curso criado com sucesso',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Check if this is for teacher's own course management (bypass pagination)
        view_mode = request.query_params.get('view_mode', 'public')
        
        if view_mode == 'teacher_courses' and request.user.is_authenticated and getattr(request.user, 'role', None) == 'teacher':
            # For teacher course management, return all courses without pagination
            context = {'request': request}
            context['include_description'] = request.query_params.get('include_description', 'true').lower() == 'true'
            context['include_enrollment_count'] = request.query_params.get('include_enrollment_count', 'false').lower() == 'true'
            
            serializer = self.get_serializer(queryset, many=True, context=context)
            
            return Response({
                'message': 'Cursos obtidos com sucesso',
                'data': serializer.data
            })
        else:
            # For public exploration, use normal pagination
            return super().list(request, *args, **kwargs)


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a course.
    
    GET /api/v1/courses/{id}/ - Get course details (public)
    PUT /api/v1/courses/{id}/ - Update course (teacher only)
    DELETE /api/v1/courses/{id}/ - Delete course (teacher only)
    
    Maps to Express: GET/PUT/DELETE /courses/:id
    """
    # Base queryset - optimization handled by serializer
    queryset = Course.objects.all()
    lookup_field = 'id'
    lookup_url_kwarg = 'courseId'
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CourseUpdateSerializer
        return CourseDetailSerializer
    
    def check_object_permissions(self, request, obj):
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            if obj.teacher != request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Apenas o professor pode editar ou apagar este curso")
    
    def retrieve(self, request, *args, **kwargs):
        # Get base queryset and apply optimizations
        instance = self.get_object()
        
        # Get fresh instance with optimizations based on query parameters
        include_sections = request.query_params.get('include_sections', 'true').lower() == 'true'
        include_enrollments = request.query_params.get('include_enrollments', 'true').lower() == 'true'
        include_chapters = request.query_params.get('include_chapters', 'true').lower() == 'true'
        include_comments = request.query_params.get('include_chapter_comments', 'false').lower() == 'true'

        # Quem não é dono nem administrador só vê cursos publicados e, sem acesso ao
        # conteúdo (inscrição + plano), só a estrutura sem capítulos.
        from apps.courses import ciclo
        if not ciclo.e_dono_ou_staff(request.user, instance):
            if instance.status != ciclo.PUBLICADO:
                from rest_framework.exceptions import NotFound
                raise NotFound('Curso não encontrado.')
            from apps.courses.api.student.video_courses.conteudo import pode_ver_conteudo
            if not pode_ver_conteudo(request.user, instance):
                include_chapters = False
                include_comments = False
        
        # Re-fetch with optimizations
        optimized_queryset = CourseDetailSerializer.optimize_queryset(
            Course.objects.filter(id=instance.id),
            include_sections=include_sections,
            include_enrollments=include_enrollments
        )
        instance = optimized_queryset.first()
        
        # Set prefetch flags for serializer
        if include_sections:
            instance._prefetched_sections = True
            # Also set prefetch flags for chapters in each section
            if include_chapters:
                for section in instance.sections.all():
                    section._prefetched_chapters = True
        if include_enrollments:
            instance._prefetched_enrollments = True
        
        # Prepare context
        context = {'request': request}
        context['include_sections'] = include_sections
        context['include_enrollments'] = include_enrollments
        context['include_chapters'] = include_chapters
        context['include_chapter_comments'] = include_comments
        
        serializer = self.get_serializer(instance, context=context)
        
        return Response({
            'message': 'Curso obtido com sucesso',
            'data': serializer.data
        })
    
    def put(self, request, *args, **kwargs):
        # Edição antiga sem validação do questionário/vídeo: use o editor novo (teacher/cursos/).
        return resposta_removida()

    def patch(self, request, *args, **kwargs):
        return resposta_removida()

    def destroy(self, request, *args, **kwargs):
        # Só cursos em rascunho, sem inscritos nem certificados (ver apps.courses.legado).
        return apagar_curso(self.get_object())


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_transaction(request):
    """
    Create transaction and enroll user in course.
    
    POST /api/v1/courses/transactions/create/
    
    Maps to Express: POST /transactions
    """
    serializer = TransactionCreateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    # Mesmas regras do student/video-courses/transactions/create/: estado do curso, inscrições
    # abertas, vagas e plano.
    from apps.courses import ciclo
    from apps.core.exceptions import corpo_erro
    course = Course.objects.filter(id=serializer.validated_data['course']['id']).first()
    if course is None:
        return Response(corpo_erro('Curso não encontrado.', 'not_found'), status=status.HTTP_404_NOT_FOUND)
    bloqueio = ciclo.bloqueio_inscricao(request.user, course)
    if bloqueio:
        return Response(corpo_erro(bloqueio[1], bloqueio[0]), status=bloqueio[2])
    if not course.user_has_access(request.user):
        return Response(corpo_erro('Não tem a subscrição necessária para este curso.', 'SUBSCRIPTION_REQUIRED'),
                        status=status.HTTP_403_FORBIDDEN)
    
    with transaction.atomic():
        # Create transaction (os cursos estão incluídos nos planos: valor sempre 0)
        new_transaction = serializer.save(amount=0)
        
        # Create enrollment
        enrollment, created = CourseEnrollment.objects.get_or_create(
            user=request.user,
            course=new_transaction.course
        )
        
        # Create initial progress record
        progress, created = UserCourseProgress.objects.get_or_create(
            user=request.user,
            course=new_transaction.course,
            defaults={
                'enrollmentDate': timezone.now(),
                'overallProgress': 0.0
            }
        )
        
        # Create chapter progress records for all chapters
        for section in new_transaction.course.sections.all():
            for chapter in section.chapters.all():
                ChapterProgress.objects.get_or_create(
                    user_progress=progress,
                    chapter=chapter,
                    defaults={'completed': False}
                )
    
    return Response({
        'message': 'Curso adquirido com sucesso',
        'data': {
            'transaction': TransactionSerializer(new_transaction).data,
            'courseProgress': UserCourseProgressSerializer(progress).data
        }
    }, status=status.HTTP_201_CREATED)


class TransactionListView(generics.ListAPIView):
    """
    List transactions for the authenticated user or all (for admins).
    
    GET /api/v1/courses/transactions/
    
    Maps to Express: GET /transactions
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 15, max: 50)
    - userId: Filter by user ID (admin only)
    - ordering: Sort order (-dateTime, amount, paymentProvider)
    """
    serializer_class = TransactionSerializer
    pagination_class = TransactionListPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.request.query_params.get('userId')
        
        if user_id and _e_admin(self.request.user):
            # Admin can view transactions for specific user
            queryset = Transaction.objects.filter(user_id=user_id)
        elif user_id and str(self.request.user.id) == user_id:
            # User can view their own transactions
            queryset = Transaction.objects.filter(user=self.request.user)
        else:
            # Regular users see only their own transactions
            queryset = Transaction.objects.filter(user=self.request.user)
        
        # Optimize queries
        queryset = queryset.select_related('user', 'course')
        
        return optimize_paginated_queryset(queryset, self.request, '-dateTime')
    
    def list(self, request, *args, **kwargs):
        """Add transaction summary to response context."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate summary for current user's transactions
        from django.db.models import Sum, Count
        summary = queryset.aggregate(
            total_amount=Sum('amount'),
            total_transactions=Count('id')
        )
        
        # Add summary to request for pagination response
        request.transaction_summary = {
            'total_spent': summary['total_amount'] or 0,
            'total_transactions': summary['total_transactions'] or 0
        }
        
        return super().list(request, *args, **kwargs)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_enrolled_courses(request, userId):
    """
    Get courses user is enrolled in.
    
    GET /api/v1/courses/users/{userId}/enrolled/
    
    Maps to Express: GET /users/course-progress/:userId
    """
    # userId is already a UUID object from Django URL converter
    # Check if user can access this data - direct UUID comparison
    if request.user.id != userId and not _e_admin(request.user):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Acesso negado")
    
    try:
        from apps.users.models import User
        user = User.objects.get(id=userId)
    except User.DoesNotExist:
        return Response({'error': 'Usuário não encontrado'}, status=404)
    
    # Get enrolled courses - only video courses
    enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    courses = [enrollment.course for enrollment in enrollments if enrollment.course.course_type == 'video']
    
    serializer = CourseListSerializer(courses, many=True)
    
    return Response({
        'message': 'Cursos inscritos obtidos com sucesso',
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_course_progress(request, userId, courseId):
    """
    Get user progress in a specific course.
    
    GET /api/v1/courses/users/{userId}/progress/{courseId}/
    
    Maps to Express: GET /users/course-progress/:userId/:courseId
    """
    # userId and courseId are already UUID objects from Django URL converter
    # Check if user can access this data
    if request.user.id != userId and not _e_admin(request.user):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Acesso negado")
    
    try:
        from apps.users.models import User
        user = User.objects.get(id=userId)
        course = Course.objects.get(id=courseId)
        progress = UserCourseProgress.objects.get(user=user, course=course)
    except (User.DoesNotExist, Course.DoesNotExist):
        return Response({'error': 'Usuário ou curso não encontrado'}, status=404)
    except UserCourseProgress.DoesNotExist:
        return Response({'error': 'Progresso do curso não encontrado para este utilizador'}, status=404)
    
    serializer = UserCourseProgressSerializer(progress)
    
    return Response({
        'message': 'Progresso do curso obtido com sucesso',
        'data': serializer.data
    })


# Course Section Management Views

class CourseSectionListCreateView(SemEscritaMixin, generics.ListCreateAPIView):
    """
    List sections for a course or create new section.
    """
    serializer_class = CourseSectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        course_id = self.kwargs['courseId']
        exigir_dono_curso(self.request, course_id)
        include_comments = self.request.query_params.get('include_comments', 'false').lower() == 'true'
        
        queryset = CourseSection.objects.filter(course__id=course_id)
        
        # Optimize based on requirements
        if include_comments:
            queryset = queryset.prefetch_related('chapters__comments__user')
        else:
            queryset = queryset.prefetch_related('chapters')
        
        return queryset.order_by('order')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CourseSectionCreateSerializer
        return CourseSectionSerializer
    
    def perform_create(self, serializer):
        course_id = self.kwargs['courseId']
        course = get_object_or_404(Course, id=course_id)
        
        # Check if user owns this course
        if course.teacher != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode adicionar secções")
        
        serializer.save(course=course)


class CourseSectionDetailView(SemEscritaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a course section.
    """
    # Base queryset - optimization handled by views and serializers
    queryset = CourseSection.objects.select_related('course', 'course__teacher')
    serializer_class = CourseSectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'sectionId'
    
    def check_object_permissions(self, request, obj):
        if obj.course.teacher != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode editar secções")


# Chapter Management Views

class ChapterListCreateView(SemEscritaMixin, generics.ListCreateAPIView):
    """
    List chapters for a section or create new chapter.
    """
    serializer_class = ChapterSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        section_id = self.kwargs['sectionId']
        exigir_dono_seccao(self.request, section_id)
        return Chapter.objects.filter(section__id=section_id).order_by('order')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChapterCreateSerializer
        return ChapterSerializer
    
    def perform_create(self, serializer):
        section_id = self.kwargs['sectionId']
        section = get_object_or_404(CourseSection, id=section_id)
        
        # Check if user owns this course
        if section.course.teacher != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode adicionar capítulos")
        
        serializer.save(section=section)


class ChapterDetailView(SemEscritaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a chapter.
    """
    # Base queryset - selective optimization in views
    queryset = Chapter.objects.select_related(
        'section', 
        'section__course', 
        'section__course__teacher'
    )
    serializer_class = ChapterSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'chapterId'
    
    def check_object_permissions(self, request, obj):
        if obj.section.course.teacher != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode editar capítulos")


# Chapter Comment Views

class ChapterCommentListCreateView(generics.ListCreateAPIView):
    """
    List comments for a chapter or create new comment.
    
    Query Parameters for GET:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 50)
    - ordering: Sort order (-timestamp, user__name)
    """
    serializer_class = ChapterCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CommentListPagination
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        queryset = ChapterComment.objects.filter(chapter__id=chapter_id)
        return ChapterCommentSerializer.optimize_queryset(queryset)
    
    def perform_create(self, serializer):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        chapter = get_object_or_404(Chapter, id=chapter_id)
        serializer.save(chapter=chapter)


# Stripe Payment Intent View

# =============================================================================
# AWS S3 VIDEO UPLOAD ENDPOINTS
# =============================================================================

class ChapterResourceListCreateView(SemEscritaMixin, generics.ListCreateAPIView):
    """
    List resources for a chapter or create new resource.
    
    GET /api/v1/courses/chapters/{chapterId}/resources/
    POST /api/v1/courses/chapters/{chapterId}/resources/
    
    Query Parameters for GET:
    - page: Page number (default: 1)  
    - page_size: Items per page (default: 20, max: 100)
    - ordering: Sort order (order, -created_at, resource_type)
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        queryset = ChapterResource.objects.filter(chapter__id=chapter_id)
        queryset = queryset.select_related('chapter', 'created_by')
        return optimize_paginated_queryset(queryset, self.request, 'order')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChapterResourceCreateSerializer
        return ChapterResourceSerializer
    
    def perform_create(self, serializer):
        chapter_id = self.kwargs['chapterId']
        chapter = get_object_or_404(Chapter, id=chapter_id)
        
        # Check if user owns this course
        if chapter.section.course.teacher != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode adicionar recursos")
        
        serializer.save(chapter=chapter)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'message': 'Recursos do capítulo obtidos com sucesso',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        
        response_serializer = ChapterResourceSerializer(resource, context={'request': request})
        
        return Response({
            'message': 'Recurso criado com sucesso',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ChapterResourceDetailView(SemEscritaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a chapter resource.
    
    GET /api/v1/courses/chapters/{chapterId}/resources/{resourceId}/
    PUT /api/v1/courses/chapters/{chapterId}/resources/{resourceId}/
    DELETE /api/v1/courses/chapters/{chapterId}/resources/{resourceId}/
    """
    serializer_class = ChapterResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'resourceId'
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        return ChapterResource.objects.filter(chapter__id=chapter_id)
    
    def check_object_permissions(self, request, obj):
        if obj.chapter.section.course.teacher != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode editar recursos")
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Increment download count for GET requests (except teacher)
        if instance.chapter.section.course.teacher != request.user:
            instance.download_count += 1
            instance.save(update_fields=['download_count'])
        
        serializer = self.get_serializer(instance)
        
        return Response({
            'message': 'Recurso obtido com sucesso',
            'data': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        
        return Response({
            'message': 'Recurso actualizado com sucesso',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        resource_title = instance.title
        self.perform_destroy(instance)
        
        return Response({
            'message': f'Recurso "{resource_title}" apagado'
        }, status=status.HTTP_200_OK)


class ChapterQuizListCreateView(SemEscritaMixin, generics.ListCreateAPIView):
    """
    Get quiz for a chapter or create new quiz.
    
    GET /api/v1/courses/chapters/{chapterId}/quiz/
    POST /api/v1/courses/chapters/{chapterId}/quiz/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        return ChapterQuiz.objects.filter(chapter__id=chapter_id)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChapterQuizCreateSerializer
        return ChapterQuizSerializer
    
    def perform_create(self, serializer):
        chapter_id = self.kwargs['chapterId']
        chapter = get_object_or_404(Chapter, id=chapter_id)
        
        # Check if user owns this course
        if chapter.section.course.teacher != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode criar quizzes")
        
        # Check if quiz already exists for this chapter
        if ChapterQuiz.objects.filter(chapter=chapter).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Este capítulo já possui um quiz")
        
        serializer.save(chapter=chapter)
        
        # Enable quiz in chapter
        chapter.quiz_enabled = True
        chapter.save(update_fields=['quiz_enabled'])
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        if not queryset.exists():
            return Response({
                'message': 'Nenhum quiz encontrado para este capítulo',
                'data': None
            })
        
        # Should be only one quiz per chapter
        quiz = queryset.first()
        serializer = self.get_serializer(quiz)
        
        return Response({
            'message': 'Quiz do capítulo obtido com sucesso',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save()
        
        response_serializer = ChapterQuizSerializer(quiz, context={'request': request})
        
        return Response({
            'message': 'Quiz criado com sucesso',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ChapterQuizDetailView(SemEscritaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a chapter quiz.
    
    GET /api/v1/courses/chapters/{chapterId}/quiz/{quizId}/
    PUT /api/v1/courses/chapters/{chapterId}/quiz/{quizId}/
    DELETE /api/v1/courses/chapters/{chapterId}/quiz/{quizId}/
    """
    serializer_class = ChapterQuizSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'quizId'
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        exigir_dono_capitulo(self.request, chapter_id)
        return ChapterQuiz.objects.filter(chapter__id=chapter_id)
    
    def check_object_permissions(self, request, obj):
        if obj.chapter.section.course.teacher != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor pode editar quizzes")
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'message': 'Quiz obtido com sucesso',
            'data': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save()
        
        return Response({
            'message': 'Quiz actualizado com sucesso',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        quiz_title = instance.title
        chapter = instance.chapter
        
        self.perform_destroy(instance)
        
        # Disable quiz in chapter
        chapter.quiz_enabled = False
        chapter.save(update_fields=['quiz_enabled'])
        
        return Response({
            'message': f'Quiz "{quiz_title}" apagado'
        }, status=status.HTTP_200_OK)


def is_admin_user(user):
    """Administrador activo (papel admin ou superutilizador); is_staff sozinho não chega."""
    from apps.core.permissions import e_administrador
    return e_administrador(user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def course_analytics_overview(request):
    """
    Comprehensive course analytics overview
    
    Returns:
        - Course overview statistics
        - Student engagement metrics
        - Performance data
        - Revenue analytics
    """
    
    if not is_admin_user(request.user):
        return Response(
            {'error': 'Acesso negado. Só os administradores podem aceder.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Cache key for analytics data
    cache_key = 'admin_course_analytics_overview'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    try:
        # Calculate analytics data
        analytics_data = {
            'overview': get_course_overview_stats(),
            'engagement': get_student_engagement_stats(),
            'performance': get_course_performance_stats(),
            'revenue': get_revenue_analytics()
        }
        
        # Cache for 15 minutes
        cache.set(cache_key, analytics_data, 900)
        
        return Response(analytics_data)
        
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Falha ao calcular as estatísticas dos cursos')
        return Response(
            {'error': 'Não foi possível calcular as estatísticas. Tente de novo.'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def get_course_overview_stats():
    """Get basic course statistics"""
    
    # Current month start
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (current_month_start - timedelta(days=32)).replace(day=1)
    
    # Course counts
    total_courses = Course.objects.count()
    published_courses = Course.objects.filter(status='Published').count()
    draft_courses = Course.objects.filter(status='Draft').count()
    video_courses = Course.objects.filter(course_type='video').count()
    practice_courses = Course.objects.filter(course_type='practice').count()
    
    # Growth calculation
    courses_this_month = Course.objects.filter(created_at__gte=current_month_start).count()
    courses_last_month = Course.objects.filter(
        created_at__gte=last_month_start,
        created_at__lt=current_month_start
    ).count()
    
    growth_percentage = 0
    if courses_last_month > 0:
        growth_percentage = round(((courses_this_month - courses_last_month) / courses_last_month) * 100, 1)
    
    return {
        'total_courses': total_courses,
        'published_courses': published_courses,
        'draft_courses': draft_courses,
        'video_courses': video_courses,
        'practice_courses': practice_courses,
        'courses_growth_percentage': growth_percentage
    }


def get_student_engagement_stats():
    """Get student engagement metrics"""
    
    # Date ranges
    now = timezone.now()
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(days=7)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (current_month_start - timedelta(days=32)).replace(day=1)
    
    # Enrollment stats
    total_enrollments = CourseEnrollment.objects.count()
    active_enrollments = CourseEnrollment.objects.filter(is_active=True).count()
    
    # Active users (based on last access)
    daily_active_users = UserCourseProgress.objects.filter(
        lastAccessedTimestamp__gte=one_day_ago
    ).values('user').distinct().count()
    
    weekly_active_users = UserCourseProgress.objects.filter(
        lastAccessedTimestamp__gte=one_week_ago
    ).values('user').distinct().count()
    
    # Enrollment growth
    enrollments_this_month = CourseEnrollment.objects.filter(
        enrollment_date__gte=current_month_start
    ).count()
    enrollments_last_month = CourseEnrollment.objects.filter(
        enrollment_date__gte=last_month_start,
        enrollment_date__lt=current_month_start
    ).count()
    
    enrollment_growth = 0
    if enrollments_last_month > 0:
        enrollment_growth = round(((enrollments_this_month - enrollments_last_month) / enrollments_last_month) * 100, 1)
    
    # Average completion rate
    avg_completion_rate = UserCourseProgress.objects.filter(
        overallProgress__gt=0
    ).aggregate(
        avg_completion=Avg('overallProgress')
    )['avg_completion'] or 0
    
    return {
        'total_enrollments': total_enrollments,
        'active_enrollments': active_enrollments,
        'daily_active_users': daily_active_users,
        'weekly_active_users': weekly_active_users,
        'enrollment_growth': enrollment_growth,
        'average_completion_rate': round(avg_completion_rate, 1)
    }


def get_course_performance_stats():
    """Get course performance data"""
    
    # Top performing courses
    top_courses = Course.objects.filter(
        status='Published'
    ).annotate(
        enrollment_count=Count('enrollments'),
        avg_completion=Avg('user_progress__overallProgress')
    ).order_by('-enrollment_count')[:5]
    
    top_courses_data = []
    for course in top_courses:
        # Calculate average rating (mock for now, you can implement a rating system later)
        avg_rating = 4.5  # Mock rating
        
        top_courses_data.append({
            'id': str(course.id),
            'title': course.title,
            'course_type': course.course_type,
            'enrollments': course.enrollment_count or 0,
            'completion_rate': round(course.avg_completion or 0, 1),
            'average_rating': avg_rating
        })
    
    # Completion trends for last 6 months
    six_months_ago = timezone.now() - timedelta(days=180)
    
    completion_trends = UserCourseProgress.objects.filter(
        completion_date__gte=six_months_ago,
        completion_date__isnull=False
    ).annotate(
        month=TruncMonth('completion_date')
    ).values('month').annotate(
        completions=Count('id')
    ).order_by('month')
    
    # Also get enrollments for the same period
    enrollment_trends = CourseEnrollment.objects.filter(
        enrollment_date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('enrollment_date')
    ).values('month').annotate(
        enrollments=Count('id')
    ).order_by('month')
    
    # Combine completion and enrollment trends
    trends_data = []
    for i in range(6):
        month_date = timezone.now() - timedelta(days=30*i)
        month_name = calendar.month_name[month_date.month][:3]
        
        # Find completions for this month
        completions = 0
        for trend in completion_trends:
            if trend['month'].month == month_date.month and trend['month'].year == month_date.year:
                completions = trend['completions']
                break
        
        # Find enrollments for this month
        enrollments = 0
        for trend in enrollment_trends:
            if trend['month'].month == month_date.month and trend['month'].year == month_date.year:
                enrollments = trend['enrollments']
                break
        
        trends_data.append({
            'month': month_name,
            'completions': completions,
            'enrollments': enrollments
        })
    
    # Reverse to show chronological order
    trends_data.reverse()
    
    return {
        'top_courses': top_courses_data,
        'completion_trends': trends_data
    }


def get_revenue_analytics():
    """Get revenue analytics (mock data for now)"""
    
    # Note: This is mock data. In a real implementation, you would:
    # 1. Have a payments/billing system
    # 2. Track subscription revenues
    # 3. Calculate actual revenue by course/template
    
    # For now, we'll generate realistic mock data based on course enrollments
    total_enrollments = CourseEnrollment.objects.count()
    
    # Estimate revenue (assuming average price per enrollment)
    avg_price_per_enrollment = 15000  # 15,000 AOA average
    estimated_total_revenue = total_enrollments * avg_price_per_enrollment
    
    # Monthly revenue (last month's enrollments)
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_enrollments = CourseEnrollment.objects.filter(
        enrollment_date__gte=current_month_start
    ).count()
    estimated_monthly_revenue = monthly_enrollments * avg_price_per_enrollment
    
    # Revenue by template (based on course distribution)
    template_distribution = Course.objects.filter(
        status='Published'
    ).values('template').annotate(
        course_count=Count('id'),
        enrollment_count=Count('enrollments')
    )
    
    revenue_by_template = {}
    for template_data in template_distribution:
        template = template_data['template']
        enrollments = template_data['enrollment_count'] or 0
        revenue = enrollments * avg_price_per_enrollment
        revenue_by_template[template] = f"{revenue:,.0f} AOA"
    
    return {
        'total_revenue': f"{estimated_total_revenue:,.0f} AOA",
        'monthly_revenue': f"{estimated_monthly_revenue:,.0f} AOA",
        'revenue_growth': 22.3,  # Mock growth percentage
        'revenue_by_template': revenue_by_template
    }


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def course_analytics_real_time(request):
    """
    Real-time course analytics for dashboard updates
    """
    
    if not is_admin_user(request.user):
        return Response(
            {'error': 'Acesso negado. Só os administradores podem aceder.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get real-time stats (no caching)
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    real_time_data = {
        'online_users': 45,  # Mock data - would need WebSocket/session tracking
        'enrollments_today': CourseEnrollment.objects.filter(
            enrollment_date__gte=today_start
        ).count(),
        'active_sessions': 23,  # Mock data
        'courses_completed_today': UserCourseProgress.objects.filter(
            completion_date__gte=today_start
        ).count(),
        'last_updated': now.isoformat()
    }
    
    return Response(real_time_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_course_data(request):
    """
    Export course analytics data for download
    """
    
    if not is_admin_user(request.user):
        return Response(
            {'error': 'Acesso negado. Só os administradores podem aceder.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    export_format = request.GET.get('format', 'json')
    
    # Get comprehensive data for export
    export_data = {
        'generated_at': timezone.now().isoformat(),
        'overview': get_course_overview_stats(),
        'engagement': get_student_engagement_stats(),
        'performance': get_course_performance_stats(),
        'revenue': get_revenue_analytics()
    }
    
    if export_format == 'csv':
        # For CSV format, you would need to flatten the data
        # This is a simplified version
        return Response({
            'message': 'CSV export not yet implemented',
            'data': export_data
        })
    
    return Response(export_data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def clear_analytics_cache(request):
    """
    Clear analytics cache to force fresh data
    """
    
    if not is_admin_user(request.user):
        return Response(
            {'error': 'Acesso negado. Só os administradores podem aceder.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    cache_keys = [
        'admin_course_analytics_overview',
        'admin_course_performance_stats',
        'admin_engagement_stats'
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    return Response({'message': 'Cache de analytics limpo com sucesso'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_courses_list(request):
    """
    List all courses for admin management with statistics
    """
    
    if not is_admin_user(request.user):
        return Response(
            {'error': 'Acesso negado. Só os administradores podem aceder.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get all courses with related data
        courses = Course.objects.select_related('teacher').prefetch_related('enrollments').all()
        
        # Calculate basic stats
        total_courses = courses.count()
        published_courses = courses.filter(status='Published').count()
        
        # Calculate total students (enrollments)
        total_students = CourseEnrollment.objects.filter(is_active=True).count()
        
        # Calculate monthly growth (simplified)
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        courses_this_month = courses.filter(created_at__gte=current_month_start).count()
        monthly_growth = round(courses_this_month / max(total_courses, 1) * 100, 1)
        
        # Estimate revenue (mock calculation)
        estimated_revenue = total_students * 15000  # 15,000 AOA average per enrollment
        
        # Prepare course data
        courses_data = []
        for course in courses:
            enrollment_count = course.enrollments.filter(is_active=True).count()
            
            courses_data.append({
                'id': str(course.id),
                'title': course.title,
                'teacher': {
                    'id': str(course.teacher.id),
                    'name': course.teacher.name,
                    'email': course.teacher.email,
                },
                'enrollment_count': enrollment_count,
                'status': course.status,
                'template': course.template,
                'course_type': course.course_type,
                'created_at': course.created_at.isoformat(),
                'updated_at': course.updated_at.isoformat(),
                'description': course.description,
                'image': course.image,
            })
        
        # Prepare stats data
        stats_data = {
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_students': total_students,
            'total_revenue': f'{estimated_revenue:,.0f} AOA',
            'monthly_growth': monthly_growth,
        }
        
        return Response({
            'courses': courses_data,
            'stats': stats_data,
            'message': 'Cursos carregados com sucesso'
        })
        
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Falha ao carregar a lista de cursos (admin)')
        return Response(
            {'error': 'Não foi possível carregar os cursos. Tente de novo.'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )