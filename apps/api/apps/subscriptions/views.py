"""
Endpoints da API de assinaturas: planos, assinatura do aluno, códigos
promocionais e relatórios de administração.

Não há renovação automática (Multicaixa Express): não existe "cancelar
subscrição". O plano pago termina no fim do período e a conta volta ao
Gratuito, mantendo o progresso.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Q, Avg
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from .models import (
    SubscriptionPlan,
    UserSubscription, 
    SubscriptionHistory,
    PromotionalCode,
    PromoCodeUsage
)
from .serializers import (
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
    SubscriptionHistorySerializer,
    PromotionalCodeSerializer,
    PromoCodeUsageSerializer,
    SubscriptionUpgradeSerializer,
    ApplyPromoCodeSerializer,
    SubscriptionStatsSerializer
)
from .utils import get_subscription_analytics
from apps.core.permissions import EAdministrador, e_administrador

User = get_user_model()


# ========================================================================
# PUBLIC ENDPOINTS - Planos disponíveis (sem autenticação)
# ========================================================================

class PublicSubscriptionPlansListView(generics.ListAPIView):
    """
    Lista pública de planos de assinatura disponíveis
    Usado na landing page e tela de preços
    """
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')
    serializer_class = SubscriptionPlanSerializer
    permission_classes = []  # Público
    
    def get_queryset(self):
        """
        Planos activos. Com sessão, também o plano desactivado que o utilizador ainda tem
        (ou teve há pouco): pode continuar a renová-lo, mas não aparece a pessoas novas.
        """
        from .services import planos_detidos_inactivos
        ids = [p.id for p in planos_detidos_inactivos(getattr(self.request, 'user', None))]
        return SubscriptionPlan.objects.filter(Q(is_active=True) | Q(id__in=ids)).order_by('sort_order')


# ========================================================================
# USER ENDPOINTS - Gestão de assinatura do utilizador
# ========================================================================

class UserSubscriptionView(generics.RetrieveAPIView):
    """
    Assinatura atual do utilizador autenticado (cria a do plano Gratuito se não existir).
    """
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        from .services import obter_ou_criar_assinatura
        return obter_ou_criar_assinatura(self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upgrade_subscription(request):
    """
    Mudança de plano.

    * Administradores: ativam qualquer plano diretamente (incluindo o Gratuito).
    * Alunos: os planos pagos só são ativados pela confirmação de um pagamento
      (app pagamentos); aqui apenas se confirma um ``pagamento_id`` já pago.
      Com preço final 0 Kz (código de 100% ou crédito do plano atual) deve usar-se
      ``POST /api/v1/pagamentos/sem-pagamento/``. O plano Gratuito não se escolhe:
      a conta volta ao Gratuito quando o período pago termina.
    """
    from .services import calcular_preco_plano, ativar_plano, PROMO_INEXISTENTE

    serializer = SubscriptionUpgradeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    plan_id = serializer.validated_data['plan_id']
    billing_cycle = serializer.validated_data['billing_cycle']
    promo_code = serializer.validated_data.get('promo_code')

    try:
        new_plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return Response({
            'error': 'Plano não encontrado.'
        }, status=status.HTTP_404_NOT_FOUND)

    user = request.user
    is_admin = e_administrador(user)

    if not is_admin:
        if new_plan.plan_type == 'FREE':
            return Response({
                'error': 'Não é possível mudar para o plano Gratuito. A sua conta volta ao '
                         'Gratuito quando o período pago terminar, e o progresso fica guardado.',
                'code': 'FREE_NOT_ALLOWED',
            }, status=status.HTTP_400_BAD_REQUEST)

        pagamento_id = request.data.get('pagamento_id')
        if not pagamento_id:
            return Response({
                'error': 'É necessário um pagamento confirmado para activar este plano.',
                'code': 'PAYMENT_REQUIRED',
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

        from apps.pagamentos.services import obter_pagamento_pago_de_plano
        pagamento = obter_pagamento_pago_de_plano(user, pagamento_id, new_plan)
        if pagamento is None:
            return Response({
                'error': 'Pagamento não encontrado ou ainda não confirmado.',
                'code': 'PAYMENT_NOT_CONFIRMED',
            }, status=status.HTTP_400_BAD_REQUEST)

        subscription = UserSubscription.objects.get(user=user)
        return Response({
            'message': 'Plano actualizado.',
            'subscription': UserSubscriptionSerializer(subscription).data,
            'amount_paid': Decimal(pagamento.total_kz),
            'discount_applied': Decimal(pagamento.desconto_kz),
            'pagamento_id': str(pagamento.id),
        })

    # Administradores: ativação direta (sem crédito do plano anterior).
    preco = calcular_preco_plano(user, new_plan, billing_cycle, promo_code)
    if preco.erro_promo:
        return Response({
            'error': preco.mensagem_erro_promo,
            'code': preco.erro_promo,
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        subscription, _history = ativar_plano(
            user, new_plan, billing_cycle,
            amount_paid=preco.final,
            discount=preco.desconto,
            promo=preco.promo,
            notas_extra='Activado por um administrador',
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'message': 'Plano actualizado.',
        'subscription': UserSubscriptionSerializer(subscription).data,
        'amount_paid': preco.final,
        'discount_applied': preco.desconto,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apply_promo_code(request):
    """
    Pré-visualiza um código promocional para um plano, sem o usar.
    Usa o mesmo cálculo do pagamento (orçamento: crédito do plano atual e código),
    por isso o valor mostrado é o valor cobrado.
    Body: {promo_code, plan_id, periodo?: "mensal"|"anual"}.
    O orçamento completo está em GET /api/v1/pagamentos/orcamento/.
    """
    from apps.pagamentos.services import orcamento, ErroPagamento

    codigo = (request.data.get('promo_code') or '').strip().upper()
    plan_id = request.data.get('plan_id')
    if not codigo or not plan_id:
        return Response({'error': 'Indique o código e o plano.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
    except (SubscriptionPlan.DoesNotExist, ValueError, ValidationError):
        return Response({'error': 'Plano não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
    # Um plano desactivado só serve a quem já o tem: a regra está em orcamento()

    periodo = 'anual' if request.data.get('periodo') == 'anual' else 'mensal'
    try:
        o = orcamento(request.user, plan, periodo, codigo)
    except ErroPagamento as e:
        return Response({'error': e.mensagem, 'code': e.codigo}, status=e.status)
    if o['erro_codigo']:
        return Response({'error': o['erro_codigo']['mensagem'], 'codigo': o['erro_codigo']['code']},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'valid': True,
        'promo_code': codigo,
        'discount_type': o['codigo']['tipo'] if o['codigo'] else None,
        'discount_value': o['codigo']['valor'] if o['codigo'] else None,
        'original_price': o['preco_base_kz'],
        'discount_amount': o['desconto_codigo_kz'],
        'credito_kz': o['credito_kz'],
        'final_price': o['final_kz'],
        'aviso_codigo': o['aviso_codigo'],
        'description': o['codigo']['descricao'] if o['codigo'] else None,
        'orcamento': o,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def renewal_reminders(request):
    """
    GET/PATCH /api/v1/subscriptions/my-subscription/lembretes/

    Liga/desliga os lembretes de renovação (Multicaixa Express não renova
    automaticamente). Body PATCH: {"lembretes_renovacao": true|false}.
    """
    from .services import obter_ou_criar_assinatura
    subscription = obter_ou_criar_assinatura(request.user)

    if request.method == 'PATCH':
        valor = request.data.get('lembretes_renovacao')
        if not isinstance(valor, bool):
            return Response({
                'error': 'Indique "lembretes_renovacao" como true ou false.'
            }, status=status.HTTP_400_BAD_REQUEST)
        subscription.lembretes_renovacao = valor
        subscription.save(update_fields=['lembretes_renovacao', 'updated_at'])

    return Response({
        'lembretes_renovacao': subscription.lembretes_renovacao,
        'expires_at': subscription.expires_at.isoformat() if subscription.expires_at else None,
        'plan_type': subscription.plan.plan_type,
    })


# ========================================================================
# ADMIN ENDPOINTS - Gestão administrativo
# ========================================================================

class AdminSubscriptionPlansListView(generics.ListCreateAPIView):
    """
    Lista e cria planos de assinatura (admin only)
    """
    queryset = SubscriptionPlan.objects.all().order_by('sort_order')
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [EAdministrador]
    
    def get_queryset(self):
        """Admins veem todos os planos, incluindo inativos"""
        return SubscriptionPlan.objects.all().order_by('sort_order')


class AdminSubscriptionPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Gere plano específico (admin only)
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [EAdministrador]


class AdminUserSubscriptionsListView(generics.ListAPIView):
    """
    Lista todas as assinaturas de utilizadores (admin only)
    """
    queryset = UserSubscription.objects.select_related('user', 'plan').order_by('-created_at')
    serializer_class = UserSubscriptionSerializer
    permission_classes = [EAdministrador]
    
    def get_queryset(self):
        """Permite filtros por status, plano, etc"""
        queryset = UserSubscription.objects.select_related('user', 'plan').order_by('-created_at')
        
        # Filtros opcionais
        plan_type = self.request.query_params.get('plan_type')
        status_filter = self.request.query_params.get('status')
        
        if plan_type:
            queryset = queryset.filter(plan__plan_type=plan_type)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset


@api_view(['GET'])
@permission_classes([EAdministrador])
def admin_subscription_stats(request):
    """
    Retorna estatísticas gerais de assinatura para o dashboard admin
    """
    # Estatísticas básicas
    total_subscribers = UserSubscription.objects.filter(status='ACTIVE').count()
    
    # Receita mensal (últimos 30 dias)
    last_30_days = timezone.now() - timedelta(days=30)
    recent_payments = SubscriptionHistory.objects.filter(
        event_type__in=['CREATED', 'UPGRADED', 'RENEWED'],
        created_at__gte=last_30_days,
        amount_paid__isnull=False
    ).aggregate(
        total_revenue=Sum('amount_paid')
    )['total_revenue'] or Decimal('0.00')
    
    # Distribuição por plano
    plan_distribution = UserSubscription.objects.filter(
        status='ACTIVE'
    ).values('plan__plan_type').annotate(count=Count('id'))
    
    free_users = premium_users = premium_plus_users = 0
    for item in plan_distribution:
        if item['plan__plan_type'] == 'FREE':
            free_users = item['count']
        elif item['plan__plan_type'] == 'PREMIUM':
            premium_users = item['count']
        elif item['plan__plan_type'] == 'PREMIUM_PLUS':
            premium_plus_users = item['count']
    
    # Account for users without subscription records (they should be considered FREE users)
    total_users = User.objects.count()
    users_with_subscriptions = UserSubscription.objects.filter(status='ACTIVE').values('user').distinct().count()
    users_without_subscriptions = total_users - users_with_subscriptions
    free_users += users_without_subscriptions  # Add users without subscriptions to FREE count
    
    # Taxa de conversão (estimativa simples)
    paying_users = premium_users + premium_plus_users
    conversion_rate = (paying_users / total_users * 100) if total_users > 0 else 0
    
    # Taxa de churn (cancelamentos nos últimos 30 dias)
    recent_cancellations = UserSubscription.objects.filter(
        status='CANCELED',
        canceled_at__gte=last_30_days
    ).count()
    churn_rate = (recent_cancellations / total_subscribers * 100) if total_subscribers > 0 else 0
    
    # Assinaturas recentes
    recent_subscriptions = UserSubscription.objects.select_related(
        'user', 'plan'
    ).filter(
        status__in=['ACTIVE', 'TRIAL']
    ).order_by('-created_at')[:10]
    
    # Códigos promocionais ativos
    active_promo_codes = PromotionalCode.objects.filter(
        is_active=True,
        valid_until__gte=timezone.now()
    ).count()
    
    # Dados para gráfico de receita (últimos 12 meses)
    revenue_chart = {}
    for i in range(12):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        
        month_revenue = SubscriptionHistory.objects.filter(
            event_type__in=['CREATED', 'UPGRADED', 'RENEWED'],
            created_at__gte=month_start,
            created_at__lt=month_end,
            amount_paid__isnull=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        revenue_chart[month_start.strftime('%Y-%m')] = float(month_revenue)
    
    stats = {
        'total_subscribers': total_subscribers,
        'monthly_revenue': recent_payments,
        'conversion_rate': round(conversion_rate, 1),
        'churn_rate': round(churn_rate, 1),
        'free_users': free_users,
        'premium_users': premium_users,
        'premium_plus_users': premium_plus_users,
        'active_promo_codes': active_promo_codes,
        'recent_subscriptions': UserSubscriptionSerializer(recent_subscriptions, many=True).data,
        'revenue_chart': revenue_chart
    }
    
    return Response(stats)


class AdminPromotionalCodesListView(generics.ListCreateAPIView):
    """
    Lista e cria códigos promocionais (admin only)
    """
    queryset = PromotionalCode.objects.all().order_by('-created_at')
    serializer_class = PromotionalCodeSerializer
    permission_classes = [EAdministrador]


class AdminPromotionalCodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Gere código promocional específico (admin only)
    """
    queryset = PromotionalCode.objects.all()
    serializer_class = PromotionalCodeSerializer
    permission_classes = [EAdministrador]


class AdminPromoCodeUsageListView(generics.ListAPIView):
    """
    Lista uso de códigos promocionais (admin only)
    """
    queryset = PromoCodeUsage.objects.select_related('user', 'promo_code').order_by('-used_at')
    serializer_class = PromoCodeUsageSerializer
    permission_classes = [EAdministrador]


# ========================================================================
# SUBSCRIPTION ANALYTICS AND UTILITIES
# ========================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_subscription_analytics(request):
    """
    GET /api/v1/subscriptions/analytics/
    
    Get comprehensive subscription analytics for the current user.
    """
    user = request.user
    analytics = get_subscription_analytics(user)
    
    return Response(analytics)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def subscription_limits_status(request):
    """
    GET /api/v1/subscriptions/limits/

    Limites diários efetivos e uso atual: ``limit`` None = ilimitado, 0 = bloqueado.
    Conta o período de teste do Gratuito e trata um plano pago expirado como Gratuito.
    """
    from .services import obter_ou_criar_assinatura
    from .limites import estado_limites

    return Response(estado_limites(obter_ou_criar_assinatura(request.user)))


# ========================================================================
# BILLING AND PAYMENT HISTORY ENDPOINTS
# ========================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_payment_history(request):
    """
    GET /api/v1/subscriptions/payment-history/
    
    Get user's subscription payment history from SubscriptionHistory model.
    """
    user = request.user
    
    # Get payment-related subscription history
    payment_history = SubscriptionHistory.objects.filter(
        subscription__user=user,
        event_type__in=['CREATED', 'UPGRADED', 'DOWNGRADED', 'RENEWED', 'PAYMENT_SUCCESS'],
        amount_paid__isnull=False
    ).select_related('subscription', 'previous_plan', 'new_plan').order_by('-created_at')
    
    # Format the payment history data
    formatted_history = []
    for history_item in payment_history:
        formatted_history.append({
            'id': str(history_item.id),
            'date': history_item.created_at.isoformat(),
            'event_type': history_item.event_type,
            'event_description': dict(SubscriptionHistory.EVENT_TYPES).get(history_item.event_type, history_item.event_type),
            'amount': float(history_item.amount_paid) if history_item.amount_paid else 0,
            'currency': 'AOA',
            'previous_plan': {
                'name': history_item.previous_plan.name,
                'type': history_item.previous_plan.plan_type
            } if history_item.previous_plan else None,
            'new_plan': {
                'name': history_item.new_plan.name,
                'type': history_item.new_plan.plan_type
            } if history_item.new_plan else None,
            'notes': history_item.notes,
            'subscription_id': str(history_item.subscription.id)
        })
    
    # Pagamentos Multicaixa Express: método, telefone mascarado e recibo
    from apps.pagamentos.services import enriquecer_historico_pagamentos
    formatted_history = enriquecer_historico_pagamentos(user, formatted_history)

    # Get summary statistics
    total_payments = payment_history.aggregate(
        total_amount=Sum('amount_paid'),
        payment_count=Count('id')
    )
    total_payments['total_amount'] = total_payments['total_amount'] or 0
    total_payments['payment_count'] = total_payments['payment_count'] or 0
    
    # Get current subscription info
    try:
        current_subscription = UserSubscription.objects.get(user=user)
        current_plan = {
            'name': current_subscription.plan.name,
            'type': current_subscription.plan.plan_type,
            'status': current_subscription.status,
            'expires_at': current_subscription.expires_at.isoformat() if current_subscription.expires_at else None,
            'next_billing_date': current_subscription.next_billing_date.isoformat() if current_subscription.next_billing_date else None,
            'lembretes_renovacao': current_subscription.lembretes_renovacao,
        }
    except UserSubscription.DoesNotExist:
        current_plan = None
    
    return Response({
        'payment_history': formatted_history,
        'summary': {
            'total_amount_paid': float(total_payments['total_amount'] or 0),
            'total_payments': total_payments['payment_count'] or 0,
            'currency': 'AOA'
        },
        'current_subscription': current_plan
    })
