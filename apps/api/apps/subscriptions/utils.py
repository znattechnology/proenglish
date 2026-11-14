"""
Subscription Utils - Utilitários para sistema de assinaturas

Funções auxiliares para verificar limitações, cálculos de preços,
e outras operações relacionadas às assinaturas.
"""

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription, SubscriptionPlan


def get_user_subscription(user):
    """Obtém ou cria a assinatura do utilizador (ver services.obter_ou_criar_assinatura)."""
    from .services import obter_ou_criar_assinatura
    return obter_ou_criar_assinatura(user)


def check_subscription_limits(user, feature_type='general', amount=1):
    """
    Verifica se o utilizador pode usar uma funcionalidade
    
    Args:
        user: Utilizador Django
        feature_type: Tipo de funcionalidade ('lesson', 'speaking', 'listening', 'hearts')
        amount: Quantidade necessária (default: 1)
        
    Returns:
        dict: {
            'allowed': bool,
            'error_message': str,
            'current_usage': int,
            'limit': int,
            'subscription': UserSubscription
        }
    """
    subscription = get_user_subscription(user)
    
    # Resetar contadores se necessário
    subscription.reset_daily_usage_if_needed()
    
    # Verificar se assinatura está ativa
    if not subscription.is_active():
        return {
            'allowed': False,
            'error_message': 'A sua subscrição terminou.',
            'upgrade_required': True
        }
    
    result = {
        'allowed': True,
        'upgrade_required': False
    }
    
    # Verificar limitações específicas
    if feature_type == 'lesson':
        can_use = subscription.can_take_lesson()
        result.update({
            'current_usage': subscription.daily_lessons_used,
            'limit': subscription.plan.daily_lessons_limit
        })
        if not can_use:
            result.update({
                'allowed': False,
                'error_message': f'Atingiu o limite diário de lições ({subscription.plan.daily_lessons_limit}).',
                'upgrade_required': True
            })
    
    elif feature_type == 'speaking':
        # None = ilimitado, 0 = bloqueado (a mesma regra de UserSubscription.can_use_speaking)
        limite = subscription.get_effective_speaking_limit()
        result.update({
            'current_usage': subscription.daily_speaking_minutes_used,
            'limit': limite
        })
        if not subscription.can_use_speaking(amount):
            result.update({
                'allowed': False,
                'error_message': (f'Atingiu o limite diário de conversa ({limite} min).' if limite
                                  else 'O seu plano não inclui conversa com o tutor.'),
                'upgrade_required': True
            })
    
    elif feature_type == 'listening':
        if subscription.plan.daily_listening_minutes is None or subscription.plan.daily_listening_minutes == 0:
            # Unlimited listening
            result.update({
                'current_usage': subscription.daily_listening_minutes_used,
                'limit': subscription.plan.daily_listening_minutes
            })
        elif subscription.daily_listening_minutes_used + amount > subscription.plan.daily_listening_minutes:
            result.update({
                'allowed': False,
                'error_message': f'Atingiu o limite diário de compreensão oral ({subscription.plan.daily_listening_minutes} min).',
                'current_usage': subscription.daily_listening_minutes_used,
                'limit': subscription.plan.daily_listening_minutes,
                'upgrade_required': True
            })
        else:
            result.update({
                'current_usage': subscription.daily_listening_minutes_used,
                'limit': subscription.plan.daily_listening_minutes
            })
    
    elif feature_type == 'hearts':
        # Recarregar vidas se necessário
        subscription.recharge_hearts_if_needed()
        
        if subscription.current_hearts < amount:
            result.update({
                'allowed': False,
                'error_message': 'Não tem vidas suficientes.',
                'current_usage': subscription.current_hearts,
                'limit': subscription.plan.hearts_limit,
                'upgrade_required': True
            })
        else:
            result.update({
                'current_usage': subscription.current_hearts,
                'limit': subscription.plan.hearts_limit
            })
    
    return result


def consume_subscription_resource(user, feature_type, amount=1):
    """
    Consome recursos da assinatura do utilizador
    
    Args:
        user: Utilizador Django
        feature_type: Tipo ('lesson', 'speaking_minutes', 'listening_minutes', 'hearts')
        amount: Quantidade a consumir
        
    Returns:
        bool: True se consumiu com sucesso
    """
    subscription = get_user_subscription(user)
    
    try:
        if feature_type == 'lesson':
            subscription.daily_lessons_used += amount
        elif feature_type == 'speaking_minutes':
            subscription.daily_speaking_minutes_used += amount
        elif feature_type == 'listening_minutes':
            subscription.daily_listening_minutes_used += amount
        elif feature_type == 'hearts':
            subscription.current_hearts = max(0, subscription.current_hearts - amount)
        
        subscription.save()
        return True
        
    except Exception:
        return False


def calculate_upgrade_price(user, new_plan_id, billing_cycle='MONTHLY', promo_code=None):
    """
    Preço de um plano com código promocional (sem crédito do plano atual).
    Delegado em services.calcular_preco_plano, que nunca devolve valores negativos.
    O orçamento completo (com crédito) é apps.pagamentos.services.orcamento.
    """
    from .services import calcular_preco_plano

    try:
        new_plan = SubscriptionPlan.objects.get(id=new_plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return {'error': 'Plano não encontrado.'}

    preco = calcular_preco_plano(user, new_plan, billing_cycle, promo_code)
    result = {
        'new_plan': new_plan.name,
        'billing_cycle': billing_cycle,
        'base_price': preco.base,
        'discount_applied': preco.desconto,
        'final_price': preco.final,
        'promo_code_valid': bool(preco.promo),
        'promo_code_error': preco.mensagem_erro_promo,
    }
    if preco.promo:
        result['promo_code_name'] = preco.promo.name
    return result


def get_subscription_analytics(user):
    """
    Retorna analytics da assinatura do utilizador
    
    Args:
        user: Utilizador Django
        
    Returns:
        dict: Dados analytics
    """
    subscription = get_user_subscription(user)
    subscription.reset_daily_usage_if_needed()
    subscription.recharge_hearts_if_needed()
    
    plan = subscription.plan
    
    # Cálculos de uso
    lesson_usage_pct = 0
    if plan.daily_lessons_limit and plan.daily_lessons_limit > 0:
        lesson_usage_pct = (subscription.daily_lessons_used / plan.daily_lessons_limit) * 100
    
    speaking_usage_pct = 0
    if plan.daily_speaking_minutes and plan.daily_speaking_minutes > 0:
        speaking_usage_pct = (subscription.daily_speaking_minutes_used / plan.daily_speaking_minutes) * 100
    
    listening_usage_pct = 0
    if plan.daily_listening_minutes and plan.daily_listening_minutes > 0:
        listening_usage_pct = (subscription.daily_listening_minutes_used / plan.daily_listening_minutes) * 100
    
    hearts_pct = 0
    if plan.hearts_limit > 0:
        hearts_pct = (subscription.current_hearts / plan.hearts_limit) * 100
    
    return {
        'subscription': {
            'plan_name': plan.name,
            'plan_type': plan.plan_type,
            'status': subscription.status,
            'expires_at': subscription.expires_at,
            'days_remaining': subscription.days_until_expiry(),
            'is_trial': subscription.is_trial(),
            'is_active': subscription.is_active()
        },
        'usage': {
            'lessons': {
                'used': subscription.daily_lessons_used,
                'limit': plan.daily_lessons_limit,
                'unlimited': plan.daily_lessons_limit == 0 or plan.daily_lessons_limit is None,
                'percentage': min(100, lesson_usage_pct),
                'can_use': subscription.can_take_lesson()
            },
            'speaking': {
                'used': subscription.daily_speaking_minutes_used,
                'limit': plan.daily_speaking_minutes,
                'unlimited': subscription.get_effective_speaking_limit() is None,
                'percentage': min(100, speaking_usage_pct),
                'can_use': subscription.can_use_speaking()
            },
            'listening': {
                'used': subscription.daily_listening_minutes_used,
                'limit': plan.daily_listening_minutes,
                'unlimited': plan.daily_listening_minutes == 0 or plan.daily_listening_minutes is None,
                'percentage': min(100, listening_usage_pct),
                'can_use': subscription.can_use_listening()
            },
            'hearts': {
                'current': subscription.current_hearts,
                'limit': plan.hearts_limit,
                'unlimited': plan.hearts_limit == 0,
                'percentage': hearts_pct if plan.hearts_limit > 0 else 100,
                'recharge_hours': plan.hearts_recharge_hours,
                'last_recharge': subscription.last_heart_recharge
            }
        },
        'features': {
            'offline_downloads': plan.offline_downloads,
            'certificates': plan.certificates,
            'ai_tutor': plan.ai_tutor,
            'native_teacher_sessions': plan.native_teacher_sessions,
            'advanced_analytics': plan.advanced_analytics,
            'priority_support': plan.priority_support,
            'streak_freeze': plan.streak_freeze,
            'multiple_devices': plan.multiple_devices
        }
    }


def check_premium_feature(user, feature_name):
    """
    Verifica se o utilizador tem acesso a uma funcionalidade premium
    
    Args:
        user: Utilizador Django
        feature_name: Nome da funcionalidade
        
    Returns:
        bool: True se tem acesso
    """
    subscription = get_user_subscription(user)
    plan = subscription.plan
    
    if not subscription.is_active():
        return False
    
    feature_mapping = {
        'offline_downloads': plan.offline_downloads,
        'certificates': plan.certificates,
        'ai_tutor': plan.ai_tutor,
        'native_teacher_sessions': plan.native_teacher_sessions > 0,
        'advanced_analytics': plan.advanced_analytics,
        'priority_support': plan.priority_support,
        'streak_freeze': plan.streak_freeze > 0,
        'multiple_devices': plan.multiple_devices > 1
    }
    
    return feature_mapping.get(feature_name, False)