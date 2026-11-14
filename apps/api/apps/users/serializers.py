"""
Serializers for user models and authentication.
"""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.utils import timezone
from django.conf import settings
from .models import User, UserAddress, NotificationSettings, UserFeedback, FeedbackPromptLog, UserEngagementMetrics
from apps.core.models import Address
from apps.courses import niveis


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        required=False
    )
    
    class Meta:
        model = User
        # Sem 'role': quem se regista é sempre aluno. Professores e administradores são
        # criados pela equipa (qualquer 'role' enviado pelo cliente é ignorado).
        fields = [
            'email', 'name', 'password', 'password_confirm',
            'phone',
        ]
        # A unicidade do email é verificada em validate_email (sem distinguir maiúsculas e com
        # mensagem própria), não pelo validador do modelo ("Já existe um registo...").
        extra_kwargs = {'email': {'validators': []}}

    def validate_email(self, value):
        email = (value or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('Já existe uma conta com este email.')
        return email

    def validate(self, attrs):
        # Se password_confirm foi enviado, as duas palavras-passe têm de ser iguais
        if 'password_confirm' in attrs and attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'As duas palavras-passe não são iguais.'})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm', None)  # Remove se existir
        password = validated_data.pop('password')
        
        validated_data.pop('role', None)
        user = User.objects.create_user(
            password=password,
            role='student',
            **validated_data
        )
        return user


CONTA_SUSPENSA = 'A sua conta está suspensa. Fale com a equipa ProEnglish.'


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer with additional user data.
    """
    
    def validate(self, attrs):
        # Check for empty credentials first and raise AuthenticationFailed
        email = attrs.get('email', '').strip()
        password = attrs.get('password', '')
        
        if not email or not password:
            raise AuthenticationFailed(
                "Indique o email e a palavra-passe."
            )
        
        # O email não distingue maiúsculas: usa-se o email tal como está guardado.
        guardado = User.objects.filter(email__iexact=email).values_list('email', flat=True).first()
        attrs['email'] = guardado or email.lower()

        try:
            # Use parent validate() which handles authentication
            data = super().validate(attrs)
        except Exception:
            # Conta suspensa: só se diz quando a palavra-passe está certa (senão, revelava-se
            # que a conta existe e está suspensa a quem não a conhece). O limite de tentativas
            # por IP da vista de login aplica-se na mesma.
            suspensa = User.objects.filter(email__iexact=attrs['email'], is_active=False).first()
            if suspensa is not None and suspensa.has_usable_password() and suspensa.check_password(password):
                raise AuthenticationFailed(CONTA_SUSPENSA, code='conta_suspensa')
            # Convert any validation error to AuthenticationFailed for 401 status
            raise AuthenticationFailed(
                "O email ou a palavra-passe não estão certos."
            )
        
        # Check if email is verified
        user = self.user
        if not user.email_verified:
            raise AuthenticationFailed(
                "Ainda não confirmou o seu email. Use o código que lhe enviámos antes de entrar."
            )
        
        # Add user data to token response
        data['user'] = {
            'id': str(user.id),
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'avatar': user.avatar or None,  # avatar is now a URLField, not ImageField
            'email_verified': user.email_verified,
            'has_password': user.has_usable_password(),
            'deve_mudar_senha': user.deve_mudar_senha,
        }
        
        # Update last login
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        return data
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to token
        token['user_id'] = str(user.id)
        token['email'] = user.email
        token['role'] = user.role
        token['name'] = user.name
        # Mesma regra que apps.core.permissions.e_administrador (papel admin ou superutilizador),
        # para o site (proxy) decidir o acesso a /admin como a API.
        token['administrador'] = bool(user.role == 'admin' or user.is_superuser)

        return token


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile management.
    Avatar field now stores S3/CloudFront URLs directly.
    """

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'phone', 'avatar',
            'role', 'email_verified', 'has_password', 'preferences', 'created_at',
            'provincia', 'deve_mudar_senha',
        ]
        read_only_fields = ['id', 'email', 'role', 'email_verified', 'has_password', 'created_at',
                            'deve_mudar_senha']

    # Província de Angola (slug de GET /api/v1/users/provincias/); null ou "" apaga.
    provincia = serializers.ChoiceField(
        choices=User._meta.get_field('provincia').choices, required=False, allow_blank=True, allow_null=True,
        error_messages={'invalid_choice': 'Província desconhecida.'},
    )

    def validate_provincia(self, value):
        return value or ''

    def to_representation(self, instance):
        dados = super().to_representation(instance)
        dados['provincia'] = dados.get('provincia') or None
        # Contas com o nível na escala antiga (Beginner/...) lêem-no já em CEFR.
        prefs = dados.get('preferences')
        if isinstance(prefs, dict) and prefs.get('nivel'):
            dados['preferences'] = {**prefs, 'nivel': niveis.normalizar(prefs['nivel']) or prefs['nivel']}
        return dados

    # false nas contas criadas com o Google que ainda não definiram palavra-passe: nesse caso
    # change-password/ define a primeira (sem current_password) e apagar-conta/ pede
    # {"confirmar": true} em vez da palavra-passe.
    has_password = serializers.SerializerMethodField()

    def get_has_password(self, obj):
        return obj.has_usable_password()

    # Preferências que a área do estudante guarda; outras chaves são recusadas.
    PREFERENCIAS = {
        'cidade': 80,
        'area': 60,
        # Escala CEFR (apps/courses/niveis.py).
        'nivel': niveis.CEFR,
        # Marca o fim da primeira entrada (área, meta e nível escolhidos).
        'acolhimento': ('concluido',),
    }

    def validate_name(self, value):
        value = (value or '').strip()
        if len(value) < 2:
            raise serializers.ValidationError('Escreva o seu nome.')
        return value

    def validate_phone(self, value):
        if not value:
            return value
        compacto = value.replace(' ', '')
        # Números estrangeiros (+351, +55...) ficam como estão: o validador do modelo trata deles.
        if compacto.startswith('+') and not compacto.startswith('+244'):
            return compacto
        from apps.pagamentos.telefone import normalizar_telefone, TelefoneInvalido
        try:
            return f'+244{normalizar_telefone(value)}'
        except TelefoneInvalido as e:
            raise serializers.ValidationError(str(e))

    def validate_preferences(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Preferências inválidas.')
        desconhecidas = set(value) - set(self.PREFERENCIAS)
        if desconhecidas:
            raise serializers.ValidationError(f'Preferência desconhecida: {", ".join(sorted(desconhecidas))}.')
        limpas = {}
        for chave, regra in self.PREFERENCIAS.items():
            if chave not in value:
                continue
            v = value[chave]
            if v in (None, ''):
                limpas[chave] = None
            elif isinstance(regra, tuple):
                if v not in regra:
                    raise serializers.ValidationError(f'Valor inválido para {chave}.')
                limpas[chave] = v
            else:
                if not isinstance(v, str) or len(v.strip()) > regra:
                    raise serializers.ValidationError(f'Valor inválido para {chave}.')
                limpas[chave] = v.strip()
        # Junta às preferências que já existem (só muda as chaves enviadas).
        actuais = dict(getattr(self.instance, 'preferences', None) or {})
        actuais.update(limpas)
        return {k: v for k, v in actuais.items() if v is not None}


class PasswordChangeSerializer(serializers.Serializer):
    """
    Mudar a palavra-passe (com current_password) ou, se a conta ainda não tem nenhuma
    (criada com o Google), definir a primeira (current_password não é pedido).
    """
    current_password = serializers.CharField(
        required=False,
        allow_blank=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        user = self.context['request'].user
        if user.has_usable_password():
            actual = attrs.get('current_password') or ''
            if not actual:
                raise serializers.ValidationError({'current_password': 'Escreva a palavra-passe actual.'})
            if not user.check_password(actual):
                raise serializers.ValidationError({'current_password': 'A palavra-passe actual não está certa.'})
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "As duas palavras-passe novas não são iguais."})
        from django.core.exceptions import ValidationError as ErroDjango
        try:
            validate_password(attrs['new_password'], user=user)  # também compara com o nome/email
        except ErroDjango as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        return attrs
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class AddressSerializer(serializers.ModelSerializer):
    """
    Serializer for Address model.
    """
    
    class Meta:
        model = Address
        fields = [
            'id', 'street', 'city', 'postal_code', 'district', 'country',
            'building_number', 'apartment', 'floor', 'additional_info',
            'full_address'
        ]
        read_only_fields = ['id', 'full_address']


class UserAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for UserAddress model.
    """
    address = AddressSerializer()
    
    class Meta:
        model = UserAddress
        fields = [
            'id', 'address', 'address_type', 'is_default', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def create(self, validated_data):
        address_data = validated_data.pop('address')
        address = Address.objects.create(**address_data)
        user_address = UserAddress.objects.create(
            address=address,
            user=self.context['request'].user,
            **validated_data
        )
        return user_address


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationSettings model.
    """
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id', 'email_bookings', 'email_messages', 'email_ratings',
            'email_orders', 'email_marketing', 'push_bookings',
            'push_messages', 'push_ratings', 'push_orders',
            'digest_frequency', 'quiet_hours_start', 'quiet_hours_end',
            'timezone'
        ]
        read_only_fields = ['id']


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    Note: Email validation is handled in the view to not reveal if email exists.
    """
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.
    """
    token = serializers.CharField()
    new_password = serializers.CharField(
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'As duas palavras-passe não são iguais.'})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification.
    """
    token = serializers.CharField()


class GoogleOAuthSerializer(serializers.Serializer):
    """
    Entrada com o Google: `code` (devolvido pelo Google ao endereço de volta) e, se existir,
    o `state` que veio no mesmo endereço. Também aceita um `id_token` emitido para o nosso
    client id. `access_token` é recusado.
    """
    code = serializers.CharField(required=False, max_length=2048)
    id_token = serializers.CharField(required=False, max_length=4096)
    state = serializers.CharField(required=False, allow_blank=True, max_length=512)
    access_token = serializers.CharField(required=False)

    def validate(self, attrs):
        if attrs.get('access_token'):
            raise serializers.ValidationError('Pedido inválido para entrar com o Google.')
        if not attrs.get('code') and not attrs.get('id_token'):
            raise serializers.ValidationError('Falta a autorização do Google.')
        attrs.pop('access_token', None)
        if not attrs.get('state'):
            attrs.pop('state', None)
        return attrs


class GoogleOAuthURLSerializer(serializers.Serializer):
    """
    Serializer for Google OAuth URL generation.
    """
    redirect_uri = serializers.URLField(
        required=False,
        help_text="Custom redirect URI (optional)"
    )
    state = serializers.CharField(
        required=False,
        help_text="State parameter for OAuth flow"
    )


class SocialUserInfoSerializer(serializers.Serializer):
    """
    Serializer for social user information from OAuth providers.
    """
    id = serializers.CharField()
    email = serializers.EmailField()
    name = serializers.CharField()
    given_name = serializers.CharField(required=False)
    family_name = serializers.CharField(required=False)
    picture = serializers.URLField(required=False)
    locale = serializers.CharField(required=False)
    verified_email = serializers.BooleanField(required=False)


# ============================================================================
# FEEDBACK SERIALIZERS
# ============================================================================

class UserFeedbackSerializer(serializers.ModelSerializer):
    """
    Serializer for user feedback submissions.
    """
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = UserFeedback
        fields = [
            'id', 'user', 'user_name', 'feedback_type', 'rating', 'nps_score',
            'comment', 'trigger', 'context_data', 'allow_public', 'allow_contact',
            'is_reviewed', 'admin_notes', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'user_name', 'created_at']


class MinhaOpiniaoSerializer(serializers.ModelSerializer):
    """A opinião vista pelo próprio aluno: sem as notas internas da equipa (admin_notes,
    is_reviewed)."""

    class Meta:
        model = UserFeedback
        fields = [
            'id', 'feedback_type', 'rating', 'nps_score', 'comment', 'trigger',
            'allow_public', 'allow_contact', 'created_at'
        ]
        read_only_fields = fields


class SubmitFeedbackSerializer(serializers.Serializer):
    """
    Serializer for submitting feedback.
    """
    feedback_type = serializers.ChoiceField(
        choices=UserFeedback.FEEDBACK_TYPE_CHOICES,
        default='general'
    )
    rating = serializers.IntegerField(
        min_value=1, max_value=5,
        required=False,
        allow_null=True
    )
    nps_score = serializers.IntegerField(
        min_value=0, max_value=10,
        required=False,
        allow_null=True
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000
    )
    trigger = serializers.ChoiceField(
        choices=UserFeedback.TRIGGER_CHOICES,
        default='manual'
    )
    context_data = serializers.JSONField(
        required=False,
        default=dict
    )
    allow_public = serializers.BooleanField(default=False)
    allow_contact = serializers.BooleanField(default=False)

    def validate(self, attrs):
        # Require at least rating or comment
        if not attrs.get('rating') and not attrs.get('comment') and not attrs.get('nps_score'):
            raise serializers.ValidationError(
                "Escolha uma nota ou escreva um comentário."
            )
        return attrs


class FeedbackPromptLogSerializer(serializers.ModelSerializer):
    """
    Serializer for feedback prompt logs.
    """
    class Meta:
        model = FeedbackPromptLog
        fields = [
            'id', 'user', 'trigger', 'status', 'feedback', 'context_data', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class UserEngagementMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for user engagement metrics.
    """
    should_show_prompt = serializers.SerializerMethodField()
    prompt_trigger = serializers.SerializerMethodField()

    class Meta:
        model = UserEngagementMetrics
        fields = [
            'total_lessons_completed', 'total_courses_completed',
            'total_ai_sessions', 'total_ai_minutes',
            'total_days_active', 'current_streak', 'longest_streak',
            'total_feedbacks_given', 'last_feedback_at', 'last_prompt_at',
            'first_lesson_at', 'last_activity_at',
            'should_show_prompt', 'prompt_trigger'
        ]

    def get_should_show_prompt(self, obj):
        should_show, _ = obj.should_show_feedback_prompt()
        return should_show

    def get_prompt_trigger(self, obj):
        _, trigger = obj.should_show_feedback_prompt()
        return trigger


class FeedbackStatusSerializer(serializers.Serializer):
    """
    Serializer for checking feedback prompt status.
    """
    should_show_prompt = serializers.BooleanField()
    trigger = serializers.CharField(allow_null=True)
    last_feedback_at = serializers.DateTimeField(allow_null=True)
    total_feedbacks_given = serializers.IntegerField()
    engagement_summary = serializers.DictField()