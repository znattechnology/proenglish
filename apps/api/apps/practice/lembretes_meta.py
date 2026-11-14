"""
Lembrete diário da meta de estudo (``manage.py enviar_lembretes_meta``, cron a cada 15 min).

Para cada aluno com o lembrete ligado cuja hora (Africa/Luanda) caiu nos últimos
15 minutos, e que ainda não cumpriu a meta de hoje, cria um aviso in-app (+ push)
"Faltam N minutos para a meta de hoje". No máximo um lembrete por dia e aluno.

Janela: hora em ]agora - 15 min, agora] (hora de Angola). Assim o lembrete nunca
chega antes da hora escolhida, e um cron atrasado alguns minutos não o perde.
"""

import math
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')
JANELA = timedelta(minutes=15)
LINK_APRENDER = '/user/laboratory/learn'


def janela(agora=None):
    fim = timezone.localtime(agora or timezone.now(), FUSO_ANGOLA)
    return fim - JANELA, fim


def _filtro_hora(inicio, fim):
    if inicio.date() == fim.date():
        return Q(lembrete_hora__gt=inicio.time(), lembrete_hora__lte=fim.time())
    # a janela atravessa a meia-noite
    return Q(lembrete_hora__gt=inicio.time()) | Q(lembrete_hora__lte=fim.time())


def textos_lembrete(goal, feitos, streak, dia):
    falta = max(1, math.ceil(goal - feitos))
    title = ('Falta 1 minuto para a meta de hoje' if falta == 1
             else f'Faltam {falta} minutos para a meta de hoje')
    sequencia = streak.get_effective_streak(dia) if streak else 0
    if sequencia > 0 and streak.last_practice_date and streak.last_practice_date < dia:
        dias = '1 dia' if sequencia == 1 else f'{sequencia} dias'
        body = f'Uma lição curta chega para não perder a sua sequência de {dias}.'
    else:
        body = 'Uma lição curta chega.'
    return title, body


def enviar_lembretes_meta(agora=None, dry_run=False):
    """Devolve {'enviados': [...user_id], 'meta_cumprida': n, 'ja_enviados': n}."""
    from apps.users.models import Notification, PreferenciasAvisos
    from .models import DailyStudyLog, UserStreak

    agora = agora or timezone.now()
    inicio, fim = janela(agora)
    dia_aviso = fim.date()  # dia em Angola (deduplicação)
    dia_log = timezone.localdate(agora)  # o mesmo dia que DailyStudyLog.add_minutes usa
    chave = f'lembrete-meta:{dia_aviso.isoformat()}'

    prefs = list(
        PreferenciasAvisos.objects
        .filter(_filtro_hora(inicio, fim), lembrete_ligado=True, user__is_active=True)
        .select_related('user')
    )
    ids = [p.user_id for p in prefs]
    logs = {l.user_id: l for l in DailyStudyLog.objects.filter(user_id__in=ids, date=dia_log)}
    streaks = {s.user_id: s for s in UserStreak.objects.filter(user_id__in=ids)}
    ja = set(Notification.objects.filter(user_id__in=ids, dedupe_key=chave).values_list('user_id', flat=True))

    resultado = {'enviados': [], 'meta_cumprida': 0, 'ja_enviados': 0}
    for p in prefs:
        if p.user_id in ja:
            resultado['ja_enviados'] += 1
            continue
        streak = streaks.get(p.user_id)
        goal = streak.daily_goal_minutes if streak else UserStreak.DEFAULT_DAILY_GOAL_MINUTES
        log = logs.get(p.user_id)
        feitos = log.total_minutes if log else 0
        if log and (log.goal_met_at is not None or feitos >= goal):
            resultado['meta_cumprida'] += 1
            continue
        title, body = textos_lembrete(goal, feitos, streak, dia_log)
        if not dry_run:
            # O lembrete tem o seu próprio interruptor (lembrete.ligado), por isso
            # não depende de tipos.meta.
            criado = Notification.notify(
                p.user, Notification.KIND_STREAK, title=title, body=body,
                link=LINK_APRENDER, dedupe_key=chave, respeitar_preferencias=False,
            )
            if criado is None:
                resultado['ja_enviados'] += 1
                continue
        resultado['enviados'].append((p.user_id, title, body))
    return resultado
