"""
Study tracking services: hearts status/refill, lesson completion, streak and
daily goal, review words and student analytics.

Kept out of the (already very large) practice views module so the logic can
be reused by other entry points (video progress, VAPI sessions) and tested
directly.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Max, Min, Q, Sum, Avg
from django.utils import timezone

from apps.practice.models import (
    ChallengeAttempt,
    ChallengeProgress,
    DailyStudyLog,
    LessonCompletion,
    PracticeChallenge,
    PracticeLesson,
    UserProgress,
    UserStreak,
    VapiSession,
)

logger = logging.getLogger(__name__)

REFILL_HEARTS_COST_POINTS = 50
FIRST_COMPLETION_BONUS_POINTS = 10
REPEAT_PRACTICE_POINTS = 5
REPEAT_PRACTICE_HEARTS = 1
UNLIMITED_HEARTS_VALUE = 999
DEFAULT_MAX_HEARTS = 5
MAX_LESSON_DURATION_SECONDS = 60 * 60
REVIEW_WINDOW_DAYS = 14
REVIEW_LIMIT = 20

WEEKDAY_LABELS_PT = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


# ---------------------------------------------------------------------------
# Hearts
# ---------------------------------------------------------------------------

def _get_subscription(user):
    from apps.subscriptions.models import UserSubscription
    return UserSubscription.objects.select_related('plan').filter(user=user).first()


def get_hearts_state(user):
    """Return the user's hearts state (recharging first if due)."""
    sub = _get_subscription(user)
    if sub is not None and sub.plan is not None:
        if sub.plan.hearts_limit == 0 and sub.is_active():
            return {
                'current': UNLIMITED_HEARTS_VALUE,
                'maximum': UNLIMITED_HEARTS_VALUE,
                'unlimited': True,
                'recharge_hours': None,
                'next_heart_at': None,
            }
        maximum = sub.plan.hearts_limit if sub.plan.hearts_limit > 0 else DEFAULT_MAX_HEARTS
        if sub.plan.hearts_limit > 0:
            sub.recharge_hearts_if_needed()
        current = min(sub.current_hearts, maximum)
        recharge_hours = sub.plan.hearts_recharge_hours or None
        next_heart_at = None
        if current < maximum and recharge_hours:
            next_heart_at = sub.last_heart_recharge + timedelta(hours=recharge_hours)
        return {
            'current': current,
            'maximum': maximum,
            'unlimited': False,
            'recharge_hours': recharge_hours,
            'next_heart_at': next_heart_at,
        }

    # No subscription: legacy hearts on UserProgress, no automatic recharge
    progress = UserProgress.objects.filter(user=user).first()
    current = progress._hearts_legacy if progress else DEFAULT_MAX_HEARTS
    return {
        'current': min(current, DEFAULT_MAX_HEARTS),
        'maximum': DEFAULT_MAX_HEARTS,
        'unlimited': False,
        'recharge_hours': None,
        'next_heart_at': None,
    }


def build_hearts_status(user):
    state = get_hearts_state(user)
    points = UserProgress.objects.filter(user=user).values_list('points', flat=True).first() or 0
    can_refill = (
        not state['unlimited']
        and state['current'] < state['maximum']
        and points >= REFILL_HEARTS_COST_POINTS
    )
    return {
        'current': state['current'],
        'maximum': state['maximum'],
        'unlimited': state['unlimited'],
        'recharge_hours': state['recharge_hours'],
        'next_heart_at': state['next_heart_at'].isoformat() if state['next_heart_at'] else None,
        'refill_cost_points': REFILL_HEARTS_COST_POINTS,
        'can_refill_with_points': can_refill,
        'points': points,
        # Lições novas de hoje (dia de Angola) e o limite do plano (None = ilimitado).
        'licoes_hoje': licoes_hoje(user),
    }


def licoes_hoje(user):
    from apps.practice import limite_licoes
    return limite_licoes.estado(user)


def refill_hearts_with_points(user):
    """
    Spend REFILL_HEARTS_COST_POINTS points to refill hearts to the plan maximum.

    Returns (payload, is_error).
    """
    from apps.subscriptions.models import UserSubscription

    with transaction.atomic():
        progress, _ = UserProgress.objects.get_or_create(user=user, defaults={'points': 0})
        progress = UserProgress.objects.select_for_update().get(pk=progress.pk)
        state = get_hearts_state(user)

        if state['unlimited']:
            return {
                'hearts': UNLIMITED_HEARTS_VALUE,
                'points': progress.points,
                'unlimited': True,
                'points_spent': 0,
                'message': 'O seu plano tem vidas ilimitadas.',
            }, False

        if state['current'] >= state['maximum']:
            return {
                'error': 'hearts_full',
                'message': 'As suas vidas já estão no máximo.',
                'hearts': state['current'],
                'points': progress.points,
            }, True

        if progress.points < REFILL_HEARTS_COST_POINTS:
            return {
                'error': 'insufficient_points',
                'message': f'Pontos insuficientes. Precisa de {REFILL_HEARTS_COST_POINTS} pontos para recarregar as vidas.',
                'required_points': REFILL_HEARTS_COST_POINTS,
                'points': progress.points,
                'hearts': state['current'],
            }, True

        UserProgress.objects.filter(pk=progress.pk).update(points=F('points') - REFILL_HEARTS_COST_POINTS)
        sub = _get_subscription(user)
        if sub is not None:
            UserSubscription.objects.filter(pk=sub.pk).update(
                current_hearts=state['maximum'], last_heart_recharge=timezone.now()
            )
        else:
            UserProgress.objects.filter(pk=progress.pk).update(_hearts_legacy=state['maximum'])
        progress.refresh_from_db()

    return {
        'hearts': state['maximum'],
        'points': progress.points,
        'points_spent': REFILL_HEARTS_COST_POINTS,
        'message': 'Vidas recarregadas com sucesso.',
    }, False


# ---------------------------------------------------------------------------
# Streak & daily goal
# ---------------------------------------------------------------------------

def get_or_create_streak(user):
    streak, _ = UserStreak.objects.get_or_create(user=user)
    return streak


def minutes_for_date(user, day):
    log = DailyStudyLog.objects.filter(user=user, date=day).first()
    return log.total_minutes if log else 0.0


def build_streak_payload(user):
    today = timezone.localdate()
    streak = get_or_create_streak(user)
    goal = streak.daily_goal_minutes
    start = today - timedelta(days=6)
    logs = {
        log.date: log
        for log in DailyStudyLog.objects.filter(user=user, date__gte=start, date__lte=today)
    }
    week = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        log = logs.get(day)
        minutes = log.total_minutes if log else 0.0
        week.append({
            'date': day.isoformat(),
            'minutes': int(minutes),
            'goal_met': bool(log and (log.goal_met_at is not None or minutes >= goal)),
        })
    today_log = logs.get(today)
    minutes_today = today_log.total_minutes if today_log else 0.0
    return {
        'current_streak': streak.get_effective_streak(today),
        'longest_streak': streak.longest_streak,
        'last_study_date': streak.last_practice_date.isoformat() if streak.last_practice_date else None,
        'practiced_today': streak.last_practice_date == today,
        'daily_goal_minutes': goal,
        'minutes_today': int(minutes_today),
        'goal_completed': bool(today_log and (today_log.goal_met_at is not None or minutes_today >= goal)),
        'week': week,
    }


# ---------------------------------------------------------------------------
# Lesson completion
# ---------------------------------------------------------------------------

class LessonLimitReached(Exception):
    """Plano com limite de lições novas por dia já atingido (corpo do 403 em .payload)."""
    def __init__(self, payload):
        self.payload = payload
        super().__init__(payload.get('mensagem', ''))


class LessonNotCompleted(Exception):
    def __init__(self, completed, total):
        self.completed = completed
        self.total = total
        super().__init__(f"{completed}/{total}")


FOLGA_LICAO_SEGUNDOS = 60  # ler o primeiro exercício antes da primeira resposta


def duracao_medida(user, lesson, duracao_cliente, agora=None):
    """
    Segundos de estudo a creditar por uma lição: o que o cliente diz, mas nunca mais do que o tempo
    que o servidor viu passar desde a primeira resposta desta volta da lição (mais uma folga para ler
    o primeiro exercício) nem mais de MAX_LESSON_DURATION_SECONDS. Sem isto, o cliente podia declarar
    60 min por cada lição de 5 min e encher a meta diária e a sequência.
    """
    agora = agora or timezone.now()
    try:
        pedido = max(0, int(duracao_cliente or 0))
    except (TypeError, ValueError):
        pedido = 0
    respostas = ChallengeProgress.objects.filter(user=user, challenge__lesson=lesson, completed=True)
    anterior = LessonCompletion.objects.filter(user=user, lesson=lesson).values_list('last_completed_at', flat=True).first()
    if anterior is not None:
        respostas = respostas.filter(updated_at__gt=anterior)  # só a volta actual ("praticar de novo")
    inicio = respostas.aggregate(inicio=Min('updated_at'))['inicio']
    medido = int((agora - inicio).total_seconds()) + FOLGA_LICAO_SEGUNDOS if inicio else 0
    return max(0, min(pedido, medido, MAX_LESSON_DURATION_SECONDS))


def complete_lesson(user, lesson, duration_seconds):
    """
    Record a lesson completion.

    - First completion: +FIRST_COMPLETION_BONUS_POINTS (idempotent per user/lesson).
    - Repeat ("praticar de novo"): +REPEAT_PRACTICE_POINTS and +1 heart (capped,
      no-op for unlimited), only when every challenge was answered correctly
      again since the previous completion. Otherwise nothing is awarded
      (protects against double submits / farming).
    - Adds the (clamped) duration to today's study log and updates the streak.
    """
    total = lesson.challenges.count()
    completed_qs = ChallengeProgress.objects.filter(user=user, challenge__lesson=lesson, completed=True)
    completed = completed_qs.count()
    if total == 0 or completed < total:
        raise LessonNotCompleted(completed, total)

    from apps.practice import limite_licoes
    limit_error = limite_licoes.erro_limite(user, lesson)
    if limit_error:
        raise LessonLimitReached(limit_error)

    now = timezone.now()
    duration_seconds = duracao_medida(user, lesson, duration_seconds, now)
    points_awarded = 0
    hearts_awarded = 0
    recorded = True

    with transaction.atomic():
        progress, _ = UserProgress.objects.get_or_create(user=user, defaults={'points': 0})
        completion, created = LessonCompletion.objects.get_or_create(
            user=user, lesson=lesson, defaults={'last_completed_at': now}
        )
        if created:
            first_completion = True
            points_awarded = FIRST_COMPLETION_BONUS_POINTS
        else:
            first_completion = False
            completion = LessonCompletion.objects.select_for_update().get(pk=completion.pk)
            replayed = completed_qs.filter(updated_at__gt=completion.last_completed_at).count()
            if replayed >= total:
                points_awarded = REPEAT_PRACTICE_POINTS
                completion.times_completed = F('times_completed') + 1
                completion.last_completed_at = now
                completion.save(update_fields=['times_completed', 'last_completed_at'])
                estado = get_hearts_state(user)
                # Só conta como vida ganha se ainda havia espaço (com as vidas cheias: 0).
                if not estado['unlimited'] and estado['current'] < estado['maximum']:
                    hearts_awarded = min(REPEAT_PRACTICE_HEARTS, estado['maximum'] - estado['current'])
                    progress.add_hearts(hearts_awarded)
            else:
                recorded = False

        if points_awarded:
            progress.add_points(points_awarded, reason='lesson', curso_id=lesson.unit.course_id)

    if first_completion:
        # Mantém UserSubscription.daily_lessons_used igual às lições novas de hoje (dia de Angola).
        from apps.subscriptions.models import UserSubscription
        UserSubscription.objects.filter(user=user).update(
            daily_lessons_used=limite_licoes.licoes_novas_hoje(user))

    if recorded:
        study = DailyStudyLog.add_minutes(
            user, DailyStudyLog.KIND_LESSON, duration_seconds / 60.0, lessons_completed=1
        )
        streak = study['streak']
        minutes_today = study['log'].total_minutes
        goal = study['goal_minutes']
        goal_completed = study['goal_completed']
        goal_just_completed = study['goal_just_completed']
    else:
        streak = get_or_create_streak(user)
        goal = streak.daily_goal_minutes
        today_log = DailyStudyLog.objects.filter(user=user, date=timezone.localdate()).first()
        minutes_today = today_log.total_minutes if today_log else 0.0
        goal_completed = bool(today_log and today_log.goal_met_at)
        goal_just_completed = False

    progress.refresh_from_db()
    return {
        'first_completion': first_completion,
        'points_awarded': points_awarded,
        'hearts_awarded': hearts_awarded,
        'already_recorded': not recorded,
        'total_points': progress.points,
        'hearts': get_hearts_state(user)['current'],
        'streak': streak.get_effective_streak(),
        'minutes_today': int(minutes_today),
        'daily_goal_minutes': goal,
        'goal_completed': goal_completed,
        'goal_just_completed': goal_just_completed,
    }


# ---------------------------------------------------------------------------
# Review words
# ---------------------------------------------------------------------------

def _challenge_answer(challenge):
    options = sorted(challenge.options.all(), key=lambda o: o.order)
    if challenge.type == 'SENTENCE_ORDER':
        return ' '.join(o.text for o in options)
    if challenge.type == 'MATCH_PAIRS':
        return '; '.join(o.text for o in options)
    return ' / '.join(o.text for o in options if o.is_correct)


def pending_review_queryset(user, now=None):
    """Challenges answered wrong in the window and not answered correctly since."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=REVIEW_WINDOW_DAYS)
    return (
        ChallengeAttempt.objects.filter(user=user)
        .values('challenge_id')
        .annotate(
            last_wrong=Max('created_at', filter=Q(is_correct=False)),
            last_correct=Max('created_at', filter=Q(is_correct=True)),
        )
        .filter(last_wrong__gte=cutoff)
        .filter(Q(last_correct__isnull=True) | Q(last_correct__lt=F('last_wrong')))
        .order_by('-last_wrong')
    )


def build_review_words(user):
    pending = pending_review_queryset(user)
    count = pending.count()
    rows = list(pending[:REVIEW_LIMIT])
    challenges = PracticeChallenge.objects.filter(
        id__in=[r['challenge_id'] for r in rows]
    ).select_related('lesson').prefetch_related('options').in_bulk()
    items = []
    for row in rows:
        ch = challenges.get(row['challenge_id'])
        if ch is None:
            continue
        items.append({
            'challenge_id': str(ch.id),
            'type': ch.type,
            'prompt': ch.question,
            'answer': _challenge_answer(ch),
            'lesson_id': str(ch.lesson_id),
            'lesson_title': ch.lesson.title,
            'last_wrong_at': row['last_wrong'].isoformat(),
        })
    return {'count': count, 'items': items}


# ---------------------------------------------------------------------------
# Course detail progress
# ---------------------------------------------------------------------------

def course_lesson_progress(user, course):
    """(completed_lessons, total_lessons, challenges_count) using a single aggregate query."""
    lessons = PracticeLesson.objects.filter(unit__course=course).annotate(
        total=Count('challenges', distinct=True),
        done=Count(
            'challenges__user_progress',
            filter=Q(challenges__user_progress__user=user, challenges__user_progress__completed=True),
            distinct=True,
        ),
    ).values_list('total', 'done')
    total_lessons = 0
    completed = 0
    challenges = 0
    for total, done in lessons:
        total_lessons += 1
        challenges += total
        if total > 0 and done >= total:
            completed += 1
    return completed, total_lessons, challenges


# ---------------------------------------------------------------------------
# Student analytics (shape read by apps/web/app/(dashboard)/user/analytics/page.tsx)
# ---------------------------------------------------------------------------

CATEGORY_BY_TYPE = {
    'SELECT': 'Vocabulário',
    'ASSIST': 'Vocabulário',
    'MATCH_PAIRS': 'Vocabulário',
    'TRUE_FALSE': 'Vocabulário',
    'FILL_BLANK': 'Gramática',
    'SENTENCE_ORDER': 'Gramática',
    'TRANSLATION': 'Tradução',
    'LISTENING': 'Compreensão',
    'SPEAKING': 'Pronúncia',
    'RESPONDER': 'Conversação',
    'VAPI_CONVERSATION': 'Conversação',
}


def _pct(part, whole):
    return round(part * 100.0 / whole) if whole else None


def _week_minutes(user, start, end):
    agg = DailyStudyLog.objects.filter(user=user, date__gte=start, date__lte=end).aggregate(
        lesson=Sum('lesson_minutes'), video=Sum('video_minutes'), conv=Sum('conversation_minutes')
    )
    return (agg['lesson'] or 0) + (agg['video'] or 0) + (agg['conv'] or 0)


def build_student_analytics(user):
    today = timezone.localdate()
    now = timezone.now()
    streak = get_or_create_streak(user)
    goal = streak.daily_goal_minutes
    progress = UserProgress.objects.filter(user=user).first()
    points = progress.points if progress else 0

    # ---- Overview -------------------------------------------------------
    totals = DailyStudyLog.objects.filter(user=user).aggregate(
        lesson=Sum('lesson_minutes'), video=Sum('video_minutes'), conv=Sum('conversation_minutes')
    )
    total_minutes = (totals['lesson'] or 0) + (totals['video'] or 0) + (totals['conv'] or 0)
    attempts = ChallengeAttempt.objects.filter(user=user).aggregate(
        total=Count('id'), correct=Count('id', filter=Q(is_correct=True))
    )
    week_start = today - timedelta(days=6)
    this_week_minutes = _week_minutes(user, week_start, today)
    weekly_goal_progress = min(100, round(this_week_minutes * 100.0 / (goal * 7))) if goal else 0

    overview = {
        'totalStudyTime': int(total_minutes),
        'lessonsCompleted': LessonCompletion.objects.filter(user=user).count(),
        'averageAccuracy': _pct(attempts['correct'], attempts['total']),
        'currentStreak': streak.get_effective_streak(today),
        'longestStreak': streak.longest_streak,
        'totalPoints': points,
        'weeklyGoalProgress': weekly_goal_progress,
    }

    # ---- Accuracy trend (last 7 days) -----------------------------------
    from django.db.models.functions import TruncDate
    daily_attempts = {
        row['day']: row
        for row in ChallengeAttempt.objects.filter(
            user=user, created_at__date__gte=week_start
        ).annotate(day=TruncDate('created_at')).values('day').annotate(
            total=Count('id'), correct=Count('id', filter=Q(is_correct=True))
        )
    }
    logs = {l.date: l for l in DailyStudyLog.objects.filter(user=user, date__gte=week_start, date__lte=today)}
    accuracy_trend = []
    weekly = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        label = WEEKDAY_LABELS_PT[day.weekday()]
        row = daily_attempts.get(day)
        accuracy_trend.append({
            'date': label,
            'isoDate': day.isoformat(),
            'accuracy': _pct(row['correct'], row['total']) if row else None,
        })
        log = logs.get(day)
        weekly.append({
            'day': label,
            'isoDate': day.isoformat(),
            'lessons': log.lessons_completed if log else 0,
            'timeSpent': int(log.total_minutes) if log else 0,
        })

    # ---- Category performance (by challenge type group) ------------------
    by_type = ChallengeAttempt.objects.filter(user=user).values('challenge__type').annotate(
        total=Count('id'), correct=Count('id', filter=Q(is_correct=True))
    )
    categories = {}
    for row in by_type:
        cat = CATEGORY_BY_TYPE.get(row['challenge__type'], 'Outros')
        c = categories.setdefault(cat, {'total': 0, 'correct': 0})
        c['total'] += row['total']
        c['correct'] += row['correct']
    category_performance = [
        # timeSpent per category is not tracked (only per activity kind)
        {'category': cat, 'accuracy': _pct(c['correct'], c['total']), 'timeSpent': None}
        for cat, c in sorted(categories.items())
    ]
    vapi = VapiSession.objects.filter(user=user, status=VapiSession.STATUS_AVALIADA).aggregate(
        n=Count('session_id'), score=Avg('overall_score')
    )
    if vapi['n']:
        category_performance.append({
            'category': 'Conversação (IA)',
            'accuracy': round(vapi['score'] or 0),
            'timeSpent': int(totals['conv'] or 0),
        })

    # ---- Weak areas / strengths (by lesson, last 30 days) ----------------
    by_lesson = list(
        ChallengeAttempt.objects.filter(user=user, created_at__gte=now - timedelta(days=30))
        .values('challenge__lesson_id', 'challenge__lesson__title')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
        .filter(total__gte=3)
    )
    for row in by_lesson:
        row['accuracy'] = _pct(row['correct'], row['total'])
    weak = sorted([r for r in by_lesson if r['accuracy'] < 70], key=lambda r: r['accuracy'])[:3]
    strong = sorted([r for r in by_lesson if r['accuracy'] >= 85], key=lambda r: -r['accuracy'])[:3]

    strong_examples = {}
    if strong:
        for ch in PracticeChallenge.objects.filter(
            lesson_id__in=[r['challenge__lesson_id'] for r in strong],
            attempts__user=user, attempts__is_correct=True,
        ).distinct().only('id', 'question', 'lesson_id'):
            bucket = strong_examples.setdefault(ch.lesson_id, [])
            if len(bucket) < 3:
                bucket.append(ch.question)

    weak_areas = [{
        'topic': r['challenge__lesson__title'],
        'lessonId': str(r['challenge__lesson_id']),
        'accuracy': r['accuracy'],
        'improvements': [
            f'Rever a lição "{r["challenge__lesson__title"]}"',
            'Praticar de novo até acertar todos os exercícios',
            'Rever as palavras na secção de revisão',
        ],
    } for r in weak]
    strengths = [{
        'topic': r['challenge__lesson__title'],
        'lessonId': str(r['challenge__lesson_id']),
        'accuracy': r['accuracy'],
        'examples': strong_examples.get(r['challenge__lesson_id'], []),
    } for r in strong]

    # ---- Monthly (last 4 weeks, % of weekly goal) ------------------------
    monthly = []
    for i in range(4):
        end = today - timedelta(days=7 * (3 - i))
        start = end - timedelta(days=6)
        minutes = _week_minutes(user, start, end)
        monthly.append({
            'week': f'Sem {i + 1}',
            'progress': min(100, round(minutes * 100.0 / (goal * 7))) if goal else 0,
        })

    # ---- Comparison ------------------------------------------------------
    last_week_minutes = _week_minutes(user, week_start - timedelta(days=7), week_start - timedelta(days=1))
    vs_last_week = (
        round((this_week_minutes - last_week_minutes) * 100.0 / last_week_minutes)
        if last_week_minutes else None
    )
    others = DailyStudyLog.objects.filter(date__gte=week_start, date__lte=today).values('user').annotate(
        m=Sum(F('lesson_minutes') + F('video_minutes') + F('conversation_minutes'))
    ).aggregate(avg=Avg('m'))
    avg_minutes = others['avg'] or 0
    vs_average = round((this_week_minutes - avg_minutes) * 100.0 / avg_minutes) if avg_minutes else None
    total_students = UserProgress.objects.count()
    rank_position = UserProgress.objects.filter(points__gt=points).count() + 1 if progress else None

    # ---- Recommendations -------------------------------------------------
    recommendations = []
    review_count = pending_review_queryset(user).count()
    if weak:
        w = weak[0]
        recommendations.append({
            'id': 'weak-area',
            'type': 'practice',
            'title': f'Concentre-se em "{w["challenge__lesson__title"]}"',
            'description': f'A sua precisão nesta lição está em {w["accuracy"]}%.',
            'action': 'Praticar agora',
            'priority': 'high',
        })
    if review_count:
        recommendations.append({
            'id': 'review-words',
            'type': 'review',
            'title': 'Rever palavras',
            'description': f'Tem {review_count} item(ns) que errou recentemente para rever.',
            'action': 'Rever agora',
            'priority': 'medium',
        })
    today_log = logs.get(today)
    minutes_today = today_log.total_minutes if today_log else 0
    if minutes_today < goal:
        recommendations.append({
            'id': 'daily-goal',
            'type': 'challenge',
            'title': 'Cumpra a meta diária',
            'description': f'Faltam {max(1, int(goal - minutes_today))} min para a sua meta de {goal} min.',
            'action': 'Começar lição',
            'priority': 'medium',
        })
    elif minutes_today >= goal * 3:
        recommendations.append({
            'id': 'take-break',
            'type': 'break',
            'title': 'Pausa recomendada',
            'description': 'Já estudou bastante hoje! Uma pausa ajuda a consolidar o que aprendeu.',
            'action': 'Entendi',
            'priority': 'low',
        })

    return {
        'overview': overview,
        'performance': {
            'accuracyTrend': accuracy_trend,
            'categoryPerformance': category_performance,
            'weakAreas': weak_areas,
            'strengths': strengths,
        },
        'progress': {
            'weekly': weekly,
            'monthly': monthly,
            'comparison': {
                'vsLastWeek': vs_last_week,
                'vsAverage': vs_average,
                'rankPosition': rank_position,
                'totalStudents': total_students,
            },
        },
        'recommendations': recommendations,
    }
