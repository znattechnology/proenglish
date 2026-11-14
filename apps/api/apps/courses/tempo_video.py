"""
Minutos de vídeo declarados pelo browser (PUT .../progress/<courseId>/update/ com watched_seconds).

O browser envia "segundos vistos desde o último envio". Antes bastava enviar
watched_seconds=99999 para ganhar 60 minutos por pedido, quantas vezes se quisesse. Agora:

- por pedido: no máximo a duração do vídeo do capítulo (se for conhecida) ou 30 minutos;
- por capítulo e por dia: no máximo a duração do vídeo (ou 30 minutos); reenviar não soma;
- se já houve um envio hoje para o capítulo, no máximo o tempo real que passou desde então
  (mais uma pequena folga);
- só o que é novo (delta) vai para o DailyStudyLog.
"""
from django.db import transaction
from django.utils import timezone

MAXIMO_SEM_DURACAO = 30 * 60  # segundos
FOLGA_SEGUNDOS = 15
CHAVES_DURACAO = ('duration_seconds', 'duracao_segundos', 'video_duration', 'duration')


def duracao_do_video(chapter):
    """Duração do vídeo em segundos (Chapter.duracao_s ou, nos antigos, os metadados); senão None."""
    if getattr(chapter, 'duracao_s', None):
        return int(chapter.duracao_s)
    meta = getattr(chapter, 'metadata', None) or {}
    for chave in CHAVES_DURACAO:
        valor = meta.get(chave) if isinstance(meta, dict) else None
        try:
            n = int(float(valor))
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


def creditar_segundos(user, chapter, segundos_declarados):
    """
    Regista os segundos de vídeo que contam e devolve quantos foram creditados (0 se nenhum).
    Os minutos creditados vão para DailyStudyLog (vídeo).
    """
    from apps.courses.models import VideoWatchLog

    try:
        declarados = int(float(segundos_declarados))
    except (TypeError, ValueError):
        return 0
    if declarados <= 0 or chapter is None:
        return 0

    limite = duracao_do_video(chapter) or MAXIMO_SEM_DURACAO
    pedido = min(declarados, limite)
    hoje = timezone.localdate()
    agora = timezone.now()

    with transaction.atomic():
        registo, criado = VideoWatchLog.objects.get_or_create(user=user, chapter=chapter, date=hoje)
        registo = VideoWatchLog.objects.select_for_update().get(pk=registo.pk)
        if not criado and registo.seconds > 0:
            passou = (agora - registo.updated_at).total_seconds() + FOLGA_SEGUNDOS
            pedido = min(pedido, max(0, int(passou)))
        novo = max(0, min(pedido, limite - registo.seconds))
        if novo <= 0:
            return 0
        registo.seconds += novo
        registo.save(update_fields=['seconds', 'updated_at'])

    from apps.practice.models import DailyStudyLog
    DailyStudyLog.add_minutes(user, DailyStudyLog.KIND_VIDEO, novo / 60.0)
    return novo


def segundos_vistos(user, chapter):
    """Segundos de vídeo já creditados ao aluno neste capítulo (todos os dias)."""
    from django.db.models import Sum
    from apps.courses.models import VideoWatchLog
    return VideoWatchLog.objects.filter(user=user, chapter=chapter).aggregate(s=Sum('seconds'))['s'] or 0


def aula_vista(user, chapter):
    """
    A aula conta como vista quando o aluno viu pelo menos Chapter.percentagem_vista (50, 80 ou
    100%) da duração do vídeo. Sem duração conhecida não se decide aqui (fica o "terminou o
    vídeo"/"marcar como vista" do browser).
    """
    duracao = duracao_do_video(chapter)
    if not duracao or not getattr(chapter, 'video', ''):
        return False
    percentagem = getattr(chapter, 'percentagem_vista', None) or 80
    return segundos_vistos(user, chapter) * 100 >= percentagem * duracao
