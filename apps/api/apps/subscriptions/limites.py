"""
Limites diários efetivos (o que o servidor aplica), para mostrar na API.

Convenção: ``None`` = ilimitado, ``0`` = bloqueado, ``n`` = n por dia.
Os limites de conversa e de lições são os mesmos que o servidor aplica
(apps.practice.conversa.quota e apps.practice.limite_licoes): contam o período
de teste do plano Gratuito e tratam uma assinatura paga expirada como Gratuito.
"""


def plano_efetivo(sub):
    from apps.practice.conversa.quota import _plano_efectivo
    return _plano_efectivo(sub)[0]


def limite_conversa_efetivo(sub):
    """Minutos de conversa com o tutor por dia (None = ilimitado, 0 = bloqueado)."""
    from apps.practice.conversa.quota import limite_diario
    return limite_diario(sub)[0]


def estado_licoes(sub):
    """{'used', 'limit'} das lições novas de hoje (limit None = ilimitado)."""
    from apps.practice import limite_licoes
    e = limite_licoes.estado(sub.user, sub)
    return {'used': e['feitas'], 'limit': e['limite'], 'renova_em': e.get('renova_em')}


def _item(usado, limite):
    return {
        'used': usado,
        'limit': limite,
        'unlimited': limite is None,
        'blocked': limite == 0,
        'remaining': None if limite is None else max(0, limite - usado),
        'can_use': limite is None or usado < limite,
    }


def estado_limites(sub):
    """Corpo de GET /api/v1/subscriptions/limits/."""
    sub.reset_daily_usage_if_needed()
    sub.recharge_hearts_if_needed()
    plano = plano_efetivo(sub)

    licoes = estado_licoes(sub)
    ouvir = plano.daily_listening_minutes
    analises = plano.daily_ai_analyses_limit
    vidas_ilimitadas = not plano.hearts_limit  # nas vidas, 0 = ilimitadas (convenção do modelo)

    return {
        'lessons': {**_item(licoes['used'], licoes['limit']), 'resets_at': licoes['renova_em']},
        'speaking': _item(sub.daily_speaking_minutes_used, limite_conversa_efetivo(sub)),
        'listening': _item(sub.daily_listening_minutes_used, ouvir),
        'ai_analyses': _item(sub.daily_ai_analyses_used, analises),
        'hearts': {
            'current': None if vidas_ilimitadas else sub.current_hearts,
            'limit': None if vidas_ilimitadas else plano.hearts_limit,
            'unlimited': vidas_ilimitadas,
            'can_use': vidas_ilimitadas or sub.current_hearts > 0,
            'recharge_hours': plano.hearts_recharge_hours,
            'last_recharge': sub.last_heart_recharge,
        },
        'plan': {
            'name': plano.name,
            'type': plano.plan_type,
            'subscribed_type': sub.plan.plan_type,
            'is_active': sub.is_active(),
            'is_trial': sub.is_in_trial_period(),
            'expires_at': None if sub.plan.plan_type == 'FREE' else sub.expires_at,
            'days_remaining': sub.days_until_expiry(),
        },
    }
