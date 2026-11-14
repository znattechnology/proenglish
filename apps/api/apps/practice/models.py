"""
Practice Lab Models - Duolingo-style learning system

This module implements the database models for the ProEnglish practice laboratory,
providing a gamified learning experience similar to Duolingo.
"""

import uuid
from django.db import models, transaction
from django.db.models import F
from django.contrib.auth import get_user_model
from apps.courses.models import Course

User = get_user_model()


class PracticeUnit(models.Model):
    """
    Practice Unit - Groups related lessons together.
    
    Maps to Drizzle 'units' table from the client project.
    Example: "Basic Vocabulary", "Conversations", "Grammar Fundamentals"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='practice_units'
    )
    title = models.CharField(
        max_length=500,  # ✅ CATEGORIA 2: Título com limite generoso sincronizado (era 200)
        help_text="Unit title"
    )
    description = models.TextField(
        help_text="Unit description - sem limite para conteúdo rico"  # ✅ CATEGORIA 1: Sem limite
    )
    order = models.PositiveIntegerField(help_text="Display order within the course")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"


class PracticeLesson(models.Model):
    """
    Practice Lesson - Individual learning sessions within a unit.
    
    Maps to Drizzle 'lessons' table from the client project.
    Example: "Colors and Numbers", "Introducing Yourself"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(
        PracticeUnit, 
        on_delete=models.CASCADE, 
        related_name='lessons'
    )
    title = models.CharField(
        max_length=500,  # ✅ CATEGORIA 2: Título com limite generoso sincronizado (era 200)
        help_text="Lesson title"
    )
    order = models.PositiveIntegerField(help_text="Display order within the unit")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['unit', 'order']
    
    def __str__(self):
        return f"{self.unit.title} - {self.title}"


class PracticeChallenge(models.Model):
    """
    Practice Challenge - Individual exercises/questions.
    
    Maps to Drizzle 'challenges' table from the client project.
    Supports different challenge types like SELECT (multiple choice) and ASSIST (translation).
    """
    CHALLENGE_TYPES = [
        ('SELECT', 'Select - Multiple Choice'),
        ('ASSIST', 'Assist - Translation/Help'),
        ('FILL_BLANK', 'Fill in the Blank'),
        ('TRANSLATION', 'Translation'),
        ('MATCH_PAIRS', 'Match Pairs'),
        ('SENTENCE_ORDER', 'Sentence Order'),
        ('TRUE_FALSE', 'True/False Questions'),
        ('LISTENING', 'Listening Comprehension'),
        ('SPEAKING', 'Speaking Practice'),
        # Responder em voz alta a uma pergunta de trabalho (avaliado com Whisper + Claude).
        ('RESPONDER', 'Answer aloud'),

        # 🚀 VAPI AI CONVERSATION TYPES
        ('VAPI_CONVERSATION', 'AI Conversation Practice'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        PracticeLesson, 
        on_delete=models.CASCADE, 
        related_name='challenges'
    )
    type = models.CharField(
        max_length=25, 
        choices=CHALLENGE_TYPES,
        help_text="Type of challenge exercise"
    )
    question = models.TextField(help_text="The question or prompt for the user")
    instruction = models.TextField(
        blank=True,
        null=True,
        help_text="General instruction for the exercise (e.g., 'Complete using I/You/am/are')"
    )
    order = models.PositiveIntegerField(help_text="Display order within the lesson")
    hint = models.TextField(
        blank=True,
        null=True,
        help_text="Optional hint to help the student (shown on request)"
    )
    explanation = models.TextField(
        blank=True,
        null=True,
        help_text="Explanation shown after the challenge is answered"
    )

    # 🎤 SPEAKING CHALLENGE FIELDS
    reference_audio_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL of the reference audio for pronunciation practice (TTS generated)"
    )

    # 🚀 VAPI CONVERSATION CHALLENGE FIELDS
    # Note: Traditional separate speaking/listening fields removed.
    # All conversation practice now handled through Vapi integration.
    conversation_context = models.JSONField(
        default=dict,
        help_text="Contexto e cenário para conversação com Vapi AI"
    )
    minimum_conversation_score = models.FloatField(
        default=70.0,
        help_text="Pontuação mínima para passar na conversação"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['lesson', 'order']
    
    def __str__(self):
        return f"{self.lesson.title} - Challenge {self.order}"


class ChallengeOption(models.Model):
    """
    Challenge Option - Answer choices for challenges.
    
    Maps to Drizzle 'challengeOptions' table from the client project.
    Contains text, images, audio, and correctness information.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(
        PracticeChallenge, 
        on_delete=models.CASCADE, 
        related_name='options'
    )
    text = models.CharField(
        max_length=300,  # ✅ CATEGORIA 3: Campo curto aumentado (era 200)
        help_text="Option text/answer"
    )
    is_correct = models.BooleanField(
        default=False,
        help_text="Whether this option is the correct answer"
    )
    image_url = models.URLField(
        blank=True, 
        null=True,
        help_text="Optional image for visual questions (S3 URL)"
    )
    audio_url = models.URLField(
        blank=True, 
        null=True,
        help_text="Optional audio pronunciation (S3 URL)"
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.challenge} - {self.text}"


class UserProgress(models.Model):
    """
    User Progress - Tracks overall user progress and gamification stats.

    Maps to Drizzle 'userProgress' table from the client project.
    Manages hearts, points, active course, and profile information.

    P2 UNIFIED: Hearts are now managed through UserSubscription.current_hearts
    to ensure consistency across the system. The hearts field here is kept
    for backward compatibility but delegates to the subscription system.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='practice_progress'
    )
    active_course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Currently selected course for practice"
    )
    # DEPRECATED: Use subscription.current_hearts instead
    # Kept for migration compatibility, but hearts property reads from subscription
    _hearts_legacy = models.PositiveIntegerField(
        default=5,
        db_column='hearts',
        help_text="DEPRECATED: Use subscription.current_hearts instead"
    )
    points = models.PositiveIntegerField(
        default=0,
        help_text="Total points earned (+10 per correct challenge)"
    )
    user_image_src = models.URLField(
        default="/mascot.jpg",
        help_text="Profile image URL"
    )

    # 🚀 VAPI CONVERSATION PRACTICE FIELDS
    total_conversation_sessions = models.IntegerField(default=0)
    total_conversation_minutes = models.FloatField(default=0.0)
    average_conversation_score = models.FloatField(default=0.0)
    conversation_streak_days = models.IntegerField(default=0)
    last_conversation_session = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def hearts(self):
        """
        Get hearts from the unified subscription system.
        Falls back to legacy field if no subscription exists.
        """
        try:
            from apps.subscriptions.models import UserSubscription
            subscription = UserSubscription.objects.select_related('plan').get(user=self.user)
            plan = subscription.plan
            if plan.hearts_limit == 0 and subscription.is_active():
                # Vidas ilimitadas enquanto o plano estiver activo.
                subscription.recharge_hearts_if_needed()
                return subscription.current_hearts
            # O máximo é o do plano (um plano "ilimitado" que já terminou vale o máximo normal).
            maximo = plan.hearts_limit if plan.hearts_limit > 0 else 5
            if plan.hearts_limit > 0:
                subscription.recharge_hearts_if_needed()
            if subscription.current_hearts > maximo:
                # Ex.: 999 vidas que sobraram de um plano pago que terminou.
                UserSubscription.objects.filter(pk=subscription.pk).update(current_hearts=maximo)
                subscription.current_hearts = maximo
            return subscription.current_hearts
        except Exception:
            # Fallback to legacy field if subscription doesn't exist
            return min(self._hearts_legacy, 5)

    @hearts.setter
    def hearts(self, value):
        """
        Set hearts in both subscription and legacy field for compatibility.
        """
        try:
            from apps.subscriptions.models import UserSubscription
            subscription = UserSubscription.objects.get(user=self.user)
            max_hearts = subscription.plan.hearts_limit if subscription.plan.hearts_limit > 0 else 5
            subscription.current_hearts = min(value, max_hearts)
            subscription.save(update_fields=['current_hearts'])
        except Exception:
            pass
        # Also update legacy field for compatibility
        self._hearts_legacy = value

    def __str__(self):
        return f"{self.user.name} - {self.points} pts, {self.hearts} hearts"

    @transaction.atomic
    def reduce_hearts(self):
        """
        Reduce hearts by 1 (minimum 0) in a thread-safe manner.

        UNIFIED: Now delegates to UserSubscription.use_heart() for consistency.
        """
        try:
            from apps.subscriptions.models import UserSubscription
            subscription = UserSubscription.objects.get(user=self.user)
            subscription.use_heart()
        except Exception:
            # Fallback to legacy behavior if no subscription
            locked_progress = UserProgress.objects.select_for_update().get(pk=self.pk)
            if locked_progress._hearts_legacy > 0:
                UserProgress.objects.filter(pk=self.pk).update(
                    _hearts_legacy=F('_hearts_legacy') - 1
                )
                self.refresh_from_db()

    @transaction.atomic
    def add_hearts(self, amount=1):
        """
        Add hearts (up to plan limit) in a thread-safe manner.

        UNIFIED: Now updates UserSubscription.current_hearts for consistency.
        """
        try:
            from apps.subscriptions.models import UserSubscription
            subscription = UserSubscription.objects.select_for_update().get(user=self.user)
            max_hearts = subscription.plan.hearts_limit if subscription.plan.hearts_limit > 0 else 5
            new_hearts = min(max_hearts, subscription.current_hearts + amount)
            UserSubscription.objects.filter(pk=subscription.pk).update(
                current_hearts=new_hearts
            )
        except Exception:
            # Fallback to legacy behavior if no subscription
            locked_progress = UserProgress.objects.select_for_update().get(pk=self.pk)
            new_hearts = min(5, locked_progress._hearts_legacy + amount)
            UserProgress.objects.filter(pk=self.pk).update(_hearts_legacy=new_hearts)
            self.refresh_from_db()

    @transaction.atomic
    def add_points(self, amount=10, check_achievements=True, reason='', curso_id=None):
        """
        Add points for correct answers in a thread-safe manner.

        Uses F() expression for atomic increment to prevent race conditions.
        Every award is also written to PointsEntry (feeds the weekly league).
        `curso_id`: curso onde os pontos foram ganhos (conquistas e competições dos professores).
        """
        # Use F() expression for atomic increment
        UserProgress.objects.filter(pk=self.pk).update(
            points=F('points') + amount
        )
        if amount and amount > 0:
            PointsEntry.objects.create(user=self.user, points=amount, reason=reason[:30], curso_id=curso_id)
        self.refresh_from_db()
        if amount and amount > 0:
            self._verificar_subida_de_liga(self.points - amount, self.points)

        # Trigger achievement progress check (unless disabled to prevent recursion)
        if check_achievements:
            self._check_achievements_for_points()
    
    def _verificar_subida_de_liga(self, pontos_antes, pontos_agora):
        """Atualiza UserLeague e avisa o aluno quando os pontos totais o fazem subir de liga."""
        antes = UserLeague.get_league_for_points(pontos_antes)
        agora = UserLeague.get_league_for_points(pontos_agora)
        ordem = [codigo for codigo, _ in UserLeague.LEAGUE_CHOICES]
        if ordem.index(agora) <= ordem.index(antes):
            return
        try:
            with transaction.atomic():
                liga, _ = UserLeague.objects.get_or_create(user=self.user, defaults={'current_league': antes})
                liga.update_league()
            from apps.users.models import Notification
            info = UserLeague.get_league_info(agora)
            Notification.notify(
                self.user,
                Notification.KIND_LEAGUE,
                title=f'Subiu para a {info["name"]}',
                body=(f'Chegou a {pontos_agora} pontos no total. '
                      + ('Está na liga mais alta. Parabéns!' if agora == ordem[-1]
                         else 'Continue a praticar para subir ainda mais.')),
                link='/user/laboratory/achievements#liga',
                dedupe_key=f'liga:{agora}',
            )
        except Exception:  # nunca bloquear a atribuição de pontos por causa da liga/aviso
            import logging
            logging.getLogger(__name__).exception("Falha ao atualizar a liga do utilizador %s", self.user_id)

    def _check_achievements_for_points(self):
        """Check and update achievements related to points"""
        from .achievement_utils import check_achievement_progress, verificar_conquistas_professor
        check_achievement_progress(self.user, 'points_earned', self.points)
        verificar_conquistas_professor(self.user)


class ChallengeProgress(models.Model):
    """
    Challenge Progress - Tracks individual challenge completion.
    
    Maps to Drizzle 'challengeProgress' table from the client project.
    Records which challenges each user has completed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='challenge_progress'
    )
    challenge = models.ForeignKey(
        PracticeChallenge, 
        on_delete=models.CASCADE, 
        related_name='user_progress'
    )
    completed = models.BooleanField(default=False)
    # Exercício de pronúncia saltado porque a análise estava indisponível: conta como feito
    # para concluir a lição, mas não deu pontos.
    skipped = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Save and trigger achievement check if challenge was completed"""
        is_new_completion = self.pk is None and self.completed
        was_just_completed = False
        
        if self.pk:
            # Check if this is a new completion
            try:
                old_instance = ChallengeProgress.objects.get(pk=self.pk)
                was_just_completed = not old_instance.completed and self.completed
            except ChallengeProgress.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Trigger achievement checks for new completions
        if is_new_completion or was_just_completed:
            self._check_achievements_for_completion()
    
    def _check_achievements_for_completion(self):
        """Check and update achievements related to challenge completions"""
        from .achievement_utils import check_achievement_progress
        
        # Count total challenges completed by this user
        total_completed = ChallengeProgress.objects.filter(
            user=self.user, 
            completed=True
        ).count()
        
        check_achievement_progress(self.user, 'challenges_completed', total_completed)
        
        # Also check for lessons completed (challenges can be part of lessons)
        # A lesson counts as completed when every one of its challenges has a
        # completed ChallengeProgress for this user. (The previous lookup used a
        # non-existent `units__` relation and raised FieldError on every save.)
        completed_lessons = PracticeLesson.objects.annotate(
            total_challenges=models.Count('challenges', distinct=True),
            done_challenges=models.Count(
                'challenges__user_progress',
                filter=models.Q(
                    challenges__user_progress__user=self.user,
                    challenges__user_progress__completed=True,
                ),
                distinct=True,
            ),
        ).filter(total_challenges__gt=0, done_challenges=F('total_challenges')).count()
        
        check_achievement_progress(self.user, 'lessons_completed', completed_lessons)
    
    class Meta:
        unique_together = ['user', 'challenge']
        indexes = [
            models.Index(fields=['user', 'completed']),
            models.Index(fields=['challenge', 'completed']),
        ]
    
    def __str__(self):
        status = "✅" if self.completed else "⏳"
        return f"{status} {self.user.name} - {self.challenge}"


class UserLeague(models.Model):
    """
    User League - Tracks user's current league based on points.
    
    Leagues provide gamification tiers: Bronze, Silver, Gold, Diamond
    Users automatically move between leagues based on their points.
    """
    LEAGUE_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'), 
        ('gold', 'Gold'),
        ('diamond', 'Diamond'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='league'
    )
    current_league = models.CharField(
        max_length=10,
        choices=LEAGUE_CHOICES,
        default='bronze'
    )
    points_when_promoted = models.PositiveIntegerField(
        default=0,
        help_text="Points when user was promoted to current league"
    )
    promoted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @classmethod
    def get_league_for_points(cls, points):
        """Determine league based on points"""
        if points >= 3000:
            return 'diamond'
        elif points >= 2000:
            return 'gold'
        elif points >= 1000:
            return 'silver'
        else:
            return 'bronze'
    
    @classmethod
    def get_league_info(cls, league):
        """Get league information"""
        league_info = {
            'bronze': {'name': 'Liga Bronze', 'icon': '🥉', 'min_points': 0, 'max_points': 999},
            'silver': {'name': 'Liga Prata', 'icon': '🥈', 'min_points': 1000, 'max_points': 1999},
            'gold': {'name': 'Liga Ouro', 'icon': '🥇', 'min_points': 2000, 'max_points': 2999},
            'diamond': {'name': 'Liga Diamante', 'icon': '💎', 'min_points': 3000, 'max_points': None}
        }
        return league_info.get(league, league_info['bronze'])
    
    def update_league(self):
        """Update user's league based on current points"""
        user_progress = self.user.practice_progress
        new_league = self.get_league_for_points(user_progress.points)
        
        if new_league != self.current_league:
            previous_league = self.current_league
            self.current_league = new_league
            self.points_when_promoted = user_progress.points
            self.save()
            
            # Create promotion record (from_league was recorded after being overwritten)
            LeaguePromotion.objects.create(
                user=self.user,
                from_league=previous_league,
                to_league=new_league,
                points_at_promotion=user_progress.points
            )
    
    def __str__(self):
        return f"{self.user.name} - {self.get_current_league_display()}"


class LeaguePromotion(models.Model):
    """
    League Promotion - Historical record of league changes.
    
    Tracks when users are promoted or demoted between leagues.
    """
    LEAGUE_CHOICES = UserLeague.LEAGUE_CHOICES
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='league_promotions'
    )
    from_league = models.CharField(max_length=10, choices=LEAGUE_CHOICES)
    to_league = models.CharField(max_length=10, choices=LEAGUE_CHOICES)
    points_at_promotion = models.PositiveIntegerField()
    promoted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-promoted_at']
    
    def __str__(self):
        return f"{self.user.name}: {self.from_league} → {self.to_league}"


class Competition(models.Model):
    """
    Competition - Periodic challenges and events.
    
    Competitions provide time-limited challenges for users to participate in
    and compete against each other for rankings and prizes.
    """
    COMPETITION_TYPES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('special', 'Special Event'),
    ]
    
    COMPETITION_STATUS = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('ended', 'Ended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=COMPETITION_TYPES)
    status = models.CharField(max_length=20, choices=COMPETITION_STATUS, default='upcoming')
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Competition rules
    min_points_to_participate = models.PositiveIntegerField(default=0)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    
    # Prizes
    first_place_prize = models.CharField(max_length=200, default="Badge especial + 500 pontos")
    second_place_prize = models.CharField(max_length=200, default="300 pontos")
    third_place_prize = models.CharField(max_length=200, default="200 pontos")

    # Competições dos professores (ver apps/practice/competicoes.py).
    CONTA_LICOES = 'licoes'
    CONTA_PONTOS = 'pontos'
    CONTA_MINUTOS = 'minutos_conversa'
    CONTA_DIAS = 'dias_seguidos'
    CONTA_CHOICES = [
        (CONTA_LICOES, 'Lições concluídas'),
        (CONTA_PONTOS, 'Pontos'),
        (CONTA_MINUTOS, 'Minutos de conversa'),
        (CONTA_DIAS, 'Dias seguidos'),
    ]
    PREMIO_CERTIFICADO = 'certificado_merito'
    PREMIO_MEDALHA = 'medalha'
    PREMIO_PLANO = 'plano'  # um mês de plano: só o administrador
    PREMIO_CHOICES = [
        (PREMIO_CERTIFICADO, 'Certificado de mérito'),
        (PREMIO_MEDALHA, 'Medalha'),
        (PREMIO_PLANO, 'Um mês de plano'),
    ]
    criado_por = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='competicoes_criadas',
        help_text='Professor que criou; vazio = competição da plataforma')
    cursos = models.ManyToManyField(Course, blank=True, related_name='competicoes')
    todos_os_cursos = models.BooleanField(
        default=False, help_text='Professor: conta todos os cursos dele (também os que criar depois)')
    conta = models.CharField(max_length=20, choices=CONTA_CHOICES, default=CONTA_PONTOS)
    premio = models.CharField(max_length=20, choices=PREMIO_CHOICES, default=PREMIO_CERTIFICADO)
    premio_lugares = models.PositiveSmallIntegerField(default=3)
    inicio_notificado = models.BooleanField(default=False)
    fechada_em = models.DateTimeField(null=True, blank=True, help_text='Quando os prémios foram atribuídos')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.title} ({self.type})"
    
    @property
    def participant_count(self):
        return self.participants.count()


class CompetitionParticipant(models.Model):
    """
    Competition Participant - User participation in competitions.
    
    Tracks which users are participating in which competitions
    and their current standings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='competition_participations'
    )
    
    # Performance metrics
    points_earned = models.PositiveIntegerField(default=0)
    challenges_completed = models.PositiveIntegerField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)
    streak_days = models.PositiveIntegerField(default=0)
    
    # Ranking
    current_rank = models.PositiveIntegerField(null=True, blank=True)
    best_rank = models.PositiveIntegerField(null=True, blank=True)
    # Competições dos professores: valor final da métrica e prémio atribuído no fecho.
    valor = models.PositiveIntegerField(default=0)
    premio = models.CharField(max_length=20, blank=True, default='')
    
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['competition', 'user']
        ordering = ['current_rank']
    
    def __str__(self):
        return f"{self.user.name} in {self.competition.title}"


class LeaderboardSnapshot(models.Model):
    """
    Leaderboard Snapshot - Historical rankings data.
    
    Stores periodic snapshots of the leaderboard for tracking
    rank changes and historical performance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Snapshot metadata
    snapshot_date = models.DateTimeField(auto_now_add=True)
    snapshot_type = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily'
    )
    
    # User ranking data
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ranking_history')
    rank = models.PositiveIntegerField()
    points = models.PositiveIntegerField()
    league = models.CharField(max_length=10, choices=UserLeague.LEAGUE_CHOICES)
    
    # Change indicators
    rank_change = models.IntegerField(default=0, help_text="Change from previous snapshot (+/-)")
    points_change = models.IntegerField(default=0, help_text="Points gained since last snapshot")
    
    class Meta:
        unique_together = ['user', 'snapshot_date', 'snapshot_type']
        ordering = ['-snapshot_date', 'rank']
    
    def __str__(self):
        return f"#{self.rank} {self.user.name} - {self.snapshot_date.date()}"


class UserStreak(models.Model):
    """
    User Streak - Daily practice streak tracking.
    
    Tracks consecutive days of practice activity for gamification.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='streak'
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_practice_date = models.DateField(null=True, blank=True)

    # Daily study goal (minutes). Lives here because it is a one-row-per-user
    # study setting that is always read together with the streak.
    DAILY_GOAL_CHOICES = [(5, '5 min'), (10, '10 min'), (15, '15 min'), (20, '20 min')]
    DEFAULT_DAILY_GOAL_MINUTES = 10
    daily_goal_minutes = models.PositiveSmallIntegerField(
        default=DEFAULT_DAILY_GOAL_MINUTES,
        choices=DAILY_GOAL_CHOICES,
        help_text="Daily study goal in minutes (5, 10, 15 or 20)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_effective_streak(self, today=None):
        """Current streak as seen today (0 if the last study day was before yesterday)."""
        from datetime import timedelta
        from django.utils import timezone

        today = today or timezone.localdate()
        if not self.last_practice_date or self.last_practice_date < today - timedelta(days=1):
            return 0
        return self.current_streak

    def update_streak(self):
        """Update streak based on practice activity"""
        from datetime import timedelta
        from django.utils import timezone

        # Use the project timezone (same date used by DailyStudyLog)
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        
        if self.last_practice_date == today:
            # Already practiced today, no change needed
            return
        elif self.last_practice_date == yesterday:
            # Consecutive day, increment streak
            self.current_streak += 1
            self.longest_streak = max(self.longest_streak, self.current_streak)
        elif self.last_practice_date and self.last_practice_date < yesterday:
            # Streak broken, reset to 1
            self.current_streak = 1
        else:
            # First practice ever
            self.current_streak = 1

        self.longest_streak = max(self.longest_streak, self.current_streak)
        self.last_practice_date = today
        self.save()
        
        # Trigger achievement progress check for streaks
        self._check_achievements_for_streak()
    
    def _check_achievements_for_streak(self):
        """Check and update achievements related to streaks"""
        from .achievement_utils import check_achievement_progress, verificar_conquistas_professor
        check_achievement_progress(self.user, 'streak_days', self.current_streak)
        verificar_conquistas_professor(self.user)
    
    def __str__(self):
        return f"{self.user.name} - {self.current_streak} days streak"


class Achievement(models.Model):
    """
    Achievement - Individual achievement/badge definition.
    
    Defines what achievements are available in the system, their requirements,
    and metadata like rarity, points, and visual representation.
    """
    CATEGORY_CHOICES = [
        ('learning', 'Learning'),
        ('streak', 'Streak'),
        ('social', 'Social'),
        ('milestone', 'Milestone'),
        ('special', 'Special'),
    ]
    
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, help_text="Emoji or unicode icon")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    points = models.PositiveIntegerField(help_text="Points awarded when unlocked")
    
    # Achievement requirements/criteria
    requirement_type = models.CharField(
        max_length=50,
        help_text="Type of requirement: lessons_completed, streak_days, points_earned, etc."
    )
    requirement_target = models.PositiveIntegerField(
        help_text="Target value to achieve (e.g., 50 for '50 lessons completed')"
    )
    requirement_unit = models.CharField(
        max_length=20,
        default="items",
        help_text="Unit for progress display (lessons, days, points, etc.)"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    is_secret = models.BooleanField(
        default=False, 
        help_text="Hidden achievements not shown until unlocked"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    # Conquistas dos professores (vazio = conquista da plataforma, só o administrador altera).
    criado_por = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='conquistas_criadas')
    # Âmbito de uma conquista de professor: um curso dele, ou vazio = todos os cursos dele.
    curso = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True, related_name='conquistas')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'category', 'rarity']
    
    def __str__(self):
        return f"{self.title} ({self.category}, {self.rarity})"
    
    def get_rarity_color(self):
        """Get CSS color class for rarity"""
        color_map = {
            'common': 'text-gray-400',
            'rare': 'text-blue-400',
            'epic': 'text-purple-400',
            'legendary': 'text-yellow-400'
        }
        return color_map.get(self.rarity, 'text-gray-400')


class UserAchievement(models.Model):
    """
    User Achievement - Tracks which achievements users have unlocked.
    
    Records when a user unlocks an achievement and tracks progress
    towards achievements that are not yet unlocked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievements'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_achievements'
    )
    
    # Progress tracking
    is_unlocked = models.BooleanField(default=False)
    current_progress = models.PositiveIntegerField(
        default=0,
        help_text="Current progress towards the achievement"
    )
    unlocked_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-unlocked_at', '-created_at']
    
    def __str__(self):
        status = "🏆" if self.is_unlocked else f"📈 {self.current_progress}/{self.achievement.requirement_target}"
        return f"{self.user.name} - {self.achievement.title} {status}"
    
    def get_progress_percentage(self):
        """Calculate progress percentage"""
        if self.achievement.requirement_target == 0:
            return 100 if self.is_unlocked else 0
        return min(100, (self.current_progress / self.achievement.requirement_target) * 100)
    
    def update_progress(self, new_progress):
        """Update progress and check if achievement should be unlocked"""
        from datetime import datetime
        from django.utils import timezone
        
        self.current_progress = new_progress
        
        # Check if achievement should be unlocked
        if (not self.is_unlocked and 
            self.current_progress >= self.achievement.requirement_target):
            self.is_unlocked = True
            self.unlocked_at = timezone.now()
            
            # Award points to user (without triggering achievement check to prevent recursion)
            user_progress, created = UserProgress.objects.get_or_create(
                user=self.user,
                defaults={'hearts': 5, 'points': 0}
            )
            user_progress.add_points(self.achievement.points, check_achievements=False, reason='achievement')
        
        self.save()
        return self.is_unlocked


class AchievementCategory(models.Model):
    """
    Achievement Category - Metadata for achievement categories.
    
    Provides additional information and configuration for achievement categories.
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    icon_class = models.CharField(max_length=50, help_text="CSS icon class")
    color = models.CharField(max_length=50, help_text="CSS color class")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Achievement Categories"
    
    def __str__(self):
        return self.display_name


class AchievementNotification(models.Model):
    """
    Achievement Notification - Tracks achievement unlock notifications.
    
    Manages notifications when users unlock new achievements,
    allowing for celebration and recognition of progress.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievement_notifications'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Notification status
    is_read = models.BooleanField(default=False)
    is_celebrated = models.BooleanField(
        default=False,
        help_text="Whether the achievement popup was shown"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-created_at']
    
    def __str__(self):
        status = "📖" if self.is_read else "🔔"
        return f"{status} {self.user.name} - {self.achievement.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_celebrated(self):
        """Mark achievement as celebrated (popup shown)"""
        self.is_celebrated = True
        self.save()


# =============================================================================
# 🚀 VAPI AI CONVERSATION PRACTICE MODELS
# =============================================================================
# 
# Note: Traditional speaking/listening models removed in favor of unified
# Vapi-based conversation practice which handles both speaking and listening
# in a single, superior AI conversation experience.
#
# A conversa com o tutor vive em apps/practice/conversa/ (servico.py, webhook.py).
# =============================================================================


class VapiSession(models.Model):
    """
    Vapi Conversation Session - Historical progress tracking
    
    Focused model for continuous progress analysis and daily improvement tracking.
    Stores essential metrics for long-term progress visualization.
    """
    
    # Core Identification
    session_id = models.CharField(max_length=100, unique=True, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vapi_sessions')
    
    # Estado da sessão (conversa/). Sessões antigas (sem estado) contam como avaliadas.
    STATUS_EM_CURSO = 'em_curso'
    STATUS_A_AVALIAR = 'a_avaliar'      # terminada e cobrada; a avaliação (Claude) ainda não acabou
    STATUS_AVALIADA = 'avaliada'
    STATUS_SEM_AVALIACAO = 'sem_avaliacao'
    STATUS_NAO_LIGOU = 'nao_ligou'      # a chamada nunca ligou: 0 minutos, não conta em lado nenhum
    STATUS_CHOICES = [
        (STATUS_EM_CURSO, 'Em curso'),
        (STATUS_A_AVALIAR, 'A avaliar'),
        (STATUS_AVALIADA, 'Avaliada'),
        (STATUS_SEM_AVALIACAO, 'Sem avaliação'),
        (STATUS_NAO_LIGOU, 'Não ligou'),
    ]
    # Conversas que aconteceram (contam sessões e minutos). As notas só vêm das avaliadas.
    STATUS_TERMINADAS = (STATUS_AVALIADA, STATUS_SEM_AVALIACAO, STATUS_A_AVALIAR)

    # Session Context
    level = models.CharField(max_length=10)  # A1, A2, B1, B2, C1, C2
    domain = models.CharField(max_length=50)  # general, petroleum, IT, business
    duration_minutes = models.PositiveIntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVALIADA, db_index=True)
    situation = models.CharField(max_length=40, blank=True, default='',
                                 help_text="Situação da conversa (ver apps.practice.conversa.situacoes)")
    mode = models.CharField(max_length=10, blank=True, default='', help_text="vapi | simulado")
    started_at = models.DateTimeField(null=True, blank=True, help_text="Início (relógio do servidor)")
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0, help_text="Duração calculada no servidor")
    max_seconds = models.PositiveIntegerField(default=0, help_text="Duração máxima permitida ao criar")
    connected_at = models.DateTimeField(null=True, blank=True,
                                        help_text="A chamada ligou (POST ligada/): o tempo cobrado conta daqui")
    last_activity_at = models.DateTimeField(null=True, blank=True,
                                            help_text="Último sinal de vida (ligada/, ajuste/, responder/)")
    
    # Core Scores (0-100) - Essential for progress tracking
    fluency_score = models.PositiveIntegerField(default=0)
    # null = não medida (as conversas só têm texto; não inventamos uma nota de pronúncia)
    pronunciation_score = models.PositiveIntegerField(default=0, null=True, blank=True)
    grammar_score = models.PositiveIntegerField(default=0)
    vocabulary_score = models.PositiveIntegerField(default=0)
    overall_score = models.PositiveIntegerField(default=0)
    
    # Speaking Performance Metrics
    total_words = models.PositiveIntegerField(default=0)
    words_per_minute = models.PositiveIntegerField(default=0)
    corrections_count = models.PositiveIntegerField(default=0)
    
    # Progress Indicators
    improvement_from_last = models.FloatField(default=0, help_text="Score improvement from last session")
    streak_days = models.PositiveIntegerField(default=0)
    
    # Rich Data (for detailed analysis)
    full_session_data = models.JSONField(default=dict, help_text="Complete session data including corrections, phrases, etc.")
    
    # Timestamps for Progress Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)  # For daily grouping
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['user', 'level', '-date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.session_id} ({self.overall_score}%)"
    
    def calculate_improvement(self):
        """Calculate improvement from previous session"""
        from django.utils import timezone
        previous_session = VapiSession.objects.filter(
            user=self.user,
            status=VapiSession.STATUS_AVALIADA,
            created_at__lt=self.created_at or timezone.now()
        ).exclude(pk=self.pk).first()
        
        if previous_session:
            self.improvement_from_last = self.overall_score - previous_session.overall_score
        else:
            self.improvement_from_last = 0
    
    def update_streak(self):
        """Update daily conversation streak (consecutive days with a session)."""
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.localdate()
        latest = VapiSession.objects.filter(user=self.user).exclude(pk=self.pk).order_by('-created_at').first()
        if latest and latest.date == today:
            self.streak_days = latest.streak_days or 1  # second session today: unchanged
        elif latest and latest.date == today - timedelta(days=1):
            self.streak_days = (latest.streak_days or 0) + 1
        else:
            self.streak_days = 1

    def save(self, *args, **kwargs):
        """Auto-calculate metrics on save"""
        # Only on creation. session_id is the (always pre-filled) primary key, so the
        # old `if not self.pk` check never ran these.
        if self._state.adding:
            self.calculate_improvement()
            self.update_streak()
        super().save(*args, **kwargs)


class DailyProgressSummary(models.Model):
    """
    Daily aggregated progress data for quick dashboard queries
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_progress')
    date = models.DateField()
    
    # Daily Aggregates
    sessions_count = models.PositiveIntegerField(default=0)
    total_practice_minutes = models.PositiveIntegerField(default=0)
    average_score = models.FloatField(default=0)
    best_score = models.PositiveIntegerField(default=0)
    total_words = models.PositiveIntegerField(default=0)
    total_corrections = models.PositiveIntegerField(default=0)
    
    # Progress Metrics
    score_improvement = models.FloatField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    
    # Achievements
    new_level_reached = models.BooleanField(default=False)
    personal_best = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', '-date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.sessions_count} sessions)"
    
    @classmethod
    def update_for_user_date(cls, user, date):
        """Update daily summary for a specific user and date"""
        sessions = VapiSession.objects.filter(user=user, date=date, status=VapiSession.STATUS_AVALIADA)
        
        if not sessions.exists():
            return None
        
        summary, created = cls.objects.get_or_create(
            user=user,
            date=date,
            defaults={
                'sessions_count': 0,
                'total_practice_minutes': 0,
                'average_score': 0,
                'best_score': 0,
                'total_words': 0,
                'total_corrections': 0,
            }
        )
        
        # Calculate aggregates
        summary.sessions_count = sessions.count()
        summary.total_practice_minutes = sum(s.duration_minutes for s in sessions)
        summary.average_score = sum(s.overall_score for s in sessions) / summary.sessions_count
        summary.best_score = max(s.overall_score for s in sessions)
        summary.total_words = sum(s.total_words for s in sessions)
        summary.total_corrections = sum(s.corrections_count for s in sessions)
        summary.current_streak = sessions.last().streak_days if sessions.last() else 0
        
        # Check for achievements
        previous_best = cls.objects.filter(user=user, date__lt=date).aggregate(
            max_score=models.Max('best_score')
        )['max_score'] or 0
        
        summary.personal_best = summary.best_score > previous_best

        summary.save()
        return summary



# =============================================================================
# STUDY TRACKING (daily log, lesson completions, attempts)
# =============================================================================


class DailyStudyLog(models.Model):
    """
    Minutes studied per user per day, split by activity kind.

    Feeds the streak widget, the daily goal and the student analytics page.
    """
    KIND_LESSON = 'lesson'
    KIND_VIDEO = 'video'
    KIND_CONVERSATION = 'conversation'
    KIND_FIELDS = {
        KIND_LESSON: 'lesson_minutes',
        KIND_VIDEO: 'video_minutes',
        KIND_CONVERSATION: 'conversation_minutes',
    }
    MAX_MINUTES_PER_EVENT = 60

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_logs')
    date = models.DateField()
    lesson_minutes = models.FloatField(default=0)
    video_minutes = models.FloatField(default=0)
    conversation_minutes = models.FloatField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)
    goal_met_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the daily goal was first met on this day",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_daily_study_log_per_user_date'),
        ]
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f"{self.user_id} - {self.date} ({self.total_minutes:.1f} min)"

    @property
    def total_minutes(self):
        return (self.lesson_minutes or 0) + (self.video_minutes or 0) + (self.conversation_minutes or 0)

    @classmethod
    def add_minutes(cls, user, kind, minutes, lessons_completed=0, day=None):
        """
        Add study minutes for today, update the streak and fire the
        "daily goal met" notification the first time the goal is reached.

        day: record on a past day instead (e.g. a conversation closed after its day ended).
        Past days only get the minutes: no streak update, no notification.

        Returns a dict: {log, streak, goal_minutes, goal_completed, goal_just_completed}.
        """
        from django.utils import timezone

        if day is not None and day < timezone.localdate():
            return cls._add_minutes_past_day(user, kind, minutes, day)

        if kind not in cls.KIND_FIELDS:
            raise ValueError(f"Unknown study kind: {kind}")
        try:
            minutes = float(minutes or 0)
        except (TypeError, ValueError):
            minutes = 0.0
        minutes = max(0.0, min(minutes, float(cls.MAX_MINUTES_PER_EVENT)))

        today = timezone.localdate()
        with transaction.atomic():
            log, _ = cls.objects.get_or_create(user=user, date=today)
            log = cls.objects.select_for_update().get(pk=log.pk)
            field = cls.KIND_FIELDS[kind]
            setattr(log, field, getattr(log, field) + minutes)
            log.lessons_completed += max(0, int(lessons_completed or 0))

            streak, _ = UserStreak.objects.get_or_create(user=user)
            goal = streak.daily_goal_minutes
            goal_just_completed = False
            if log.goal_met_at is None and log.total_minutes >= goal:
                log.goal_met_at = timezone.now()
                goal_just_completed = True
            log.save()

        # Streak update (also triggers streak achievements)
        streak.update_streak()

        if goal_just_completed:
            try:
                from apps.users.models import Notification
                Notification.notify(
                    user,
                    Notification.KIND_STREAK,
                    title='Meta diária cumprida!',
                    body=f'Estudou {goal} minutos hoje. Sequência actual: {streak.current_streak} dia(s).',
                    link='/user/laboratory',
                    dedupe_key=f'meta-cumprida:{today.isoformat()}',
                )
            except Exception:  # never block study tracking on notifications
                import logging
                logging.getLogger(__name__).exception("Failed to create daily goal notification")

        return {
            'log': log,
            'streak': streak,
            'goal_minutes': goal,
            'goal_completed': log.goal_met_at is not None,
            'goal_just_completed': goal_just_completed,
        }

    @classmethod
    def _add_minutes_past_day(cls, user, kind, minutes, day):
        if kind not in cls.KIND_FIELDS:
            raise ValueError(f"Unknown study kind: {kind}")
        minutes = max(0.0, min(float(minutes or 0), float(cls.MAX_MINUTES_PER_EVENT)))
        with transaction.atomic():
            log, _ = cls.objects.get_or_create(user=user, date=day)
            log = cls.objects.select_for_update().get(pk=log.pk)
            field = cls.KIND_FIELDS[kind]
            setattr(log, field, getattr(log, field) + minutes)
            log.save()
        streak, _ = UserStreak.objects.get_or_create(user=user)
        return {
            'log': log,
            'streak': streak,
            'goal_minutes': streak.daily_goal_minutes,
            'goal_completed': log.goal_met_at is not None,
            'goal_just_completed': False,
        }


class LessonCompletion(models.Model):
    """
    One row per (user, lesson): makes the first-completion bonus idempotent and
    records repeat practice ("praticar de novo").
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_completions')
    lesson = models.ForeignKey(PracticeLesson, on_delete=models.CASCADE, related_name='completions')
    times_completed = models.PositiveIntegerField(default=1)
    first_completed_at = models.DateTimeField(auto_now_add=True)
    last_completed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'lesson'], name='unique_lesson_completion_per_user'),
        ]
        indexes = [models.Index(fields=['user', '-last_completed_at'])]

    def __str__(self):
        return f"{self.user_id} - {self.lesson_id} x{self.times_completed}"


class ChallengeAttempt(models.Model):
    """
    Every answer submitted through ChallengeProgressView (right or wrong).

    ChallengeProgress only stores the latest correct state, so wrong answers
    were not persisted. This log powers review words and accuracy analytics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_attempts')
    challenge = models.ForeignKey(PracticeChallenge, on_delete=models.CASCADE, related_name='attempts')
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'challenge', 'is_correct']),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.challenge_id} ({'ok' if self.is_correct else 'wrong'})"


class TentativaPronuncia(models.Model):
    """
    Cada gravação de um exercício de falar (SPEAKING) analisada em analyze-ai-pronunciation/.

    Guarda o que o aluno disse (transcrição), as notas e as palavras a melhorar: é a base
    do perfil de fala do aluno. A resposta (certa/errada) também fica em ChallengeAttempt,
    para as estatísticas de acerto e a revisão incluírem a fala.
    """
    FONTE_IA = 'ia'
    FONTE_SIMULADA = 'simulada'
    FONTE_CHOICES = [(FONTE_IA, 'IA'), (FONTE_SIMULADA, 'Simulada (desenvolvimento)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tentativas_pronuncia')
    # SET_NULL: o histórico de fala do aluno fica mesmo que o professor apague o exercício.
    challenge = models.ForeignKey(PracticeChallenge, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='tentativas_pronuncia')
    resposta = models.OneToOneField(ChallengeAttempt, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='pronuncia')
    texto_esperado = models.TextField()
    transcricao = models.TextField(blank=True, default='')
    nota_pronuncia = models.PositiveSmallIntegerField(default=0)
    nota_fluencia = models.PositiveSmallIntegerField(default=0)
    nota_clareza = models.PositiveSmallIntegerField(default=0)
    nota_geral = models.PositiveSmallIntegerField(default=0)
    palavras_problematicas = models.JSONField(default=list, blank=True)
    sugestoes = models.JSONField(default=list, blank=True)
    feedback = models.TextField(blank=True, default='')
    aceite = models.BooleanField()
    fonte = models.CharField(max_length=10, choices=FONTE_CHOICES, default=FONTE_IA)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        indexes = [models.Index(fields=['user', '-criada_em'])]

    def __str__(self):
        return f"{self.user_id} - {self.challenge_id} ({self.nota_geral})"


class PointsEntry(models.Model):
    """
    Ledger of points earned (one row per UserProgress.add_points call).
    UserProgress.points only keeps the running total; this table lets the
    weekly league rank students by points earned in a given week.
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_entries')
    points = models.PositiveIntegerField()
    reason = models.CharField(max_length=30, blank=True, default='')
    # Curso onde os pontos foram ganhos (vazio: conquista, prática com IA, conversa geral...).
    curso = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='pontos_ganhos')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f"{self.user_id} +{self.points} ({self.reason or '-'})"


class Situacao(models.Model):
    """
    Situação da conversa com o tutor (apps/practice/conversa/).

    `slug` é o valor guardado em VapiSession.situation (as 5 situações originais mantêm
    as chaves antigas: pedir_relatorio, reuniao_seguranca, ...). criado_por vazio = situação
    da plataforma (só o administrador altera); curso vazio = Geral (todos os alunos).
    `extras` guarda o guião detalhado das situações da plataforma (brief, primeira_fala,
    primeira_fala_simples, palavras, guiao, minutos_sugeridos e frases com tradução).
    """
    NIVEIS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    DURACOES = [3, 5, 10]
    CORRECCOES = ['suave', 'directa']
    RASCUNHO = 'rascunho'
    ACTIVO = 'activo'
    ESTADOS = [RASCUNHO, ACTIVO]

    slug = models.CharField(max_length=40, unique=True)
    nome = models.CharField(max_length=80)
    descricao = models.TextField(help_text='O que acontece (orienta o tutor)')
    papel_tutor = models.CharField(max_length=300, blank=True, default='')
    frases = models.JSONField(default=list, blank=True, help_text='Frases-alvo (lista de textos)')
    curso = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='situacoes_conversa')
    area = models.CharField(max_length=20, default='general')
    nivel = models.CharField(max_length=2, default='B1')
    duracao_min = models.PositiveSmallIntegerField(default=5)
    correccao = models.CharField(max_length=10, default='suave')
    estado = models.CharField(max_length=10, default=RASCUNHO, db_index=True)
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='situacoes_criadas')
    ordem = models.PositiveIntegerField(default=100)
    extras = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'created_at']

    def __str__(self):
        return f"{self.nome} ({self.slug})"
