"""
Oferta de plano quando o aluno chega a um limite (vidas, lições, análises, conversa, exame,
certificado). A API decide qual é o plano que resolve aquele limite; os clientes só mostram.

``oferta(user, recurso, sub=None)`` devolve None (já tem o melhor que há, ou não há plano
activo que resolva) ou:

    {
      'recurso': 'vidas',
      'plano': {'tipo': 'PREMIUM', 'nome': 'Premium', 'preco_mensal_kz': 14950,
                'preco_anual_kz': 149500, 'dias_teste': 7, 'pode_experimentar': True},
      'ganhos': ['Vidas ilimitadas', 'Lições novas sem limite', ...],   # o do recurso primeiro
      'ligacao': '/user/upgrade?plan=PREMIUM',
    }

O plano sugerido é o mais barato, entre os activos e pagos, que melhora o recurso em relação
ao plano efectivo do aluno (uma assinatura paga expirada conta como Gratuito).
"""
from apps.subscriptions.models import SubscriptionPlan

VIDAS = 'vidas'
LICOES = 'licoes'
ANALISES = 'analises'
CONVERSA = 'conversa'
EXAME = 'exame'
CERTIFICADO = 'certificado'
RECURSOS = (VIDAS, LICOES, ANALISES, CONVERSA, EXAME, CERTIFICADO)


def _mais(valor):
    """Limite diário comparável: None (ilimitado) vale mais do que qualquer número."""
    return float('inf') if valor is None else valor


def _vidas_ilimitadas(plano):
    return not plano.hearts_limit  # 0 = ilimitadas (convenção do modelo)


def _licoes(plano):
    return _mais(plano.daily_lessons_limit or None)


def _analises(plano):
    return _mais(plano.daily_ai_analyses_limit or None)


def _conversa(plano):
    return _mais(plano.daily_speaking_minutes)


def melhora(plano, actual, recurso):
    """O ``plano`` resolve o limite do ``recurso`` que o ``actual`` tem?"""
    if recurso == VIDAS:
        return _vidas_ilimitadas(plano) and not _vidas_ilimitadas(actual)
    if recurso == LICOES:
        return _licoes(plano) > _licoes(actual)
    if recurso == ANALISES:
        return _analises(plano) > _analises(actual)
    if recurso == CONVERSA:
        return _conversa(plano) > _conversa(actual)
    if recurso in (EXAME, CERTIFICADO):
        return bool(plano.certificates) and not actual.certificates
    return False


def _por_dia(n, singular, plural):
    return f'{n} {singular if n == 1 else plural} por dia'


def ganhos(plano):
    """O que o plano dá, por recurso, em frases curtas para o ecrã."""
    g = {}
    g[VIDAS] = 'Vidas ilimitadas' if _vidas_ilimitadas(plano) else None
    g[LICOES] = ('Lições novas sem limite' if not plano.daily_lessons_limit
                 else _por_dia(plano.daily_lessons_limit, 'lição nova', 'lições novas'))
    g[ANALISES] = ('Análises de pronúncia sem limite' if not plano.daily_ai_analyses_limit
                   else _por_dia(plano.daily_ai_analyses_limit, 'análise de pronúncia', 'análises de pronúncia'))
    if plano.daily_speaking_minutes is None:
        g[CONVERSA] = 'Conversa com o tutor sem limite de tempo'
    elif plano.daily_speaking_minutes > 0:
        g[CONVERSA] = (f'{plano.daily_speaking_minutes} minutos de conversa com o tutor por dia')
    else:
        g[CONVERSA] = None
    g[EXAME] = 'Exame oral e certificado de cada curso' if plano.certificates else None
    g[CERTIFICADO] = g[EXAME]
    if plano.daily_detailed_pronunciation_limit:
        g['pronuncia_detalhada'] = 'Análise detalhada da pronúncia, som a som'
    if plano.offline_downloads:
        g['offline'] = 'Aulas para ver sem rede'
    return g


def lista_ganhos(plano, primeiro=None):
    g = ganhos(plano)
    ordem = [primeiro] if primeiro else []
    ordem += [k for k in (VIDAS, LICOES, CONVERSA, ANALISES, EXAME, 'pronuncia_detalhada', 'offline')
              if k != primeiro and not (primeiro == CERTIFICADO and k == EXAME)]
    vistos, lista = set(), []
    for k in ordem:
        texto = g.get(k)
        if texto and texto not in vistos:
            vistos.add(texto)
            lista.append(texto)
    return lista


def perdas(plano_pago, gratuito):
    """O que se perde ao voltar do ``plano_pago`` ao ``gratuito`` (para os avisos do fim)."""
    return [lista_ganhos(plano_pago, r)[0] for r in (VIDAS, LICOES, CONVERSA, ANALISES, EXAME)
            if melhora(plano_pago, gratuito, r) and lista_ganhos(plano_pago, r)]


def plano_efectivo(sub):
    from apps.practice.conversa.quota import _plano_efectivo
    return _plano_efectivo(sub)[0]


def plano_sugerido(actual, recurso):
    planos = (SubscriptionPlan.objects.filter(is_active=True).exclude(plan_type='FREE')
              .order_by('monthly_price', 'sort_order'))
    return next((p for p in planos if melhora(p, actual, recurso)), None)


def oferta(user, recurso, sub=None):
    from apps.pagamentos.teste import motivo_sem_teste
    from apps.subscriptions.services import kz_inteiro, obter_ou_criar_assinatura

    sub = sub or obter_ou_criar_assinatura(user)
    plano = plano_sugerido(plano_efectivo(sub), recurso)
    if plano is None:
        return None
    try:
        pode_experimentar = motivo_sem_teste(user, plano, sub) is None
    except Exception:
        pode_experimentar = False
    return {
        'recurso': recurso,
        'plano': {
            'tipo': plano.plan_type,
            'nome': plano.name,
            'preco_mensal_kz': kz_inteiro(plano.monthly_price or 0),
            'preco_anual_kz': kz_inteiro(plano.yearly_price) if plano.yearly_price else None,
            'dias_teste': plano.dias_teste or 0,
            'pode_experimentar': pode_experimentar,
        },
        'ganhos': lista_ganhos(plano, recurso),
        'ligacao': f'/user/upgrade?plan={plano.plan_type}',
    }


def oferta_segura(user, recurso, sub=None):
    """oferta() que nunca deita abaixo a resposta do limite."""
    import logging
    try:
        return oferta(user, recurso, sub)
    except Exception:
        logging.getLogger(__name__).exception('oferta de plano falhou (recurso=%s)', recurso)
        return None
