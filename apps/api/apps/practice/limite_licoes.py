"""
Limite diário de lições NOVAS (plano Gratuito: SubscriptionPlan.daily_lessons_limit, p.ex. 3).

- O dia é o de Angola (Africa/Luanda), não o do servidor (TIME_ZONE='UTC').
- Conta uma lição quando é concluída pela primeira vez (LessonCompletion criada nesse dia).
- Repetir uma lição já concluída nunca conta e é sempre permitido.
- Uma lição começada antes de o limite ser atingido (primeira resposta antes da conclusão que
  esgotou o limite) pode ser terminada e aberta outra vez.
- Limite None/0 (Premium, Premium Plus) = ilimitado. Uma assinatura paga expirada usa o
  limite do plano gratuito.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')
CODIGO = 'limite_licoes'


def hoje_luanda(agora=None):
    return timezone.localtime(agora or timezone.now(), FUSO_ANGOLA).date()


def inicio_do_dia(dia):
    """Meia-noite (Luanda) do dia dado, como datetime com fuso."""
    return datetime.combine(dia, time.min, tzinfo=FUSO_ANGOLA)


def proxima_meia_noite(agora=None):
    return inicio_do_dia(hoje_luanda(agora) + timedelta(days=1))


def _conclusoes_de_hoje(user, agora=None):
    from apps.practice.models import LessonCompletion
    inicio = inicio_do_dia(hoje_luanda(agora))
    return LessonCompletion.objects.filter(
        user=user, first_completed_at__gte=inicio, first_completed_at__lt=inicio + timedelta(days=1))


def licoes_novas_hoje(user, agora=None):
    return _conclusoes_de_hoje(user, agora).count()


def limite_do_plano(sub):
    """Lições novas por dia (None = ilimitado) segundo o plano efectivo da assinatura."""
    from apps.practice.conversa.quota import _plano_efectivo
    plano, _ = _plano_efectivo(sub)
    return plano.daily_lessons_limit or None


def _assinatura(user):
    from apps.subscriptions.services import obter_ou_criar_assinatura
    return obter_ou_criar_assinatura(user)


def estado(user, sub=None):
    """{feitas, limite, renova_em} para o ecrã (limite None = ilimitado)."""
    sub = sub or _assinatura(user)
    return {
        'feitas': licoes_novas_hoje(user),
        'limite': limite_do_plano(sub),
        'renova_em': proxima_meia_noite().isoformat(),
    }


def erro_limite(user, lesson, sub=None):
    """
    None se a pessoa pode fazer (ou terminar) esta lição agora; caso contrário o corpo do 403.
    """
    from apps.practice.models import ChallengeProgress, LessonCompletion

    sub = sub or _assinatura(user)
    limite = limite_do_plano(sub)
    if not limite:
        return None
    if LessonCompletion.objects.filter(user=user, lesson=lesson).exists():
        return None  # repetição: sempre permitida
    hoje = list(_conclusoes_de_hoje(user).order_by('first_completed_at')
                .values_list('first_completed_at', flat=True)[:limite])
    if len(hoje) < limite:
        return None
    momento_limite = hoje[limite - 1]
    comecou = (ChallengeProgress.objects.filter(user=user, challenge__lesson=lesson)
               .order_by('completed_at').values_list('completed_at', flat=True).first())
    if comecou is not None and comecou < momento_limite:
        return None  # começou antes de esgotar o limite: pode terminar
    feitas = licoes_novas_hoje(user)
    return {
        'codigo': CODIGO,
        'mensagem': (f'Já fez as {limite} lições novas de hoje. Amanhã há mais, ou assine um plano '
                     'para lições sem limite.'),
        'limite': limite,
        'feitas': feitas,
        'renova_em': proxima_meia_noite().isoformat(),
        'oferta': _oferta(user, sub),
    }


def _oferta(user, sub):
    from apps.subscriptions.oferta import LICOES, oferta_segura
    return oferta_segura(user, LICOES, sub)
