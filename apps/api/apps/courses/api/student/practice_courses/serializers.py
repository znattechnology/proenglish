"""
Practice Lab Serializers - API data serialization

This module provides DRF serializers for the Practice Lab system,
handling data serialization for frontend-backend communication.
"""

from rest_framework import serializers
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


class ChallengeOptionSerializer(serializers.ModelSerializer):
    """
    Challenge Option serializer - for multiple choice answers.
    
    Maps to frontend challengeOptions structure from client project.
    """
    id = serializers.UUIDField(read_only=True)
    imageSrc = serializers.URLField(source='image_url', allow_null=True, required=False)
    audioSrc = serializers.URLField(source='audio_url', allow_null=True, required=False)
    
    class Meta:
        model = ChallengeOption
        fields = [
            'id', 'text', 'is_correct', 'imageSrc', 
            'audioSrc', 'order'
        ]
        extra_kwargs = {
            'is_correct': {'write_only': True},  # Don't expose correct answer to frontend
        }


class ChallengeOptionWithAnswerSerializer(serializers.ModelSerializer):
    """
    Challenge Option serializer WITH correct answers - for practice mode.
    Used when user has already completed the challenge.
    """
    id = serializers.UUIDField(read_only=True)
    imageSrc = serializers.URLField(source='image_url', allow_null=True, required=False)
    audioSrc = serializers.URLField(source='audio_url', allow_null=True, required=False)
    
    class Meta:
        model = ChallengeOption
        fields = [
            'id', 'challenge', 'text', 'is_correct', 'imageSrc', 
            'audioSrc', 'order'
        ]


class ChallengeOptionCreateSerializer(serializers.ModelSerializer):
    """
    Challenge Option creation serializer - for creating new options.
    Accepts challenge_id from frontend and maps it to challenge field.
    """
    id = serializers.UUIDField(read_only=True)
    challenge_id = serializers.UUIDField(write_only=True)
    imageSrc = serializers.URLField(source='image_url', allow_null=True, required=False)
    audioSrc = serializers.URLField(source='audio_url', allow_null=True, required=False)
    
    class Meta:
        model = ChallengeOption
        fields = [
            'id', 'challenge_id', 'text', 'is_correct', 'imageSrc', 
            'audioSrc', 'order'
        ]
    
    def create(self, validated_data):
        """Create challenge option with proper challenge mapping"""
        challenge_id = validated_data.pop('challenge_id')
        
        try:
            challenge = PracticeChallenge.objects.get(id=challenge_id)
            validated_data['challenge'] = challenge
        except PracticeChallenge.DoesNotExist:
            raise serializers.ValidationError(f"Challenge with id {challenge_id} does not exist")
        
        return super().create(validated_data)


class ChallengeProgressSerializer(serializers.ModelSerializer):
    """
    Challenge Progress serializer - tracks user completion.
    
    Maps to frontend challengeProgress structure from client project.
    """
    id = serializers.UUIDField(read_only=True)
    
    class Meta:
        model = ChallengeProgress
        fields = ['id', 'completed', 'completed_at']


def _utilizador(context):
    request = context.get('request')
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else None


class PracticeChallengeSerializer(serializers.ModelSerializer):
    """
    Exercício para o aluno (units-with-progress/, courses/<id>/units/, lessons/<id>/): só a
    estrutura e o progresso. Sem enunciado nem opções, para não revelar respostas (o texto das
    opções é a resposta em completar, traduzir, ditado, ordenar e pares). Para jogar, o ecrã usa
    lessons/<id>/jogar/.
    """
    id = serializers.UUIDField(read_only=True)
    challenge_progress = serializers.SerializerMethodField()
    completed = serializers.SerializerMethodField()

    class Meta:
        model = PracticeChallenge
        fields = ['id', 'lesson', 'type', 'order', 'challenge_progress', 'completed']

    def _progresso(self, obj):
        user = _utilizador(self.context)
        if user is None:
            return None
        cache = self.context.setdefault('_progresso_cache', {})
        if user.pk not in cache:
            cache[user.pk] = {}
        if obj.id not in cache[user.pk]:
            cache[user.pk][obj.id] = ChallengeProgress.objects.filter(user=user, challenge=obj).first()
        return cache[user.pk][obj.id]

    def get_challenge_progress(self, obj):
        progress = self._progresso(obj)
        return [ChallengeProgressSerializer(progress).data] if progress else []

    def get_completed(self, obj):
        progress = self._progresso(obj)
        return bool(progress and progress.completed)


class PracticeLessonSerializer(serializers.ModelSerializer):
    """Lição para o aluno: estrutura e progresso (ver PracticeChallengeSerializer)."""
    id = serializers.UUIDField(read_only=True)
    challenges = PracticeChallengeSerializer(many=True, read_only=True)
    completed = serializers.SerializerMethodField()

    class Meta:
        model = PracticeLesson
        fields = ['id', 'unit', 'title', 'order', 'challenges', 'completed']

    def get_completed(self, obj):
        user = _utilizador(self.context)
        if user is None:
            return False
        total = obj.challenges.count()
        if total == 0:
            return False
        feitos = ChallengeProgress.objects.filter(user=user, challenge__lesson=obj, completed=True).count()
        return feitos == total


class PracticeUnitSerializer(serializers.ModelSerializer):
    """Unidade para o aluno; as lições escondidas (context['licoes_escondidas']) não aparecem."""
    id = serializers.UUIDField(read_only=True)
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = PracticeUnit
        fields = ['id', 'course', 'title', 'description', 'order', 'lessons']

    def get_lessons(self, obj):
        escondidas = self.context.get('licoes_escondidas') or set()
        licoes = [l for l in obj.lessons.all() if l.id not in escondidas]
        return PracticeLessonSerializer(licoes, many=True, context=self.context).data

    def to_representation(self, instance):
        dados = super().to_representation(instance)
        # Unidade fora das unidades de amostra, para quem não tem o plano (apps/courses/amostra.py).
        dados['bloqueada'] = instance.id in (self.context.get('unidades_bloqueadas') or ())
        return dados


class ChallengeOptionProfessorSerializer(serializers.ModelSerializer):
    """Opção com a resposta certa, para o professor dono do curso. Não muda de exercício."""
    id = serializers.UUIDField(read_only=True)
    challenge = serializers.PrimaryKeyRelatedField(read_only=True)
    imageSrc = serializers.URLField(source='image_url', allow_null=True, allow_blank=True, required=False)
    audioSrc = serializers.URLField(source='audio_url', allow_null=True, allow_blank=True, required=False)

    class Meta:
        model = ChallengeOption
        fields = ['id', 'challenge', 'text', 'is_correct', 'imageSrc', 'audioSrc', 'order']


class PracticeChallengeProfessorSerializer(PracticeChallengeSerializer):
    """Exercício para o professor: campos de edição e opções com a resposta certa."""
    options = serializers.SerializerMethodField()

    class Meta(PracticeChallengeSerializer.Meta):
        fields = PracticeChallengeSerializer.Meta.fields + [
            'question', 'options', 'instruction', 'hint', 'explanation', 'reference_audio_url',
            'conversation_context', 'minimum_conversation_score',
        ]
        extra_kwargs = {
            'instruction': {'required': False},
            'hint': {'required': False},
            'explanation': {'required': False},
            'reference_audio_url': {'required': False},
        }

    def get_options(self, obj):
        return ChallengeOptionProfessorSerializer(obj.options.all(), many=True).data


class PracticeLessonProfessorSerializer(PracticeLessonSerializer):
    challenges = PracticeChallengeProfessorSerializer(many=True, read_only=True)


class PracticeUnitProfessorSerializer(PracticeUnitSerializer):
    lessons = PracticeLessonProfessorSerializer(many=True, read_only=True)


class UserProgressSerializer(serializers.ModelSerializer):
    """
    User Progress serializer - gamification stats.
    
    Maps to frontend userProgress structure from client project.
    Manages hearts, points, and active course.
    """
    active_course = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProgress
        fields = [
            'hearts', 'points', 'user_image_src', 
            'active_course', 'created_at', 'updated_at'
        ]
    
    def get_active_course(self, obj):
        """Get active course details"""
        if obj.active_course:
            return {
                'id': str(obj.active_course.id),
                'title': obj.active_course.title,
                'image': obj.active_course.image,
            }
        return None


class ChallengeProgressCreateSerializer(serializers.ModelSerializer):
    """
    Challenge Progress creation serializer - for completing challenges.
    
    Used when user submits an answer to a challenge.
    """
    class Meta:
        model = ChallengeProgress
        fields = ['challenge', 'completed']
        
    def create(self, validated_data):
        """Create or update challenge progress"""
        user = self.context['request'].user
        challenge = validated_data['challenge']
        
        progress, created = ChallengeProgress.objects.get_or_create(
            user=user,
            challenge=challenge,
            defaults={'completed': validated_data['completed']}
        )
        
        if not created:
            progress.completed = validated_data['completed']
            progress.save()
            
        return progress


class UserProgressUpdateSerializer(serializers.ModelSerializer):
    """
    User Progress update serializer - for hearts/points management.
    
    Used when updating user hearts and points after challenges.
    """
    class Meta:
        model = UserProgress
        fields = ['hearts', 'points', 'active_course']
        
    def update(self, instance, validated_data):
        """Update user progress with validation"""
        # Ensure hearts don't exceed 5 or go below 0
        if 'hearts' in validated_data:
            validated_data['hearts'] = max(0, min(5, validated_data['hearts']))
            
        return super().update(instance, validated_data)


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Detailed lesson serializer - for quiz page.
    
    Used for the lesson/quiz page, includes all challenges with options.
    Maps to the getLesson query from client project.
    """
    id = serializers.UUIDField(read_only=True)
    challenges = PracticeChallengeSerializer(many=True, read_only=True)
    unit = serializers.SerializerMethodField()
    
    class Meta:
        model = PracticeLesson
        fields = ['id', 'title', 'order', 'unit', 'challenges']
    
    def get_unit(self, obj):
        """Get unit details"""
        return {
            'id': str(obj.unit.id),
            'title': obj.unit.title,
            'description': obj.unit.description,
        }


# Leaderboard Serializers

class UserStreakSerializer(serializers.ModelSerializer):
    """User Streak serializer for leaderboard data"""
    class Meta:
        model = UserStreak
        fields = ['current_streak', 'longest_streak', 'last_practice_date']


class UserLeagueSerializer(serializers.ModelSerializer):
    """User League serializer for leaderboard data"""
    league_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UserLeague
        fields = ['current_league', 'points_when_promoted', 'promoted_at', 'league_info']
    
    def get_league_info(self, obj):
        """Get detailed league information"""
        return UserLeague.get_league_info(obj.current_league)


class LeaderboardEntrySerializer(serializers.Serializer):
    """Leaderboard entry serializer for ranking display"""
    id = serializers.CharField()
    rank = serializers.IntegerField()
    username = serializers.CharField()
    avatar = serializers.CharField(required=False, allow_null=True)
    points = serializers.IntegerField()
    streak = serializers.IntegerField()
    league = serializers.CharField()
    change = serializers.CharField()  # 'up', 'down', 'same', 'new'
    changeAmount = serializers.IntegerField(required=False, allow_null=True)
    isCurrentUser = serializers.BooleanField(default=False)


class LeagueInfoSerializer(serializers.Serializer):
    """League information serializer"""
    id = serializers.CharField()
    name = serializers.CharField()
    icon = serializers.CharField()
    color = serializers.CharField()
    minPoints = serializers.IntegerField()
    maxPoints = serializers.IntegerField(allow_null=True)
    participants = serializers.IntegerField()


class CompetitionSerializer(serializers.ModelSerializer):
    """Competition serializer for competition display"""
    participants = serializers.SerializerMethodField()
    currentPosition = serializers.SerializerMethodField()
    startDate = serializers.SerializerMethodField()
    endDate = serializers.SerializerMethodField()
    prize = serializers.SerializerMethodField()
    
    class Meta:
        model = Competition
        fields = [
            'id', 'title', 'description', 'type', 'status',
            'participants', 'currentPosition', 'startDate', 'endDate', 'prize'
        ]
    
    def get_participants(self, obj):
        """Get number of participants"""
        return obj.participant_count
    
    def get_currentPosition(self, obj):
        """Get current user's position in competition"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
            
        try:
            participant = CompetitionParticipant.objects.get(
                competition=obj, 
                user=request.user
            )
            return participant.current_rank
        except CompetitionParticipant.DoesNotExist:
            return None
    
    def get_startDate(self, obj):
        """Format start date for display"""
        from django.utils import timezone
        now = timezone.now()
        diff = now - obj.start_date
        
        if diff.days == 0:
            return "hoje"
        elif diff.days == 1:
            return "ontem"
        elif diff.days < 0:
            return f"em {abs(diff.days)} dias"
        else:
            return f"há {diff.days} dias"
    
    def get_endDate(self, obj):
        """Format end date for display"""
        from django.utils import timezone
        now = timezone.now()
        diff = obj.end_date - now
        
        if diff.days == 0:
            return "hoje"
        elif diff.days == 1:
            return "amanhã"
        elif diff.days < 0:
            return "terminado"
        else:
            return f"em {diff.days} dias"
    
    def get_prize(self, obj):
        """Get prize based on user's potential position"""
        return obj.first_place_prize  # For now, show top prize


class CompetitionParticipantSerializer(serializers.ModelSerializer):
    """Competition participant serializer"""
    username = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = CompetitionParticipant
        fields = [
            'id', 'username', 'points_earned', 'challenges_completed',
            'lessons_completed', 'streak_days', 'current_rank', 'best_rank'
        ]


class LeaderboardSnapshotSerializer(serializers.ModelSerializer):
    """Leaderboard snapshot serializer for historical data"""
    username = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = LeaderboardSnapshot
        fields = [
            'id', 'username', 'rank', 'points', 'league',
            'rank_change', 'points_change', 'snapshot_date', 'snapshot_type'
        ]


# Achievement Serializers

class AchievementSerializer(serializers.ModelSerializer):
    """Achievement serializer for achievement definitions"""
    rarity_color = serializers.CharField(source='get_rarity_color', read_only=True)
    unlocked_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Achievement
        fields = [
            'id', 'title', 'description', 'icon', 'category', 'rarity',
            'points', 'requirement_type', 'requirement_target', 'requirement_unit',
            'is_active', 'is_secret', 'order', 'created_at', 'rarity_color', 'unlocked_count'
        ]
    
    def get_unlocked_count(self, obj):
        """Get count of users who unlocked this achievement"""
        return obj.user_achievements.filter(is_unlocked=True).count()


class UserAchievementSerializer(serializers.ModelSerializer):
    """User achievement serializer with progress tracking"""
    achievement = AchievementSerializer(read_only=True)
    progress_percentage = serializers.FloatField(source='get_progress_percentage', read_only=True)
    unlocked_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = UserAchievement
        fields = [
            'id', 'achievement', 'is_unlocked', 'current_progress',
            'unlocked_at', 'unlocked_at_formatted', 'progress_percentage'
        ]
    
    def get_unlocked_at_formatted(self, obj):
        """Format unlock date for display"""
        if not obj.unlocked_at:
            return None
            
        from datetime import datetime
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - obj.unlocked_at
        
        if diff.days == 0:
            return "hoje"
        elif diff.days == 1:
            return "há 1 dia"
        elif diff.days < 7:
            return f"há {diff.days} dias"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"há {weeks} semana{'s' if weeks > 1 else ''}"
        else:
            months = diff.days // 30
            return f"há {months} mês{'es' if months > 1 else ''}"


class AchievementStatsSerializer(serializers.Serializer):
    """Serializer for achievement statistics"""
    totalUnlocked = serializers.IntegerField()
    totalAvailable = serializers.IntegerField()
    totalPoints = serializers.IntegerField()
    rareAchievements = serializers.IntegerField()
    recentUnlocked = serializers.IntegerField()


class AchievementCategorySerializer(serializers.ModelSerializer):
    """Achievement category serializer"""
    achievement_count = serializers.SerializerMethodField()
    unlocked_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AchievementCategory
        fields = [
            'name', 'display_name', 'description', 'icon_class',
            'color', 'order', 'achievement_count', 'unlocked_count'
        ]
    
    def get_achievement_count(self, obj):
        """Get total achievements in this category"""
        return Achievement.objects.filter(category=obj.name, is_active=True).count()
    
    def get_unlocked_count(self, obj):
        """Get unlocked achievements in this category for current user"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
            
        return UserAchievement.objects.filter(
            user=request.user,
            achievement__category=obj.name,
            is_unlocked=True
        ).count()


class AchievementNotificationSerializer(serializers.ModelSerializer):
    """Achievement notification serializer"""
    achievement = AchievementSerializer(read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = AchievementNotification
        fields = [
            'id', 'achievement', 'is_read', 'is_celebrated',
            'created_at', 'time_ago'
        ]
    
    def get_time_ago(self, obj):
        """Get time since notification was created"""
        from datetime import datetime
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.total_seconds() < 60:
            return "agora"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() // 60)
            return f"há {minutes} min"
        elif diff.days == 0:
            hours = int(diff.total_seconds() // 3600)
            return f"há {hours} h"
        elif diff.days == 1:
            return "ontem"
        else:
            return f"há {diff.days} dias"


class DetailedAchievementSerializer(serializers.Serializer):
    """Detailed achievement data for frontend page"""
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    category = serializers.CharField()
    rarity = serializers.CharField()
    points = serializers.IntegerField()
    isUnlocked = serializers.BooleanField()
    unlockedAt = serializers.CharField(allow_null=True)
    progress = serializers.DictField(allow_null=True)


# =============================================================================
# 🚀 VAPI AI CONVERSATION PRACTICE SERIALIZERS
# =============================================================================
# 
# Note: Traditional speaking/listening serializers removed in favor of unified
# Vapi-based conversation practice which handles both speaking and listening
# in a single, superior AI conversation experience.
#
# All speaking/listening functionality is now handled through:
# - apps/practice/services/vapi_client.py
# - apps/practice/services/conversation_ai.py  
# - apps/practice/views/vapi_views.py
# =============================================================================

class VapiConversationSerializer(serializers.Serializer):
    """
    Vapi Conversation serializer - for AI conversation practice.
    
    Maps Vapi conversation sessions and feedback for frontend display.
    """
    conversation_id = serializers.CharField()
    assistant_id = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    duration_minutes = serializers.FloatField()
    conversation_score = serializers.FloatField()
    feedback = serializers.DictField()


class VapiConversationFeedbackSerializer(serializers.Serializer):
    """
    Vapi Conversation Feedback serializer - detailed AI feedback.
    
    Maps comprehensive conversation feedback and analysis.
    """
    overall_score = serializers.FloatField()
    pronunciation_score = serializers.FloatField()
    fluency_score = serializers.FloatField()
    vocabulary_score = serializers.FloatField()
    grammar_score = serializers.FloatField()
    engagement_score = serializers.FloatField()
    comprehension_score = serializers.FloatField()
    
    # Detailed feedback sections
    strengths = serializers.ListField(child=serializers.CharField())
    improvements = serializers.ListField(child=serializers.CharField())
    vocabulary_used = serializers.ListField(child=serializers.DictField())
    grammar_patterns = serializers.ListField(child=serializers.DictField())
    pronunciation_notes = serializers.ListField(child=serializers.DictField())
    
    # Recommendations
    next_topics = serializers.ListField(child=serializers.CharField())
    recommended_practice = serializers.ListField(child=serializers.CharField())
    
    # Session metadata
    total_turns = serializers.IntegerField()
    conversation_flow = serializers.CharField()
    difficulty_level = serializers.CharField()
    topic_coverage = serializers.ListField(child=serializers.CharField())

# ============================================================================
# STUDY TRACKING SERIALIZERS (streak goal, lesson completion, notifications)
# ============================================================================

class StudyGoalSerializer(serializers.Serializer):
    """Validate the daily study goal (minutes)."""
    daily_goal_minutes = serializers.IntegerField(
        error_messages={
            'required': 'Indique a meta diária em minutos.',
            'invalid': 'A meta diária deve ser um número inteiro de minutos.',
            'null': 'Indique a meta diária em minutos.',
        }
    )

    def validate_daily_goal_minutes(self, value):
        allowed = [choice for choice, _ in UserStreak.DAILY_GOAL_CHOICES]
        if value not in allowed:
            raise serializers.ValidationError(
                'Meta diária inválida. Escolha 5, 10, 15 ou 20 minutos.'
            )
        return value


class CompleteLessonSerializer(serializers.Serializer):
    """Body for POST complete-lesson/. Accepts `time_spent` (seconds) as an alias."""
    lesson_id = serializers.UUIDField(error_messages={
        'required': 'O campo lesson_id é obrigatório.',
        'invalid': 'lesson_id inválido.',
        'null': 'O campo lesson_id é obrigatório.',
    })
    duration_seconds = serializers.IntegerField(required=False, min_value=0, allow_null=True, error_messages={
        'invalid': 'duration_seconds deve ser um número inteiro de segundos.',
        'min_value': 'duration_seconds não pode ser negativo.',
    })
    time_spent = serializers.IntegerField(required=False, min_value=0, allow_null=True, error_messages={
        'invalid': 'time_spent deve ser um número inteiro de segundos.',
        'min_value': 'time_spent não pode ser negativo.',
    })


class NotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    kind = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    read = serializers.BooleanField(source='is_read', read_only=True)
    read_at = serializers.DateTimeField(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
