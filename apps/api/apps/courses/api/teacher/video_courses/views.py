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
from apps.courses.api.teacher.decorators import teacher_required, course_owner_required
from rest_framework.views import APIView
from apps.courses.legado import SemEscritaMixin, apagar_curso, resposta_removida
from apps.courses.api.teacher.posse import exigir_dono_curso, exigir_dono_seccao, exigir_dono_capitulo
from django.db import models, transaction
from django.db.models import Q

from apps.courses.models import (
    Course, CourseSection, Chapter, ChapterComment,
    CourseEnrollment, Transaction, UserCourseProgress, ChapterProgress,
    ChapterResource, ChapterQuiz, StudentQuizAttempt
)
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateSerializer, CourseUpdateSerializer,
    CourseSectionSerializer, CourseSectionCreateSerializer,
    ChapterSerializer, ChapterCreateSerializer, ChapterCommentSerializer,
    TransactionSerializer, TransactionCreateSerializer,
    UserCourseProgressSerializer, UserCourseProgressUpdateSerializer,
    ChapterProgressSerializer, CourseEnrollmentSerializer,
    ChapterResourceSerializer, ChapterResourceCreateSerializer,
    ChapterQuizSerializer, ChapterQuizCreateSerializer,
    StudentQuizAttemptSerializer, StudentQuizAttemptCreateSerializer
)
from apps.courses.pagination import (
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
        # Teacher endpoint requires authentication AND teacher role
        return [permissions.IsAuthenticated()]
    
    def check_teacher_permission(self):
        """Check if user is a teacher, raise PermissionDenied if not."""
        if not self.request.user.is_authenticated:
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated("Autenticação necessária.")
        
        if getattr(self.request.user, 'role', None) != 'teacher':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas professores podem aceder a esta área")
    
    def get_queryset(self):
        # Teacher endpoints require teacher role
        self.check_teacher_permission()
        
        # Teachers see only their own VIDEO courses (Draft + Published)
        queryset = Course.objects.filter(teacher=self.request.user, course_type='video')
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🎥 VIDEO TEACHER - Found {queryset.count()} video courses for teacher {self.request.user.email}")
        
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
        # Passa pelo perform_create: é aí que se exige o papel de professor e se fixa
        # course_type='video' (antes, um estudante conseguia criar cursos por aqui).
        self.perform_create(serializer)
        course = serializer.instance
        
        # Return course with full details
        response_serializer = CourseDetailSerializer(course, context={'request': request})
        
        return Response({
            'message': 'Curso criado com sucesso',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Teacher course management - return all courses without pagination
        context = {'request': request}
        context['include_description'] = request.query_params.get('include_description', 'true').lower() == 'true'
        context['include_enrollment_count'] = request.query_params.get('include_enrollment_count', 'false').lower() == 'true'
        
        serializer = self.get_serializer(queryset, many=True, context=context)
        
        return Response({
            'message': 'Cursos obtidos com sucesso',
            'data': serializer.data
        })


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
        # Teacher endpoints require authentication for ALL methods
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CourseUpdateSerializer
        return CourseDetailSerializer
    
    def check_object_permissions(self, request, obj):
        # For teacher endpoints, check teacher role first
        if getattr(request.user, 'role', None) != 'teacher':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas professores podem aceder a esta área")
        
        # For all operations, verify ownership
        if obj.teacher != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor proprietário pode aceder a este curso")
    
    def retrieve(self, request, *args, **kwargs):
        # Get base queryset and apply optimizations
        instance = self.get_object()
        
        # Get fresh instance with optimizations based on query parameters
        include_sections = request.query_params.get('include_sections', 'true').lower() == 'true'
        include_enrollments = request.query_params.get('include_enrollments', 'true').lower() == 'true'
        include_chapters = request.query_params.get('include_chapters', 'true').lower() == 'true'
        include_comments = request.query_params.get('include_chapter_comments', 'false').lower() == 'true'
        
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


# Transaction creation moved to student API


class TransactionListView(generics.ListAPIView):
    """
    List transactions for teacher's courses (analytics).
    
    GET /api/v1/teacher/video-courses/transactions/
    
    Teachers can see transactions for their courses to track sales.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 15, max: 50)
    - courseId: Filter by specific course
    - ordering: Sort order (-dateTime, amount, paymentProvider)
    """
    serializer_class = TransactionSerializer
    pagination_class = TransactionListPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def check_teacher_permission(self):
        """Check if user is a teacher, raise PermissionDenied if not."""
        if not self.request.user.is_authenticated:
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated("Autenticação necessária.")
        
        if getattr(self.request.user, 'role', None) != 'teacher':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas professores podem aceder a esta área")
    
    def get_queryset(self):
        # Check teacher permission
        self.check_teacher_permission()
        
        # Get transactions for teacher's video courses only
        course_id = self.request.query_params.get('courseId')
        
        if course_id:
            # Filter by specific course if provided (must be teacher's course)
            queryset = Transaction.objects.filter(
                course_id=course_id,
                course__teacher=self.request.user,
                course__course_type='video'
            )
        else:
            # All transactions for teacher's video courses
            queryset = Transaction.objects.filter(
                course__teacher=self.request.user,
                course__course_type='video'
            )
        
        # Optimize queries
        queryset = queryset.select_related('user', 'course')
        
        return optimize_paginated_queryset(queryset, self.request, '-dateTime')
    
    def list(self, request, *args, **kwargs):
        """Add transaction summary to response context for teacher analytics."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate summary for teacher's course sales
        from django.db.models import Sum, Count
        summary = queryset.aggregate(
            total_revenue=Sum('amount'),
            total_sales=Count('id')
        )
        
        # Add summary to request for pagination response
        request.transaction_summary = {
            'total_revenue': summary['total_revenue'] or 0,
            'total_sales': summary['total_sales'] or 0
        }
        
        return super().list(request, *args, **kwargs)


# User enrolled courses moved to student API


# User course progress moved to student API


# Update user course progress moved to student API


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

        # Auto-set order to next available position if not provided
        if not serializer.validated_data.get('order'):
            max_order = CourseSection.objects.filter(course=course).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            serializer.save(course=course, order=max_order + 1)
        else:
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

        # Auto-set order to next available position if not provided
        if not serializer.validated_data.get('order'):
            max_order = Chapter.objects.filter(section=section).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            serializer.save(section=section, order=max_order + 1)
        else:
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

# Stripe payment intent moved to student API


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


# Student quiz attempts moved to student API


# Student quiz summary moved to student API