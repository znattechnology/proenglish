"""
User models for the ProEnglish platform.

Following Django best practices with AbstractUser and proper role management.
"""

import datetime
import uuid
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from apps.core.models import BaseModel, Address
from .managers import UserManager


# Províncias de Angola: as 21 da Divisão Político-Administrativa de 2024 (Lei n.º 14/24):
# o Cuando Cubango dividiu-se em Cuando e Cubango, o Moxico em Moxico e Moxico Leste, e de
# Luanda saiu Ícolo e Bengo. Valor = slug, rótulo em pt-PT.
PROVINCIAS = [
    ('bengo', 'Bengo'),
    ('benguela', 'Benguela'),
    ('bie', 'Bié'),
    ('cabinda', 'Cabinda'),
    ('cuando', 'Cuando'),
    ('cubango', 'Cubango'),
    ('cuanza-norte', 'Cuanza Norte'),
    ('cuanza-sul', 'Cuanza Sul'),
    ('cunene', 'Cunene'),
    ('huambo', 'Huambo'),
    ('huila', 'Huíla'),
    ('icolo-e-bengo', 'Ícolo e Bengo'),
    ('luanda', 'Luanda'),
    ('lunda-norte', 'Lunda Norte'),
    ('lunda-sul', 'Lunda Sul'),
    ('malanje', 'Malanje'),
    ('moxico', 'Moxico'),
    ('moxico-leste', 'Moxico Leste'),
    ('namibe', 'Namibe'),
    ('uige', 'Uíge'),
    ('zaire', 'Zaire'),
]


class User(AbstractUser):
    """
    Custom user model extending AbstractUser.
    
    Improvements over original schema:
    - Uses AbstractUser instead of extending User (cleaner approach)
    - Proper role management with choices
    - Better field organization
    """
    
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Administrator'),
    ]
    
    # Override id to use UUID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Required fields
    email = models.EmailField(
        unique=True,
        help_text="User's email address - used for login"
    )
    name = models.CharField(
        max_length=255,
        help_text="User's full name"
    )
    
    # Optional profile fields
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                # Updated regex for better international phone validation
                # Supports Angola (+244), Brazil (+55), Portugal (+351), etc.
                regex=r'^\+(?:[1-9]\d{0,3})?[1-9]\d{8,14}$',
                message="Número de telefone deve estar no formato internacional: '+244912345678' (Angola) ou '+351912345678' (Portugal)."
            )
        ],
        help_text="Número de telefone no formato internacional (ex: +244912345678 para Angola)"
    )
    avatar = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="User's profile picture URL (S3/CloudFront)"
    )
    
    # Role and status
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student',
        help_text="User's role in the system"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user should be treated as active."
    )
    
    # Email verification
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email has been verified"
    )
    email_verification_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Token for email verification"
    )
    
    # Password reset
    reset_password_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Token for password reset"
    )
    reset_password_expires = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the password reset token expires"
    )
    
    # OAuth fields
    google_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Google OAuth user ID"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    
    provincia = models.CharField(
        max_length=20, choices=PROVINCIAS, blank=True, default='',
        help_text='Província de Angola (opcional)',
    )

    # A administração pode obrigar a mudar a palavra-passe: até lá, só change-password/,
    # logout/ e profile/ respondem (ver apps.users.middleware).
    deve_mudar_senha = models.BooleanField(default=False)
    # Tokens de acesso emitidos antes deste instante deixam de valer (sessões terminadas
    # pela administração). Os refresh tokens vão para a lista negra ao mesmo tempo.
    sessoes_invalidas_antes = models.DateTimeField(null=True, blank=True)
    # Email novo pedido pela administração: só passa a ser o email da conta depois de
    # confirmado com o código enviado para ele (EmailVerification finalidade "mudar_email").
    # Até lá, o email, a confirmação e a entrada continuam com o email actual.
    email_pendente = models.EmailField(null=True, blank=True)

    # JSON fields for preferences (using JSONField is better than JSONB reference)
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="User preferences and settings"
    )
    
    # Use email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    # Custom manager
    objects = UserManager()
    
    # Fix related_name conflicts
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='tuwi_users',
        related_query_name='tuwi_user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='tuwi_users',
        related_query_name='tuwi_user',
    )
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['email_verified']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def save(self, *args, **kwargs):
        # Sempre definir username como email para evitar problemas
        if self.email:
            self.username = self.email
        super().save(*args, **kwargs)
    
    @property
    def is_teacher(self):
        """Check if user is a teacher."""
        return self.role == 'teacher'
    
    @property
    def is_student(self):
        """Check if user is a student."""
        return self.role == 'student'
    
    @property
    def is_platform_admin(self):
        """Check if user is a platform admin."""
        return self.role == 'admin'
    
    def get_full_name(self):
        """Return the user's full name."""
        return self.name
    
    def get_short_name(self):
        """Return the user's short name."""
        return self.name.split()[0] if self.name else self.email


class UserAddress(BaseModel):
    """
    User addresses - improved approach vs storing in JSON field.
    
    Benefits:
    - Proper validation
    - Easier querying
    - Better normalization
    - Supports multiple addresses per user
    """
    
    ADDRESS_TYPES = [
        ('billing', 'Billing Address'),
        ('shipping', 'Shipping Address'),
        ('home', 'Home Address'),
        ('work', 'Work Address'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE
    )
    address_type = models.CharField(
        max_length=20,
        choices=ADDRESS_TYPES,
        default='home'
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the user's default address for this type"
    )
    
    class Meta:
        verbose_name = 'User Address'
        verbose_name_plural = 'User Addresses'
        db_table = 'user_addresses'
        unique_together = ['user', 'address_type', 'is_default']
        indexes = [
            models.Index(fields=['user', 'address_type']),
            models.Index(fields=['is_default']),
        ]
        ordering = ['user', 'address_type', '-is_default', 'created_at']
    
    def __str__(self):
        return f"{self.user.name} - {self.get_address_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per type per user
        if self.is_default:
            UserAddress.objects.filter(
                user=self.user,
                address_type=self.address_type,
                is_default=True
            ).update(is_default=False)
        super().save(*args, **kwargs)


class NotificationSettings(BaseModel):
    """
    User notification preferences.
    
    Improvements over original:
    - Better field organization
    - More granular control
    - Proper defaults
    """
    
    DIGEST_FREQUENCY_CHOICES = [
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('never', 'Never'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )
    
    # Email notifications
    email_bookings = models.BooleanField(
        default=True,
        help_text="Receive email notifications for booking updates"
    )
    email_messages = models.BooleanField(
        default=True,
        help_text="Receive email notifications for new messages"
    )
    email_ratings = models.BooleanField(
        default=True,
        help_text="Receive email notifications for new ratings"
    )
    email_orders = models.BooleanField(
        default=True,
        help_text="Receive email notifications for order updates"
    )
    email_marketing = models.BooleanField(
        default=False,
        help_text="Receive marketing emails"
    )
    
    # Push notifications (for future mobile app)
    push_bookings = models.BooleanField(default=True)
    push_messages = models.BooleanField(default=True)
    push_ratings = models.BooleanField(default=True)
    push_orders = models.BooleanField(default=True)
    
    # Digest settings
    digest_frequency = models.CharField(
        max_length=20,
        choices=DIGEST_FREQUENCY_CHOICES,
        default='daily',
        help_text="How often to receive digest emails"
    )
    
    # Quiet hours
    quiet_hours_start = models.TimeField(
        blank=True,
        null=True,
        help_text="Start of quiet hours (no notifications)"
    )
    quiet_hours_end = models.TimeField(
        blank=True,
        null=True,
        help_text="End of quiet hours"
    )
    
    timezone = models.CharField(
        max_length=50,
        default='Europe/Lisbon',
        help_text="User's timezone for notification timing"
    )
    
    class Meta:
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
        db_table = 'notification_settings'
    
    def __str__(self):
        return f"Notification settings for {self.user.name}"


class EmailVerification(BaseModel):
    """
    Email verification codes for new user registration.
    
    Stores verification codes that are sent to users' emails
    during registration to verify email ownership.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verifications'
    )
    code = models.CharField(
        max_length=6,
        help_text="6-digit verification code"
    )
    email = models.EmailField(
        help_text="Email address this verification is for"
    )
    is_used = models.BooleanField(
        default=False,
        help_text="Whether this verification code has been used"
    )
    expires_at = models.DateTimeField(
        help_text="When this verification code expires"
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of verification attempts"
    )
    max_attempts = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of attempts allowed"
    )

    FINALIDADE_VERIFICAR = 'verificar'
    FINALIDADE_RECUPERAR = 'recuperar'
    FINALIDADE_MUDAR_EMAIL = 'mudar_email'
    FINALIDADES = [
        (FINALIDADE_VERIFICAR, 'Confirmar o email'),
        (FINALIDADE_RECUPERAR, 'Recuperar a palavra-passe'),
        (FINALIDADE_MUDAR_EMAIL, 'Confirmar o email novo'),
    ]
    # Um código de recuperar a palavra-passe não serve para confirmar o email, e vice-versa.
    finalidade = models.CharField(
        max_length=12,
        choices=FINALIDADES,
        default=FINALIDADE_VERIFICAR,
        help_text="Para que serve o código"
    )
    
    class Meta:
        verbose_name = 'Email Verification'
        verbose_name_plural = 'Email Verifications'
        db_table = 'email_verifications'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['email']),
            models.Index(fields=['code']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_used']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email verification for {self.email} - {self.code}"
    
    def is_expired(self):
        """Check if the verification code has expired."""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if the verification code is valid (not used, not expired, not max attempts)."""
        return (
            not self.is_used and 
            not self.is_expired() and 
            self.attempts < self.max_attempts
        )
    
    def increment_attempts(self):
        """Increment the number of attempts."""
        self.attempts += 1
        self.save(update_fields=['attempts'])


class UserFeedback(BaseModel):
    """
    User feedback submissions.

    Stores feedback from users about their experience with the platform.
    """

    FEEDBACK_TYPE_CHOICES = [
        ('general', 'General Feedback'),
        ('feature', 'Feature Request'),
        ('bug', 'Bug Report'),
        ('lesson', 'Lesson Feedback'),
        ('ai_tutor', 'AI Tutor Feedback'),
        ('content', 'Content Quality'),
        ('testimonial', 'Testimonial'),
    ]

    TRIGGER_CHOICES = [
        ('first_lesson', 'After First Lesson'),
        ('milestone_lessons', 'Milestone Lessons Completed'),
        ('course_complete', 'Course Completed'),
        ('ai_sessions', 'AI Tutor Sessions'),
        ('days_active', 'Days Active'),
        ('manual', 'User Initiated'),
        ('prompt', 'System Prompt'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )

    # Feedback content
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPE_CHOICES,
        default='general'
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Rating from 1 to 5",
        null=True,
        blank=True
    )
    nps_score = models.PositiveSmallIntegerField(
        help_text="Net Promoter Score (0-10)",
        null=True,
        blank=True
    )
    comment = models.TextField(
        blank=True,
        help_text="User's feedback comment"
    )

    # Context
    trigger = models.CharField(
        max_length=30,
        choices=TRIGGER_CHOICES,
        default='manual',
        help_text="What triggered this feedback request"
    )
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (lessons completed, course, etc.)"
    )

    # Permissions
    allow_public = models.BooleanField(
        default=False,
        help_text="User allows this feedback to be used as testimonial"
    )
    allow_contact = models.BooleanField(
        default=False,
        help_text="User allows follow-up contact"
    )

    # Status
    is_reviewed = models.BooleanField(
        default=False,
        help_text="Whether admin has reviewed this feedback"
    )

    # Revisão pela administração. "aprovada" + allow_public = pode aparecer no site
    # (como testemunho, se `mostrar`, pela ordem de `ordem`).
    POR_REVER = 'por_rever'
    APROVADA = 'aprovada'
    RECUSADA = 'recusada'
    ESTADOS = [(POR_REVER, 'Por rever'), (APROVADA, 'Aprovada'), (RECUSADA, 'Recusada')]
    estado = models.CharField(max_length=10, choices=ESTADOS, default=POR_REVER, db_index=True)
    mostrar = models.BooleanField(default=True, help_text='Testemunho visível no site')
    ordem = models.PositiveIntegerField(default=0, help_text='Ordem no site (menor primeiro)')
    admin_notes = models.TextField(
        blank=True,
        help_text="Admin notes about this feedback"
    )

    class Meta:
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedbacks'
        db_table = 'user_feedbacks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['feedback_type']),
            models.Index(fields=['rating']),
            models.Index(fields=['trigger']),
            models.Index(fields=['allow_public']),
            models.Index(fields=['is_reviewed']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Feedback from {self.user.name} - {self.feedback_type} ({self.rating}/5)"

    def save(self, *args, **kwargs):
        # Compatibilidade: marcar is_reviewed (fluxo antigo) numa opinião por rever aprova-a.
        campos = {'estado', 'is_reviewed'}
        if self.is_reviewed and self.estado == self.POR_REVER:
            self.estado = self.APROVADA
            # Aprovada agora: fica no fim da ordem dos testemunhos.
            m = UserFeedback.objects.filter(estado=self.APROVADA).aggregate(m=models.Max('ordem'))['m']
            self.ordem = (m or 0) + 1
            campos.add('ordem')
        if self.estado != self.POR_REVER:
            self.is_reviewed = True
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = list(set(update_fields) | campos)
        super().save(*args, **kwargs)


class FeedbackPromptLog(BaseModel):
    """
    Tracks when feedback prompts were shown to users.

    Used to prevent showing prompts too frequently and track engagement.
    """

    PROMPT_STATUS_CHOICES = [
        ('shown', 'Prompt Shown'),
        ('dismissed', 'User Dismissed'),
        ('completed', 'Feedback Completed'),
        ('skipped', 'User Skipped'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feedback_prompt_logs'
    )

    trigger = models.CharField(
        max_length=30,
        help_text="What triggered this prompt"
    )
    status = models.CharField(
        max_length=20,
        choices=PROMPT_STATUS_CHOICES,
        default='shown'
    )

    # Related feedback if completed
    feedback = models.ForeignKey(
        UserFeedback,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prompt_logs'
    )

    # Context when prompt was shown
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context when prompt was shown (lessons count, etc.)"
    )

    class Meta:
        verbose_name = 'Feedback Prompt Log'
        verbose_name_plural = 'Feedback Prompt Logs'
        db_table = 'feedback_prompt_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['trigger']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Prompt for {self.user.name} - {self.trigger} ({self.status})"


class UserEngagementMetrics(BaseModel):
    """
    Tracks user engagement metrics for smart feedback triggers.

    Updated automatically as user interacts with the platform.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )

    # Lesson metrics
    total_lessons_completed = models.PositiveIntegerField(default=0)
    total_courses_completed = models.PositiveIntegerField(default=0)

    # AI Tutor metrics
    total_ai_sessions = models.PositiveIntegerField(default=0)
    total_ai_minutes = models.PositiveIntegerField(default=0)

    # Activity metrics
    total_days_active = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)

    # Feedback metrics
    total_feedbacks_given = models.PositiveIntegerField(default=0)
    last_feedback_at = models.DateTimeField(null=True, blank=True)
    last_prompt_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    first_lesson_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'User Engagement Metrics'
        verbose_name_plural = 'User Engagement Metrics'
        db_table = 'user_engagement_metrics'
        indexes = [
            models.Index(fields=['total_lessons_completed']),
            models.Index(fields=['total_ai_sessions']),
            models.Index(fields=['total_days_active']),
            models.Index(fields=['last_feedback_at']),
            models.Index(fields=['last_prompt_at']),
        ]

    def __str__(self):
        return f"Engagement metrics for {self.user.name}"

    def should_show_feedback_prompt(self):
        """
        Determine if user should see a feedback prompt.

        Returns tuple: (should_show, trigger_type)
        """
        from datetime import timedelta

        now = timezone.now()

        # Don't show if gave feedback in last 7 days
        if self.last_feedback_at and (now - self.last_feedback_at) < timedelta(days=7):
            return False, None

        # Don't show if prompt shown in last 3 days
        if self.last_prompt_at and (now - self.last_prompt_at) < timedelta(days=3):
            return False, None

        # Trigger: First lesson completed
        if self.total_lessons_completed == 1 and self.total_feedbacks_given == 0:
            return True, 'first_lesson'

        # Trigger: Milestone lessons (5, 10, 25, 50, 100)
        milestones = [5, 10, 25, 50, 100]
        for milestone in milestones:
            if self.total_lessons_completed == milestone:
                return True, 'milestone_lessons'

        # Trigger: First course completed
        if self.total_courses_completed == 1 and self.total_feedbacks_given == 0:
            return True, 'course_complete'

        # Trigger: AI Tutor usage (5, 10, 20 sessions)
        ai_milestones = [5, 10, 20]
        for milestone in ai_milestones:
            if self.total_ai_sessions == milestone:
                return True, 'ai_sessions'

        # Trigger: Days active (7, 14, 30 days)
        day_milestones = [7, 14, 30]
        for milestone in day_milestones:
            if self.total_days_active == milestone:
                return True, 'days_active'

        return False, None

class Notification(models.Model):
    """
    In-app notification shown in the student's notification centre.

    Generic (not tied to a single app) so achievements, streaks, courses,
    certificates and subscriptions can all publish here.
    """
    KIND_ACHIEVEMENT = 'achievement'
    KIND_STREAK = 'streak'
    KIND_COURSE = 'course'
    KIND_CERTIFICATE = 'certificate'
    KIND_SUBSCRIPTION = 'subscription'
    KIND_SYSTEM = 'system'
    KIND_LEAGUE = 'league'
    KIND_CHOICES = [
        (KIND_ACHIEVEMENT, 'Conquista'),
        (KIND_STREAK, 'Sequência / meta diária'),
        (KIND_LEAGUE, 'Liga'),
        (KIND_COURSE, 'Curso'),
        (KIND_CERTIFICATE, 'Certificado'),
        (KIND_SUBSCRIPTION, 'Subscrição'),
        (KIND_SYSTEM, 'Sistema'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default='')
    link = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # Chave de deduplicação opcional (ex.: "pagamento:<id>", "lembrete-meta:2026-11-13"):
    # o mesmo aviso nunca é criado duas vezes para o mesmo utilizador.
    dedupe_key = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'dedupe_key'],
                condition=models.Q(dedupe_key__isnull=False),
                name='notification_unica_por_dedupe_key',
            ),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.kind}: {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None

    @classmethod
    def notify(cls, user, kind, title, body='', link='', dedupe_key=None,
               push=True, respeitar_preferencias=True):
        """
        Cria um aviso in-app (e envia web push, se disponível) para ``user``.

        Devolve a Notification criada, ou None quando o aviso foi suprimido
        (tipo desligado nas preferências do aluno ou ``dedupe_key`` repetida).
        Nunca falha por causa do push: o envio corre depois do commit.
        """
        from django.db import IntegrityError, transaction

        if respeitar_preferencias and not PreferenciasAvisos.tipo_ligado(user, kind):
            return None
        if dedupe_key and cls.objects.filter(user=user, dedupe_key=dedupe_key).exists():
            return None
        try:
            with transaction.atomic():  # savepoint: não estraga a transação do chamador
                notification = cls.objects.create(
                    user=user, kind=kind, title=title[:200], body=body or '',
                    link=link or '', dedupe_key=dedupe_key or None,
                )
        except IntegrityError:
            return None  # outra execução criou o mesmo aviso em paralelo
        if push:
            from .push import agendar_push
            agendar_push(user, notification)
        return notification


class PreferenciasAvisos(models.Model):
    """
    Preferências de avisos do aluno (GET/PATCH /api/v1/users/avisos/).

    Os avisos de subscrição (renovação, fim do plano, recibos) são mensagens de
    serviço e não se podem desligar.
    """
    HORA_LEMBRETE_PADRAO = '19:00'

    # tipo de Notification -> campo de preferência (None = sempre ligado)
    CAMPO_POR_TIPO = {
        'streak': 'meta',
        'achievement': 'liga',
        'league': 'liga',
        'certificate': 'certificados',
        'course': 'cursos',
        'subscription': None,
        'system': None,
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferencias_avisos')
    meta = models.BooleanField(default=True, help_text='Meta diária e sequência')
    liga = models.BooleanField(default=True, help_text='Liga semanal e conquistas')
    certificados = models.BooleanField(default=True)
    cursos = models.BooleanField(default=True, help_text='Novos capítulos nos cursos em que está inscrito')
    lembrete_ligado = models.BooleanField(default=False, help_text='Lembrete diário da meta')
    lembrete_hora = models.TimeField(default=datetime.time(19, 0), help_text='Hora de Angola (Africa/Luanda)')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preferências de avisos'
        verbose_name_plural = 'Preferências de avisos'
        indexes = [models.Index(fields=['lembrete_ligado', 'lembrete_hora'])]

    def __str__(self):
        return f'Avisos de {self.user_id}'

    @classmethod
    def tipo_ligado(cls, user, kind):
        campo = cls.CAMPO_POR_TIPO.get(kind)
        if campo is None:
            return True
        prefs = cls.objects.filter(user=user).only(campo).first()
        return True if prefs is None else bool(getattr(prefs, campo))


class PushSubscription(models.Model):
    """Subscrição Web Push de um navegador (POST/DELETE /api/v1/users/avisos/push/)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Push {self.user_id} ({self.endpoint[:40]}...)'


class PerfilProfessor(BaseModel):
    """
    O que os alunos vêem do professor na página de cada curso seu.
    A fotografia fica em User.avatar e o nome em User.name.
    """

    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='perfil_professor',
    )
    cidade = models.CharField(max_length=80, blank=True, default='')
    especialidade = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Uma linha, p. ex. "Inglês técnico para Petróleo e Gás".',
    )
    experiencia = models.CharField(
        max_length=160, blank=True, default='',
        help_text='Uma linha, p. ex. "12 anos como intérprete em plataformas".',
    )
    sobre = models.TextField(max_length=800, blank=True, default='')
    # Professor de confiança: os cursos dele publicam-se sem passar pela revisão
    # (aplicado em apps.courses; marcado pela administração ou pelo convite).
    publica_sem_revisao = models.BooleanField(default=False)

    class Meta:
        db_table = 'users_perfil_professor'
        verbose_name = 'Perfil de professor'
        verbose_name_plural = 'Perfis de professor'

    def __str__(self):
        return f'Perfil de {self.user}'


# ---------------------------------------------------------------------------
# Administração: registo de acções, suspensões e convites de professor
# ---------------------------------------------------------------------------

class RegistoAdmin(models.Model):
    """Registo (auditoria) de cada alteração feita pela administração."""

    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    accao = models.CharField(max_length=40, db_index=True)
    alvo_tipo = models.CharField(max_length=30, blank=True, default='')
    alvo_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    detalhes = models.JSONField(default=dict, blank=True)
    ip = models.CharField(max_length=45, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Registo da administração'
        verbose_name_plural = 'Registos da administração'
        indexes = [models.Index(fields=['alvo_tipo', 'alvo_id'])]

    def __str__(self):
        return f'{self.criado_em:%Y-%m-%d %H:%M} {self.autor_id} {self.accao} {self.alvo_tipo}:{self.alvo_id}'


class SuspensaoConta(models.Model):
    """
    Suspensão de uma conta pela administração (User.is_active=False enquanto durar).

    Se o utilizador tinha um plano pago em vigor, a subscrição fica "em pausa": guarda-se o
    plano e o tempo que faltava; ao reactivar, o fim do plano passa para agora + esse tempo.
    """

    MOTIVOS = [
        ('pagamento_contestado', 'Pagamento contestado'),
        ('partilha_conta', 'Partilha de conta'),
        ('abusivo', 'Comportamento abusivo'),
        ('pedido_proprio', 'A pedido do próprio'),
        ('outro', 'Outro motivo'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suspensoes')
    motivo = models.CharField(max_length=30, choices=MOTIVOS)
    nota = models.TextField(blank=True, default='', max_length=2000)
    por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    desde = models.DateTimeField(default=timezone.now)
    avisado = models.BooleanField(default=False)
    # Subscrição em pausa
    plano_pausado = models.CharField(max_length=20, blank=True, default='')
    segundos_restantes = models.PositiveIntegerField(default=0)
    # Fim da suspensão (reactivação)
    terminada_em = models.DateTimeField(null=True, blank=True)
    terminada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['-desde']
        verbose_name = 'Suspensão de conta'
        verbose_name_plural = 'Suspensões de conta'

    def __str__(self):
        return f'{self.user_id} {self.motivo} ({self.desde:%Y-%m-%d})'


class ConviteProfessor(models.Model):
    """
    Convite para um professor criar conta. O token só vai no email: guarda-se o SHA-256.
    Estado "expirado" é calculado (pendente com expira_em no passado).
    """

    PENDENTE = 'pendente'
    ACEITE = 'aceite'
    CANCELADO = 'cancelado'
    EXPIRADO = 'expirado'
    ESTADOS = [(PENDENTE, 'Pendente'), (ACEITE, 'Aceite'), (CANCELADO, 'Cancelado')]
    VALIDADE = datetime.timedelta(days=7)

    email = models.EmailField()
    nome = models.CharField(max_length=255)
    area = models.CharField(max_length=120, blank=True, default='')
    publica_sem_revisao = models.BooleanField(default=False)
    token_hash = models.CharField(max_length=64, unique=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDENTE, db_index=True)
    enviado_em = models.DateTimeField(default=timezone.now)
    expira_em = models.DateTimeField()
    aceite_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    utilizador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='convite_professor')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enviado_em']
        verbose_name = 'Convite de professor'
        verbose_name_plural = 'Convites de professor'
        indexes = [models.Index(fields=['email'])]

    def __str__(self):
        return f'Convite {self.email} ({self.estado})'

    @property
    def estado_actual(self):
        if self.estado == self.PENDENTE and self.expira_em <= timezone.now():
            return self.EXPIRADO
        return self.estado
