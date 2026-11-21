"""
Estatísticas de estudo do aluno para um período (7 dias, 30 dias ou tudo).

Fontes (todas tabelas reais):
- DailyStudyLog: minutos por dia (lições, vídeo, conversação) e lições concluídas por dia;
  é a ÚNICA fonte de minutos (também os da conversação)
- UserStreak: sequência actual / maior e meta diária
- ChallengeAttempt: respostas certas / total, por tipo de exercício
- VapiSession: conversas com o tutor (número de sessões e pontuações, não minutos)

Os dias seguem timezone.localdate() / TIME_ZONE, como o DailyStudyLog.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone

from apps.practice.models import ChallengeAttempt, DailyStudyLog, VapiSession

PERIODOS = {'7': 7, '30': 30, 'tudo': None}
PERIODO_PADRAO = '7'
MAX_DIAS_TUDO = 366  # o gráfico "por dia" de "tudo" fica limitado ao último ano

WEEKDAY_LABELS_PT = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

ROTULOS_TIPO = {
    'SELECT': 'Escolha múltipla',
    'ASSIST': 'Escolher a tradução',
    'TRUE_FALSE': 'Verdadeiro ou falso',
    'FILL_BLANK': 'Completar a frase',
    'SENTENCE_ORDER': 'Ordenar a frase',
    'MATCH_PAIRS': 'Associar pares',
    'TRANSLATION': 'Tradução',
    'LISTENING': 'Compreensão oral',
    'SPEAKING': 'Pronúncia',
    'RESPONDER': 'Responder em voz alta',
    'VAPI_CONVERSATION': 'Conversação',
}
GRUPO_TIPO = {
    'SELECT': 'escolha', 'ASSIST': 'escolha', 'TRUE_FALSE': 'escolha', 'MATCH_PAIRS': 'escolha',
    'FILL_BLANK': 'escrita', 'SENTENCE_ORDER': 'escrita',
    'TRANSLATION': 'traducao',
    'LISTENING': 'audicao',
    'SPEAKING': 'pronuncia',
    'RESPONDER': 'conversacao',
    'VAPI_CONVERSATION': 'conversacao',
}


def _pct(part, whole):
    return round(part * 100.0 / whole) if whole else None


def _minutos(qs):
    agg = qs.aggregate(l=Sum('lesson_minutes'), v=Sum('video_minutes'), c=Sum('conversation_minutes'),
                       n=Sum('lessons_completed'))
    return {
        'licoes': agg['l'] or 0.0, 'videos': agg['v'] or 0.0, 'conversacao': agg['c'] or 0.0,
        'licoes_concluidas': agg['n'] or 0,
    }


def _variacao(atual, anterior):
    if anterior is None:
        return None, None
    dif = atual - anterior
    return dif, (round(dif * 100.0 / anterior) if anterior else None)


def construir_estatisticas(user, periodo=PERIODO_PADRAO):
    if periodo not in PERIODOS:
        raise ValueError(periodo)
    from apps.practice.study_services import get_or_create_streak

    hoje = timezone.localdate()
    dias = PERIODOS[periodo]
    logs_user = DailyStudyLog.objects.filter(user=user)
    tentativas_user = ChallengeAttempt.objects.filter(user=user)

    if dias:
        inicio = hoje - timedelta(days=dias - 1)
        ant_inicio, ant_fim = inicio - timedelta(days=dias), inicio - timedelta(days=1)
    else:
        primeiro_log = logs_user.aggregate(d=Min('date'))['d']
        primeira_tentativa = tentativas_user.aggregate(d=Min('created_at'))['d']
        primeiros = [primeiro_log] if primeiro_log else []
        if primeira_tentativa:
            primeiros.append(timezone.localtime(primeira_tentativa).date())
        inicio = min(primeiros) if primeiros else hoje
        ant_inicio = ant_fim = None

    logs = logs_user.filter(date__gte=inicio, date__lte=hoje)
    m = _minutos(logs)
    total_min = m['licoes'] + m['videos'] + m['conversacao']
    if ant_inicio:
        ma = _minutos(logs_user.filter(date__gte=ant_inicio, date__lte=ant_fim))
        total_ant = ma['licoes'] + ma['videos'] + ma['conversacao']
        licoes_ant = ma['licoes_concluidas']
    else:
        total_ant = licoes_ant = None

    streak = get_or_create_streak(user)
    meta = streak.daily_goal_minutes

    # ---- minutos por dia (uma barra por dia) -----------------------------
    por_data = {l.date: l for l in logs}
    inicio_barras = max(inicio, hoje - timedelta(days=MAX_DIAS_TUDO - 1))
    minutos_por_dia = []
    d = inicio_barras
    while d <= hoje:
        log = por_data.get(d)
        minutos = log.total_minutes if log else 0.0
        minutos_por_dia.append({
            'data': d.isoformat(),
            'dia_semana': WEEKDAY_LABELS_PT[d.weekday()],
            'minutos': round(minutos),
            'meta_cumprida': bool(log and (log.goal_met_at is not None or minutos >= meta)),
        })
        d += timedelta(days=1)

    # ---- respostas -------------------------------------------------------
    tentativas = tentativas_user.filter(created_at__date__gte=inicio, created_at__date__lte=hoje)
    agg = tentativas.aggregate(total=Count('id'), certas=Count('id', filter=Q(is_correct=True)))
    por_tipo = []
    for row in (tentativas.values('challenge__type')
                .annotate(total=Count('id'), certas=Count('id', filter=Q(is_correct=True)))
                .order_by('-total')):
        t = row['challenge__type']
        por_tipo.append({
            'tipo': t,
            'rotulo': ROTULOS_TIPO.get(t, t.title()),
            'grupo': GRUPO_TIPO.get(t, 'outros'),
            'certas': row['certas'],
            'total': row['total'],
            'percentagem': _pct(row['certas'], row['total']),
        })

    # ---- conversação com o tutor (VapiSession) ---------------------------
    # Contam as conversas terminadas; as notas só das avaliadas (sem as "sem avaliação").
    sessoes = VapiSession.objects.filter(user=user, date__gte=inicio, date__lte=hoje,
                                         status__in=VapiSession.STATUS_TERMINADAS)
    av = Q(status=VapiSession.STATUS_AVALIADA)
    va = sessoes.aggregate(
        n=Count('session_id'), media=Avg('overall_score', filter=av),
        melhor=Max('overall_score', filter=av), fluencia=Avg('fluency_score', filter=av),
        pronuncia=Avg('pronunciation_score', filter=av),
        gramatica=Avg('grammar_score', filter=av), vocabulario=Avg('vocabulary_score', filter=av),
    )
    ultima = sessoes.filter(av).order_by('-created_at').first()

    def _r(v):
        return round(v) if v is not None else None

    conversacao = {
        'sessoes': va['n'],
        # Minutos: a mesma fonte de tempo_estudo.por_tipo.conversacao (DailyStudyLog, segundos
        # reais da chamada). VapiSession só dá o número de sessões e as pontuações.
        'minutos': round(m['conversacao']),
        'pontuacao_media': _r(va['media']),
        'melhor_pontuacao': va['melhor'],
        'criterios': {
            'fluencia': _r(va['fluencia']), 'pronuncia': _r(va['pronuncia']),
            'gramatica': _r(va['gramatica']), 'vocabulario': _r(va['vocabulario']),
        },
        'ultima_sessao': None if ultima is None else {
            'data': ultima.date.isoformat(),
            'pontuacao': ultima.overall_score,
            'duracao_minutos': ultima.duration_minutes,
            'nivel': ultima.level,
            'tema': ultima.domain,
            'variacao_vs_anterior': round(ultima.improvement_from_last),
            'resumo': (ultima.full_session_data or {}).get('summary') or None,
        },
    }

    var_min, var_min_pct = _variacao(round(total_min), round(total_ant) if total_ant is not None else None)
    var_lic, var_lic_pct = _variacao(m['licoes_concluidas'], licoes_ant)
    return {
        'periodo': periodo,
        'inicio': inicio.isoformat(),
        'fim': hoje.isoformat(),
        'dias': (hoje - inicio).days + 1,
        'meta_diaria_minutos': meta,
        'tempo_estudo': {
            'minutos': round(total_min),
            'por_tipo': {k: round(m[k]) for k in ('licoes', 'videos', 'conversacao')},
            'periodo_anterior': round(total_ant) if total_ant is not None else None,
            'variacao': var_min,
            'variacao_pct': var_min_pct,
        },
        'licoes_concluidas': {
            'total': m['licoes_concluidas'],
            'periodo_anterior': licoes_ant,
            'variacao': var_lic,
            'variacao_pct': var_lic_pct,
        },
        'sequencia': {
            'atual': streak.get_effective_streak(hoje),
            'maior': streak.longest_streak,
            'estudou_hoje': streak.last_practice_date == hoje,
        },
        'respostas': {
            'certas': agg['certas'],
            'total': agg['total'],
            'percentagem': _pct(agg['certas'], agg['total']),
        },
        'dias_meta_cumprida': sum(1 for x in minutos_por_dia if x['meta_cumprida']),
        'minutos_por_dia': minutos_por_dia,
        'por_tipo_exercicio': por_tipo,
        'conversacao': conversacao,
    }
