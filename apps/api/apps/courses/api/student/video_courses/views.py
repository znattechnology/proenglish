"""
Views for the ProEnglish course management system - Student Video Courses API.

This module contains all API views for student video course-related operations,
maintaining the same endpoints and response format as the Express API.
"""

import uuid

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from apps.core.permissions import e_administrador as _e_admin
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError

from django.db.models import Count, Avg


# =============================================================================
# SECURITY MIXIN - Enrollment Verification
# =============================================================================

class EnrollmentRequiredMixin:
    """
    Mixin that requires user to be enrolled in the course to access content.

    SECURITY: This mixin prevents unauthorized access to paid course content.
    Apply to views that expose course content (chapters, quizzes, resources).

    The mixin checks:
    1. User is authenticated
    2. User has an active and non-expired enrollment in the course
    3. User has the required subscription level for premium courses

    To use, add this mixin BEFORE the base class:
        class MyView(EnrollmentRequiredMixin, generics.RetrieveAPIView):
            ...
    """

    def check_enrollment(self, course, chapter=None, parcial=False):
        """
        Check if the current user is enrolled in the course and has proper subscription.

        SECURITY: Uses atomic check to prevent race conditions.

        Args:
            course: The Course model instance
            chapter: a aula pedida; sem o plano do curso, só abre se estiver numa unidade de
                amostra (apps/courses/amostra.py). Fora da amostra: 403 plano_insuficiente.
            parcial: o pedido é do curso (p.ex. o percurso) e basta ter parte dele (a amostra).

        Raises:
            PermissionDenied: If user is not enrolled or doesn't have proper subscription
        """
        from django.utils import timezone

        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied("Autenticação necessária para aceder a este conteúdo.")

        # Estado do curso: fechado pelo professor (arquivado a fechar) ou não publicado.
        from apps.courses.ciclo import bloqueio_conteudo
        bloqueio = bloqueio_conteudo(user, course)
        if bloqueio:
            raise PermissionDenied(bloqueio[1])

        # Leitura simples: select_for_update() fora de transacção rebentava (500) em PostgreSQL.
        from ....models import CourseEnrollment
        try:
            enrollment = CourseEnrollment.objects.get(
                user=user,
                course=course,
                is_active=True
            )

            # Check if enrollment has expired
            if enrollment.expires_at and timezone.now() > enrollment.expires_at:
                raise PermissionDenied(
                    "A sua inscrição neste curso expirou. Renove para continuar a aceder."
                )

        except CourseEnrollment.DoesNotExist:
            raise PermissionDenied(
                "Precisa de estar inscrito neste curso para aceder a este conteúdo."
            )

        # SECURITY: Check subscription access for non-free courses
        # This is checked AFTER enrollment to prevent information leakage
        if not course.user_has_access(user):
            # Unidades de amostra: sem o plano, só as aulas das primeiras unidades.
            from apps.courses import amostra
            if amostra.unidades_amostra(course) > 0:
                if chapter is not None:
                    if chapter.section_id in amostra.ids_seccoes_amostra(course):
                        return
                    raise amostra.PlanoNecessario()
                if parcial:
                    return
            access_messages = {
                'premium': 'Este curso requer um plano Premium ou superior. A sua subscrição pode ter expirado.',
                'premium_plus': 'Este curso é exclusivo para assinantes Premium Plus.',
            }
            message = access_messages.get(
                course.access_level,
                'Não tem permissão para aceder a este conteúdo.'
            )
            raise PermissionDenied(message)

    def get_course_from_chapter(self, chapter):
        """Extract course from chapter object."""
        return chapter.section.course

    def get_course_from_quiz(self, quiz):
        """Extract course from quiz object."""
        return quiz.chapter.section.course

    def get_course_from_resource(self, resource):
        """Extract course from resource object."""
        return resource.chapter.section.course


class EstadoCursoMixin:
    def check_estado_curso(self, course):
        """Arquivado: só os inscritos (e não se o curso foi fechado). Ver apps/courses/ciclo.py."""
        from apps.courses import ciclo as _ciclo
        if course.status == _ciclo.PUBLICADO:
            return
        from .conteudo import pode_ver_parte
        if not pode_ver_parte(self.request.user, course):
            raise NotFound('Curso não encontrado.')

    def contexto_amostra(self, course):
        """Secções com conteúdo / bloqueadas num curso com unidades de amostra (conteudo.contexto_seccoes)."""
        from .conteudo import contexto_seccoes
        return contexto_seccoes(self.request.user, course)


class SubscriptionAccessMixin(EstadoCursoMixin):
    """
    Mixin that checks subscription access for course content without requiring enrollment.

    SECURITY: This mixin is for views that list content (sections, chapters).
    For free courses: allows unauthenticated access
    For premium courses: requires authentication and valid subscription

    Unlike EnrollmentRequiredMixin, this doesn't require enrollment, just subscription.
    Use this for browsing course structure (sections, chapter lists).
    Use EnrollmentRequiredMixin for accessing actual content (chapter details, videos).
    """

    def check_subscription_access(self, course):
        """
        Check if the current user has subscription access to the course.

        Args:
            course: The Course model instance

        Returns:
            bool: True if user has access, False otherwise

        Raises:
            PermissionDenied: If premium course and user lacks subscription
        """
        # Free courses are accessible to everyone
        if course.access_level == 'free':
            return True

        user = self.request.user

        # Premium courses require authentication
        if not user.is_authenticated:
            raise PermissionDenied(
                "Este curso requer uma subscrição. Inicie sessão para verificar o seu acesso."
            )

        # Check subscription access
        if not course.user_has_access(user):
            # Curso com unidades de amostra: a estrutura vê-se; o conteúdo só nas aulas da amostra
            # (contexto_amostra nos serializers, check_enrollment com a aula).
            from apps.courses import amostra
            if amostra.unidades_amostra(course) > 0:
                return True
            access_messages = {
                'premium': 'Este curso requer um plano Premium ou superior.',
                'premium_plus': 'Este curso é exclusivo para assinantes Premium Plus.',
            }
            message = access_messages.get(
                course.access_level,
                'Não tem a subscrição necessária para aceder a este conteúdo.'
            )
            raise PermissionDenied(message)

        return True


from apps.courses import ciclo, niveis
from ....models import (
    Course, CourseSection, Chapter, ChapterComment,
    CourseEnrollment, Transaction, UserCourseProgress, ChapterProgress,
    ChapterResource, ChapterQuiz, StudentQuizAttempt,
    CourseWishlist, CourseReview, StudentNote, StudentBookmark, CourseCertificate
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
    StudentQuizAttemptSerializer, StudentQuizAttemptCreateSerializer,
    CourseWishlistSerializer, CourseReviewSerializer, StudentNoteSerializer,
    StudentBookmarkSerializer, CourseCertificateSerializer
)
from ....pagination import (
    CourseListPagination, TransactionListPagination, CommentListPagination,
    QuizAttemptPagination, StandardResultsSetPagination, optimize_paginated_queryset
)


class StudentCourseListPagination(CourseListPagination):
    """Catálogo do estudante: 12 por página por omissão, `page_size` até 50."""
    max_page_size = 50


class CourseListView(generics.ListAPIView):
    """
    List published video courses for students.

    GET /api/v1/student/video-courses/ - List all published video courses

    Query Parameters for GET:
    - category: Filter by category ('all' for no filter)
    - access_level: Filter by access level ('free', 'premium', 'premium_plus', 'all')
    - is_featured: Filter by featured status ('true', 'false')
    - level: nível CEFR ('B1') ou lista ('A2,B1'); os nomes antigos valem a sua banda
    - search: texto a procurar no título, descrição ou categoria (todas as páginas)
    - status: ignorado (só cursos publicados)
    - ordering: created_at, title, level, category, is_featured, updated_at (com ou sem '-');
      outro valor usa -created_at
    - include_description: Include description field (default: true)
    - include_enrollment_count: Include enrollment count (default: false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 12, max: 50)
    """
    serializer_class = CourseListSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StudentCourseListPagination
    ORDENACOES = {
        'created_at', '-created_at', 'updated_at', '-updated_at', 'title', '-title',
        'level', '-level', 'category', '-category', 'is_featured', '-is_featured',
    }

    def get_queryset(self):
        # Students see only published VIDEO courses
        queryset = Course.objects.filter(ciclo.q_catalogo(), course_type='video')

        # Apply category filter
        category = self.request.query_params.get('category')
        if category and category != 'all':
            queryset = queryset.filter(category=category)

        # Apply access_level filter
        access_level = self.request.query_params.get('access_level')
        if access_level and access_level != 'all':
            valid_levels = ['free', 'premium', 'premium_plus']
            if access_level in valid_levels:
                queryset = queryset.filter(access_level=access_level)

        # Apply is_featured filter
        is_featured = self.request.query_params.get('is_featured')
        if is_featured == 'true':
            queryset = queryset.filter(is_featured=True)
        elif is_featured == 'false':
            queryset = queryset.filter(is_featured=False)

        # Apply level filter
        codigos = niveis.filtro(self.request.query_params.get('level'))
        if codigos:
            queryset = queryset.filter(level__in=codigos)

        # Pesquisa no servidor (título, descrição, categoria), em todas as páginas.
        search = (self.request.query_params.get('search') or '').strip()[:100]
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search) | Q(category__icontains=search)
            )
        # `status`: os estudantes só vêem cursos publicados; outro valor não alarga a lista.

        # Use optimized queryset from serializer
        include_enrollment_count = self.request.query_params.get('include_enrollment_count', 'false').lower() == 'true'
        queryset = CourseListSerializer.optimize_queryset(
            queryset,
            include_enrollment_count=include_enrollment_count
        )

        # Ordenação só de uma lista fechada (antes um valor desconhecido dava 500 e
        # permitia ordenar por campos internos como teacher__password).
        ordering = self.request.query_params.get('ordering') or '-created_at'
        if ordering not in self.ORDENACOES:
            ordering = '-created_at'
        campos = [ordering] if ordering == '-created_at' else [ordering, '-created_at']
        return queryset.order_by(*campos)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Get context for serialization
        context = {'request': request}
        context['include_description'] = request.query_params.get('include_description', 'true').lower() == 'true'
        context['include_enrollment_count'] = request.query_params.get('include_enrollment_count', 'false').lower() == 'true'

        # Paginate queryset
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context=context)
            response = self.get_paginated_response(serializer.data)
            # Add custom message to paginated response
            response.data['message'] = 'Cursos obtidos com sucesso'
            return response

        # Fallback without pagination (shouldn't happen with pagination_class set)
        serializer = self.get_serializer(queryset, many=True, context=context)

        return Response({
            'message': 'Cursos obtidos com sucesso',
            'data': serializer.data
        })


class CourseDetailView(generics.RetrieveAPIView):
    """
    Retrieve course details for students.

    GET /api/v1/student/video-courses/{id}/ - Get course details

    SECURITY: For premium courses, unauthenticated users and users without
    subscription only see limited preview (section titles, no chapter details).
    """
    # Publicados (mesmo fora do catálogo, por ligação) e arquivados a manter para os inscritos.
    queryset = Course.objects.filter(ciclo.q_conteudo_aluno(), course_type='video')
    serializer_class = CourseDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    lookup_url_kwarg = 'courseId'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if instance.status != ciclo.PUBLICADO:
            from .conteudo import pode_ver_parte
            if not pode_ver_parte(user, instance):
                from rest_framework.exceptions import NotFound
                raise NotFound("Curso não encontrado ou não está publicado")

        # SECURITY: Check if user has access to this course
        user_has_access = False

        if user and user.is_authenticated:
            user_has_access = instance.user_has_access(user)
        else:
            # Unauthenticated users only have access to free courses
            user_has_access = instance.access_level == 'free'

        # Get fresh instance with optimizations based on query parameters
        include_sections = request.query_params.get('include_sections', 'true').lower() == 'true'
        include_enrollments = request.query_params.get('include_enrollments', 'true').lower() == 'true'
        include_chapters = request.query_params.get('include_chapters', 'true').lower() == 'true'
        include_comments = request.query_params.get('include_chapter_comments', 'false').lower() == 'true'

        # SECURITY: Limit content for users without subscription access
        # (num curso com unidades de amostra a estrutura das aulas vê-se: o conteúdo só nas da amostra)
        from apps.courses import amostra
        n_amostra = amostra.unidades_amostra(instance)
        if not user_has_access and instance.access_level != 'free' and n_amostra == 0:
            # Show only basic course info and section titles (no chapters)
            include_chapters = False
            include_comments = False

        # Re-fetch with optimizations
        optimized_queryset = CourseDetailSerializer.optimize_queryset(
            Course.objects.filter(ciclo.q_conteudo_aluno(), id=instance.id, course_type='video'),
            include_sections=include_sections,
            include_enrollments=include_enrollments
        )
        instance = optimized_queryset.first()

        if not instance:
            from rest_framework.exceptions import NotFound
            raise NotFound("Curso não encontrado ou não está publicado")

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
        context['user_has_subscription_access'] = user_has_access
        from .conteudo import contexto_seccoes, pode_ver_conteudo
        context['so_estrutura'] = not pode_ver_conteudo(user, instance)
        context.update(contexto_seccoes(user, instance))

        serializer = self.get_serializer(instance, context=context)

        # Add access information to response
        response_data = {
            'message': 'Curso obtido com sucesso',
            'data': serializer.data,
            'access_info': {
                'has_access': user_has_access,
                'access_level': instance.access_level,
                'access_level_display': instance.access_level_display,
                'content_limited': not user_has_access and instance.access_level != 'free',
                # Unidades de amostra: 'total' | 'amostra' | None (apps/courses/amostra.py).
                'acesso': amostra.acesso(user, instance, total=user_has_access),
                'unidades_amostra': n_amostra,
            }
        }

        return Response(response_data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_transaction(request):
    """
    Create transaction and enroll user in course.

    POST /api/v1/courses/transactions/create/

    Maps to Express: POST /transactions

    SECURITY: Verifies user has required subscription before enrollment.
    """
    serializer = TransactionCreateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    # SECURITY FIX: Get course and verify subscription access BEFORE enrollment
    course_id = request.data.get('courseId')
    if course_id:
        try:
            course = Course.objects.get(id=course_id)
            # Check if user has subscription access for non-free courses
            # (ou o curso tem unidades de amostra: inscreve-se e abre só essas).
            from apps.courses import amostra
            if not amostra.pode_inscrever(request.user, course):
                access_messages = {
                    'premium': 'Este curso requer um plano Premium ou superior.',
                    'premium_plus': 'Este curso é exclusivo para assinantes Premium Plus.',
                }
                message = access_messages.get(
                    course.access_level,
                    'Não tem a subscrição necessária para aceder a este curso.'
                )
                return Response({
                    'error': 'Acesso negado',
                    'message': message,
                    'code': 'SUBSCRIPTION_REQUIRED',
                    'required_plan': course.access_level,
                    'upgrade_required': True
                }, status=status.HTTP_403_FORBIDDEN)
        except Course.DoesNotExist:
            return Response({
                'error': 'Curso não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        # Estado e definições do curso: só publicados, inscrições abertas e com vagas.
        bloqueio = ciclo.bloqueio_inscricao(request.user, course)
        if bloqueio:
            from apps.core.exceptions import corpo_erro
            return Response(corpo_erro(bloqueio[1], bloqueio[0]), status=bloqueio[2])

    with transaction.atomic():
        # Os cursos estão incluídos nos planos: a inscrição nunca tem custo próprio.
        # O valor vem do servidor, nunca do cliente.
        import uuid
        new_transaction = serializer.save(amount=0, transactionId=f'inscricao_{uuid.uuid4().hex}')

        # Create enrollment + initial progress (user already verified to have access)
        from apps.courses.matriculas import matricular_em_curso
        enrollment, progress = matricular_em_curso(request.user, new_transaction.course)

    return Response({
        'message': 'Inscrição feita com sucesso',
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
        return Response({'error': 'Utilizador não encontrado.'}, status=404)
    
    # Get enrolled courses - only published video courses
    # Ordem: o curso mexido mais recentemente primeiro (último acesso/progresso), depois a
    # data de inscrição. O "Continuar" do painel usa o primeiro.
    from django.db.models import F, OuterRef, Subquery
    ultimo_acesso = UserCourseProgress.objects.filter(
        user=user, course=OuterRef('course_id')).values('lastAccessedTimestamp')[:1]
    enrollments = CourseEnrollment.objects.filter(
        user=user,
        course__course_type='video',
    ).filter(ciclo.q_conteudo_aluno('course__')).select_related('course', 'course__teacher').annotate(
        _ultimo_acesso=Subquery(ultimo_acesso)
    ).order_by(F('_ultimo_acesso').desc(nulls_last=True), '-enrollment_date')

    courses = [enrollment.course for enrollment in enrollments]

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
        return Response({'error': 'Utilizador ou curso não encontrado.'}, status=404)
    except UserCourseProgress.DoesNotExist:
        return Response({'error': 'Ainda não há progresso neste curso.'}, status=404)
    
    serializer = UserCourseProgressSerializer(progress)
    
    return Response({
        'message': 'Progresso do curso obtido com sucesso',
        'data': serializer.data
    })


def _pode_marcar_vista(dados, capitulo):
    """Falso se o pedido desmarcou este capítulo (completed=false) ou se já está concluído."""
    for sec in (dados.get('sections') or []) if isinstance(dados.get('sections'), list) else []:
        if not isinstance(sec, dict):
            continue
        for cap in sec.get('chapters') or []:
            if isinstance(cap, dict) and str(cap.get('chapterId')) == str(capitulo.id) and cap.get('completed') is False:
                return False
    return True


def _marcar_vista(progresso, capitulo):
    """
    Regista o vídeo como visto e recalcula o progresso. Devolve True se a aula ficou concluída
    agora (numa aula com questionário, só quando o questionário também está passado).
    """
    from apps.courses.conclusao import actualizar_progresso, registar
    if not registar(progresso, capitulo, vista=True):
        return False
    actualizar_progresso(progresso)
    return True


def _exigir_aulas_da_amostra(dados, course):
    """
    Sem o plano do curso: todas as aulas do pedido (chapter_id e sections[].chapters[]) têm de
    estar nas secções da amostra; senão 403 plano_insuficiente e nada é gravado.
    """
    from apps.courses import amostra
    ids = [dados.get('chapter_id')] if dados.get('chapter_id') else []
    seccoes = dados.get('sections') if isinstance(dados.get('sections'), list) else []
    ids += [c.get('chapterId') for sec in seccoes if isinstance(sec, dict)
            for c in (sec.get('chapters') or []) if isinstance(c, dict) and c.get('chapterId')]
    if not ids:
        return
    abertas = amostra.ids_seccoes_amostra(course)
    validos = []
    for i in ids:
        try:
            validos.append(uuid.UUID(str(i)))
        except (ValueError, TypeError, AttributeError):
            continue  # ids inválidos são ignorados mais à frente, como antes
    fora = Chapter.objects.filter(id__in=validos, section__course=course).exclude(section_id__in=abertas)
    if fora.exists():
        raise amostra.PlanoNecessario()


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_user_course_progress(request, userId, courseId):
    """
    Update user progress in a specific course.
    
    PUT /api/v1/courses/users/{userId}/progress/{courseId}/
    
    Maps to Express: PUT /users/course-progress/:userId/:courseId
    """
    # userId and courseId are already UUID objects from Django URL converter
    # Check if user can update this data
    if request.user.id != userId:
        raise PermissionDenied("Acesso negado")
    
    try:
        from apps.users.models import User
        user = User.objects.get(id=userId)
        course = Course.objects.get(id=courseId)
        progress = UserCourseProgress.objects.get(user=user, course=course)
    except (User.DoesNotExist, Course.DoesNotExist):
        return Response({'error': 'Utilizador ou curso não encontrado.'}, status=404)
    except UserCourseProgress.DoesNotExist:
        progress = None

    # Só regista progresso quem está inscrito e tem o plano do curso (antes qualquer aluno podia),
    # ou, num curso com unidades de amostra, nas aulas da amostra (apps/courses/amostra.py).
    from apps.courses import amostra
    total = course.user_has_access(user)
    if not total and amostra.unidades_amostra(course) <= 0:
        raise PermissionDenied('Não tem a subscrição necessária para este curso.')
    from .conteudo import pode_ver_parte
    if not pode_ver_parte(user, course):
        raise PermissionDenied('Precisa de estar inscrito neste curso para registar progresso.')
    if not total:
        _exigir_aulas_da_amostra(request.data, course)

    if progress is None:
        # Create progress if it doesn't exist
        progress = UserCourseProgress.objects.create(
            user=user,
            course=course,
            enrollmentDate=timezone.now(),
            overallProgress=0.0
        )
    
    serializer = UserCourseProgressUpdateSerializer(
        progress,
        data=request.data,
        context={'request': request}
    )
    serializer.is_valid(raise_exception=True)

    # Opcional: segundos vistos desde o último envio -> registo diário + sequência.
    # O capítulo é `chapter_id` ou o único capítulo enviado em `sections`. Os segundos são
    # limitados (ver apps.courses.tempo_video): só o que é novo conta e nunca mais do que o tempo
    # real desde que o aluno abriu a aula. Creditam-se ANTES de gravar, para "marcar como vista"
    # já contar com o que o aluno acabou de ver.
    watched_seconds = request.data.get('watched_seconds')
    segundos_creditados = 0
    capitulo = None
    chapter_id = request.data.get('chapter_id')
    if not chapter_id:
        ids = [c.get('chapterId') for sec in (request.data.get('sections') or []) if isinstance(sec, dict)
               for c in (sec.get('chapters') or []) if isinstance(c, dict) and c.get('chapterId')]
        chapter_id = ids[0] if len(ids) == 1 else None
    if chapter_id:
        try:
            capitulo = Chapter.objects.filter(ciclo.q_aula_visivel(), id=chapter_id, section__course=course).first()
        except (ValueError, TypeError, DjangoValidationError):
            capitulo = None
    if capitulo is not None and watched_seconds not in (None, ''):
        try:
            from ....tempo_video import creditar_segundos
            segundos_creditados = creditar_segundos(request.user, capitulo, watched_seconds)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to log video study minutes")

    def _concluida():
        return capitulo is not None and ChapterProgress.objects.filter(
            user_progress=progress, chapter=capitulo, completed=True).exists()

    concluida_antes = _concluida()
    # Várias aulas no mesmo pedido: ou ficam todas gravadas ou nenhuma (um erro a meio, como um
    # vídeo por ver, não deixa metade do pedido gravado).
    with transaction.atomic():
        updated_progress = serializer.save()
        if capitulo is not None and watched_seconds not in (None, ''):
            # A aula conta como vista quando o aluno viu a percentagem que o professor escolheu
            # (Chapter.percentagem_vista), salvo se este pedido a desmarcou explicitamente.
            if _pode_marcar_vista(request.data, capitulo):
                from ....tempo_video import aula_vista
                if aula_vista(request.user, capitulo):
                    _marcar_vista(updated_progress, capitulo)
    # aula_concluida: a aula passou a concluída com este pedido (estado antes vs. depois).
    aula_concluida = not concluida_antes and _concluida()

    # Return updated progress
    response_serializer = UserCourseProgressSerializer(updated_progress)
    
    return Response({
        'message': 'Progresso actualizado com sucesso',
        'segundos_creditados': segundos_creditados,
        'aula_concluida': aula_concluida,
        'data': response_serializer.data
    })


# Course Section Views (Read-only for students)

class CourseSectionListView(SubscriptionAccessMixin, generics.ListAPIView):
    """
    List sections for a published course.

    SECURITY: Checks subscription access for premium courses.
    Free courses: accessible to everyone
    Premium courses: requires valid subscription
    """
    serializer_class = CourseSectionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        course_id = self.kwargs['courseId']
        include_comments = self.request.query_params.get('include_comments', 'false').lower() == 'true'

        # Only sections from published video courses
        queryset = CourseSection.objects.filter(
            ciclo.q_conteudo_aluno('course__'),
            course__id=course_id,
            course__course_type='video'
        )

        # Optimize based on requirements
        if include_comments:
            queryset = queryset.prefetch_related('chapters__comments__user')
        else:
            queryset = queryset.prefetch_related('chapters')

        return queryset.order_by('order')

    def list(self, request, *args, **kwargs):
        """Override list to check subscription access before returning sections."""
        course_id = self.kwargs['courseId']
        try:
            course = Course.objects.filter(ciclo.q_conteudo_aluno()).get(id=course_id, course_type='video')
        except Course.DoesNotExist:
            return Response({
                'error': 'Curso não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        # SECURITY: Check subscription access
        self.check_subscription_access(course)
        self.check_estado_curso(course)
        self._curso = course

        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        curso = getattr(self, '_curso', None)
        if curso is not None:
            context.update(self.contexto_amostra(curso))
        return context


class CourseSectionDetailView(SubscriptionAccessMixin, generics.RetrieveAPIView):
    """
    Retrieve a course section details.

    SECURITY: Checks subscription access for premium courses.
    """
    serializer_class = CourseSectionSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    lookup_url_kwarg = 'sectionId'

    def get_queryset(self):
        return CourseSection.objects.filter(
            ciclo.q_conteudo_aluno('course__'),
            course__course_type='video'
        ).select_related('course')

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to check subscription access before returning section."""
        instance = self.get_object()
        course = instance.course

        # SECURITY: Check subscription access
        self.check_subscription_access(course)
        self.check_estado_curso(course)

        context = self.get_serializer_context()
        context.update(self.contexto_amostra(course))
        serializer = self.get_serializer_class()(instance, context=context)
        return Response(serializer.data)


# Chapter Views (Read-only for students)

class ChapterListView(SubscriptionAccessMixin, generics.ListAPIView):
    """
    List chapters for a section.

    SECURITY: Checks subscription access for premium courses.
    Free courses: accessible to everyone
    Premium courses: requires valid subscription
    """
    serializer_class = ChapterSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        section_id = self.kwargs['sectionId']
        return Chapter.objects.filter(
            ciclo.q_conteudo_aluno('section__course__'), ciclo.q_aula_visivel(),
            section__id=section_id,
            section__course__course_type='video'
        ).order_by('order')

    def list(self, request, *args, **kwargs):
        """Override list to check subscription access before returning chapters."""
        section_id = self.kwargs['sectionId']
        try:
            section = CourseSection.objects.select_related('course').filter(
                ciclo.q_conteudo_aluno('course__')).get(
                id=section_id,
                course__course_type='video'
            )
        except CourseSection.DoesNotExist:
            return Response({
                'error': 'Secção não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)

        # SECURITY: Check subscription access
        self.check_subscription_access(section.course)
        self.check_estado_curso(section.course)
        self._curso = section.course

        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        from .conteudo import pode_ver_conteudo
        context = super().get_serializer_context()
        curso = getattr(self, '_curso', None)
        context['so_estrutura'] = curso is None or not pode_ver_conteudo(self.request.user, curso)
        if curso is not None:
            context.update(self.contexto_amostra(curso))
        return context


class ChapterDetailView(EnrollmentRequiredMixin, generics.RetrieveAPIView):
    """
    Retrieve chapter details.

    SECURITY: Requires enrollment to access chapter content.
    """
    serializer_class = ChapterSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'chapterId'

    def get_queryset(self):
        return Chapter.objects.filter(
            ciclo.q_conteudo_aluno('section__course__'), ciclo.q_aula_visivel(),
            section__course__course_type='video'
        ).select_related('section', 'section__course')

    def get_object(self):
        """Override to check enrollment before returning object."""
        obj = super().get_object()
        course = self.get_course_from_chapter(obj)
        self.check_enrollment(course, chapter=obj)
        # Hora a que o aluno abriu a aula: o tempo de vídeo creditado não passa do tempo real
        # desde aqui (apps.courses.tempo_video).
        if course.teacher_id != self.request.user.id:
            from ....tempo_video import marcar_aberta
            marcar_aberta(self.request.user, obj)
        return obj


# Chapter Comment Views

class ChapterCommentListCreateView(EnrollmentRequiredMixin, generics.ListCreateAPIView):
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
    
    def _chapter(self):
        # Mesmas regras do detalhe do capítulo: inscrição activa e plano com acesso.
        if not hasattr(self, '_cached_chapter'):
            chapter = get_object_or_404(
                Chapter.objects.filter(ciclo.q_aula_visivel()).select_related('section__course'),
                id=self.kwargs['chapterId']
            )
            self.check_enrollment(self.get_course_from_chapter(chapter), chapter=chapter)
            self._cached_chapter = chapter
        return self._cached_chapter

    def get_queryset(self):
        queryset = ChapterComment.objects.filter(chapter=self._chapter())
        return ChapterCommentSerializer.optimize_queryset(queryset)
    
    def perform_create(self, serializer):
        serializer.save(chapter=self._chapter())


# Stripe Payment Intent View
# NOTE: This endpoint is for SUBSCRIPTION payments, not individual course purchases.
# The platform uses a subscription model - all courses are included with subscription.

# =============================================================================
# 🆕 PHASE 1 BRIDGE ENDPOINTS - Chapter Enhancement API
# =============================================================================

class ChapterResourceListView(EnrollmentRequiredMixin, generics.ListAPIView):
    """
    List resources for a chapter (read-only for students).

    GET /api/v1/student/video-courses/chapters/{chapterId}/resources/

    Query Parameters for GET:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - ordering: Sort order (order, -created_at, resource_type)

    SECURITY: Requires enrollment to access chapter resources.
    """
    serializer_class = ChapterResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        queryset = ChapterResource.objects.filter(
            ciclo.q_conteudo_aluno('chapter__section__course__'), ciclo.q_aula_visivel('chapter__'),
            chapter__id=chapter_id,
            chapter__section__course__course_type='video'
        )
        queryset = queryset.select_related('chapter', 'chapter__section__course', 'created_by')
        return optimize_paginated_queryset(queryset, self.request, 'order')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Check enrollment using first resource's course (if any)
        if queryset.exists():
            first_resource = queryset.first()
            course = self.get_course_from_resource(first_resource)
            self.check_enrollment(course, chapter=first_resource.chapter)

        serializer = self.get_serializer(queryset, many=True)

        return Response({
            'message': 'Recursos do capítulo obtidos com sucesso',
            'data': serializer.data
        })


class ChapterResourceDetailView(EnrollmentRequiredMixin, generics.RetrieveAPIView):
    """
    Retrieve a chapter resource (read-only for students).

    GET /api/v1/student/video-courses/chapters/{chapterId}/resources/{resourceId}/

    SECURITY: Requires enrollment to access resource.
    """
    serializer_class = ChapterResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'resourceId'

    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        return ChapterResource.objects.filter(
            ciclo.q_conteudo_aluno('chapter__section__course__'), ciclo.q_aula_visivel('chapter__'),
            chapter__id=chapter_id,
            chapter__section__course__course_type='video'
        ).select_related('chapter__section__course')

    def get_object(self):
        """Override to check enrollment before returning object."""
        obj = super().get_object()
        course = self.get_course_from_resource(obj)
        self.check_enrollment(course, chapter=obj.chapter)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Increment download count for students
        instance.download_count += 1
        instance.save(update_fields=['download_count'])

        serializer = self.get_serializer(instance)

        return Response({
            'message': 'Recurso obtido com sucesso',
            'data': serializer.data
        })


class ChapterQuizListView(EnrollmentRequiredMixin, generics.ListAPIView):
    """
    Get quiz for a chapter (read-only for students).

    GET /api/v1/student/video-courses/chapters/{chapterId}/quiz/

    SECURITY: Requires enrollment to access quiz.
    """
    serializer_class = ChapterQuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        return ChapterQuiz.objects.filter(
            ciclo.q_conteudo_aluno('chapter__section__course__'), ciclo.q_aula_visivel('chapter__'),
            chapter__id=chapter_id,
            chapter__section__course__course_type='video',
            is_active=True
        ).select_related('chapter__section__course')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if not queryset.exists():
            return Response({
                'message': 'Nenhum quiz encontrado para este capítulo',
                'data': None
            })

        # Should be only one quiz per chapter
        quiz = queryset.first()

        # Check enrollment
        course = self.get_course_from_quiz(quiz)
        self.check_enrollment(course, chapter=quiz.chapter)

        serializer = self.get_serializer(quiz)

        return Response({
            'message': 'Quiz do capítulo obtido com sucesso',
            'data': serializer.data
        })


class ChapterQuizDetailView(EnrollmentRequiredMixin, generics.RetrieveAPIView):
    """
    Retrieve a chapter quiz (read-only for students).

    GET /api/v1/student/video-courses/chapters/{chapterId}/quiz/{quizId}/

    SECURITY: Requires enrollment to access quiz details.
    """
    serializer_class = ChapterQuizSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'quizId'

    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']
        return ChapterQuiz.objects.filter(
            ciclo.q_conteudo_aluno('chapter__section__course__'), ciclo.q_aula_visivel('chapter__'),
            chapter__id=chapter_id,
            chapter__section__course__course_type='video',
            is_active=True
        ).select_related('chapter__section__course')

    def get_object(self):
        """Override to check enrollment before returning object."""
        obj = super().get_object()
        course = self.get_course_from_quiz(obj)
        self.check_enrollment(course, chapter=obj.chapter)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return Response({
            'message': 'Quiz obtido com sucesso',
            'data': serializer.data
        })


class StudentQuizAttemptListCreateView(EnrollmentRequiredMixin, generics.ListCreateAPIView):
    """
    List quiz attempts for a student or create new attempt.
    
    GET /api/v1/courses/chapters/{chapterId}/quiz/attempts/
    POST /api/v1/courses/chapters/{chapterId}/quiz/attempts/
    
    Query Parameters for GET:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 25, max: 50)
    - ordering: Sort order (-created_at, score, attempt_number)
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = QuizAttemptPagination
    
    def get_queryset(self):
        chapter_id = self.kwargs['chapterId']

        # Get the chapter quiz with optimized query
        try:
            chapter_quiz = ChapterQuiz.objects.select_related(
                'chapter__section__course__teacher'
            ).filter(ciclo.q_aula_visivel('chapter__')).get(chapter__id=chapter_id)
        except ChapterQuiz.DoesNotExist:
            return StudentQuizAttempt.objects.none()

        # Base queryset with optimized relations to avoid N+1
        base_queryset = StudentQuizAttempt.objects.select_related(
            'student',
            'chapter_quiz',
            'chapter_quiz__chapter'
        )

        # Students see only their attempts, teachers see all attempts
        if self.request.user.role == 'teacher' and chapter_quiz.chapter.section.course.teacher == self.request.user:
            return base_queryset.filter(chapter_quiz=chapter_quiz).order_by('-created_at')
        else:
            return base_queryset.filter(
                chapter_quiz=chapter_quiz,
                student=self.request.user
            ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudentQuizAttemptCreateSerializer
        return StudentQuizAttemptSerializer
    
    def perform_create(self, serializer):
        chapter_id = self.kwargs['chapterId']
        chapter_quiz = ChapterQuiz.objects.select_related('chapter__section__course').filter(
            ciclo.q_aula_visivel('chapter__'), chapter__id=chapter_id).first()
        if chapter_quiz is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('Este capítulo não tem questionário.')
        self.check_enrollment(self.get_course_from_quiz(chapter_quiz), chapter=chapter_quiz.chapter)

        # Check if quiz is active
        if not chapter_quiz.is_active:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Este questionário não está activo.")
        
        # Check if student exceeded max attempts
        student_attempts = StudentQuizAttempt.objects.filter(
            student=self.request.user,
            chapter_quiz=chapter_quiz
        ).count()
        
        limite = chapter_quiz.limite_tentativas(self.request.user)
        if student_attempts >= limite:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f"Já usou as {limite} tentativas deste questionário.")
        
        # is_passed é decidido pelo servidor (StudentQuizAttempt.save compara com passing_score);
        # as estatísticas do quiz também são actualizadas no save() do modelo.
        serializer.save(chapter_quiz=chapter_quiz, is_passed=False)
    
    def list(self, request, *args, **kwargs):
        from .conteudo import correccao_para_aluno, pode_revelar_respostas
        chapter_quiz = ChapterQuiz.objects.select_related('chapter__section__course').filter(
            chapter__id=self.kwargs['chapterId']).first()
        if chapter_quiz is not None:
            curso = self.get_course_from_quiz(chapter_quiz)
            if curso.teacher_id != request.user.id:
                self.check_enrollment(curso, chapter=chapter_quiz.chapter)
        queryset = list(self.filter_queryset(self.get_queryset()))
        serializer = self.get_serializer(queryset, many=True)
        dados = [dict(d) for d in serializer.data]
        revela = False
        if chapter_quiz is not None:
            minhas = [a for a in queryset if a.student_id == request.user.id]
            revela = (chapter_quiz.chapter.section.course.teacher_id == request.user.id
                      or pode_revelar_respostas(chapter_quiz, any(a.is_passed for a in minhas),
                                                chapter_quiz.limite_tentativas(request.user) - len(minhas)))
            for item, tentativa in zip(dados, queryset):
                item['correccao'] = correccao_para_aluno(
                    (tentativa.answers_data or {}).get('correccao'), revela, chapter_quiz.chapter_id)

        return Response({
            'message': 'Tentativas do questionário obtidas com sucesso',
            'revela_respostas': revela,
            'data': dados,
        })

    def create(self, request, *args, **kwargs):
        """
        POST {respostas: {id_da_pergunta: id_da_opção | [ids]}, time_taken?}
        A nota é calculada aqui a partir do quiz do capítulo; a pontuação enviada pelo
        browser é ignorada (antes qualquer estudante podia dar a si próprio 100%).

        A resposta traz `revela_respostas` e, por pergunta, só `certa`/`respondida`;
        `opcoes_certas` e `explicacao` só quando passou ou já não tem tentativas.
        """
        from .conteudo import corrigir_quiz, correccao_para_aluno, pode_revelar_respostas, respondidas
        respostas = request.data.get('respostas')
        if not isinstance(respostas, dict):
            return Response({'error': 'Envie as respostas: {"respostas": {"<pergunta>": "<opção>"}}.'},
                            status=status.HTTP_400_BAD_REQUEST)
        chapter = get_object_or_404(Chapter, id=self.kwargs['chapterId'])
        pontos, maximo, correccao = corrigir_quiz(chapter.quiz_data, respostas, chapter.id)
        if maximo == 0:
            return Response({'error': 'Este questionário ainda não tem perguntas.'}, status=status.HTTP_400_BAD_REQUEST)
        if respondidas(correccao) == 0:
            return Response({'error': 'Responda a pelo menos uma pergunta antes de enviar.'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data={
            'score': pontos,
            'max_score': maximo,
            'time_taken': request.data.get('time_taken'),
            'is_completed': True,
        })
        serializer.is_valid(raise_exception=True)
        # perform_create usa o quiz do URL e aplica inscrição, quiz activo e limite de tentativas.
        self.perform_create(serializer)
        attempt = serializer.instance
        # Guarda as respostas e a correcção completa (para a revisão quando puder ser revelada).
        attempt.answers_data = {'respostas': respostas, 'correccao': correccao}
        StudentQuizAttempt.objects.filter(pk=attempt.pk).update(answers_data=attempt.answers_data)
        minhas = StudentQuizAttempt.objects.filter(student=request.user, chapter_quiz=attempt.chapter_quiz)
        restantes = max(0, attempt.chapter_quiz.limite_tentativas(request.user) - minhas.count())
        aula_concluida = False
        if attempt.is_passed or restantes <= 0:
            # Passar o questionário conclui a aula (se o vídeo, quando o há, já foi visto). Gastar
            # as tentativas todas sem passar também (rede de segurança: a aula não fica presa para
            # sempre; a nota do questionário continua a contar na nota do curso).
            from apps.courses.conclusao import apos_questionario_passado
            aula_concluida = apos_questionario_passado(request.user, chapter)
        revela = pode_revelar_respostas(attempt.chapter_quiz, minhas.filter(is_passed=True).exists(), restantes)

        response_serializer = StudentQuizAttemptSerializer(attempt, context={'request': request})
        dados = dict(response_serializer.data)
        dados['revela_respostas'] = revela
        dados['correccao'] = correccao_para_aluno(correccao, revela, chapter.id)
        dados['tentativas_restantes'] = restantes
        dados['aula_concluida'] = aula_concluida

        return Response({
            'message': 'Tentativa registada com sucesso',
            'revela_respostas': revela,
            'data': dados
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_student_quiz_summary(request, chapterId):
    """
    Resumo das tentativas do estudante no questionário de um capítulo.

    GET /api/v1/student/video-courses/chapters/{chapterId}/quiz/summary/

    Só para quem pode ver o conteúdo do curso (inscrito com o plano certo, o professor do
    curso ou administrador). `revela_respostas` diz se a correcção traz as opções certas.
    """
    from .conteudo import pode_ver_aula, correccao_para_aluno, pode_revelar_respostas

    chapter = get_object_or_404(Chapter.objects.filter(ciclo.q_aula_visivel()).select_related('section__course'),
                                id=chapterId)
    if not pode_ver_aula(request.user, chapter):
        from apps.courses import amostra
        if (amostra.unidades_amostra(chapter.section.course) > 0
                and not amostra.aula_aberta(request.user, chapter)):
            raise amostra.PlanoNecessario()
        return Response({'error': 'Precisa de estar inscrito neste curso para ver o questionário.'},
                        status=status.HTTP_403_FORBIDDEN)
    try:
        chapter_quiz = ChapterQuiz.objects.get(chapter=chapter)
    except ChapterQuiz.DoesNotExist:
        return Response({
            'message': 'Este capítulo não tem questionário',
            'data': None
        })

    # Get student's attempts
    attempts = StudentQuizAttempt.objects.filter(
        chapter_quiz=chapter_quiz,
        student=request.user
    ).order_by('-created_at')

    if not attempts.exists():
        return Response({
            'message': 'Ainda não há tentativas',
            'revela_respostas': False,
            'data': {
                'quiz_info': ChapterQuizSerializer(chapter_quiz, context={'request': request}).data,
                'attempts_count': 0,
                'best_score': 0,
                'is_passed': False,
                'attempts_remaining': chapter_quiz.limite_tentativas(request.user),
                'revela_respostas': False,
                'last_attempt': None
            }
        })

    best_attempt = attempts.filter(is_completed=True).order_by('-score').first()
    last_attempt = attempts.first()
    passed_attempt = attempts.filter(is_passed=True).first()
    restantes = max(0, chapter_quiz.limite_tentativas(request.user) - attempts.count())
    revela = pode_revelar_respostas(chapter_quiz, bool(passed_attempt), restantes)

    def _tentativa(t):
        if not t:
            return None
        dados = dict(StudentQuizAttemptSerializer(t, context={'request': request}).data)
        dados['correccao'] = correccao_para_aluno((t.answers_data or {}).get('correccao'), revela, chapter.id)
        return dados

    summary_data = {
        'quiz_info': ChapterQuizSerializer(chapter_quiz, context={'request': request}).data,
        'attempts_count': attempts.count(),
        'best_score': best_attempt.score_percentage if best_attempt else 0,
        'is_passed': bool(passed_attempt),
        'attempts_remaining': restantes,
        'revela_respostas': revela,
        'last_attempt': _tentativa(last_attempt),
        'best_attempt': _tentativa(best_attempt),
    }

    return Response({
        'message': 'Resumo do questionário obtido com sucesso',
        'revela_respostas': revela,
        'data': summary_data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_course_enrollment_status(request, courseId):
    """
    Check if user is enrolled in a specific course and has access.

    GET /api/v1/student/video-courses/{courseId}/enrollment-status/

    Returns:
    - is_enrolled: Whether user is enrolled
    - has_access: Whether user's subscription allows access
    - can_enroll: Whether user can enroll (has required subscription)
    - access_level: Course's required access level
    - access_level_display: Human-readable access level
    """
    try:
        course = Course.objects.filter(ciclo.q_conteudo_aluno()).get(id=courseId, course_type='video')
    except Course.DoesNotExist:
        return Response({
            'error': 'Curso não encontrado ou não está publicado'
        }, status=404)

    # Check if user is enrolled
    is_enrolled = CourseEnrollment.objects.filter(
        user=request.user,
        course=course,
        is_active=True
    ).exists()

    # Check subscription access
    has_access = course.user_has_access(request.user)
    from apps.courses import amostra
    n_amostra = amostra.unidades_amostra(course)

    # Get enrollment details if enrolled
    enrollment_data = None
    if is_enrolled:
        try:
            enrollment = CourseEnrollment.objects.get(user=request.user, course=course)
            enrollment_data = {
                'enrolled_at': enrollment.enrollment_date,
                'enrollment_source': getattr(enrollment, 'enrollment_source', 'direct'),
                'is_active': enrollment.is_active
            }
        except CourseEnrollment.DoesNotExist:
            pass

    # Determine if user can enroll (needs proper subscription for non-free courses)
    bloqueio_inscricao = ciclo.bloqueio_inscricao(request.user, course)
    # Num curso com unidades de amostra também se pode inscrever sem o plano (abre só essas).
    can_enroll = (has_access or n_amostra > 0) and not is_enrolled and bloqueio_inscricao is None

    # Get subscription info for premium courses
    subscription_info = None
    if not has_access:
        required_plan = 'Premium' if course.access_level == 'premium' else 'Premium Plus'
        subscription_info = {
            'required_plan': required_plan,
            'message': f'Este curso requer o plano {required_plan} ou superior.'
        }

    return Response({
        'message': 'Estado da inscrição verificado com sucesso',
        'data': {
            'course_id': str(courseId),
            'course_title': course.title,
            'is_enrolled': is_enrolled,
            'has_access': has_access,
            'can_enroll': can_enroll,
            'access_level': course.access_level,
            'access_level_display': course.access_level_display,
            'is_free': course.is_free,
            'is_premium': course.is_premium,
            # Unidades de amostra: 'total' | 'amostra' | None (apps/courses/amostra.py).
            'acesso': amostra.acesso(request.user, course, total=has_access),
            'unidades_amostra': n_amostra,
            'enrollment_details': enrollment_data,
            'subscription_info': subscription_info,
            'estado': ciclo.estado(course),
            'motivo_sem_inscricao': bloqueio_inscricao[1] if bloqueio_inscricao and not is_enrolled else None,
            'codigo_sem_inscricao': bloqueio_inscricao[0] if bloqueio_inscricao and not is_enrolled else None,
        }
    })


# =============================================================================
# COURSE DISCOVERY ENDPOINTS (Featured, Popular, Search)
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_featured_courses(request):
    """
    Get featured video courses.

    GET /api/v1/student/video-courses/featured/

    Query params:
    - limit: Number of courses to return (default: 6, max: 20)
    - access_level: Filter by access level ('free', 'premium', 'premium_plus', 'all')

    Returns courses marked as featured (is_featured=True).
    Falls back to highest enrollment courses if no featured courses exist.
    """
    # SECURITY: Validate and cap limit
    try:
        limit = min(int(request.query_params.get('limit', 6)), 20)
        if limit < 1:
            limit = 6
    except (ValueError, TypeError):
        limit = 6

    # Base query: Published video courses marked as featured
    queryset = Course.objects.filter(
        ciclo.q_catalogo(),
        course_type='video',
        is_featured=True
    )

    # Apply access_level filter
    access_level = request.query_params.get('access_level')
    if access_level and access_level != 'all':
        valid_levels = ['free', 'premium', 'premium_plus']
        if access_level in valid_levels:
            queryset = queryset.filter(access_level=access_level)

    # Annotate with enrollment count for ordering
    queryset = queryset.annotate(
        enrollment_count=Count('enrollments')
    ).order_by('-enrollment_count')[:limit]

    # Fallback: if no featured courses, get most popular
    if not queryset.exists():
        fallback_queryset = Course.objects.filter(
            ciclo.q_catalogo(),
            course_type='video'
        )
        # Apply same access_level filter to fallback
        if access_level and access_level != 'all' and access_level in ['free', 'premium', 'premium_plus']:
            fallback_queryset = fallback_queryset.filter(access_level=access_level)

        queryset = fallback_queryset.annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-enrollment_count')[:limit]

    serializer = CourseListSerializer(
        queryset,
        many=True,
        context={'request': request, 'include_enrollment_count': True}
    )

    return Response({
        'message': 'Cursos em destaque obtidos com sucesso',
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_popular_courses(request):
    """
    Get popular video courses.

    GET /api/v1/student/video-courses/popular/

    Query params:
    - limit: Number of courses to return (default: 10, max: 50)
    - access_level: Filter by access level ('free', 'premium', 'premium_plus', 'all')
    - category: Filter by category
    """
    # SECURITY: Validate and cap limit to prevent DoS
    try:
        limit = min(int(request.query_params.get('limit', 10)), 50)
        if limit < 1:
            limit = 10
    except (ValueError, TypeError):
        limit = 10

    queryset = Course.objects.filter(
        ciclo.q_catalogo(),
        course_type='video'
    )

    # Apply access_level filter
    access_level = request.query_params.get('access_level')
    if access_level and access_level != 'all':
        valid_levels = ['free', 'premium', 'premium_plus']
        if access_level in valid_levels:
            queryset = queryset.filter(access_level=access_level)

    # Apply category filter
    category = request.query_params.get('category')
    if category and category != 'all':
        queryset = queryset.filter(category=category)

    courses = queryset.annotate(
        enrollment_count=Count('enrollments'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-enrollment_count', '-avg_rating')[:limit]

    serializer = CourseListSerializer(
        courses,
        many=True,
        context={'request': request, 'include_enrollment_count': True}
    )

    return Response({
        'message': 'Cursos populares obtidos com sucesso',
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def search_courses(request):
    """
    Search video courses.

    GET /api/v1/student/video-courses/search/

    Query params:
    - q: Search query (searches title and description)
    - category: Filter by category
    - level: nível CEFR ('B1') ou lista ('A2,B1')
    - access_level: Filter by access level ('free', 'premium', 'premium_plus')
    - is_featured: Filter by featured status ('true', 'false')
    - limit: Number of results (default: 20, max: 100)

    SECURITY:
    - Query is sanitized to prevent injection attacks
    - Limit is capped to prevent excessive resource usage
    """
    query = request.query_params.get('q', '').strip()
    category = request.query_params.get('category')
    level = request.query_params.get('level')
    access_level = request.query_params.get('access_level')
    is_featured = request.query_params.get('is_featured')

    # SECURITY: Validate and cap limit to prevent DoS
    try:
        limit = min(int(request.query_params.get('limit', 20)), 100)
        if limit < 1:
            limit = 20
    except (ValueError, TypeError):
        limit = 20

    # SECURITY: Cap query length to prevent regex DoS or memory issues
    MAX_QUERY_LENGTH = 100
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]

    courses = Course.objects.filter(
        ciclo.q_catalogo(),
        course_type='video'
    )

    if query:
        # Django's icontains uses parameterized queries - safe from SQL injection
        courses = courses.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    if category and category != 'all':
        courses = courses.filter(category=category)

    codigos = niveis.filtro(level)
    if codigos:
        courses = courses.filter(level__in=codigos)

    # Apply access_level filter
    if access_level and access_level != 'all':
        valid_access_levels = ['free', 'premium', 'premium_plus']
        if access_level in valid_access_levels:
            courses = courses.filter(access_level=access_level)

    # Apply is_featured filter
    if is_featured == 'true':
        courses = courses.filter(is_featured=True)
    elif is_featured == 'false':
        courses = courses.filter(is_featured=False)

    courses = courses.annotate(
        enrollment_count=Count('enrollments')
    ).order_by('-enrollment_count')[:limit]

    serializer = CourseListSerializer(
        courses,
        many=True,
        context={'request': request}
    )

    return Response({
        'message': 'Pesquisa realizada com sucesso',
        'data': serializer.data,
        'total': courses.count()
    })


# =============================================================================
# WISHLIST ENDPOINTS
# =============================================================================

class WishlistListCreateView(generics.ListCreateAPIView):
    """
    List user's wishlist or add course to wishlist.

    GET /api/v1/student/video-courses/wishlist/
    POST /api/v1/student/video-courses/wishlist/
    """
    serializer_class = CourseWishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CourseWishlist.objects.filter(
            user=self.request.user
        ).select_related('course').order_by('-added_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'message': 'Lista de desejos obtida com sucesso',
            'data': serializer.data
        })

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Curso adicionado à lista de desejos',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def remove_from_wishlist(request, courseId):
    """
    Remove course from wishlist.

    DELETE /api/v1/student/video-courses/wishlist/{courseId}/
    """
    try:
        wishlist_item = CourseWishlist.objects.get(
            user=request.user,
            course_id=courseId
        )
        wishlist_item.delete()
        return Response({
            'message': 'Curso removido da lista de desejos'
        })
    except CourseWishlist.DoesNotExist:
        return Response({
            'error': 'Curso não encontrado na lista de desejos'
        }, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# NOTES ENDPOINTS
# =============================================================================

class NoteListCreateView(generics.ListCreateAPIView):
    """
    List user's notes or create new note.

    GET /api/v1/student/video-courses/notes/
    POST /api/v1/student/video-courses/notes/

    Query params for GET:
    - course_id: Filter by course
    """
    serializer_class = StudentNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = StudentNote.objects.filter(
            user=self.request.user
        ).select_related('course', 'chapter').order_by('-created_at')

        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'message': 'Notas obtidas com sucesso',
            'data': serializer.data
        })


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a note.

    GET/PUT/DELETE /api/v1/student/video-courses/notes/{noteId}/
    """
    serializer_class = StudentNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = 'noteId'

    def get_queryset(self):
        return StudentNote.objects.filter(user=self.request.user)


# =============================================================================
# BOOKMARKS ENDPOINTS
# =============================================================================

class BookmarkListCreateView(generics.ListCreateAPIView):
    """
    List user's bookmarks or create new bookmark.

    GET /api/v1/student/video-courses/bookmarks/
    POST /api/v1/student/video-courses/bookmarks/

    Query params for GET:
    - course_id: Filter by course
    """
    serializer_class = StudentBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = StudentBookmark.objects.filter(
            user=self.request.user
        ).select_related(
            'chapter', 'chapter__section', 'chapter__section__course'
        ).order_by('-created_at')

        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(chapter__section__course_id=course_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'message': 'Marcadores obtidos com sucesso',
            'data': serializer.data
        })


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_bookmark(request, bookmarkId):
    """
    Delete a bookmark.

    DELETE /api/v1/student/video-courses/bookmarks/{bookmarkId}/
    """
    try:
        bookmark = StudentBookmark.objects.get(id=bookmarkId, user=request.user)
        bookmark.delete()
        return Response({'message': 'Marcador removido com sucesso'})
    except StudentBookmark.DoesNotExist:
        return Response({
            'error': 'Marcador não encontrado'
        }, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# REVIEWS ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_course_reviews(request, courseId):
    """
    Get reviews for a course.

    GET /api/v1/student/video-courses/{courseId}/reviews/

    Query params:
    - page: Page number
    """
    # Optimized: select_related on user to avoid N+1 when serializing user_name/avatar
    reviews = CourseReview.objects.filter(
        course_id=courseId
    ).select_related('user', 'course').order_by('-created_at')

    # Calculate average rating
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    serializer = CourseReviewSerializer(reviews, many=True, context={'request': request})

    return Response({
        'message': 'Avaliações obtidas com sucesso',
        'data': serializer.data,
        'average': round(avg_rating, 1),
        'total': reviews.count()
    })


class ReviewCreateView(generics.CreateAPIView):
    """
    Create a course review.

    POST /api/v1/student/video-courses/reviews/
    """
    serializer_class = CourseReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Check if user already reviewed this course
        course_id = request.data.get('course')
        if CourseReview.objects.filter(user=request.user, course_id=course_id).exists():
            return Response({
                'error': 'Já avaliou este curso.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Avaliação criada com sucesso',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_student_video_analytics(request):
    """
    Get student's video learning analytics.

    GET /api/v1/student/video-courses/analytics/
    """
    user = request.user

    # Get enrolled courses count
    total_enrolled = CourseEnrollment.objects.filter(
        user=user,
        course__course_type='video'
    ).count()

    # Get completed courses count
    courses_completed = UserCourseProgress.objects.filter(
        user=user,
        overallProgress__gte=100.0,
        course__course_type='video'
    ).count()

    # Get certificates count
    certificates_earned = CourseCertificate.objects.filter(user=user).count()

    # Calculate average progress
    progress_data = UserCourseProgress.objects.filter(
        user=user,
        course__course_type='video'
    ).aggregate(avg_progress=Avg('overallProgress'))
    average_progress = progress_data['avg_progress'] or 0

    # Calculate total watch time (from chapter progress time_spent)
    total_time = ChapterProgress.objects.filter(
        user_progress__user=user,
        user_progress__course__course_type='video'
    ).aggregate(total=models.Sum('time_spent'))['total'] or 0

    # Get recent activity (last 5 accessed courses)
    recent_courses = UserCourseProgress.objects.filter(
        user=user,
        course__course_type='video'
    ).select_related('course').order_by('-lastAccessedTimestamp')[:5]

    recent_activity = [{
        'course_id': str(p.course.id),
        'course_title': p.course.title,
        'progress': p.overallProgress,
        'last_accessed': p.lastAccessedTimestamp.isoformat()
    } for p in recent_courses]

    return Response({
        'message': 'Analytics obtidos com sucesso',
        'data': {
            'total_courses_enrolled': total_enrolled,
            'courses_completed': courses_completed,
            'total_watch_time': total_time,
            'certificates_earned': certificates_earned,
            'average_progress': round(average_progress, 1),
            'current_streak': 0,  # TODO: Implement streak tracking
            'recent_activity': recent_activity
        }
    })


# =============================================================================
# GRADING ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_course_grade(request, courseId):
    """
    Get student's grade for a specific course.

    GET /api/v1/student/video-courses/{courseId}/grade/

    Returns:
    - Quiz scores and details
    - Practice completion and details
    - Conversation scores (if applicable)
    - Final weighted grade
    - Certificate eligibility status
    """
    from ....services import GradeCalculatorService
    from ....models import StudentCourseGrade

    # Verify enrollment
    try:
        enrollment = CourseEnrollment.objects.select_related('course').get(
            user=request.user,
            course_id=courseId
        )
    except CourseEnrollment.DoesNotExist:
        return Response({
            'error': 'Não está inscrito neste curso.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Calculate and save grades
    calculator = GradeCalculatorService(request.user, enrollment.course)
    grade = calculator.calculate_and_save(change_reason='recalculation')

    # Elegibilidade = as mesmas regras da emissão do certificado (apps.courses.certificados):
    # requisitos da nota + conclusão do curso (100% dos capítulos) e, para emitir, o plano.
    from ....certificados import estado_certificado
    estado = estado_certificado(request.user, enrollment.course, grade)
    missing_requirements = [
        {'requirement': r['requisito'], 'message': r['mensagem'],
         'required': r['necessario'], 'actual': r['atual']}
        for r in estado['em_falta']
    ]
    eligibility_details = dict(grade.eligibility_details or {})
    eligibility_details['conclusao_curso'] = {
        'met': estado['progresso'] >= 100.0,
        'required': 100,
        'actual': estado['progresso'],
        'message': f"Capítulos concluídos: {estado['progresso']:.0f}% (necessário: 100%)",
    }

    # Build weight info with mode explanation
    weight_info = grade.weight_info or {}
    grading_mode = weight_info.get('mode', 'full')
    active_components = weight_info.get('active_components', [])

    mode_explanation = ''
    if grading_mode == 'simplified':
        mode_explanation = f'Avaliação baseada apenas em: {", ".join(active_components)}'
    elif grading_mode == 'no_content':
        mode_explanation = 'Nenhum componente de avaliação disponível neste curso'
    elif weight_info.get('weights_adjusted'):
        mode_explanation = 'Pesos ajustados automaticamente com base no conteúdo disponível'

    return Response({
        'message': 'Notas obtidas com sucesso',
        'data': {
            'course': {
                'id': str(enrollment.course.id),
                'title': enrollment.course.title,
                'level': getattr(enrollment.course, 'level', None),
            },
            'grades': {
                'quizzes': {
                    'score': grade.quiz_score,
                    'count': grade.quiz_count,
                    'completed': grade.quiz_completed,
                    'passed': grade.quiz_passed,
                    'details': grade.quiz_details,
                },
                'practice': {
                    'score': grade.practice_score,
                    'count': grade.practice_count,
                    'completed': grade.practice_completed,
                    'details': grade.practice_details,
                },
                'conversation': {
                    'score': grade.conversation_score,
                    'sessions': grade.conversation_sessions,
                    'minutes': grade.conversation_minutes,
                    'required': grade.has_conversation_requirement,
                    'details': grade.conversation_details,
                },
            },
            'final_grade': {
                'percentage': grade.final_grade_percentage,
                'letter': grade.final_grade_letter,
            },
            'weight_info': {
                'quiz_weight': weight_info.get('quiz_weight', 0),
                'practice_weight': weight_info.get('practice_weight', 0),
                'conversation_weight': weight_info.get('conversation_weight', 0),
                'exam_weight': weight_info.get('exam_weight', 0),
                'phrases_weight': weight_info.get('phrases_weight', 0),
                'study_weight': weight_info.get('study_weight', 0),
                'study_score': weight_info.get('study_score'),
                'mode': grading_mode,
                'mode_explanation': mode_explanation,
                'active_components': active_components,
                'weights_adjusted': weight_info.get('weights_adjusted', False),
            },
            'certificate_eligibility': {
                'is_eligible': estado['cumpre_requisitos'],
                'pode_emitir': estado['pode_emitir'],
                'progresso': estado['progresso'],
                'nota_minima': estado['nota_minima'],
                'plano_inclui_certificados': estado['plano_inclui_certificados'],
                'details': eligibility_details,
                'missing_requirements': missing_requirements,
                'em_falta': estado['em_falta'],
            },
            'exame_oral': {
                'score': grade.exam_score,
                'passed': grade.exam_passed,
                'attempts': (grade.exam_details or {}).get('attempts', 0),
                'min_score': (grade.exam_details or {}).get('min_score'),
            },
            'frases_curso': {
                'score': grade.phrases_score,
                'total': grade.phrases_total,
                'mastered': grade.phrases_mastered,
            },
            'nota_minima': estado['nota_minima'],
            'plano_inclui_certificados': estado['plano_inclui_certificados'],
            'last_calculated_at': grade.last_calculated_at.isoformat(),
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_certificate_eligibility(request, courseId):
    """
    Check if student is eligible for a certificate.

    GET /api/v1/student/video-courses/{courseId}/certificate-eligibility/

    Returns a simplified view of certificate eligibility.
    """
    from ....services import GradeCalculatorService
    from ....models import StudentCourseGrade, CourseGradingConfig

    # Verify enrollment
    try:
        enrollment = CourseEnrollment.objects.select_related('course').get(
            user=request.user,
            course_id=courseId
        )
    except CourseEnrollment.DoesNotExist:
        return Response({
            'error': 'Não está inscrito neste curso.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get or calculate grades
    calculator = GradeCalculatorService(request.user, enrollment.course)
    grade = calculator.calculate_and_save(change_reason='recalculation')

    # Get grading config for requirements display
    try:
        config = enrollment.course.grading_config
    except CourseGradingConfig.DoesNotExist:
        config = None

    # Build requirements list
    requirements = []

    if config:
        requirements.append({
            'name': 'Média mínima em quizzes',
            'required_value': f'{config.min_quiz_average}%',
            'current_value': f'{grade.quiz_score}%',
            'met': grade.quiz_score >= config.min_quiz_average,
        })

        if config.require_all_quizzes_passed:
            requirements.append({
                'name': 'Todos os quizzes aprovados',
                'required_value': f'{grade.quiz_count} quizzes',
                'current_value': f'{grade.quiz_passed} aprovados',
                'met': grade.quiz_passed == grade.quiz_count and grade.quiz_count > 0,
            })

        requirements.append({
            'name': 'Exercícios práticos completados',
            'required_value': f'{config.min_practice_completion}%',
            'current_value': f'{grade.practice_score}%',
            'met': grade.practice_score >= config.min_practice_completion,
        })

        if config.require_conversation_if_available and grade.has_conversation_requirement:
            requirements.append({
                'name': 'Pontuação em conversação',
                'required_value': f'{config.min_conversation_score}%',
                'current_value': f'{grade.conversation_score}%',
                'met': grade.conversation_score >= config.min_conversation_score,
            })

        requirements.append({
            'name': 'Nota final mínima',
            'required_value': f'{config.min_final_grade}%',
            'current_value': f'{grade.final_grade_percentage}%',
            'met': grade.final_grade_percentage >= config.min_final_grade,
        })

    return Response({
        'message': 'Elegibilidade verificada com sucesso',
        'data': {
            'course': {
                'id': str(enrollment.course.id),
                'title': enrollment.course.title,
            },
            'is_eligible': grade.is_eligible_for_certificate,
            'final_grade': {
                'percentage': grade.final_grade_percentage,
                'letter': grade.final_grade_letter,
            },
            'requirements': requirements,
            'can_generate_certificate': grade.is_eligible_for_certificate,
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_grade_history(request, courseId):
    """
    Get grade history for a course.

    GET /api/v1/student/video-courses/{courseId}/grade-history/

    Returns history of grade changes over time.
    """
    from ....models import StudentCourseGrade, GradeHistory

    # Verify enrollment
    try:
        enrollment = CourseEnrollment.objects.select_related('course').get(
            user=request.user,
            course_id=courseId
        )
    except CourseEnrollment.DoesNotExist:
        return Response({
            'error': 'Não está inscrito neste curso.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get grade record
    try:
        grade = StudentCourseGrade.objects.get(
            user=request.user,
            course_id=courseId
        )
        from ....services import GradeCalculatorService
        if (grade.calculation_version or 0) < GradeCalculatorService.CALCULATION_VERSION:
            grade = GradeCalculatorService(request.user, enrollment.course).calculate_and_save(
                change_reason='recalculation')
    except StudentCourseGrade.DoesNotExist:
        return Response({
            'message': 'Nenhum histórico de notas encontrado',
            'data': {
                'history': []
            }
        })

    # Get history entries
    history_entries = GradeHistory.objects.filter(
        student_grade=grade
    ).order_by('-created_at')[:20]

    history_data = [{
        'id': str(entry.id),
        'date': entry.created_at.isoformat(),
        'change_reason': entry.change_reason,
        'quiz_score': entry.quiz_score,
        'practice_score': entry.practice_score,
        'conversation_score': entry.conversation_score,
        'final_grade_percentage': entry.final_grade_percentage,
        'final_grade_letter': entry.final_grade_letter,
        'is_eligible': entry.is_eligible,
        'details': entry.change_details,
    } for entry in history_entries]

    return Response({
        'message': 'Histórico obtido com sucesso',
        'data': {
            'course': {
                'id': str(enrollment.course.id),
                'title': enrollment.course.title,
            },
            'current_grade': {
                'percentage': grade.final_grade_percentage,
                'letter': grade.final_grade_letter,
                'is_eligible': grade.is_eligible_for_certificate,
            },
            'history': history_data
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_all_student_grades(request):
    """
    Get all grades for the authenticated student across all enrolled courses.

    GET /api/v1/student/video-courses/grades/all/

    Returns:
    - List of all courses with their grades
    - Summary statistics (average grade, total courses, certificates earned)
    - Grade breakdown per course

    Query Parameters:
    - include_details: Include detailed quiz/practice/conversation info (default: true)
    - sort_by: Sort order (grade, title, recent) (default: recent)
    """
    from ....services import GradeCalculatorService
    from ....models import StudentCourseGrade, CourseCertificate

    include_details = request.query_params.get('include_details', 'true').lower() == 'true'
    sort_by = request.query_params.get('sort_by', 'recent')

    # Get all enrollments for the user with optimized queries
    # Include course.teacher for serialization to avoid N+1
    # Só cursos de vídeo publicados (como em enrolled/): os de prática não têm notas nem página.
    enrollments = CourseEnrollment.objects.filter(
        user=request.user,
        course__course_type='video',
    ).filter(ciclo.q_conteudo_aluno('course__')).select_related('course', 'course__teacher').order_by('-enrollment_date')

    # Prefetch existing grades to avoid N+1 queries in the loop
    existing_grades = {
        grade.course_id: grade
        for grade in StudentCourseGrade.objects.filter(
            user=request.user,
            course__in=[e.course_id for e in enrollments]
        )
    }

    if not enrollments.exists():
        return Response({
            'message': 'Nenhum curso encontrado',
            'data': {
                'courses': [],
                'summary': {
                    'total_courses': 0,
                    'courses_with_grades': 0,
                    'average_grade': 0,
                    'certificates_earned': 0,
                    'eligible_for_certificate': 0,
                }
            }
        })

    # Process each enrollment
    courses_grades = []
    total_percentage = 0
    courses_with_grades = 0
    eligible_count = 0

    from ....certificados import estado_certificado, plano_inclui_certificados
    plano_ok = plano_inclui_certificados(request.user)

    for enrollment in enrollments:
        course = enrollment.course

        # Use prefetched grade if available, otherwise calculate
        grade = existing_grades.get(course.id)
        if grade is None or (grade.calculation_version or 0) < GradeCalculatorService.CALCULATION_VERSION:
            # Sem nota, ou nota de uma versão antiga do cálculo (a elegibilidade guardada podia
            # não contar com o exame oral): calcula agora com as regras actuais.
            calculator = GradeCalculatorService(request.user, course)
            grade = calculator.calculate_and_save(change_reason='recalculation')
        # Elegibilidade com as regras da emissão (inclui a conclusão do curso).
        estado = estado_certificado(request.user, course, grade, plano_ok=plano_ok)

        # Build grade data
        grade_data = {
            'course': {
                'id': str(course.id),
                'title': course.title,
                'thumbnail': course.image if course.image else None,
                'level': getattr(course, 'level', None),
                'category': getattr(course, 'category', None),
            },
            'enrollment': {
                'enrolled_at': enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None,
            },
            'final_grade': {
                'percentage': round(grade.final_grade_percentage, 2),
                'letter': grade.final_grade_letter,
            },
            'is_eligible_for_certificate': estado['cumpre_requisitos'],
            'pode_emitir_certificado': estado['pode_emitir'],
            'progresso': estado['progresso'],
            'nota_minima': estado['nota_minima'],
            'last_calculated_at': grade.last_calculated_at.isoformat(),
        }

        # Include weight info
        weight_info = grade.weight_info or {}
        grade_data['grading_mode'] = weight_info.get('mode', 'full')
        grade_data['active_components'] = weight_info.get('active_components', [])

        # Include detailed breakdown if requested
        if include_details:
            grade_data['grades'] = {
                'quizzes': {
                    'score': grade.quiz_score,
                    'count': grade.quiz_count,
                    'completed': grade.quiz_completed,
                    'passed': grade.quiz_passed,
                },
                'practice': {
                    'score': grade.practice_score,
                    'count': grade.practice_count,
                    'completed': grade.practice_completed,
                },
                'conversation': {
                    'score': grade.conversation_score,
                    'sessions': grade.conversation_sessions,
                    'minutes': grade.conversation_minutes,
                    'required': grade.has_conversation_requirement,
                },
            }

            # Add missing requirements if not eligible
            if not estado['cumpre_requisitos']:
                grade_data['missing_requirements'] = [
                    {'requirement': r['requisito'], 'message': r['mensagem'],
                     'required': r['necessario'], 'actual': r['atual']}
                    for r in estado['em_falta']
                ]

        courses_grades.append(grade_data)

        # Update summary stats
        if grade.final_grade_letter != 'N/A':
            total_percentage += grade.final_grade_percentage
            courses_with_grades += 1

        if estado['cumpre_requisitos']:
            eligible_count += 1

    # Sort courses
    if sort_by == 'grade':
        courses_grades.sort(key=lambda x: x['final_grade']['percentage'], reverse=True)
    elif sort_by == 'title':
        courses_grades.sort(key=lambda x: x['course']['title'])
    # 'recent' is already sorted by enrolled_at

    # Get certificates count
    certificates_count = CourseCertificate.objects.filter(
        user=request.user
    ).count()

    # Calculate average grade
    average_grade = round(total_percentage / courses_with_grades, 2) if courses_with_grades > 0 else 0

    # Determine overall grade letter
    def get_letter_from_percentage(pct):
        if pct >= 90:
            return 'A'
        elif pct >= 80:
            return 'B'
        elif pct >= 70:
            return 'C'
        elif pct >= 60:
            return 'D'
        elif pct > 0:
            return 'F'
        return 'N/A'

    return Response({
        'message': 'Notas obtidas com sucesso',
        'data': {
            'courses': courses_grades,
            'plano_inclui_certificados': plano_ok,
            'summary': {
                'total_courses': len(courses_grades),
                'courses_with_grades': courses_with_grades,
                'average_grade': {
                    'percentage': average_grade,
                    'letter': get_letter_from_percentage(average_grade),
                },
                'certificates_earned': certificates_count,
                'eligible_for_certificate': eligible_count,
            }
        }
    })


# Certificados: ver certificados_views.py (listar, emitir, PDF) e apps/courses/api/public (verificação).
