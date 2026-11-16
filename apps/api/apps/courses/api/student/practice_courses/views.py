"""
Practice Lab Views - REST API endpoints

This module provides DRF views for the Practice Lab system,
implementing all necessary endpoints for the Duolingo-style learning experience.
"""

import logging

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)
from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, status as status_module
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.core.permissions import EAdministrador
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

# Rate limiting for security
from apps.practice.throttling import ChallengeProgressThrottle

# Course management views removed - student endpoints only

# Import subscription decorators
from apps.subscriptions.decorators import (
    subscription_required,
    lesson_required,
    speaking_required,
    listening_required,
    hearts_required,
    premium_required,
    premium_plus_required
)
from apps.subscriptions.models import UserSubscription
from apps.practice.study_services import corpo_sem_vidas

from apps.courses.models import Course
from apps.practice.models import (
    PracticeUnit, 
    PracticeLesson, 
    PracticeChallenge, 
    ChallengeOption,
    UserProgress, 
    ChallengeProgress,
    UserLeague,
    LeaguePromotion,
    Competition,
    CompetitionParticipant,
    LeaderboardSnapshot,
    UserStreak,
    Achievement,
    UserAchievement,
    AchievementCategory,
    AchievementNotification
    # Note: AI Speaking/Listening models removed - now handled by Vapi integration
)
from .serializers import (
    PracticeUnitSerializer,
    PracticeLessonSerializer,
    PracticeChallengeSerializer,
    ChallengeOptionSerializer,
    ChallengeOptionWithAnswerSerializer,
    ChallengeOptionCreateSerializer,
    UserProgressSerializer,
    UserProgressUpdateSerializer,
    ChallengeProgressCreateSerializer,
    LessonDetailSerializer,
    UserStreakSerializer,
    UserLeagueSerializer,
    LeaderboardEntrySerializer,
    LeagueInfoSerializer,
    CompetitionSerializer,
    CompetitionParticipantSerializer,
    LeaderboardSnapshotSerializer,
    AchievementSerializer,
    UserAchievementSerializer,
    AchievementStatsSerializer,
    AchievementCategorySerializer,
    AchievementNotificationSerializer,
    DetailedAchievementSerializer,
    # Vapi AI Conversation Serializers
    VapiConversationSerializer,
    VapiConversationFeedbackSerializer
    # Note: AI Speaking/Listening serializers removed - now handled by Vapi integration
)


def has_unlimited_hearts(user):
    """
    Check if user has an active subscription with unlimited hearts.

    Returns True if user has a subscription where hearts_limit == 0 (unlimited).
    """
    try:
        subscription = UserSubscription.objects.select_related('plan').get(user=user)
        if subscription.plan and subscription.is_active() and subscription.plan.hearts_limit == 0:
            logger.info(f"User {user.username} has unlimited hearts (subscription: {subscription.plan.name})")
            return True
    except UserSubscription.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error checking unlimited hearts for user {user}: {e}")
    return False


class CoursesListView(generics.ListAPIView):
    """
    GET /api/v1/student/practice-courses/courses/

    List all published practice courses for students.
    """
    permission_classes = []
    
    def get_queryset(self):
        """
        Get published practice courses for students only
        """
        try:
            # Students see only published practice courses
            from apps.courses.ciclo import q_catalogo
            queryset = Course.objects.filter(
                q_catalogo(), course_type='practice'
            ).distinct().order_by('-created_at')
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🎓 STUDENT - Found {queryset.count()} published practice courses")
            return queryset
                    
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"🚨 ERROR in get_queryset: {str(e)}")
            return Course.objects.none()
    
    def list(self, request, *args, **kwargs):
        courses = self.get_queryset()
        data = []

        # Check if statistics are requested (for student course info)
        include_stats = request.query_params.get('include_stats', 'false').lower() in ['true', '1', 'yes']

        # Check if user is authenticated for progress calculation
        user = request.user if request.user.is_authenticated else None

        from apps.courses import teste_basico
        from apps.courses.ciclo import bloqueio_requisito_pratica

        for course in courses:
            course_data = {
                'id': str(course.id),
                'title': course.title,
                'description': course.description,
                'image': course.image,
                'category': course.category,
                'level': course.level,
                'template': course.template,
                'created_at': course.created_at.isoformat() if course.created_at else None,
                'updated_at': course.updated_at.isoformat() if course.updated_at else None,
                # Curso de sector; e se esta pessoa ainda precisa do nível básico para o começar.
                'de_sector': teste_basico.curso_de_sector(course),
                'requisito_basico': bool(user) and bloqueio_requisito_pratica(user, course) is not None,
            }

            # Add statistics if requested for student course selection
            if include_stats:
                try:
                    # Get units count for this course
                    units_count = course.practice_units.count()

                    # Get lessons for this course
                    lessons = PracticeLesson.objects.filter(unit__course=course)
                    lessons_count = lessons.count()

                    # Get challenges count for this course
                    challenges_count = PracticeChallenge.objects.filter(
                        lesson__unit__course=course
                    ).count()

                    # Calculate user progress if authenticated
                    progress = 0
                    completed_lessons = 0
                    if user and lessons_count > 0:
                        # For each lesson, check if ALL its challenges are completed
                        for lesson in lessons:
                            lesson_challenges_count = lesson.challenges.count()
                            if lesson_challenges_count > 0:
                                completed_challenges = ChallengeProgress.objects.filter(
                                    user=user,
                                    challenge__lesson=lesson,
                                    completed=True
                                ).count()
                                if completed_challenges == lesson_challenges_count:
                                    completed_lessons += 1

                        # Calculate percentage
                        progress = round((completed_lessons / lessons_count) * 100)

                    course_data.update({
                        'units_count': units_count,
                        'lessons_count': lessons_count,
                        'challenges_count': challenges_count,
                        'totalUnits': units_count,
                        'total_lessons': lessons_count,
                        'total_challenges': challenges_count,
                        'progress': progress,
                        'completed_lessons': completed_lessons,
                    })

                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"⚠️ Failed to calculate statistics for course {course.id}: {str(e)}")
                    course_data.update({
                        'units_count': 0,
                        'lessons_count': 0,
                        'challenges_count': 0,
                        'totalUnits': 0,
                        'total_lessons': 0,
                        'total_challenges': 0,
                        'progress': 0,
                        'completed_lessons': 0,
                    })

            data.append(course_data)

        return Response(data)


# Course creation removed - student endpoints only


class CourseUnitsView(generics.ListAPIView):
    """
    GET /api/v1/practice/courses/{course_id}/units/
    
    List all practice units for a specific course.
    Maps to getCourse query from client project.
    """
    serializer_class = PracticeUnitSerializer
    permission_classes = []
    
    def get_queryset(self):
        from rest_framework.exceptions import NotFound
        from apps.courses import ciclo
        course_id = self.kwargs['course_id']
        course = get_object_or_404(Course, id=course_id)
        user = self.request.user
        if user.is_authenticated:
            if ciclo.bloqueio_pratica(user, course):
                raise NotFound('Curso não encontrado.')
        elif course.status != ciclo.PUBLICADO:
            raise NotFound('Curso não encontrado.')
        self._curso = course
        return PracticeUnit.objects.filter(course=course).order_by('order').prefetch_related(
            'lessons__challenges'
        )

    def get_serializer_context(self):
        # Só a estrutura (sem enunciados nem opções) e sem as lições ainda incompletas.
        from apps.practice.acesso_licoes import ids_escondidas
        context = super().get_serializer_context()
        curso = getattr(self, '_curso', None)
        context['licoes_escondidas'] = ids_escondidas(curso) if curso is not None else set()
        return context


class LessonDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/practice/lessons/{lesson_id}/

    Get detailed lesson with challenges for quiz page.
    Maps to getLesson query from client project.

    P1 FIX: Now enforces subscription limits via @subscription_required decorator.
    """
    serializer_class = LessonDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'lesson_id'

    # P1 FIX: Enforce subscription limits on lesson access
    @method_decorator(subscription_required('lesson'))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return PracticeLesson.objects.select_related('unit', 'unit__course').prefetch_related(
            'challenges'
        )

    def retrieve(self, request, *args, **kwargs):
        # As mesmas regras que lessons/<id>/jogar/: estado do curso, ordem do trilho, plano,
        # lição escondida e limite diário. Só devolve a estrutura (sem respostas).
        from rest_framework.exceptions import NotFound
        from apps.practice import acesso_licoes, limite_licoes
        licao = self.get_object()
        erro = acesso_licoes.erro_acesso_licao(request.user, licao)
        if erro:
            if erro.get('codigo') in ('curso_indisponivel', acesso_licoes.CODIGO_INDISPONIVEL):
                raise NotFound('Lição não encontrada.')
            return Response(erro, status=status_module.HTTP_403_FORBIDDEN)
        if not acesso_licoes._sem_restricoes(request.user, licao.unit.course):
            erro = limite_licoes.erro_limite(request.user, licao)
            if erro:
                return Response(erro, status=status_module.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(licao).data)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UserProgressView(APIView):
    """
    GET/PUT /api/v1/practice/user-progress/
    
    Get or update user's practice progress (hearts, points, active course).
    Maps to getUserProgress query from client project.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's current progress including subscription status"""
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={
                'hearts': 5,
                'points': 0,
                'active_course': None
            }
        )
        serializer = UserProgressSerializer(user_progress)
        data = serializer.data

        # Add subscription status to response
        has_active_subscription = False
        has_unlimited_hearts_flag = False
        try:
            subscription = UserSubscription.objects.select_related('plan').get(user=request.user)
            if subscription.plan and subscription.is_active():
                has_active_subscription = True
                if subscription.plan.hearts_limit == 0:
                    has_unlimited_hearts_flag = True
        except UserSubscription.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error checking subscription for user {request.user}: {e}")

        data['has_active_subscription'] = has_active_subscription
        data['has_unlimited_hearts'] = has_unlimited_hearts_flag

        return Response(data)
    
    def put(self, request):
        """Update user's progress (hearts, points, active course)"""
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={
                'hearts': 5,
                'points': 0,
                'active_course': None
            }
        )
        
        # Handle active_course selection from frontend
        data = request.data.copy()
        if 'active_course' in data and isinstance(data['active_course'], dict):
            # Frontend sends full course object, we need just the ID
            course_id = data['active_course'].get('id')
            if course_id:
                try:
                    course = Course.objects.get(id=course_id)
                    data['active_course'] = course.id
                except Course.DoesNotExist:
                    return Response(
                        {'error': 'Course not found'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        serializer = UserProgressUpdateSerializer(
            user_progress, 
            data=data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            # Return the full serialized data including course details
            full_serializer = UserProgressSerializer(user_progress)
            return Response(full_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def solucao(challenge):
    """A resposta certa em texto, para mostrar depois de um erro (o exercício volta no fim da lição)."""
    opcoes = list(challenge.options.order_by('order'))
    certas = [o.text for o in opcoes if o.is_correct]
    tipo = challenge.type
    if tipo == 'SENTENCE_ORDER':
        return ' '.join(o.text for o in opcoes) or None
    if tipo == 'MATCH_PAIRS':
        return '; '.join(o.text for o in opcoes) or None
    if tipo == 'FILL_BLANK':
        import re
        fila = list(certas)
        frase = re.sub(r'_{2,}|\[\s*\]', lambda _m: fila.pop(0) if fila else '___', challenge.question or '')
        return frase if certas else None
    if tipo in ('SELECT', 'ASSIST', 'TRUE_FALSE', 'TRANSLATION', 'LISTENING'):
        return certas[0] if certas else None
    return None


class ChallengeProgressView(APIView):
    """
    POST /api/v1/practice/challenge-progress/

    Create or update challenge progress when user completes a challenge.
    Maps to upsertChallengeProgress action from client project.

    Uses database transaction to ensure consistency when updating
    challenge progress and user points/hearts atomically.

    SECURITY: Rate limited to prevent abuse of points/hearts system.

    P1 FIX: Now enforces hearts requirement via @hearts_required decorator.

    Supports multiple challenge types:
    - SELECT/ASSIST/TRUE_FALSE: selected_option (option ID)
    - FILL_BLANK/TRANSLATION: text_answer (string with typo tolerance)
    - SENTENCE_ORDER: ordered_options (array of option IDs in user's order)
    - MATCH_PAIRS: paired_options (dict mapping left option ID to right option ID)
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChallengeProgressThrottle]

    # Only gate on an active subscription. Hearts are checked/deducted inside the
    # view (0 hearts blocks new challenges; wrong answers on new challenges cost 1;
    # practice mode never costs hearts). The previous @hearts_required() also ran
    # track_usage('hearts'), which took a heart on EVERY successful submission
    # (correct answers and practice included) and saved a stale subscription copy,
    # overwriting the practice-mode heart restore.
    @method_decorator(subscription_required('general'))
    @transaction.atomic
    def post(self, request):
        """Complete a challenge and update user progress"""
        import logging
        from difflib import SequenceMatcher
        logger = logging.getLogger(__name__)

        logger.info(f"ChallengeProgress POST request: {request.data}")

        # Accept both 'challenge' and 'challenge_id' for compatibility
        challenge_id = request.data.get('challenge_id') or request.data.get('challenge')
        selected_option_id = request.data.get('selected_option')
        text_answer = request.data.get('text_answer')
        text_answers = request.data.get('text_answers')  # Array for multiple blanks
        ordered_options = request.data.get('ordered_options')
        paired_options = request.data.get('paired_options')
        pronunciation_score = request.data.get('pronunciation_score')

        logger.info(f"Challenge ID: {challenge_id}, Selected Option: {selected_option_id}, Text Answer: {text_answer is not None}, Text Answers: {text_answers is not None}")

        # Input length validation to prevent abuse
        MAX_TEXT_LENGTH = 2000
        MAX_ANSWER_COUNT = 50

        if text_answer and len(str(text_answer)) > MAX_TEXT_LENGTH:
            logger.warning(f"Text answer too long: {len(str(text_answer))} chars")
            return Response(
                {'error': f'Text answer exceeds maximum length of {MAX_TEXT_LENGTH} characters'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        if text_answers:
            if len(text_answers) > MAX_ANSWER_COUNT:
                logger.warning(f"Too many text answers: {len(text_answers)}")
                return Response(
                    {'error': f'Too many answers (max {MAX_ANSWER_COUNT})'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )
            for i, ans in enumerate(text_answers):
                if ans and len(str(ans)) > MAX_TEXT_LENGTH:
                    logger.warning(f"Text answer {i} too long: {len(str(ans))} chars")
                    return Response(
                        {'error': f'Text answer exceeds maximum length of {MAX_TEXT_LENGTH} characters'},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )

        if not challenge_id:
            return Response(
                {'error': 'challenge is required'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        try:
            challenge = PracticeChallenge.objects.select_related('lesson', 'lesson__unit', 'lesson__unit__course').get(id=challenge_id)
            logger.info(f"Found challenge: {challenge}, type: {challenge.type}")

            # Validate hierarchy: challenge belongs to a valid lesson/unit/course
            if not challenge.lesson:
                logger.error(f"Challenge {challenge_id} has no associated lesson")
                return Response(
                    {'error': 'Invalid challenge configuration'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

        except PracticeChallenge.DoesNotExist:
            logger.error(f"Challenge not found: {challenge_id}")
            return Response(
                {'error': 'Invalid challenge'},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        except Exception:
            logger.exception("Unexpected error")
            return Response(
                {'error': 'Ocorreu um erro inesperado. Tente de novo.'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Ordem do trilho e plano do curso: uma lição bloqueada não pode ser respondida.
        from apps.practice.acesso_licoes import erro_acesso_licao
        erro_acesso = erro_acesso_licao(request.user, challenge.lesson)
        if erro_acesso:
            return Response(erro_acesso, status=status_module.HTTP_403_FORBIDDEN)

        # Get user progress
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={'hearts': 5, 'points': 0}
        )
        logger.info(f"User progress: hearts={user_progress.hearts}, points={user_progress.points}, created={created}")

        if request.data.get('saltar') in (True, 'true', '1', 1):
            return self._saltar(request, challenge, user_progress)

        # Check if this is practice mode (challenge already completed)
        existing_progress = ChallengeProgress.objects.filter(
            user=request.user,
            challenge=challenge
        ).first()

        is_practice = existing_progress is not None
        logger.info(f"Is practice mode: {is_practice}, existing progress: {existing_progress}")

        # Duplicate submission protection: prevent rapid re-submissions (within 2 seconds)
        if existing_progress and existing_progress.updated_at:
            from datetime import timedelta
            time_since_last = timezone.now() - existing_progress.updated_at
            if time_since_last < timedelta(seconds=2):
                logger.warning(f"Duplicate submission detected for challenge {challenge_id} by user {request.user.id}")
                # Return success with existing data to prevent frontend errors
                return Response({
                    'success': True,
                    'correct': existing_progress.completed,
                    'duplicate': True,
                    'message': 'Submission already processed',
                    'user_progress': {
                        'hearts': user_progress.hearts,
                        'points': user_progress.points
                    }
                }, status=status_module.HTTP_200_OK)

        # Check hearts for new challenges (skip for users with unlimited hearts subscription).
        # A conversa curta do fim da lição nunca custa vidas: não precisa delas.
        if (user_progress.hearts == 0 and not is_practice and challenge.type != 'VAPI_CONVERSATION'
                and not has_unlimited_hearts(request.user)):
            logger.info("User has no hearts and this is not practice mode")
            return Response(
                corpo_sem_vidas(request.user),
                status=status_module.HTTP_400_BAD_REQUEST
            )

        # Validate answer based on challenge type
        is_correct = False
        challenge_type = challenge.type

        # Initialize variables that may be used in response
        similarity = None
        matched = None

        if challenge_type in ['SELECT', 'ASSIST', 'TRUE_FALSE']:
            # Simple option selection - validate selected_option
            if not selected_option_id:
                return Response(
                    {'error': f'selected_option is required for {challenge_type} challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )
            try:
                selected_option = ChallengeOption.objects.get(id=selected_option_id, challenge=challenge)
                is_correct = selected_option.is_correct
                logger.info(f"Option validation: {selected_option.text}, is_correct: {is_correct}")
            except ChallengeOption.DoesNotExist:
                logger.error(f"Option not found: {selected_option_id} for challenge: {challenge_id}")
                return Response(
                    {'error': 'Invalid option'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

        elif challenge_type == 'LISTENING':
            # LISTENING can be either:
            # 1. Dictation style (has text_answer/text_answers) - validate like FILL_BLANK
            # 2. Multiple choice style (has selected_option) - validate option selection

            if text_answer or text_answers:
                # Dictation style - validate text answers like FILL_BLANK
                logger.info(f"LISTENING dictation mode: text_answer={text_answer}, text_answers={text_answers}")

                correct_options = list(challenge.options.filter(is_correct=True).order_by('order'))
                if not correct_options:
                    logger.error(f"No correct options for LISTENING challenge: {challenge_id}")
                    return Response(
                        {'error': 'Challenge has no correct answer configured'},
                        status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                from apps.practice.services.text_validation import TextValidationService

                # Handle multiple blanks
                if text_answers and isinstance(text_answers, list) and len(text_answers) > 1:
                    logger.info(f"LISTENING multiple blanks: {len(text_answers)} answers for {len(correct_options)} blanks")

                    # Validate answer count matches expected blank count
                    if len(text_answers) != len(correct_options):
                        logger.warning(f"LISTENING: Answer count mismatch. Expected {len(correct_options)}, got {len(text_answers)}")
                        return Response(
                            {'error': f'Expected {len(correct_options)} answers, received {len(text_answers)}'},
                            status=status_module.HTTP_400_BAD_REQUEST
                        )

                    all_correct = True
                    total_similarity = 0.0

                    for i, user_ans in enumerate(text_answers):
                        # Validate that answer is not empty
                        if not user_ans or not str(user_ans).strip():
                            logger.info(f"LISTENING Blank {i+1}: Empty answer provided")
                            all_correct = False
                            continue

                        correct_ans = correct_options[i].text
                        ans_correct, ans_similarity, _ = TextValidationService.validate_against_multiple(
                            user_answer=str(user_ans).strip(),
                            correct_answers=[correct_ans],
                            tolerance=TextValidationService.DEFAULT_TOLERANCE
                        )
                        if not ans_correct:
                            all_correct = False
                        total_similarity += ans_similarity
                        logger.info(f"LISTENING Blank {i+1}: '{user_ans}' vs '{correct_ans}' = {ans_correct} ({ans_similarity:.2%})")

                    is_correct = all_correct
                    similarity = total_similarity / len(text_answers) if text_answers else 0
                    matched = ', '.join([opt.text for opt in correct_options])
                    logger.info(f"LISTENING multiple blanks result: is_correct={is_correct}, avg_similarity={similarity:.2%}")
                else:
                    # Single blank
                    correct_answers = [opt.text for opt in correct_options]
                    is_correct, similarity, matched = TextValidationService.validate_against_multiple(
                        user_answer=text_answer,
                        correct_answers=correct_answers,
                        tolerance=TextValidationService.DEFAULT_TOLERANCE
                    )
                    logger.info(f"LISTENING single blank result: is_correct={is_correct}, similarity={similarity:.2%}")

            elif selected_option_id:
                # Multiple choice style - original behavior
                try:
                    selected_option = ChallengeOption.objects.get(id=selected_option_id, challenge=challenge)
                    is_correct = selected_option.is_correct
                    logger.info(f"LISTENING option validation: {selected_option.text}, is_correct: {is_correct}")
                except ChallengeOption.DoesNotExist:
                    logger.error(f"Option not found: {selected_option_id} for LISTENING challenge: {challenge_id}")
                    return Response(
                        {'error': 'Invalid option'},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Either selected_option or text_answer/text_answers is required for LISTENING challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

        elif challenge_type == 'TRANSLATION':
            # Translation with aggressive normalization and multiple correct answers
            if not text_answer:
                return Response(
                    {'error': 'text_answer is required for TRANSLATION challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Get all correct options (supports multiple correct translations)
            correct_options = challenge.options.filter(is_correct=True)
            if not correct_options.exists():
                logger.error(f"No correct options for challenge: {challenge_id}")
                return Response(
                    {'error': 'Challenge has no correct answer configured'},
                    status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Use specialized translation validation with aggressive normalization
            from apps.practice.services.text_validation import TextValidationService

            correct_answers = [opt.text for opt in correct_options]

            # Debug: Log expected answers for troubleshooting
            logger.info(f"TRANSLATION challenge {challenge_id}: "
                       f"User answer: '{text_answer}', "
                       f"Expected answers: {correct_answers}")

            is_correct, similarity, matched = TextValidationService.validate_translation(
                user_answer=text_answer,
                correct_answers=correct_answers
                # Uses TRANSLATION_TOLERANCE (70%) by default
            )

            logger.info(f"Translation validation result: is_correct={is_correct}, "
                       f"similarity={similarity:.2%}, matched='{matched}'")

        elif challenge_type == 'FILL_BLANK':
            # Fill blank with typo tolerance - supports single or multiple blanks
            if not text_answer and not text_answers:
                return Response(
                    {'error': 'text_answer or text_answers is required for FILL_BLANK challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Get correct options ordered by position
            correct_options = list(challenge.options.filter(is_correct=True).order_by('order'))
            if not correct_options:
                logger.error(f"No correct options for challenge: {challenge_id}")
                return Response(
                    {'error': 'Challenge has no correct answer configured'},
                    status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
                )

            from apps.practice.services.text_validation import TextValidationService

            # Handle multiple blanks (text_answers array)
            if text_answers and isinstance(text_answers, list) and len(text_answers) > 1:
                logger.info(f"Multiple blanks validation: {len(text_answers)} answers for {len(correct_options)} blanks")

                # Validate answer count matches expected blank count
                if len(text_answers) != len(correct_options):
                    logger.warning(f"FILL_BLANK: Answer count mismatch. Expected {len(correct_options)}, got {len(text_answers)}")
                    return Response(
                        {'error': f'Expected {len(correct_options)} answers, received {len(text_answers)}'},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )

                # Validate each answer against corresponding correct option
                all_correct = True
                total_similarity = 0.0
                results = []

                for i, user_ans in enumerate(text_answers):
                    # Validate that answer is not empty
                    if not user_ans or not str(user_ans).strip():
                        logger.info(f"Blank {i+1}: Empty answer provided")
                        all_correct = False
                        results.append({
                            'blank': i + 1,
                            'user': user_ans,
                            'correct': False,
                            'similarity': 0.0
                        })
                        continue

                    correct_ans = correct_options[i].text
                    ans_correct, ans_similarity, ans_matched = TextValidationService.validate_against_multiple(
                        user_answer=str(user_ans).strip(),
                        correct_answers=[correct_ans],
                        tolerance=TextValidationService.DEFAULT_TOLERANCE
                    )
                    results.append({
                        'blank': i + 1,
                        'user': user_ans,
                        'correct': ans_correct,
                        'similarity': ans_similarity
                    })
                    total_similarity += ans_similarity
                    if not ans_correct:
                        all_correct = False
                    logger.info(f"Blank {i+1}: '{user_ans}' vs '{correct_ans}' = {ans_correct} ({ans_similarity:.2%})")

                is_correct = all_correct
                similarity = total_similarity / len(text_answers) if text_answers else 0
                matched = ', '.join([opt.text for opt in correct_options])

                logger.info(f"Multiple blanks result: is_correct={is_correct}, avg_similarity={similarity:.2%}")
            else:
                # Single blank - original validation
                correct_answers = [opt.text for opt in correct_options]
                is_correct, similarity, matched = TextValidationService.validate_against_multiple(
                    user_answer=text_answer,
                    correct_answers=correct_answers,
                    tolerance=TextValidationService.DEFAULT_TOLERANCE  # 85%
                )
                logger.info(f"Fill blank validation: '{text_answer}', is_correct: {is_correct}, "
                           f"similarity: {similarity:.2%}, matched: '{matched}'")

        elif challenge_type == 'SENTENCE_ORDER':
            # Ordered sequence validation
            if not ordered_options or not isinstance(ordered_options, list):
                return Response(
                    {'error': 'ordered_options (array) is required for SENTENCE_ORDER challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Get correct order from options using the 'order' field
            correct_order = list(
                challenge.options.order_by('order')
                .values_list('id', flat=True)
            )
            correct_order_str = [str(opt_id) for opt_id in correct_order]

            # Convert user order to comparable format (string UUIDs)
            user_order = [str(opt_id) for opt_id in ordered_options]

            # Validate array length matches expected options
            if len(user_order) != len(correct_order_str):
                logger.warning(f"SENTENCE_ORDER: Length mismatch. Expected {len(correct_order_str)}, got {len(user_order)}")
                return Response(
                    {'error': f'Expected {len(correct_order_str)} items, received {len(user_order)}'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Check for duplicates in user submission
            if len(user_order) != len(set(user_order)):
                logger.warning(f"SECURITY: SENTENCE_ORDER duplicate IDs in submission")
                return Response(
                    {'error': 'Duplicate option IDs are not allowed'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate that all submitted UUIDs belong to this challenge
            valid_option_ids = set(correct_order_str)
            submitted_ids = set(user_order)

            if submitted_ids != valid_option_ids:
                invalid_ids = submitted_ids - valid_option_ids
                missing_ids = valid_option_ids - submitted_ids
                logger.warning(f"SECURITY: SENTENCE_ORDER invalid submission. Invalid IDs: {invalid_ids}, Missing: {missing_ids}")
                return Response(
                    {'error': 'Invalid option IDs submitted'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Compara o texto e não os ids: frases com palavras repetidas ("the ... the")
            # ficam certas seja qual for a cópia da palavra que a pessoa usou primeiro.
            textos = {str(o.id): ' '.join((o.text or '').lower().split()) for o in challenge.options.all()}
            is_correct = [textos[i] for i in user_order] == [textos[i] for i in correct_order_str]
            logger.info(f"Sentence order validation: user={user_order}, correct={correct_order_str}, is_correct: {is_correct}")

        elif challenge_type == 'MATCH_PAIRS':
            # Paired matching validation
            # Frontend sends: { "option_id": "portuguese_text", ... }
            # Options are stored as "English - Portuguese" format
            if not paired_options or not isinstance(paired_options, dict):
                return Response(
                    {'error': 'paired_options (object) is required for MATCH_PAIRS challenges'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Get all options for this challenge
            all_options = list(challenge.options.order_by('order'))
            valid_option_ids = {str(opt.id) for opt in all_options}

            # SECURITY: Validate that all submitted IDs belong to this challenge
            submitted_ids = set(paired_options.keys())
            if not submitted_ids.issubset(valid_option_ids):
                invalid_ids = submitted_ids - valid_option_ids
                logger.warning(f"SECURITY: MATCH_PAIRS invalid IDs submitted: {invalid_ids}")
                return Response(
                    {'error': 'Invalid option IDs submitted'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Check all options are paired
            if len(paired_options) != len(all_options):
                logger.info(f"MATCH_PAIRS: Incomplete pairs. Expected {len(all_options)}, got {len(paired_options)}")
                return Response(
                    {'error': 'All pairs must be matched'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Helper function for text normalization
            def normalize_text(text):
                if not text:
                    return ""
                return ' '.join(text.lower().strip().split())

            # TYPO_TOLERANCE for MATCH_PAIRS (85% - stricter than text input)
            MATCH_PAIRS_TOLERANCE = 0.85

            # Validate each pair
            all_correct = True
            for opt in all_options:
                opt_id = str(opt.id)
                if opt_id in paired_options:
                    # Parse the expected format - support multiple delimiters
                    text = opt.text
                    parts = None

                    # Try common delimiters: " - ", " – ", " = ", " : "
                    for delimiter in [' - ', ' – ', ' = ', ' : ']:
                        if delimiter in text:
                            parts = text.split(delimiter, 1)  # Split only on first occurrence
                            break

                    if parts and len(parts) == 2:
                        expected_portuguese = normalize_text(parts[1])
                        submitted_portuguese = normalize_text(paired_options[opt_id])

                        if expected_portuguese != submitted_portuguese:
                            similarity = SequenceMatcher(None, expected_portuguese, submitted_portuguese).ratio()
                            if similarity < MATCH_PAIRS_TOLERANCE:
                                all_correct = False
                                logger.info(f"MATCH_PAIRS: Mismatch for {opt_id}. Expected: '{parts[1]}', Got: '{paired_options[opt_id]}' (similarity: {similarity:.2%})")
                                break
                    else:
                        # Fallback: compare full text if no delimiter found
                        logger.warning(f"MATCH_PAIRS: No delimiter found in '{opt.text}', using full text comparison")
                        expected = normalize_text(opt.text)
                        submitted = normalize_text(paired_options[opt_id])
                        similarity = SequenceMatcher(None, expected, submitted).ratio()
                        if similarity < MATCH_PAIRS_TOLERANCE:
                            all_correct = False
                            break

            is_correct = all_correct
            logger.info(f"Match pairs validation: paired_options={paired_options}, is_correct: {is_correct}")

        elif challenge_type == 'VAPI_CONVERSATION':
            # Conversa curta no fim da lição: conta quando a conversa {sessao_id} deste exercício
            # terminou com pelo menos 2 falas do aluno. Senão não é um erro (sem perder vidas):
            # pode fazer outra conversa ou saltar ({saltar: true}).
            from apps.practice.conversa.licao import conversa_concluida, MIN_FALAS_ALUNO
            ok, motivo = conversa_concluida(request.user, challenge, request.data.get('sessao_id'))
            if not ok:
                mensagem = (f'A conversa precisa de pelo menos {MIN_FALAS_ALUNO} respostas suas. '
                            'Pode tentar outra vez ou saltar, sem perder vidas.'
                            if motivo == 'poucas_falas' else 'Termine primeiro a conversa com o tutor.')
                return Response({'codigo': 'conversa_incompleta', 'motivo': motivo, 'mensagem': mensagem,
                                 'pode_saltar': True}, status=status_module.HTTP_400_BAD_REQUEST)
            is_correct = True

        elif challenge_type == 'RESPONDER':
            # Avaliado no servidor a partir da gravação (Whisper + Claude).
            return Response(
                {'error': 'RESPONDER challenges must use the answer evaluation endpoint',
                 'codigo': 'usar_gravacao',
                 'endpoint': f'/api/v1/student/practice-courses/challenges/{challenge.id}/responder/'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        elif challenge_type == 'SPEAKING':
            # SECURITY FIX: SPEAKING challenges must use AIPronunciationAnalysisView endpoint
            # which performs server-side AI validation (Whisper + GPT-4) and updates progress.
            #
            # This endpoint does NOT accept client-supplied pronunciation_score to prevent
            # score injection attacks. Users must call:
            # POST /api/v1/practice/analyze-ai-pronunciation/
            # with audio file and challenge_id for proper server-side validation.
            #
            # The AIPronunciationAnalysisView already handles:
            # - Server-side AI pronunciation analysis
            # - ChallengeProgress creation/update
            # - Hearts and points management
            # - Subscription-based AI analysis limits

            logger.warning(f"SPEAKING: Direct validation not allowed. Use AIPronunciationAnalysisView endpoint.")
            return Response(
                {
                    'error': 'SPEAKING challenges must use the AI pronunciation analysis endpoint',
                    'endpoint': '/api/v1/practice/analyze-ai-pronunciation/',
                    'message': 'Submit audio file with challenge_id for server-side pronunciation analysis'
                },
                status=status_module.HTTP_400_BAD_REQUEST
            )

        else:
            logger.warning(f"Unknown challenge type: {challenge_type}")
            return Response(
                {'error': f'Unsupported challenge type: {challenge_type}'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        # Persist every answer (right or wrong) for review words / accuracy analytics
        from apps.practice.models import ChallengeAttempt
        ChallengeAttempt.objects.create(user=request.user, challenge=challenge, is_correct=is_correct)

        # Process result based on correctness
        if is_correct:
            # Correct answer: mark challenge as completed
            if existing_progress:
                existing_progress.completed = True
                existing_progress.save()
                progress = existing_progress
            else:
                progress = ChallengeProgress.objects.create(
                    user=request.user,
                    challenge=challenge,
                    completed=True
                )

            # Update user progress based on practice mode
            # Prática repetida (exercício já concluído antes): não dá pontos nem vidas por
            # exercício. A recompensa da repetição é dada uma vez por lição em
            # complete-lesson/ (+5 pontos e +1 vida no total), como definido no produto.
            if not is_practice:
                # Exercício novo: +10 pontos
                user_progress.add_points(10, reason='challenge', curso_id=challenge.lesson.unit.course_id)

            return Response({
                'success': True,
                'correct': True,
                # Explicação do professor, mostrada depois de acertar.
                'explicacao': challenge.explanation or None,
                'challenge_progress': {
                    'id': str(progress.id),
                    'completed': progress.completed,
                    'completed_at': progress.completed_at
                },
                'user_progress': {
                    'hearts': user_progress.hearts,
                    'points': user_progress.points
                }
            }, status=status_module.HTTP_200_OK)
        else:
            # Wrong answer: don't complete challenge, reduce hearts if not practice
            # Check if user has active subscription with unlimited hearts
            user_has_unlimited = has_unlimited_hearts(request.user)

            if not is_practice and user_progress.hearts > 0 and not user_has_unlimited:
                user_progress.reduce_hearts()

            # Build response with optional feedback for text challenges
            response_data = {
                'success': True,
                'correct': False,
                'dica': challenge.hint or None,
                # O exercício volta no fim da lição: mostra-se já a resposta certa e a explicação.
                'solucao': solucao(challenge),
                'explicacao': challenge.explanation or None,
                'user_progress': {
                    'hearts': user_progress.hearts if not user_has_unlimited else 999,
                    'points': user_progress.points
                },
                'heartsUsed': 1 if not user_has_unlimited and not is_practice else 0,
            }

            # Add feedback for TRANSLATION/FILL_BLANK challenges
            if challenge_type in ('TRANSLATION', 'FILL_BLANK', 'LISTENING') and similarity is not None:
                response_data['feedback'] = {
                    'similarity': round(similarity * 100, 1),
                }
                if matched:
                    # Give a hint without revealing full answer
                    hint_text = matched[:3] + '...' if len(matched) > 3 else matched
                    response_data['feedback']['hint'] = hint_text

            return Response(response_data, status=status_module.HTTP_200_OK)


    def _saltar(self, request, challenge, user_progress):
        """
        Exercício saltado: conta como feito, sem pontos e sem perder vidas.
        - pronúncia (SPEAKING) com a análise indisponível (apps.practice.saltar_pronuncia, com token);
        - responder em voz alta (RESPONDER) com a avaliação indisponível (o mesmo token);
        - conversa curta (VAPI_CONVERSATION): é opcional, pode ser sempre saltada (sem minutos,
          Vapi em baixo, ou o aluno não quer);
        - escuta (LISTENING) sem áudio e exercícios incompletos: sempre (o ecrã de jogar/ marca-os
          com modo "indisponivel").
        """
        from apps.practice.saltar_pronuncia import pode_saltar
        from .jogar import motivo_saltar
        # Um responder incompleto (sem pergunta ou frase-alvo) não pode ser gravado: salta sem token.
        com_token = challenge.type in ('SPEAKING', 'RESPONDER') and not motivo_saltar(challenge)
        if not com_token and challenge.type != 'VAPI_CONVERSATION' and not motivo_saltar(challenge):
            return Response({'codigo': 'saltar_invalido',
                             'mensagem': 'Este exercício não pode ser saltado.'},
                            status=status_module.HTTP_400_BAD_REQUEST)
        if com_token and not pode_saltar(request.data.get('token_saltar'), request.user, challenge):
            return Response({'codigo': 'analise_disponivel',
                             'mensagem': 'A análise de pronúncia está disponível: grave a frase.'},
                            status=status_module.HTTP_409_CONFLICT)
        progress = ChallengeProgress.objects.filter(user=request.user, challenge=challenge).first()
        if progress is None:
            progress = ChallengeProgress.objects.create(user=request.user, challenge=challenge,
                                                        completed=True, skipped=True)
        elif not progress.completed:
            progress.completed = True
            progress.skipped = True
            progress.save()
        return Response({
            'success': True,
            'correct': None,
            'saltado': True,
            'points_earned': 0,
            'challenge_progress': {
                'id': str(progress.id),
                'completed': progress.completed,
                'skipped': progress.skipped,
                'completed_at': progress.completed_at,
            },
            'user_progress': {'hearts': user_progress.hearts, 'points': user_progress.points},
        }, status=status_module.HTTP_200_OK)


class ReduceHeartsView(APIView):
    """
    POST /api/v1/practice/reduce-hearts/
    
    Reduce user hearts when they get an answer wrong.
    Maps to reduceHearts action from client project.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Reduce user hearts by 1 (skip for users with unlimited hearts subscription)"""
        # Check if user has unlimited hearts subscription
        if has_unlimited_hearts(request.user):
            return Response({
                'hearts': 999,  # Symbolic infinite value
                'points': 0,
                'unlimited': True
            })

        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={'hearts': 5, 'points': 0}
        )

        if user_progress.hearts > 0:
            user_progress.reduce_hearts()

            return Response({
                'hearts': user_progress.hearts,
                'points': user_progress.points
            })

        return Response(
            {'error': 'No hearts to reduce'},
            status=status.HTTP_400_BAD_REQUEST
        )


class RefillHeartsView(APIView):
    """
    POST /api/v1/student/practice-courses/refill-hearts/

    Refill all hearts (up to the plan maximum) by spending REFILL_HEARTS_COST_POINTS points.
    No-op for plans with unlimited hearts. Previously this was a premium-only
    free refill to 5 hearts; it now follows the product rule "refill with 50 points".
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.practice.study_services import refill_hearts_with_points
        result, error = refill_hearts_with_points(request.user)
        if error:
            return Response(result, status=status_module.HTTP_400_BAD_REQUEST)
        return Response(result)


class ValidateTextAnswerView(APIView):
    """
    POST /api/v1/practice/validate-text-answer/
    
    Validate text-based answers for FILL_BLANK, TRANSLATION, and other text input challenges.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Validate user's text answer against correct option"""
        import logging
        logger = logging.getLogger(__name__)
        
        challenge_id = request.data.get('challenge_id')
        user_answer = request.data.get('user_answer', '').strip()
        
        if not challenge_id or not user_answer:
            return Response(
                {'error': 'challenge_id and user_answer are required'}, 
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        try:
            challenge = PracticeChallenge.objects.get(id=challenge_id)
        except PracticeChallenge.DoesNotExist:
            return Response(
                {'error': 'Challenge not found'}, 
                status=status_module.HTTP_404_NOT_FOUND
            )
        
        # Get user progress
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={'hearts': 5, 'points': 0}
        )
        
        # Check if user already completed this challenge
        existing_progress = ChallengeProgress.objects.filter(
            user=request.user,
            challenge=challenge
        ).first()
        
        is_practice = existing_progress is not None
        logger.info(f"Text answer validation - Practice mode: {is_practice}")
        
        # Check hearts for new challenges (skip for users with unlimited hearts subscription)
        if user_progress.hearts == 0 and not is_practice and not has_unlimited_hearts(request.user):
            return Response(
                corpo_sem_vidas(request.user),
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        # Get the correct answer from challenge options
        correct_option = challenge.options.filter(is_correct=True).first()
        if not correct_option:
            return Response(
                {'error': 'No correct answer found for this challenge'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Use TextValidationService for consistent validation with typo tolerance
        from apps.practice.services.text_validation import TextValidationService

        is_correct, similarity = TextValidationService.validate(
            user_answer=user_answer,
            correct_answer=correct_option.text,
            tolerance=TextValidationService.DEFAULT_TOLERANCE  # 85%
        )

        logger.info(f"Text validation: '{user_answer}' vs '{correct_option.text}' "
                   f"(similarity: {similarity:.2%}, correct: {is_correct})")
        
        if is_correct:
            # Correct answer: mark challenge as completed
            if existing_progress:
                existing_progress.completed = True
                existing_progress.save()
                progress = existing_progress
            else:
                progress = ChallengeProgress.objects.create(
                    user=request.user,
                    challenge=challenge,
                    completed=True
                )
            
            # Update user progress based on practice mode
            # Prática repetida (exercício já concluído antes): não dá pontos nem vidas por
            # exercício. A recompensa da repetição é dada uma vez por lição em
            # complete-lesson/ (+5 pontos e +1 vida no total), como definido no produto.
            if not is_practice:
                # Exercício novo: +10 pontos
                user_progress.add_points(10, reason='challenge', curso_id=challenge.lesson.unit.course_id)
            
            return Response({
                'success': True,
                'correct': True,
                'user_answer': user_answer,
                'correct_answer': correct_option.text,
                'challenge_progress': {
                    'id': str(progress.id),
                    'completed': progress.completed,
                    'completed_at': progress.completed_at
                },
                'user_progress': {
                    'hearts': user_progress.hearts,
                    'points': user_progress.points
                }
            }, status=status_module.HTTP_200_OK)
        else:
            # Wrong answer: don't complete challenge, reduce hearts if not practice
            # P1 FIX: Check has_unlimited_hearts before reducing hearts
            user_has_unlimited = has_unlimited_hearts(request.user)
            if not is_practice and user_progress.hearts > 0 and not user_has_unlimited:
                user_progress.reduce_hearts()

            return Response({
                'success': True,
                'correct': False,
                'user_answer': user_answer,
                'correct_answer': correct_option.text,
                'user_progress': {
                    'hearts': user_progress.hearts,
                    'points': user_progress.points
                }
            }, status=status_module.HTTP_200_OK)


class GetAudioUploadUrlView(APIView):
    """
    POST /api/v1/practice/challenges/{challenge_id}/get-audio-upload-url/

    Get presigned S3 URL for audio upload in listening challenges.

    Security:
    - Validates user ownership (must be course teacher or staff)
    - Validates MIME type (audio only)
    - Validates file size (max 50MB)
    - Validates file extension
    """
    permission_classes = [IsAuthenticated]

    # Allowed audio MIME types
    ALLOWED_AUDIO_TYPES = [
        'audio/mpeg',
        'audio/mp3',
        'audio/wav',
        'audio/x-wav',
        'audio/ogg',
        'audio/webm',
        'audio/x-m4a',
        'audio/mp4',
        'audio/aac',
    ]

    # Allowed audio extensions
    ALLOWED_AUDIO_EXTENSIONS = ['mp3', 'wav', 'ogg', 'webm', 'm4a', 'aac', 'mp4']

    # Max file size: 50MB
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def post(self, request, challenge_id):
        """Generate presigned URL for audio upload to S3"""
        import boto3
        import uuid
        import os
        from django.conf import settings

        try:
            # Validate request data
            lesson_id = request.data.get('lessonId')
            file_name = request.data.get('fileName', '')
            file_type = request.data.get('fileType', '')
            file_size = request.data.get('fileSize', 0)

            if not all([lesson_id, file_name, file_type]):
                return Response(
                    {'error': 'lessonId, fileName e fileType são obrigatórios'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Verify challenge exists and get ownership info
            try:
                challenge = PracticeChallenge.objects.select_related(
                    'lesson__unit__course'
                ).get(id=challenge_id)
            except PracticeChallenge.DoesNotExist:
                return Response(
                    {'error': 'Desafio não encontrado'},
                    status=status_module.HTTP_404_NOT_FOUND
                )

            # SECURITY: Verify user ownership
            course = challenge.lesson.unit.course
            if course.teacher_id != request.user.id and not _ciclo.e_staff(request.user):
                return Response(
                    {'error': 'Não autorizado. Apenas o professor do curso pode fazer upload de áudio.'},
                    status=status_module.HTTP_403_FORBIDDEN
                )

            # SECURITY: Validate MIME type
            if file_type not in self.ALLOWED_AUDIO_TYPES:
                return Response(
                    {'error': f'Tipo de ficheiro não permitido. Use: MP3, WAV, OGG, WebM, M4A, AAC'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate file extension
            file_extension = os.path.splitext(file_name)[1].lower().lstrip('.')
            if not file_extension or file_extension not in self.ALLOWED_AUDIO_EXTENSIONS:
                return Response(
                    {'error': f'Extensão de ficheiro não permitida. Use: {", ".join(self.ALLOWED_AUDIO_EXTENSIONS)}'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate file size
            if file_size and int(file_size) > self.MAX_FILE_SIZE:
                max_mb = self.MAX_FILE_SIZE // (1024 * 1024)
                return Response(
                    {'error': f'Ficheiro demasiado grande. Tamanho máximo: {max_mb}MB'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Generate unique file name to avoid conflicts (use validated extension)
            unique_filename = f"audio/{lesson_id}/{challenge_id}/{uuid.uuid4().hex}.{file_extension}"

            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME or 'us-east-1'
            )

            # Generate presigned URL for upload
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': unique_filename,
                    'ContentType': file_type
                },
                ExpiresIn=3600  # 1 hour
            )

            # Construct the final audio URL
            audio_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{unique_filename}"

            return Response({
                'message': 'URL de upload de áudio gerada com sucesso',
                'data': {
                    'uploadUrl': presigned_url,
                    'audioUrl': audio_url,
                    'fileName': unique_filename
                }
            }, status=status_module.HTTP_200_OK)

        except Exception:
            logger.exception('Falha ao gerar URL de upload')
            return Response(
                {'error': 'Não foi possível preparar o envio do ficheiro. Tente de novo.'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetImageUploadUrlView(APIView):
    """
    POST /api/v1/practice/challenges/{challenge_id}/get-image-upload-url/

    Get presigned S3 URL for image upload in listening challenges.

    Security:
    - Validates user ownership (must be course teacher or staff)
    - Validates MIME type (images only)
    - Validates file size (max 10MB)
    - Validates file extension
    """
    permission_classes = [IsAuthenticated]

    # Allowed image MIME types
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/webp',
        'image/gif',
        'image/svg+xml',
    ]

    # Allowed image extensions
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'svg']

    # Max file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def post(self, request, challenge_id):
        """Generate presigned URL for image upload to S3"""
        import boto3
        import uuid
        import os
        from django.conf import settings

        try:
            # Validate request data
            lesson_id = request.data.get('lessonId')
            file_name = request.data.get('fileName', '')
            file_type = request.data.get('fileType', '')
            file_size = request.data.get('fileSize', 0)

            if not all([lesson_id, file_name, file_type]):
                return Response(
                    {'error': 'lessonId, fileName e fileType são obrigatórios'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Verify challenge exists and get ownership info
            try:
                challenge = PracticeChallenge.objects.select_related(
                    'lesson__unit__course'
                ).get(id=challenge_id)
            except PracticeChallenge.DoesNotExist:
                return Response(
                    {'error': 'Desafio não encontrado'},
                    status=status_module.HTTP_404_NOT_FOUND
                )

            # SECURITY: Verify user ownership
            course = challenge.lesson.unit.course
            if course.teacher_id != request.user.id and not _ciclo.e_staff(request.user):
                return Response(
                    {'error': 'Não autorizado. Apenas o professor do curso pode fazer upload de imagens.'},
                    status=status_module.HTTP_403_FORBIDDEN
                )

            # SECURITY: Validate MIME type
            if file_type not in self.ALLOWED_IMAGE_TYPES:
                return Response(
                    {'error': f'Tipo de ficheiro não permitido. Use: JPG, PNG, WebP, GIF, SVG'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate file extension
            file_extension = os.path.splitext(file_name)[1].lower().lstrip('.')
            if not file_extension or file_extension not in self.ALLOWED_IMAGE_EXTENSIONS:
                return Response(
                    {'error': f'Extensão de ficheiro não permitida. Use: {", ".join(self.ALLOWED_IMAGE_EXTENSIONS)}'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate file size
            if file_size and int(file_size) > self.MAX_FILE_SIZE:
                max_mb = self.MAX_FILE_SIZE // (1024 * 1024)
                return Response(
                    {'error': f'Ficheiro demasiado grande. Tamanho máximo: {max_mb}MB'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )

            # Generate unique file name to avoid conflicts (use validated extension)
            unique_filename = f"images/{lesson_id}/{challenge_id}/{uuid.uuid4().hex}.{file_extension}"

            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME or 'us-east-1'
            )

            # Generate presigned URL for upload
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': unique_filename,
                    'ContentType': file_type
                },
                ExpiresIn=3600  # 1 hour
            )

            # Construct the final image URL
            image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{unique_filename}"

            return Response({
                'message': 'URL de upload de imagem gerada com sucesso',
                'data': {
                    'uploadUrl': presigned_url,
                    'imageUrl': image_url,
                    'fileName': unique_filename
                }
            }, status=status_module.HTTP_200_OK)

        except Exception:
            logger.exception('Falha ao gerar URL de upload')
            return Response(
                {'error': 'Não foi possível preparar o envio do ficheiro. Tente de novo.'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_lesson_percentage(request, lesson_id):
    """
    GET /api/v1/practice/lessons/{lesson_id}/percentage/
    
    Get lesson completion percentage for current user.
    """
    lesson = get_object_or_404(PracticeLesson, id=lesson_id)
    total_challenges = lesson.challenges.count()
    
    if total_challenges == 0:
        return Response({'percentage': 0})
    
    completed_challenges = ChallengeProgress.objects.filter(
        user=request.user,
        challenge__lesson=lesson,
        completed=True
    ).count()
    
    percentage = (completed_challenges / total_challenges) * 100
    
    return Response({
        'percentage': round(percentage, 2),
        'completed_challenges': completed_challenges,
        'total_challenges': total_challenges
    })


from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# ============================================================================
# TEACHER MANAGEMENT VIEWS - CRUD operations for practice content
#
# Só o professor dono do curso (ou um administrador) lê e altera unidades, lições,
# exercícios e opções por aqui: os alunos usam os endpoints de student/practice-courses
# (jogar/, trilho/), que nunca mostram as respostas certas. Para os outros, os objectos
# não existem (404) e as criações são recusadas (403).
# ============================================================================

from rest_framework.exceptions import PermissionDenied as _SemPermissao, ValidationError as _Invalido
from rest_framework.permissions import BasePermission
from apps.courses import ciclo as _ciclo
from .serializers import (
    PracticeChallengeProfessorSerializer,
    PracticeLessonProfessorSerializer,
    PracticeUnitProfessorSerializer,
    ChallengeOptionProfessorSerializer,
)

MENSAGEM_SO_DONO = 'Apenas o professor do curso pode alterar este conteúdo.'


def _pode_gerir_curso(user, course):
    """Professor dono do curso ou administrador."""
    if _ciclo.e_staff(user):
        return True
    return _ciclo.e_professor(user) and course is not None and course.teacher_id == user.id


def _exigir_dono(user, course):
    if not _pode_gerir_curso(user, course):
        raise _SemPermissao(MENSAGEM_SO_DONO)


class _SoProfessoresEscrevem(BasePermission):
    """Escritas só para professores e administradores (antes de validar os dados)."""
    message = MENSAGEM_SO_DONO

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return _ciclo.e_professor(request.user) or _ciclo.e_staff(request.user)


ROTA_ANTIGA_MENSAGEM = ('Esta forma de editar cursos de prática foi retirada. '
                       'Use o editor de cursos de prática na área do professor.')


def _rota_antiga(request, *args, **kwargs):
    """410: as escritas nas rotas antigas não passavam pelas validações do editor novo."""
    return Response({'error': ROTA_ANTIGA_MENSAGEM, 'message': ROTA_ANTIGA_MENSAGEM,
                     'code': 'rota_removida', 'details': {'editor': '/api/v1/teacher/pratica/'}},
                    status=status_module.HTTP_410_GONE)


class _ConteudoPraticaMixin:
    """
    Restringe o queryset ao professor dono (o administrador vê tudo) e mostra as respostas.
    Só leitura: criar, alterar e apagar unidades, lições, exercícios e opções faz-se no editor
    novo (/api/v1/teacher/pratica/, apps/courses/api/teacher/pratica.py) -> 410 aqui.
    """
    caminho_professor = None  # ex.: 'course__teacher'

    def post(self, request, *args, **kwargs):
        return _rota_antiga(request)

    put = patch = delete = post

    def get_permissions(self):
        return [IsAuthenticated(), _SoProfessoresEscrevem()]

    def _filtrar_dono(self, qs):
        user = self.request.user
        if _ciclo.e_staff(user):
            return qs
        if not _ciclo.e_professor(user):
            return qs.none()
        return qs.filter(**{self.caminho_professor: user})

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['mostrar_respostas'] = True
        return context


def _guardar_opcoes(challenge, opcoes, substituir=False):
    """Cria as opções enviadas com o exercício (o construtor do professor manda-as juntas)."""
    if opcoes is None:
        return
    if not isinstance(opcoes, list):
        raise _Invalido({'options': ['As opções devem ser uma lista.']})
    serializers_ = []
    for i, dados in enumerate(opcoes):
        if not isinstance(dados, dict):
            raise _Invalido({'options': ['Cada opção deve ser um objecto.']})
        dados = dict(dados)
        dados.pop('id', None)
        dados.pop('challenge', None)
        dados.pop('challenge_id', None)
        if 'audio_url' in dados and 'audioSrc' not in dados:
            dados['audioSrc'] = dados.pop('audio_url')
        if 'image_url' in dados and 'imageSrc' not in dados:
            dados['imageSrc'] = dados.pop('image_url')
        dados.setdefault('order', i)
        s = ChallengeOptionProfessorSerializer(data=dados)
        s.is_valid(raise_exception=True)
        serializers_.append(s)
    if substituir:
        challenge.options.all().delete()
    for s in serializers_:
        s.save(challenge=challenge)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_units_with_progress(request, course_id):
    """
    GET /api/v1/practice/courses/{course_id}/units-with-progress/          (professor)
    GET /api/v1/student/practice-courses/courses/{course_id}/units-with-progress/ (aluno)

    O professor dono e o administrador vêem qualquer estado e as respostas certas.
    Os alunos só vêem cursos que podem abrir (publicados ou arquivados a manter) e nunca
    as respostas certas de exercícios por fazer.
    """
    course = get_object_or_404(Course.objects.select_related('teacher'), id=course_id, course_type='practice')
    dono = _ciclo.e_dono_ou_staff(request.user, course)
    if not dono:
        if _ciclo.bloqueio_pratica(request.user, course):
            from rest_framework.exceptions import NotFound
            raise NotFound('Curso de prática não encontrado.')
    units = PracticeUnit.objects.filter(course=course).order_by('order').prefetch_related(
        'lessons__challenges__options'
    )

    course_data = {
        'id': str(course.id),
        'title': course.title,
        'description': course.description,
        'category': course.category,
        'level': course.level,
        'status': course.status,
        'estado': _ciclo.estado(course),
        'course_type': course.course_type,
        'template': course.template,
        'image': course.image,
        'created_at': course.created_at.isoformat(),
        'updated_at': course.updated_at.isoformat(),
        'teacher': {
            'id': str(course.teacher.id),
            'username': course.teacher.username,
            'email': course.teacher.email if dono else None,
            'first_name': getattr(course.teacher, 'first_name', ''),
            'last_name': getattr(course.teacher, 'last_name', ''),
        } if course.teacher else None,
        'teacherName': course.teacherName,
    }
    if dono:
        course_data['motivo_recusa'] = course.motivo_recusa or None

    # O aluno recebe só a estrutura e o progresso (sem enunciados, opções nem respostas) e não vê
    # as lições ainda incompletas; o ecrã da lição usa lessons/<id>/jogar/.
    from apps.practice.acesso_licoes import ids_escondidas
    serializer_class = PracticeUnitProfessorSerializer if dono else PracticeUnitSerializer
    units_serializer = serializer_class(
        units,
        many=True,
        context={'request': request, 'mostrar_respostas': dono,
                 'licoes_escondidas': set() if dono else ids_escondidas(course)}
    )

    return Response({
        'course': course_data,
        'units': units_serializer.data
    })


@method_decorator(csrf_exempt, name='dispatch')
class PracticeUnitCreateView(_ConteudoPraticaMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/practice/units/?course=<id> - Unidades dos cursos do professor
    POST /api/v1/practice/units/ - Cria uma unidade (professor dono do curso)
    """
    serializer_class = PracticeUnitProfessorSerializer
    permission_classes = [IsAuthenticated]
    caminho_professor = 'course__teacher'

    def get_queryset(self):
        queryset = self._filtrar_dono(PracticeUnit.objects.select_related('course'))
        course_id = self.request.GET.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset.annotate(_n_licoes=models.Count('lessons')).order_by('order')

    def list(self, request, *args, **kwargs):
        units_data = [{
            'id': str(unit.id),
            'title': unit.title,
            'description': unit.description,
            'order': unit.order,
            'course_id': str(unit.course_id),
            'lessons_count': unit._n_licoes,
        } for unit in self.get_queryset()]
        return Response({
            'results': units_data,
            'count': len(units_data),
            'message': 'Unidades obtidas com sucesso'
        })

    def perform_create(self, serializer):
        _exigir_dono(self.request.user, serializer.validated_data.get('course'))
        serializer.save()


class PracticeUnitUpdateView(_ConteudoPraticaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/practice/units/{unit_id}/ (professor dono do curso)
    """
    serializer_class = PracticeUnitProfessorSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'unit_id'
    caminho_professor = 'course__teacher'

    def get_queryset(self):
        return self._filtrar_dono(PracticeUnit.objects.select_related('course'))

    def perform_update(self, serializer):
        if 'course' in serializer.validated_data:
            _exigir_dono(self.request.user, serializer.validated_data['course'])
        serializer.save()


class PracticeLessonCreateView(_ConteudoPraticaMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/practice/lessons/?unit=<id> - Lições de uma unidade (professor dono)
    POST /api/v1/practice/lessons/ - Cria uma lição (professor dono do curso)
    """
    serializer_class = PracticeLessonProfessorSerializer
    permission_classes = [IsAuthenticated]
    caminho_professor = 'unit__course__teacher'

    def get_queryset(self):
        queryset = self._filtrar_dono(PracticeLesson.objects.all())
        unit_id = self.request.GET.get('unit')
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
        return queryset.prefetch_related('challenges__options').order_by('order')

    def list(self, request, *args, **kwargs):
        if not request.GET.get('unit'):
            return Response(
                {'error': 'Indique a unidade (parâmetro unit).', 'message': 'Indique a unidade (parâmetro unit).',
                 'code': 'unit_obrigatorio', 'details': {}},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({
            "message": "Lições obtidas com sucesso",
            "data": serializer.data
        })

    def perform_create(self, serializer):
        unit = serializer.validated_data.get('unit')
        _exigir_dono(self.request.user, unit.course if unit else None)
        serializer.save()


class PracticeLessonUpdateView(_ConteudoPraticaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/practice/lessons/{lesson_id}/ (professor dono do curso)
    """
    serializer_class = PracticeLessonProfessorSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'lesson_id'
    caminho_professor = 'unit__course__teacher'

    def get_queryset(self):
        return self._filtrar_dono(PracticeLesson.objects.select_related('unit__course')
                                  .prefetch_related('challenges__options'))

    def perform_update(self, serializer):
        if 'unit' in serializer.validated_data:
            _exigir_dono(self.request.user, serializer.validated_data['unit'].course)
        serializer.save()


class PracticeChallengeCreateView(_ConteudoPraticaMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/practice/challenges/?lesson=<id> - Exercícios de uma lição (professor dono)
    POST /api/v1/practice/challenges/ - Cria um exercício com as opções (professor dono)
    """
    serializer_class = PracticeChallengeProfessorSerializer
    permission_classes = [IsAuthenticated]
    caminho_professor = 'lesson__unit__course__teacher'

    def get_queryset(self):
        queryset = self._filtrar_dono(PracticeChallenge.objects.all())
        lesson_id = self.request.GET.get('lesson')
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        return queryset.prefetch_related('options').order_by('order')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lesson = serializer.validated_data.get('lesson')
        _exigir_dono(request.user, lesson.unit.course if lesson else None)
        with transaction.atomic():
            challenge = serializer.save()
            _guardar_opcoes(challenge, request.data.get('options'))
        response_serializer = self.get_serializer(challenge)
        return Response(response_serializer.data, status=status_module.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        if not request.GET.get('lesson'):
            return Response(
                {'error': 'Indique a lição (parâmetro lesson).', 'message': 'Indique a lição (parâmetro lesson).',
                 'code': 'lesson_obrigatorio', 'details': {}},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({
            "message": "Exercícios obtidos com sucesso",
            "data": serializer.data
        })


class PracticeChallengeUpdateView(_ConteudoPraticaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/practice/challenges/{challenge_id}/ (professor dono)

    Se o pedido trouxer `options`, as opções do exercício são substituídas por essas.
    """
    serializer_class = PracticeChallengeProfessorSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'challenge_id'
    caminho_professor = 'lesson__unit__course__teacher'

    def get_queryset(self):
        return self._filtrar_dono(PracticeChallenge.objects.select_related('lesson__unit__course')
                                  .prefetch_related('options'))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if 'lesson' in serializer.validated_data:
            _exigir_dono(request.user, serializer.validated_data['lesson'].unit.course)
        with transaction.atomic():
            challenge = serializer.save()
            if 'options' in request.data:
                _guardar_opcoes(challenge, request.data.get('options'), substituir=True)
        challenge = self.get_queryset().get(pk=challenge.pk)
        return Response(self.get_serializer(challenge).data)


class ChallengeOptionCreateView(_ConteudoPraticaMixin, generics.CreateAPIView):
    """
    POST /api/v1/practice/challenge-options/ {challenge_id, text, is_correct, ...}

    Acrescenta uma opção a um exercício (professor dono do curso).
    """
    serializer_class = ChallengeOptionCreateSerializer
    permission_classes = [IsAuthenticated]
    caminho_professor = 'challenge__lesson__unit__course__teacher'

    def perform_create(self, serializer):
        challenge = PracticeChallenge.objects.select_related('lesson__unit__course').filter(
            id=serializer.validated_data.get('challenge_id')).first()
        if challenge is None or not _pode_gerir_curso(self.request.user, challenge.lesson.unit.course):
            from rest_framework.exceptions import NotFound
            raise NotFound('Exercício não encontrado.')
        serializer.save()


class ChallengeOptionUpdateView(_ConteudoPraticaMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/practice/challenge-options/{option_id}/ (professor dono)
    """
    serializer_class = ChallengeOptionProfessorSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'option_id'
    caminho_professor = 'challenge__lesson__unit__course__teacher'

    def get_queryset(self):
        return self._filtrar_dono(ChallengeOption.objects.all())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unit_lessons(request, unit_id):
    """
    GET /api/v1/practice/units/{unit_id}/lessons/ (professor dono do curso)
    """
    unit = get_object_or_404(PracticeUnit.objects.select_related('course'), id=unit_id)
    if not _pode_gerir_curso(request.user, unit.course):
        from rest_framework.exceptions import NotFound
        raise NotFound('Unidade não encontrada.')
    lessons = PracticeLesson.objects.filter(unit=unit).prefetch_related('challenges__options')
    serializer = PracticeLessonProfessorSerializer(
        lessons,
        many=True,
        context={'request': request, 'mostrar_respostas': True}
    )
    return Response(serializer.data)


# ============================================================================
# LEADERBOARD VIEWS - Competition and ranking system
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_global_leaderboard(request):
    """
    GET /api/v1/practice/leaderboard/global/
    
    Get global leaderboard with top users ranked by points.
    """
    from apps.practice.liga import nome_publico
    
    # Get top users with progress, ordered by points
    leaderboard_data = []
    
    # Get all users with progress, ordered by points
    users_with_progress = UserProgress.objects.select_related('user').filter(
        user__role='student', user__is_active=True
    ).order_by('-points')[:50]
    
    current_user_rank = None
    current_user_data = None
    
    for index, user_progress in enumerate(users_with_progress):
        # Get or create league
        user_league, created = UserLeague.objects.get_or_create(
            user=user_progress.user,
            defaults={'current_league': UserLeague.get_league_for_points(user_progress.points)}
        )
        
        if created or user_league.current_league != UserLeague.get_league_for_points(user_progress.points):
            user_league.update_league()
        
        # Get or create streak
        user_streak, _ = UserStreak.objects.get_or_create(
            user=user_progress.user,
            defaults={'current_streak': 0}
        )
        
        # Calculate rank change (mock for now - would need historical data)
        rank_change = 'same'  # TODO: Implement based on LeaderboardSnapshot
        change_amount = None
        
        # Check if this is current user
        is_current_user = user_progress.user == request.user
        if is_current_user:
            current_user_rank = index + 1
            current_user_data = {
                'rank': index + 1,
                'username': nome_publico(user_progress.user.name),
                'points': user_progress.points,
                'streak': user_streak.current_streak,
                'league': user_league.current_league,
                'change': rank_change,
                'changeAmount': change_amount,
                'isCurrentUser': True
            }
        
        # Privacidade: sem id/e-mail/nome completo dos outros alunos, só o nome público.
        entry = {
            'rank': index + 1,
            'username': nome_publico(user_progress.user.name),
            'avatar': user_progress.user_image_src,
            'points': user_progress.points,
            'streak': user_streak.current_streak,
            'league': user_league.current_league,
            'change': rank_change,
            'changeAmount': change_amount,
            'isCurrentUser': is_current_user
        }
        
        leaderboard_data.append(entry)
    
    # If current user not in top 10, add separately
    response_data = {
        'leaderboard': leaderboard_data[:10],  # Top 10
        'currentUser': current_user_data
    }
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_leagues_info(request):
    """
    GET /api/v1/practice/leaderboard/leagues/
    
    Get leagues information with participant counts.
    """
    leagues_info = []
    
    for league_id, league_name in UserLeague.LEAGUE_CHOICES:
        league_data = UserLeague.get_league_info(league_id)
        
        # Count participants in this league
        participants_count = UserLeague.objects.filter(current_league=league_id).count()
        
        leagues_info.append({
            'id': league_id,
            'name': league_data['name'],
            'icon': league_data['icon'],
            'color': f'text-{league_id}-400' if league_id != 'bronze' else 'text-amber-600',
            'minPoints': league_data['min_points'],
            'maxPoints': league_data['max_points'],
            'participants': participants_count
        })
    
    return Response(leagues_info)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_competitions(request):
    """
    GET /api/v1/practice/leaderboard/competitions/
    
    Get active competitions.
    """
    # Competições da plataforma activas (as antigas, de inscrição) + as dos cursos do aluno,
    # em que participa automaticamente (apps/practice/competicoes.py).
    from django.db.models import Q
    from django.utils import timezone
    from apps.practice.competicoes import competicoes_do_aluno
    agora = timezone.now()
    ids = {c.id for c in competicoes_do_aluno(request.user, agora)}
    competitions = (Competition.objects.filter(
        Q(status='active', criado_por__isnull=True, cursos__isnull=True, todos_os_cursos=False)
        | Q(id__in=ids))
        .distinct().order_by('-start_date'))
    
    serializer = CompetitionSerializer(
        competitions, 
        many=True, 
        context={'request': request}
    )
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_leaderboard_position(request):
    """
    GET /api/v1/practice/leaderboard/user-position/
    
    Get current user's leaderboard position and stats.
    """
    user = request.user
    
    try:
        user_progress = UserProgress.objects.get(user=user)
    except UserProgress.DoesNotExist:
        return Response({'error': 'User progress not found'}, status=404)
    
    # Get or create league
    user_league, created = UserLeague.objects.get_or_create(
        user=user,
        defaults={'current_league': UserLeague.get_league_for_points(user_progress.points)}
    )
    
    # Get or create streak
    user_streak, _ = UserStreak.objects.get_or_create(
        user=user,
        defaults={'current_streak': 0}
    )
    
    # Calculate rank (count users with more points)
    users_with_more_points = UserProgress.objects.filter(points__gt=user_progress.points).count()
    current_rank = users_with_more_points + 1
    
    # Get league info
    league_info = UserLeague.get_league_info(user_league.current_league)
    
    return Response({
        'rank': current_rank,
        'points': user_progress.points,
        'hearts': user_progress.hearts,
        'streak': user_streak.current_streak,
        'league': {
            'id': user_league.current_league,
            'name': league_info['name'],
            'icon': league_info['icon'],
            'min_points': league_info['min_points'],
            'max_points': league_info['max_points']
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_competition(request, competition_id):
    """
    POST /api/v1/practice/leaderboard/competitions/{competition_id}/join/
    
    Join a competition.
    """
    competition = get_object_or_404(Competition, id=competition_id, status='active')
    user = request.user
    if competition.criado_por_id or competition.todos_os_cursos or competition.cursos.exists():
        return Response({'error': 'Nesta competição a participação é automática para os alunos dos cursos.'},
                        status=400)
    
    # Check if user meets requirements
    try:
        user_progress = UserProgress.objects.get(user=user)
        if user_progress.points < competition.min_points_to_participate:
            return Response(
                {'error': f'Minimum {competition.min_points_to_participate} points required'}, 
                status=400
            )
    except UserProgress.DoesNotExist:
        return Response({'error': 'User progress not found'}, status=400)
    
    # Check if already joined
    if CompetitionParticipant.objects.filter(competition=competition, user=user).exists():
        return Response({'error': 'Already joined this competition'}, status=400)
    
    # Check participant limit
    if competition.max_participants and competition.participant_count >= competition.max_participants:
        return Response({'error': 'Competition is full'}, status=400)
    
    # Join competition
    participant = CompetitionParticipant.objects.create(
        competition=competition,
        user=user,
        points_earned=0,
        current_rank=competition.participant_count + 1
    )
    
    return Response({
        'message': 'Successfully joined competition',
        'participant_id': str(participant.id),
        'current_rank': participant.current_rank
    })


class LeaderboardSnapshotCreateView(APIView):
    """
    POST /api/v1/practice/leaderboard/snapshot/

    Create a leaderboard snapshot (for automated tasks).
    Admin only - used by Celery tasks for scheduled snapshots.
    """
    permission_classes = [EAdministrador]  # SECURITY FIX: Admin only
    
    def post(self, request):
        """Create snapshot of current leaderboard"""
        snapshot_type = request.data.get('type', 'daily')
        
        # Get all users with progress
        users_with_progress = UserProgress.objects.select_related('user').order_by('-points')
        
        snapshots_created = 0
        for index, user_progress in enumerate(users_with_progress):
            # Get user's league
            user_league, _ = UserLeague.objects.get_or_create(
                user=user_progress.user,
                defaults={'current_league': UserLeague.get_league_for_points(user_progress.points)}
            )
            
            # Create snapshot
            snapshot, created = LeaderboardSnapshot.objects.get_or_create(
                user=user_progress.user,
                snapshot_type=snapshot_type,
                defaults={
                    'rank': index + 1,
                    'points': user_progress.points,
                    'league': user_league.current_league,
                    'rank_change': 0,
                    'points_change': 0
                }
            )
            
            if created:
                snapshots_created += 1
        
        return Response({
            'message': f'Created {snapshots_created} leaderboard snapshots',
            'snapshot_type': snapshot_type
        })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_streak(request):
    """
    PUT /api/v1/practice/leaderboard/update-streak/
    
    Update user's practice streak (called after completing activities).
    """
    user = request.user
    
    # Get or create streak
    user_streak, created = UserStreak.objects.get_or_create(
        user=user,
        defaults={'current_streak': 0}
    )
    
    # Update streak
    user_streak.update_streak()
    
    return Response({
        'current_streak': user_streak.current_streak,
        'longest_streak': user_streak.longest_streak,
        'last_practice_date': user_streak.last_practice_date
    })


@api_view(['GET'])
@permission_classes([EAdministrador])  # SECURITY FIX: Admin only - was public, leaked PII
def test_leaderboard_data(request):
    """
    Test endpoint to check leaderboard data (Admin only).
    WARNING: This endpoint exposes user PII - use only for debugging.
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Get all users with progress, ordered by points
    users_with_progress = UserProgress.objects.select_related('user').order_by('-points')[:10]
    
    leaderboard_data = []
    
    for index, user_progress in enumerate(users_with_progress):
        # Get or create league
        user_league, created = UserLeague.objects.get_or_create(
            user=user_progress.user,
            defaults={'current_league': UserLeague.get_league_for_points(user_progress.points)}
        )
        
        # Get or create streak
        user_streak, _ = UserStreak.objects.get_or_create(
            user=user_progress.user,
            defaults={'current_streak': 0}
        )
        
        entry = {
            'id': str(user_progress.user.id),
            'rank': index + 1,
            'username': user_progress.user.name if hasattr(user_progress.user, 'name') else user_progress.user.first_name or user_progress.user.email,
            'avatar': user_progress.user_image_src,
            'points': user_progress.points,
            'streak': user_streak.current_streak,
            'league': user_league.current_league,
            'change': 'same',
            'changeAmount': None,
            'isCurrentUser': False
        }
        
        leaderboard_data.append(entry)
    
    # Get leagues info
    leagues_info = []
    for league_id, league_name in UserLeague.LEAGUE_CHOICES:
        league_data = UserLeague.get_league_info(league_id)
        participants_count = UserLeague.objects.filter(current_league=league_id).count()
        
        leagues_info.append({
            'id': league_id,
            'name': league_data['name'],
            'icon': league_data['icon'],
            'color': f'text-{league_id}-400' if league_id != 'bronze' else 'text-amber-600',
            'minPoints': league_data['min_points'],
            'maxPoints': league_data['max_points'],
            'participants': participants_count
        })
    
    # Get active competitions
    competitions = Competition.objects.filter(status='active').order_by('-start_date')
    competitions_data = []
    
    for competition in competitions:
        competitions_data.append({
            'id': str(competition.id),
            'title': competition.title,
            'description': competition.description,
            'type': competition.type,
            'startDate': competition.start_date.strftime('%Y-%m-%d'),
            'endDate': competition.end_date.strftime('%Y-%m-%d'),
            'participants': competition.participant_count,
            'currentPosition': None,
            'prize': competition.first_place_prize
        })
    
    return Response({
        'leaderboard': {
            'leaderboard': leaderboard_data,
            'currentUser': None
        },
        'leagues': leagues_info,
        'competitions': competitions_data,
        'stats': {
            'total_users': User.objects.count(),
            'users_with_progress': UserProgress.objects.count(),
            'active_competitions': Competition.objects.filter(status='active').count()
        }
    })


# ============================================================================
# ACHIEVEMENT VIEWS - Gamification and badge system
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_achievements(request):
    """
    GET /api/v1/student/practice-courses/achievements/

    Todas as conquistas activas com estado (desbloqueada ou não), data e progresso.
    O progresso é lido das tabelas reais para os tipos conhecidos (e desbloqueia a
    conquista se o objectivo já foi atingido). Conquistas secretas só aparecem depois
    de desbloqueadas.
    """
    from django.utils import timezone
    from apps.practice.achievement_utils import (
        check_achievement_progress, conquistas_plataforma_do_aluno, conquistas_professor_do_aluno,
        live_achievement_values,
        valor_conquista_professor, verificar_conquistas_professor,
    )

    user = request.user
    # Conquistas da plataforma + as dos professores dos cursos do aluno (só contam esses cursos).
    verificar_conquistas_professor(user)
    # Inclui as da plataforma já desligadas que o aluno ganhou (continuam visíveis).
    achievements = list(conquistas_plataforma_do_aluno(user).order_by('order', 'category', 'rarity'))
    do_professor = list(conquistas_professor_do_aluno(user).select_related('curso').order_by('created_at'))
    achievements += do_professor
    user_achievements = {
        ua.achievement_id: ua for ua in UserAchievement.objects.filter(user=user, achievement__in=achievements)
    }
    live = live_achievement_values(user, {a.requirement_type for a in achievements if a.criado_por_id is None})
    live_professor = {a.id: valor_conquista_professor([user.id], a)[user.id] for a in do_professor
                      if not getattr(user_achievements.get(a.id), 'is_unlocked', False)}

    # Desbloqueia o que já foi atingido mas ainda não tinha sido verificado.
    for req_type, value in live.items():
        if any(a.requirement_type == req_type and value >= a.requirement_target and a.criado_por_id is None
               and not getattr(user_achievements.get(a.id), 'is_unlocked', False) for a in achievements):
            check_achievement_progress(user, req_type, value)
            user_achievements = {
                ua.achievement_id: ua
                for ua in UserAchievement.objects.filter(user=user, achievement__in=achievements)
            }

    now = timezone.now()
    achievements_data = []
    for achievement in achievements:
        ua = user_achievements.get(achievement.id)
        unlocked = bool(ua and ua.is_unlocked)
        if achievement.is_secret and not unlocked:
            continue

        progress_data = None
        if not unlocked and achievement.requirement_target > 0:
            if achievement.criado_por_id is None:
                current = max(ua.current_progress if ua else 0, live.get(achievement.requirement_type, 0))
            else:
                current = live_professor.get(achievement.id, ua.current_progress if ua else 0)
            current = min(current, achievement.requirement_target)
            progress_data = {
                'current': current,
                'target': achievement.requirement_target,
                'unit': achievement.requirement_unit,
                'percentage': round(current * 100 / achievement.requirement_target),
            }

        unlocked_at_formatted = None
        if unlocked and ua.unlocked_at:
            diff = now - ua.unlocked_at
            if diff.days == 0:
                unlocked_at_formatted = "hoje"
            elif diff.days == 1:
                unlocked_at_formatted = "há 1 dia"
            elif diff.days < 7:
                unlocked_at_formatted = f"há {diff.days} dias"
            else:
                semanas = diff.days // 7
                unlocked_at_formatted = f"há {semanas} semana{'s' if semanas > 1 else ''}"

        achievements_data.append({
            'id': str(achievement.id),
            'title': achievement.title,
            'description': achievement.description,
            'icon': achievement.icon,
            'category': achievement.category,
            'rarity': achievement.rarity,
            'points': achievement.points,
            'isSecret': achievement.is_secret,
            'isUnlocked': unlocked,
            'unlockedAt': unlocked_at_formatted,
            'unlockedAtIso': ua.unlocked_at.isoformat() if unlocked and ua.unlocked_at else None,
            'progress': progress_data,
            # Conquista de um professor: o curso a que se limita (null = todos os cursos dele).
            'professor': (
                {'curso': ({'id': str(achievement.curso_id), 'titulo': achievement.curso.title}
                           if achievement.curso_id else None)}
                if achievement.criado_por_id else None
            ),
        })

    return Response(achievements_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_achievement_stats(request):
    """
    GET /api/v1/practice/achievements/stats/
    
    Get achievement statistics for the current user.
    """
    user = request.user
    
    # Get all achievements and user achievements
    from apps.practice.achievement_utils import conquistas_plataforma_do_aluno, conquistas_professor_do_aluno
    total_achievements = (conquistas_plataforma_do_aluno(user).count()
                          + conquistas_professor_do_aluno(user).count())
    user_achievements = UserAchievement.objects.filter(user=user)
    
    # Calculate stats
    unlocked_achievements = user_achievements.filter(is_unlocked=True)
    total_unlocked = unlocked_achievements.count()
    
    # Calculate total points from unlocked achievements
    total_points = 0
    for ua in unlocked_achievements:
        total_points += ua.achievement.points
    
    # Count rare achievements (rare, epic, legendary)
    rare_achievements = unlocked_achievements.filter(
        achievement__rarity__in=['rare', 'epic', 'legendary']
    ).count()
    
    # Count recent unlocks (last 7 days)
    from datetime import timedelta
    from django.utils import timezone
    
    recent_cutoff = timezone.now() - timedelta(days=7)
    recent_unlocked = unlocked_achievements.filter(
        unlocked_at__gte=recent_cutoff
    ).count()
    
    stats = {
        'totalUnlocked': total_unlocked,
        'totalAvailable': total_achievements,
        'totalPoints': total_points,
        'rareAchievements': rare_achievements,
        'recentUnlocked': recent_unlocked
    }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_achievement_categories(request):
    """
    GET /api/v1/practice/achievements/categories/
    
    Get achievement categories with counts.
    """
    categories = AchievementCategory.objects.filter(is_active=True).order_by('order')
    
    serializer = AchievementCategorySerializer(
        categories, 
        many=True, 
        context={'request': request}
    )
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_achievement_notifications(request):
    """
    GET /api/v1/practice/achievements/notifications/
    
    Get unread achievement notifications for the current user.
    """
    notifications = AchievementNotification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')
    
    serializer = AchievementNotificationSerializer(notifications, many=True)
    
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """
    POST /api/v1/practice/achievements/notifications/{notification_id}/read/
    
    Mark an achievement notification as read.
    """
    try:
        notification = AchievementNotification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.mark_as_read()
        
        return Response({'message': 'Notification marked as read'})
        
    except AchievementNotification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'}, 
            status=status_module.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_achievement_celebrated(request, achievement_id):
    """
    POST /api/v1/practice/achievements/{achievement_id}/celebrate/
    
    Mark an achievement as celebrated (popup shown).
    """
    try:
        notification = AchievementNotification.objects.get(
            achievement_id=achievement_id,
            user=request.user
        )
        notification.mark_as_celebrated()
        
        return Response({'message': 'Achievement marked as celebrated'})
        
    except AchievementNotification.DoesNotExist:
        return Response(
            {'error': 'Achievement notification not found'}, 
            status=status_module.HTTP_404_NOT_FOUND
        )


def check_achievement_progress(user, achievement_type, current_value):
    """
    Helper function to check and update achievement progress.
    
    Called from other parts of the system when user actions occur.
    """
    # Get achievements of the specified type
    achievements = Achievement.objects.filter(
        requirement_type=achievement_type,
        is_active=True,
        criado_por__isnull=True,  # as dos professores só contam os cursos deles (achievement_utils)
    )
    
    newly_unlocked = []
    
    for achievement in achievements:
        # Get or create user achievement
        user_achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={'current_progress': 0}
        )
        
        # Update progress if not already unlocked
        if not user_achievement.is_unlocked:
            was_unlocked = user_achievement.update_progress(current_value)
            
            if was_unlocked:
                # Create notification
                notification, created = AchievementNotification.objects.get_or_create(
                    user=user,
                    achievement=achievement
                )
                if created:
                    from apps.practice.achievement_utils import notify_achievement_unlocked
                    notify_achievement_unlocked(user, achievement)
                newly_unlocked.append(achievement)
    
    return newly_unlocked


@api_view(['GET'])
@permission_classes([EAdministrador])  # SECURITY FIX: Admin only - was public, wrote to DB
def test_achievements_data(request):
    """
    Test endpoint to check achievements data (Admin only).
    WARNING: This endpoint creates UserAchievement records - use only for debugging.
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Get first user for testing
    user = User.objects.first()
    if not user:
        return Response({'error': 'No users found'})
    
    # Get all active achievements
    achievements = Achievement.objects.filter(is_active=True).order_by('order', 'category', 'rarity')
    
    # Build achievements data
    achievements_data = []
    
    for achievement in achievements:
        # Get or create user achievement record
        user_achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={'current_progress': 0}
        )
        
        # Build progress data
        progress_data = None
        if not user_achievement.is_unlocked and achievement.requirement_target > 0:
            progress_data = {
                'current': user_achievement.current_progress,
                'target': achievement.requirement_target,
                'unit': achievement.requirement_unit
            }
        
        # Format unlock date
        unlocked_at_formatted = None
        if user_achievement.unlocked_at:
            from django.utils import timezone
            now = timezone.now()
            diff = now - user_achievement.unlocked_at
            
            if diff.days == 0:
                unlocked_at_formatted = "hoje"
            elif diff.days == 1:
                unlocked_at_formatted = "há 1 dia"
            elif diff.days < 7:
                unlocked_at_formatted = f"há {diff.days} dias"
            else:
                unlocked_at_formatted = f"há {diff.days // 7} semana{'s' if diff.days // 7 > 1 else ''}"
        
        achievement_data = {
            'id': str(achievement.id),
            'title': achievement.title,
            'description': achievement.description,
            'icon': achievement.icon,
            'category': achievement.category,
            'rarity': achievement.rarity,
            'points': achievement.points,
            'isUnlocked': user_achievement.is_unlocked,
            'unlockedAt': unlocked_at_formatted,
            'progress': progress_data
        }
        
        achievements_data.append(achievement_data)
    
    # Calculate stats
    total_achievements = Achievement.objects.filter(is_active=True).count()
    user_achievements = UserAchievement.objects.filter(user=user)
    unlocked_achievements = user_achievements.filter(is_unlocked=True)
    total_unlocked = unlocked_achievements.count()
    
    total_points = 0
    for ua in unlocked_achievements:
        total_points += ua.achievement.points
    
    rare_achievements = unlocked_achievements.filter(
        achievement__rarity__in=['rare', 'epic', 'legendary']
    ).count()
    
    from datetime import timedelta
    from django.utils import timezone
    recent_cutoff = timezone.now() - timedelta(days=7)
    recent_unlocked = unlocked_achievements.filter(
        unlocked_at__gte=recent_cutoff
    ).count()
    
    stats = {
        'totalUnlocked': total_unlocked,
        'totalAvailable': total_achievements,
        'totalPoints': total_points,
        'rareAchievements': rare_achievements,
        'recentUnlocked': recent_unlocked
    }
    
    return Response({
        'achievements': achievements_data,
        'stats': stats,
        'user': user.name if hasattr(user, 'name') else user.email,
        'total_created': len(achievements_data)
    })


# ============================================================================
# 🚀 VAPI AI CONVERSATION PRACTICE ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_vapi_conversation(request):
    """Start a new Vapi AI conversation session"""
    return Response({
        'message': 'Vapi conversation endpoints coming soon',
        'status': 'success'
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_vapi_conversation(request, conversation_id):
    """End a Vapi AI conversation session"""
    return Response({
        'message': 'Vapi conversation end endpoint coming soon',
        'conversation_id': conversation_id,
        'status': 'success'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_feedback(request, conversation_id):
    """Get conversation feedback and analysis"""
    return Response({
        'message': 'Vapi conversation feedback endpoint coming soon',
        'conversation_id': conversation_id,
        'status': 'success'
    })

# ============================================================================
# TEST ENDPOINTS - Required by URLs
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_units_simple(request):
    """Test endpoint for units"""
    return Response({
        'message': 'Test units endpoint active',
        'status': 'success'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_lessons_simple(request):
    """Test endpoint for lessons"""
    return Response({
        'message': 'Test lessons endpoint active',
        'status': 'success'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_challenges_simple(request):
    """Test endpoint for challenges"""
    return Response({
        'message': 'Test challenges endpoint active',
        'status': 'success'
    })


# ============================================================================
# PLACEHOLDER VIEWS - Required by URLs but functionality moved to Vapi
# ============================================================================

class AITranslationValidationView(APIView):
    """Placeholder for AI translation validation - moved to Vapi"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        return Response({
            'message': 'AI translation validation moved to Vapi integration',
            'status': 'placeholder'
        })

