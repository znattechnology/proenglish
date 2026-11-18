"""
Subscription Models - Sistema de assinaturas e planos

Este módulo define modelos para gerenciar assinaturas mensais,
planos (Free, Premium, Premium+) e limitações por tipo de usuário.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone


def get_current_date():
    """Helper function to get current date for default values"""
    return timezone.now().date()


class SubscriptionPlan(models.Model):
    """
    Plano de Assinatura - Define os diferentes tipos de planos disponíveis
    
    Exemplos: Free, Premium, Premium+
    """
    
    PLAN_TYPES = [
        ('FREE', 'Gratuito'),
        ('PREMIUM', 'Premium'),
        ('PREMIUM_PLUS', 'Premium Plus'),
    ]
    
    BILLING_CYCLES = [
        ('MONTHLY', 'Mensal'),
        ('YEARLY', 'Anual'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    description = models.TextField()
    
    # Preços em Kuanzas (AOA)
    monthly_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Preço mensal em Kuanzas (AOA)"
    )
    yearly_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Preço anual em Kuanzas (AOA) - com desconto"
    )
    
    # Limitações do plano
    daily_lessons_limit = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Limite diário de lições (null = ilimitado)"
    )
    daily_speaking_minutes = models.IntegerField(
        null=True,
        blank=True, 
        help_text="Minutos diários de Speaking Practice (null = ilimitado)"
    )
    daily_listening_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minutos diários de Listening Practice (null = ilimitado)"
    )
    daily_ai_analyses_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text="Limite diário de análises AI de pronúncia (null = ilimitado)"
    )
    # Avaliações de pronúncia detalhadas (fornecedor pago, p.ex. Azure: nota por palavra e por som).
    # Acima do limite (ou com o fornecedor desligado) a avaliação é a normal, pelo texto.
    daily_detailed_pronunciation_limit = models.PositiveIntegerField(
        default=0,
        help_text="Avaliações de pronúncia detalhadas por dia (0 = nenhuma)"
    )
    hearts_limit = models.IntegerField(
        default=5,
        help_text="Número máximo de vidas (0 = ilimitado)"
    )
    hearts_recharge_hours = models.IntegerField(
        default=4,
        help_text="Horas para recarregar 1 vida (0 = sem recarga)"
    )
    
    # Trial settings (para novos usuários)
    trial_days = models.IntegerField(
        default=0,
        help_text="Dias de trial após o registo (0 = sem trial)"
    )
    trial_speaking_minutes = models.IntegerField(
        default=0,
        help_text="Minutos diários de speaking durante o trial"
    )
    # Limite mensal da conversa com o tutor (Vapi, o recurso mais caro). None = sem limite mensal.
    # Soma-se ao diário: vale o que acabar primeiro. O mês é o de calendário, na hora de Angola.
    monthly_speaking_minutes = models.IntegerField(
        null=True, blank=True,
        help_text="Minutos de conversa com o tutor por mês (vazio = sem limite mensal)"
    )

    # Recursos premium
    offline_downloads = models.BooleanField(default=False)
    certificates = models.BooleanField(default=False)
    ai_tutor = models.BooleanField(default=False)
    native_teacher_sessions = models.IntegerField(
        default=0,
        help_text="Sessões mensais com professores nativos"
    )
    advanced_analytics = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    streak_freeze = models.IntegerField(
        default=0,
        help_text="Freezes de streak por semana"
    )
    multiple_devices = models.IntegerField(
        default=1,
        help_text="Número de dispositivos simultâneos permitidos"
    )
    
    # Período de teste de um plano PAGO (sem pagamento), uma vez por pessoa.
    # Não confundir com trial_days, que é o teste de conversa do Gratuito depois do registo.
    dias_teste = models.PositiveSmallIntegerField(
        default=0,
        help_text="Dias de teste grátis deste plano pago (0 = sem teste, máximo 30)"
    )
    # Plano em destaque nas páginas de planos (só um de cada vez)
    destaque = models.BooleanField(default=False)

    # Configurações
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'monthly_price']
    
    def __str__(self):
        return f"{self.name} - {self.monthly_price} Kz/mês"
    
    def get_yearly_discount_percentage(self):
        """Calcula percentual de desconto anual"""
        if self.yearly_price and self.monthly_price:
            yearly_equivalent = self.monthly_price * 12
            discount = yearly_equivalent - self.yearly_price
            return round((discount / yearly_equivalent) * 100, 1)
        return 0


class UserSubscription(models.Model):
    """
    Assinatura do Usuário - Controla a assinatura ativa de cada usuário
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Activa'),
        ('CANCELED', 'Cancelada'),
        ('EXPIRED', 'Expirada'),
        ('PENDING', 'Pendente'),
        ('TRIAL', 'Período de Teste'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Datas de controle
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    canceled_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Pagamento
    stripe_subscription_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=200, null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    # Renovação manual (Multicaixa Express não permite débito automático):
    # quando ligado, o aluno recebe lembretes 3 dias antes e no último dia.
    lembretes_renovacao = models.BooleanField(
        default=True,
        help_text="Enviar lembretes de renovação antes do fim do período pago"
    )

    # Preço contratado (mantém-se nas renovações do mesmo plano até a subscrição
    # terminar; mudar o preço do plano só afecta subscrições novas).
    preco_mensal_kz = models.PositiveIntegerField(null=True, blank=True)
    preco_anual_kz = models.PositiveIntegerField(null=True, blank=True)

    # Código promocional que continua nas renovações (duração "meses" ou "sempre")
    promo_codigo = models.ForeignKey(
        'PromotionalCode', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    promo_meses_usados = models.PositiveIntegerField(
        default=0, help_text="Meses já pagos com o desconto do código em curso"
    )
    
    # Controle de uso diário
    last_reset_date = models.DateField(default=get_current_date)
    daily_lessons_used = models.IntegerField(default=0)
    daily_speaking_minutes_used = models.IntegerField(default=0)
    # Minutos de conversa gastos no mês `speaking_month` ("2026-11"); renova no dia 1.
    monthly_speaking_minutes_used = models.IntegerField(default=0)
    speaking_month = models.CharField(max_length=7, blank=True, default='')
    daily_listening_minutes_used = models.IntegerField(default=0)
    daily_ai_analyses_used = models.IntegerField(default=0)

    # Sistema de vidas
    current_hearts = models.IntegerField(default=5)
    last_heart_recharge = models.DateTimeField(default=timezone.now)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"
    
    def is_active(self):
        """
        Verifica se a assinatura está ativa.

        Uma assinatura é considerada ativa se:
        - Status é ACTIVE e não expirou
        - Status é CANCELED mas ainda não expirou (acesso até o fim do período pago)
        - Está em período de trial (baseado na data de criação do usuário)

        Nota: O status 'TRIAL' está deprecado. Agora usamos is_in_trial_period()
        para verificar trial de forma consistente.
        """
        now = timezone.now()

        # Verificar trial primeiro (baseado na data de criação do usuário)
        if self.is_in_trial_period():
            return True

        # Assinaturas ativas (inclui status TRIAL por compatibilidade)
        if self.status in ('ACTIVE', 'TRIAL') and self.expires_at > now:
            return True

        # Assinaturas canceladas mas ainda dentro do período pago
        if self.status == 'CANCELED' and self.expires_at > now:
            return True

        return False
    
    def is_trial(self):
        """
        Verifica se está em período de teste.

        UNIFIED: Agora usa is_in_trial_period() baseado na data de criação
        do usuário, que é mais preciso e consistente.

        O status 'TRIAL' e trial_ends_at estão deprecados - use is_in_trial_period().
        """
        return self.is_in_trial_period()
    
    def days_until_expiry(self):
        """Dias até expirar"""
        now = timezone.now()
        if self.expires_at > now:
            return (self.expires_at - now).days
        return 0
    
    def reset_daily_usage_if_needed(self):
        """
        Reseta contadores diários se necessário. O dia é o de Angola (Africa/Luanda).

        daily_lessons_used é sincronizado com as lições novas concluídas hoje
        (apps.practice.limite_licoes), para os ecrãs que lêem o campo mostrarem o valor real.
        """
        from apps.practice.limite_licoes import hoje_luanda, licoes_novas_hoje
        today = hoje_luanda()
        campos = []
        if self.last_reset_date < today:
            self.daily_lessons_used = 0
            self.daily_speaking_minutes_used = 0
            self.daily_listening_minutes_used = 0
            self.daily_ai_analyses_used = 0
            self.last_reset_date = today
            campos = ['daily_lessons_used', 'daily_speaking_minutes_used', 'daily_listening_minutes_used',
                      'daily_ai_analyses_used', 'last_reset_date']
        mes = today.strftime('%Y-%m')
        if self.speaking_month != mes:
            self.monthly_speaking_minutes_used = 0
            self.speaking_month = mes
            campos += ['monthly_speaking_minutes_used', 'speaking_month']
        licoes = licoes_novas_hoje(self.user_id)
        if licoes != self.daily_lessons_used:
            self.daily_lessons_used = licoes
            if 'daily_lessons_used' not in campos:
                campos.append('daily_lessons_used')
        if campos and self.pk:
            self.save(update_fields=campos)

    def can_take_lesson(self):
        """Pode fazer mais uma lição NOVA hoje (dia de Angola; repetir lições não conta)."""
        from apps.practice.limite_licoes import limite_do_plano
        self.reset_daily_usage_if_needed()
        limite = limite_do_plano(self)
        if not limite:  # Ilimitado
            return True
        return self.daily_lessons_used < limite

    def is_in_trial_period(self):
        """
        Verifica se o usuário está no período de trial.
        O trial é baseado na data de criação do usuário (created_at).
        """
        if not self.plan.trial_days or self.plan.trial_days <= 0:
            return False

        # Usar data de criação do usuário
        user_created = getattr(self.user, 'created_at', None) or getattr(self.user, 'date_joined', None)
        if not user_created:
            return False

        now = timezone.now()
        trial_end = user_created + timedelta(days=self.plan.trial_days)

        return now < trial_end

    def get_trial_remaining_days(self):
        """Retorna quantos dias restam do trial"""
        if not self.is_in_trial_period():
            return 0

        user_created = getattr(self.user, 'created_at', None) or getattr(self.user, 'date_joined', None)
        if not user_created:
            return 0

        now = timezone.now()
        trial_end = user_created + timedelta(days=self.plan.trial_days)
        remaining = (trial_end - now).days

        return max(0, remaining)

    def get_effective_speaking_limit(self):
        """
        Minutos de conversa por dia: None = ilimitado, 0 = bloqueado, n = n por dia.
        - Durante o trial do Gratuito (depois do registo): trial_speaking_minutes, se houver
        - Senão: daily_speaking_minutes do plano (None continua a ser ilimitado)
        """
        if self.is_in_trial_period() and self.plan.trial_speaking_minutes:
            return self.plan.trial_speaking_minutes
        return self.plan.daily_speaking_minutes

    def can_use_speaking(self, minutes_needed=1):
        """
        Verifica se pode usar Speaking Practice.
        Considera período de trial para usuários no plano gratuito.
        """
        self.reset_daily_usage_if_needed()
        effective_limit = self.get_effective_speaking_limit()
        if effective_limit is None:  # ilimitado
            return True
        if effective_limit <= 0:  # bloqueado
            return False
        return (self.daily_speaking_minutes_used + minutes_needed) <= effective_limit

    def can_use_listening(self, minutes_needed=1):
        """Verifica se pode usar Listening Practice"""
        self.reset_daily_usage_if_needed()

        if not self.plan.daily_listening_minutes:  # Ilimitado
            return True

        return (self.daily_listening_minutes_used + minutes_needed) <= self.plan.daily_listening_minutes

    def can_use_ai_analysis(self):
        """Verifica se pode usar análise AI de pronúncia"""
        self.reset_daily_usage_if_needed()

        if not self.plan.daily_ai_analyses_limit:  # Ilimitado (null)
            return True

        return self.daily_ai_analyses_used < self.plan.daily_ai_analyses_limit

    def get_ai_analyses_remaining(self):
        """Retorna quantas análises AI restam hoje"""
        self.reset_daily_usage_if_needed()

        if not self.plan.daily_ai_analyses_limit:  # Ilimitado
            return -1  # -1 indica ilimitado

        return max(0, self.plan.daily_ai_analyses_limit - self.daily_ai_analyses_used)

    @transaction.atomic
    def use_ai_analysis(self):
        """
        Usa uma análise AI de forma thread-safe.
        Retorna True se conseguiu usar, False se limite atingido.
        """
        self.reset_daily_usage_if_needed()

        if not self.plan.daily_ai_analyses_limit:  # Ilimitado
            self.daily_ai_analyses_used = F('daily_ai_analyses_used') + 1
            self.save(update_fields=['daily_ai_analyses_used'])
            self.refresh_from_db()
            return True

        # Lock the row for update to prevent race conditions
        locked_sub = UserSubscription.objects.select_for_update().get(pk=self.pk)

        if locked_sub.daily_ai_analyses_used < locked_sub.plan.daily_ai_analyses_limit:
            UserSubscription.objects.filter(pk=self.pk).update(
                daily_ai_analyses_used=F('daily_ai_analyses_used') + 1
            )
            self.refresh_from_db()
            return True

        return False

    @transaction.atomic
    def use_heart(self):
        """
        Usa uma vida de forma thread-safe.

        Uses select_for_update to prevent race conditions when multiple
        requests try to use hearts simultaneously.
        """
        # Lock the row for update to prevent race conditions
        locked_sub = UserSubscription.objects.select_for_update().select_related('plan').get(pk=self.pk)

        if locked_sub.current_hearts > 0:
            campos = {'current_hearts': F('current_hearts') - 1}
            # Com as vidas no máximo o relógio da recarga estava parado (às vezes há dias):
            # ao perder a primeira vida começa a contar agora, senão ela voltava logo.
            limite = locked_sub.plano_das_vidas().hearts_limit if locked_sub.plan else 0
            if limite and locked_sub.current_hearts >= limite:
                campos['last_heart_recharge'] = timezone.now()
            # Use F() expression for atomic decrement
            UserSubscription.objects.filter(pk=self.pk).update(**campos)
            # Refresh to get updated value
            self.refresh_from_db()
            return True
        return False
    
    def plano_das_vidas(self):
        """
        O plano cujas regras de vidas se aplicam agora: o da assinatura ou, numa assinatura paga
        que já terminou (antes de o cron a passar ao Gratuito), o Gratuito. Sem isto, um plano
        pago expirado ficava com 5 vidas e sem recarga nenhuma.
        """
        if self.plan.plan_type != 'FREE' and not self.is_active():
            gratuito = SubscriptionPlan.objects.filter(plan_type='FREE').first()
            if gratuito is not None:
                return gratuito
        return self.plan

    def recharge_hearts_if_needed(self):
        """Recarrega vidas se necessário (segundo o plano_das_vidas)."""
        plano = self.plano_das_vidas()
        if plano.hearts_limit == 0:  # Vidas ilimitadas
            self.current_hearts = 999
            self.save(update_fields=['current_hearts'])
            return

        if self.current_hearts > plano.hearts_limit:
            # Ex.: as 999 de um plano pago que terminou.
            self.current_hearts = plano.hearts_limit
            self.save(update_fields=['current_hearts'])
        if self.current_hearts >= plano.hearts_limit:
            return  # Já está no máximo (use_heart reinicia o relógio ao perder a 1.ª vida)

        now = timezone.now()
        horas = plano.hearts_recharge_hours or 0
        if horas <= 0:
            return
        hours_since_recharge = (now - self.last_heart_recharge).total_seconds() / 3600
        hearts_to_add = int(hours_since_recharge / horas)

        if hearts_to_add > 0:
            self.current_hearts = min(
                self.current_hearts + hearts_to_add,
                plano.hearts_limit
            )
            if self.current_hearts >= plano.hearts_limit:
                self.last_heart_recharge = now
            else:
                # Guarda o tempo já decorrido para a próxima vida (não o deita fora).
                self.last_heart_recharge = self.last_heart_recharge + timedelta(hours=horas * hearts_to_add)
            self.save(update_fields=['current_hearts', 'last_heart_recharge'])
    
    def has_hearts(self):
        """Verifica se o usuário tem vidas disponíveis"""
        self.recharge_hearts_if_needed()
        return self.current_hearts > 0


class SubscriptionHistory(models.Model):
    """
    Histórico de Assinaturas - Registra mudanças e eventos da assinatura
    """
    
    EVENT_TYPES = [
        ('CREATED', 'Criada'),
        ('UPGRADED', 'Upgrade'),
        ('DOWNGRADED', 'Downgrade'),
        ('RENEWED', 'Renovada'),
        ('CANCELED', 'Cancelada'),
        ('EXPIRED', 'Expirada'),
        ('TRIAL_STARTED', 'Trial Iniciado'),
        ('TRIAL_ENDED', 'Trial Finalizado'),
        ('PAYMENT_SUCCESS', 'Pagamento Realizado'),
        ('PAYMENT_FAILED', 'Falha no Pagamento'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='history'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    previous_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    new_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor pago em Kuanzas (AOA)"
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.user.username} - {self.event_type} - {self.created_at.date()}"


class PromotionalCode(models.Model):
    """
    Códigos Promocionais - descontos no pagamento por Multicaixa Express.

    Regras (aplicadas em apps.subscriptions.services.validar_promo e no checkout):
    * ``estado``: rascunho (não aceite), activo, desligado (não aceite).
      Esgotado/expirado são derivados de ``max_uses`` e ``valid_until``.
    * ``applicable_plans`` (vazio = todos os planos pagos) e ``periodo_aplicavel``.
    * ``duracao``: primeiro (só o 1.º pagamento), meses (os primeiros N meses pagos),
      sempre (todas as renovações do mesmo plano).
    """

    DISCOUNT_TYPES = [
        ('PERCENTAGE', 'Percentual'),
        ('FIXED_AMOUNT', 'Valor Fixo'),
        ('FREE_TRIAL', 'Trial Gratuito'),
    ]

    RASCUNHO = 'rascunho'
    ACTIVO = 'activo'
    DESLIGADO = 'desligado'
    ESTADOS = [(RASCUNHO, 'Rascunho'), (ACTIVO, 'Activo'), (DESLIGADO, 'Desligado')]

    PERIODO_TODOS = 'todos'
    PERIODOS = [('todos', 'Mensal e anual'), ('mensal', 'Só mensal'), ('anual', 'Só anual')]

    DURACAO_PRIMEIRO = 'primeiro'
    DURACAO_MESES = 'meses'
    DURACAO_SEMPRE = 'sempre'
    DURACOES = [
        (DURACAO_PRIMEIRO, 'Só o primeiro pagamento'),
        (DURACAO_MESES, 'Os primeiros meses'),
        (DURACAO_SEMPRE, 'Sempre'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')

    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor do desconto (% ou AOA)"
    )

    # Limitações
    max_uses = models.IntegerField(default=1, null=True, blank=True,
                                   help_text="Máximo de utilizações (vazio = sem limite)")
    current_uses = models.IntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True, help_text="Vazio = não expira")

    # Aplicabilidade
    applicable_plans = models.ManyToManyField(
        SubscriptionPlan,
        blank=True,
        help_text="Planos elegíveis (vazio = todos)"
    )
    periodo_aplicavel = models.CharField(max_length=10, choices=PERIODOS, default=PERIODO_TODOS)
    duracao = models.CharField(max_length=10, choices=DURACOES, default=DURACAO_PRIMEIRO)
    duracao_meses = models.PositiveSmallIntegerField(null=True, blank=True)
    first_time_users_only = models.BooleanField(default=False)

    estado = models.CharField(max_length=10, choices=ESTADOS, default=ACTIVO)
    # Espelho de estado == activo (compatibilidade com código antigo)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.discount_value}"

    # Tipos que o pagamento sabe aplicar (FREE_TRIAL existe só por compatibilidade
    # com dados antigos e é recusado na criação/edição e no pagamento).
    TIPOS_SUPORTADOS = ('PERCENTAGE', 'FIXED_AMOUNT')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'is_active' in kwargs and 'estado' not in kwargs:  # criado à moda antiga
            self.estado = self.ACTIVO if kwargs['is_active'] else self.DESLIGADO
        # __dict__: não carregar campos adiados (.only())
        self._estado_orig, self._activo_orig = self.__dict__.get('estado'), self.__dict__.get('is_active')

    def save(self, *args, **kwargs):
        # estado manda; mudar só is_active (código antigo) traduz-se em activo/desligado
        if (self._activo_orig is not None and self.estado == self._estado_orig
                and self.is_active != self._activo_orig):
            self.estado = self.ACTIVO if self.is_active else self.DESLIGADO
            campos = kwargs.get('update_fields')
            if campos is not None and 'estado' not in campos:
                kwargs['update_fields'] = list(campos) + ['estado']
        self.is_active = self.estado == self.ACTIVO
        if self.code:
            self.code = self.code.strip().upper()
        campos = kwargs.get('update_fields')
        if campos is not None and 'estado' in campos and 'is_active' not in campos:
            kwargs['update_fields'] = list(campos) + ['is_active']
        super().save(*args, **kwargs)
        self._estado_orig, self._activo_orig = self.estado, self.is_active

    def clean(self):
        from django.core.exceptions import ValidationError
        erros = {}
        valor = self.discount_value
        if self.discount_type not in self.TIPOS_SUPORTADOS:
            erros['discount_type'] = 'Tipo de código não suportado: use percentagem ou valor fixo.'
        elif valor is None:
            erros['discount_value'] = 'Indique o valor do desconto.'
        elif self.discount_type == 'PERCENTAGE' and not (0 < valor <= 100):
            erros['discount_value'] = 'A percentagem tem de ser maior que 0 e no máximo 100.'
        elif self.discount_type == 'FIXED_AMOUNT' and not valor > 0:
            erros['discount_value'] = 'O valor fixo tem de ser maior que 0 Kz.'
        if self.max_uses is not None and self.max_uses < 1:
            erros['max_uses'] = 'O número máximo de utilizações tem de ser pelo menos 1.'
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            erros['valid_until'] = 'A data de fim tem de ser posterior à data de início.'
        if erros:
            raise ValidationError(erros)

    @property
    def esgotado(self):
        return self.max_uses is not None and self.current_uses >= self.max_uses

    def expirado(self, agora=None):
        return self.valid_until is not None and self.valid_until < (agora or timezone.now())

    def estado_actual(self, agora=None):
        """rascunho | desligado | expirado | esgotado | activo."""
        if self.estado != self.ACTIVO:
            return self.estado
        if not self.is_active:
            return self.DESLIGADO
        if self.expirado(agora):
            return 'expirado'
        if self.esgotado:
            return 'esgotado'
        return self.ACTIVO

    def is_valid(self):
        """Verifica se o código está válido"""
        now = timezone.now()
        return (
            self.estado == self.ACTIVO and self.is_active and
            (self.valid_from is None or self.valid_from <= now) and
            not self.expirado(now) and
            not self.esgotado
        )


class PromoCodeUsage(models.Model):
    """
    Uso de Códigos Promocionais - Registra quando um código foi usado
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promo_code = models.ForeignKey(
        PromotionalCode,
        on_delete=models.CASCADE,
        related_name='usages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='promo_usages'
    )
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='promo_usages'
    )
    
    discount_applied = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Desconto aplicado em AOA"
    )

    # Reservado quando o pagamento é criado (conta para max_uses); passa a
    # confirmado quando o pagamento é confirmado e é apagado se o pagamento
    # falhar, expirar ou for cancelado.
    RESERVADO = 'reservado'
    CONFIRMADO = 'confirmado'
    ESTADOS = [(RESERVADO, 'Reservado'), (CONFIRMADO, 'Confirmado')]
    estado = models.CharField(max_length=12, choices=ESTADOS, default=CONFIRMADO)

    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['promo_code', 'user']
        ordering = ['-used_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.promo_code.code}"

def normalizar_email(email):
    """
    Caixa de correio de um email, para "um teste grátis por pessoa": minúsculas, sem a
    etiqueta "+..." e, no Gmail, sem pontos (a.b+x@Gmail.com == ab@gmail.com).
    """
    email = (email or '').strip().lower()
    if '@' not in email:
        return email
    local, dominio = email.rsplit('@', 1)
    local = local.split('+', 1)[0]
    if dominio in ('gmail.com', 'googlemail.com'):
        local = local.replace('.', '')
        dominio = 'gmail.com'
    return f'{local}@{dominio}'


class TesteGratis(models.Model):
    """
    Teste grátis de um plano pago: um por pessoa. A pessoa é identificada pelo número
    Multicaixa Express (normalizado, 9 dígitos) e pela caixa de correio (``normalizar_email``):
    nenhum dos dois pode voltar a ser usado noutro teste, mesmo noutra conta.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='testes_gratis')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='testes_gratis')
    # Nulo só nos testes anteriores a esta regra (sem número registado)
    telefone = models.CharField(max_length=9, null=True, blank=True)
    email_normalizado = models.CharField(max_length=254, blank=True, default='')
    iniciado_em = models.DateTimeField(default=timezone.now)
    termina_em = models.DateTimeField()

    class Meta:
        ordering = ['-iniciado_em']
        constraints = [
            models.UniqueConstraint(fields=['telefone'], condition=models.Q(telefone__isnull=False),
                                    name='teste_gratis_um_por_telefone'),
            models.UniqueConstraint(fields=['email_normalizado'], condition=~models.Q(email_normalizado=''),
                                    name='teste_gratis_um_por_email'),
        ]

    def __str__(self):
        return f'{self.user_id} - {self.plan_id} ({self.telefone or "sem número"})'
