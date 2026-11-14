"""
Subscription Serializers - API data serialization

Este módulo fornece serializers DRF para o sistema de assinaturas,
lidando com serialização de dados para comunicação frontend-backend.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .limites import limite_conversa_efetivo
from .models import (
    SubscriptionPlan,
    UserSubscription,
    SubscriptionHistory,
    PromotionalCode,
    PromoCodeUsage
)

User = get_user_model()


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer para Planos de Assinatura
    """
    yearly_discount_percentage = serializers.ReadOnlyField(source='get_yearly_discount_percentage')
    is_most_popular = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    pode_experimentar = serializers.SerializerMethodField()
    so_renovacao = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name', 
            'plan_type',
            'description',
            'monthly_price',
            'yearly_price',
            'yearly_discount_percentage',
            'is_most_popular',
            'destaque',
            'dias_teste',
            'pode_experimentar',
            # Plano desactivado que quem pede ainda tem (só pode renovar/converter, não é para novos)
            'so_renovacao',
            'features',
            # Limitações
            'daily_lessons_limit',
            'daily_speaking_minutes',
            'daily_listening_minutes',
            'hearts_limit',
            'hearts_recharge_hours',
            # Recursos premium
            'offline_downloads',
            'certificates',
            'ai_tutor',
            'native_teacher_sessions',
            'advanced_analytics',
            'priority_support',
            'streak_freeze',
            'multiple_devices',
            'sort_order',
            'is_active'
        ]
        
    def get_is_most_popular(self, obj):
        """O plano em destaque (escolhido na administração; só um de cada vez)."""
        return obj.destaque

    def get_so_renovacao(self, obj):
        return not obj.is_active and obj.plan_type != 'FREE'

    def get_pode_experimentar(self, obj):
        """
        Se quem pede pode começar o teste grátis deste plano. Sem sessão: True se o plano
        tem teste (uma conta nova pode experimentar).
        """
        if obj.plan_type == 'FREE' or not obj.dias_teste or not obj.is_active:
            return False
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return True
        cache = self.context.setdefault('_teste', {})
        if 'historico' not in cache:
            from apps.pagamentos.teste import historico_teste
            cache['historico'] = historico_teste(user)
            cache['sub'] = UserSubscription.objects.filter(user=user).select_related('plan').first()
        from apps.pagamentos.teste import motivo_sem_teste
        return motivo_sem_teste(user, obj, cache['sub'], _historico=cache['historico']) is None
    
    def get_features(self, obj):
        """Vantagens do plano em pt-PT, geradas a partir dos limites reais do plano."""
        features = []
        if obj.daily_lessons_limit:
            features.append(f"{obj.daily_lessons_limit} lições por dia")
        else:
            features.append("Lições ilimitadas")
        if obj.daily_speaking_minutes:
            features.append(f"{obj.daily_speaking_minutes} minutos de conversa com o tutor por dia")
        elif obj.daily_speaking_minutes is None:
            features.append("Conversa com o tutor sem limite diário")
        if obj.hearts_limit and obj.hearts_limit > 0:
            features.append(f"{obj.hearts_limit} vidas, que recuperam com o tempo")
        else:
            features.append("Vidas ilimitadas")
        if obj.plan_type == 'FREE':
            features.append("Cursos gratuitos")
        elif obj.plan_type == 'PREMIUM':
            features.append("Cursos gratuitos e Premium")
        else:
            features.append("Todos os cursos, incluindo os Premium Plus")
        if obj.certificates:
            features.append("Certificados de conclusão")
        if obj.advanced_analytics:
            features.append("Estatísticas detalhadas do progresso")
        if obj.priority_support:
            features.append("Apoio prioritário")
        return features


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer para Assinatura do Utilizador
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    days_until_expiry = serializers.ReadOnlyField()
    is_active_subscription = serializers.ReadOnlyField(source='is_active')
    is_trial_subscription = serializers.ReadOnlyField(source='is_trial')
    
    # Usage stats
    daily_usage = serializers.SerializerMethodField()
    hearts_status = serializers.SerializerMethodField()

    termina_em = serializers.SerializerMethodField()
    termina_hoje = serializers.SerializerMethodField()
    pode_renovar = serializers.SerializerMethodField()
    renovavel_a_partir_de = serializers.SerializerMethodField()
    periodo = serializers.SerializerMethodField()
    valor_periodo_kz = serializers.SerializerMethodField()
    em_teste = serializers.SerializerMethodField()
    teste_termina_em = serializers.SerializerMethodField()
    pode_experimentar = serializers.SerializerMethodField()
    dias_teste = serializers.SerializerMethodField()
    plano_teste = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id',
            'user_name',
            'user_email',
            'plan',
            'status',
            'started_at',
            'expires_at',
            'canceled_at',
            'trial_ends_at',
            'days_until_expiry',
            'is_active_subscription',
            'is_trial_subscription',
            'daily_usage',
            'hearts_status',
            'last_payment_at',
            'next_billing_date',
            'lembretes_renovacao',
            # Renovação manual (Multicaixa Express): valores calculados no servidor
            'termina_em',
            'termina_hoje',
            'pode_renovar',
            'renovavel_a_partir_de',
            'periodo',
            'valor_periodo_kz',
            # Teste grátis de um plano pago
            'em_teste',
            'teste_termina_em',
            'pode_experimentar',
            'dias_teste',
            'plano_teste',
        ]
        read_only_fields = [
            'id', 'started_at',
            'last_payment_at', 'next_billing_date', 'lembretes_renovacao'
        ]

    def _renovacao(self, obj):
        cache = getattr(self, '_cache_renovacao', None)
        if cache is None:
            cache = self._cache_renovacao = {}
        if obj.pk not in cache:
            from apps.pagamentos.services import periodo_atual
            cache[obj.pk] = periodo_atual(obj)
        return cache[obj.pk]

    def _teste(self, obj):
        cache = getattr(self, '_cache_teste', None)
        if cache is None:
            cache = self._cache_teste = {}
        if obj.pk not in cache:
            from apps.pagamentos.teste import estado_teste
            cache[obj.pk] = estado_teste(obj.user, None, sub=obj)
        return cache[obj.pk]

    def get_em_teste(self, obj):
        return self._teste(obj)['em_teste']

    def get_teste_termina_em(self, obj):
        return self._teste(obj)['teste_termina_em']

    def get_pode_experimentar(self, obj):
        return self._teste(obj)['pode_experimentar']

    def get_dias_teste(self, obj):
        return self._teste(obj)['dias_teste']

    def get_plano_teste(self, obj):
        return self._teste(obj)['plano_teste']

    def get_termina_em(self, obj):
        if obj.plan.plan_type == 'FREE' or not obj.expires_at:
            return None
        return obj.expires_at.isoformat()

    def get_termina_hoje(self, obj):
        from .services import termina_hoje
        return termina_hoje(obj)

    def get_pode_renovar(self, obj):
        from .services import pode_renovar
        return pode_renovar(obj)

    def get_renovavel_a_partir_de(self, obj):
        from .services import renovavel_a_partir_de
        quando = renovavel_a_partir_de(obj)
        return quando.isoformat() if quando else None

    def get_periodo(self, obj):
        return self._renovacao(obj)['periodo']

    def get_valor_periodo_kz(self, obj):
        return self._renovacao(obj)['valor_periodo_kz']
    
    def get_daily_usage(self, obj):
        """Retorna uso diário atual"""
        obj.reset_daily_usage_if_needed()
        return {
            'lessons_used': obj.daily_lessons_used,
            'lessons_limit': obj.plan.daily_lessons_limit,
            'speaking_minutes_used': obj.daily_speaking_minutes_used,
            'speaking_limit': limite_conversa_efetivo(obj),
            'listening_minutes_used': obj.daily_listening_minutes_used,
            'listening_limit': obj.plan.daily_listening_minutes,
            'can_take_lesson': obj.can_take_lesson(),
            'can_use_speaking': obj.can_use_speaking(),
            'can_use_listening': obj.can_use_listening()
        }
    
    def get_hearts_status(self, obj):
        """Retorna status das vidas"""
        obj.recharge_hearts_if_needed()
        return {
            'current_hearts': obj.current_hearts,
            'max_hearts': obj.plan.hearts_limit,
            'is_unlimited': obj.plan.hearts_limit == 0,
            'next_recharge': obj.last_heart_recharge,
            'recharge_hours': obj.plan.hearts_recharge_hours
        }


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """
    Serializer para Histórico de Assinatura
    """
    user_name = serializers.CharField(source='subscription.user.username', read_only=True)
    previous_plan_name = serializers.CharField(source='previous_plan.name', read_only=True)
    new_plan_name = serializers.CharField(source='new_plan.name', read_only=True)
    
    class Meta:
        model = SubscriptionHistory
        fields = [
            'id',
            'user_name',
            'event_type',
            'previous_plan_name',
            'new_plan_name',
            'amount_paid',
            'notes',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PromotionalCodeSerializer(serializers.ModelSerializer):
    """
    Serializer para Códigos Promocionais
    """
    applicable_plan_names = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()
    is_valid_now = serializers.ReadOnlyField(source='is_valid')
    
    class Meta:
        model = PromotionalCode
        fields = [
            'id',
            'code',
            'name', 
            'description',
            'discount_type',
            'discount_value',
            'max_uses',
            'current_uses',
            'usage_stats',
            'valid_from',
            'valid_until',
            'applicable_plan_names',
            'first_time_users_only',
            'is_active',
            'is_valid_now'
        ]
    
    def validate(self, data):
        """Mesmas regras do modelo (PromotionalCode.clean): valores e tipo suportado."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        instancia = PromotionalCode(**{
            campo: data.get(campo, getattr(self.instance, campo, None))
            for campo in ('discount_type', 'discount_value', 'max_uses', 'valid_from', 'valid_until')
        })
        try:
            instancia.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        if 'code' in data and data['code']:
            data['code'] = data['code'].strip().upper()
        return data

    @staticmethod
    def _estado(validated_data):
        # is_active é espelho de estado (PromotionalCode.save): traduzir para estado
        if 'is_active' in validated_data:
            validated_data['estado'] = (PromotionalCode.ACTIVO if validated_data.pop('is_active')
                                        else PromotionalCode.DESLIGADO)
        return validated_data

    def create(self, validated_data):
        return super().create(self._estado(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._estado(validated_data))

    def get_applicable_plan_names(self, obj):
        """Retorna nomes dos planos aplicáveis"""
        if not obj.applicable_plans.exists():
            return ["Todos os planos"]
        return [plan.name for plan in obj.applicable_plans.all()]
    
    def get_usage_stats(self, obj):
        """Retorna estatísticas de uso"""
        if not obj.max_uses:
            return {'used': obj.current_uses, 'remaining': None, 'usage_percentage': 0}
        return {
            'used': obj.current_uses,
            'remaining': obj.max_uses - obj.current_uses,
            'usage_percentage': (obj.current_uses / obj.max_uses * 100) if obj.max_uses > 0 else 0
        }


class PromoCodeUsageSerializer(serializers.ModelSerializer):
    """
    Serializer para Uso de Código Promocional
    """
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    promo_code_name = serializers.CharField(source='promo_code.code', read_only=True)
    
    class Meta:
        model = PromoCodeUsage
        fields = [
            'id',
            'user_name',
            'user_email',
            'promo_code_name',
            'discount_applied',
            'used_at'
        ]
        read_only_fields = ['id', 'used_at']


# Serializers específicos para operações

class SubscriptionUpgradeSerializer(serializers.Serializer):
    """
    Serializer para upgrade/downgrade de plano
    """
    plan_id = serializers.UUIDField()
    billing_cycle = serializers.ChoiceField(choices=['MONTHLY', 'YEARLY'], default='MONTHLY')
    promo_code = serializers.CharField(required=False, allow_blank=True)
    
    # Validation moved to view to return proper 404 status code


class ApplyPromoCodeSerializer(serializers.Serializer):
    """
    Serializer para aplicar código promocional
    """
    promo_code = serializers.CharField(max_length=50)
    plan_id = serializers.UUIDField()
    
    def validate_promo_code(self, value):
        """Valida se o código promocional existe e é válido"""
        try:
            promo = PromotionalCode.objects.get(code=value.upper())
            if not promo.is_valid():
                raise serializers.ValidationError("Código promocional expirado ou esgotado.")
            return value.upper()
        except PromotionalCode.DoesNotExist:
            raise serializers.ValidationError("Código promocional não encontrado.")

    def validate(self, data):
        """Validação cruzada entre código e plano"""
        promo_code = data.get('promo_code')
        plan_id = data.get('plan_id')
        
        if promo_code and plan_id:
            try:
                promo = PromotionalCode.objects.get(code=promo_code)
                plan = SubscriptionPlan.objects.get(id=plan_id)
                
                # Verificar se o código é aplicável ao plano
                if promo.applicable_plans.exists() and plan not in promo.applicable_plans.all():
                    raise serializers.ValidationError({
                        'promo_code': 'Este código não é válido para o plano escolhido.'
                    })
                    
            except (PromotionalCode.DoesNotExist, SubscriptionPlan.DoesNotExist):
                pass  # Já validado acima
                
        return data


class SubscriptionStatsSerializer(serializers.Serializer):
    """
    Serializer para estatísticas de assinatura (admin dashboard)
    """
    total_subscribers = serializers.IntegerField()
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    conversion_rate = serializers.FloatField()
    churn_rate = serializers.FloatField()
    free_users = serializers.IntegerField()
    premium_users = serializers.IntegerField()
    premium_plus_users = serializers.IntegerField()
    active_promo_codes = serializers.IntegerField()
    recent_subscriptions = UserSubscriptionSerializer(many=True)
    revenue_chart = serializers.DictField()  # Dados para gráfico de receita