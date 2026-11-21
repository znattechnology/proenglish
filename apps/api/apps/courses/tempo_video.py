"""
Minutos de vídeo declarados pelo browser (PUT .../progress/<courseId>/update/ com watched_seconds).

O browser envia "segundos vistos desde o último envio". Antes bastava enviar
watched_seconds=99999 para ganhar 60 minutos por pedido, quantas vezes se quisesse, e o primeiro
envio do dia valia logo a duração inteira do vídeo. Agora:

- por pedido: no máximo a duração do vídeo do capítulo (se for conhecida) ou 30 minutos;
- por capítulo e por dia: no máximo a duração do vídeo (ou 30 minutos); reenviar não soma;
- TODOS os envios (incluindo o primeiro) valem no máximo o tempo real que passou desde a
  referência mais recente (mais uma pequena folga): a abertura da aula por este aluno (GET do
  capítulo, marcar_aberta) ou o envio anterior para o capítulo. Sem referência nenhuma (nunca
  abriu a aula) não se credita nada, mas o envio fica como referência para o seguinte;
- só o que é novo (delta) vai para o DailyStudyLog.
"""
from datetime import datetime, timezone as dt_timezone

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

MAXIMO_SEM_DURACAO = 30 * 60  # segundos
FOLGA_SEGUNDOS = 15
CHAVES_DURACAO = ('duration_seconds', 'duracao_segundos', 'video_duration', 'duration')
TEMPO_ABERTA = 12 * 3600  # quanto tempo a cache guarda a hora de abertura da aula


def _chave_aberta(user_id, chapter_id):
    return f'aula-aberta:{user_id}:{chapter_id}'


def marcar_aberta(user, chapter):
    """O aluno abriu o conteúdo da aula agora (o crédito seguinte não passa do tempo desde aqui)."""
    try:
        cache.set(_chave_aberta(user.pk, chapter.pk), timezone.now().timestamp(), TEMPO_ABERTA)
    except Exception:  # sem cache: fica a referência do envio anterior
        pass


def aberta_em(user, chapter):
    try:
        ts = cache.get(_chave_aberta(user.pk, chapter.pk))
    except Exception:
        return None
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc) if ts else None


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
        # Referência = o mais recente entre a abertura da aula e o envio anterior (qualquer dia;
        # o registo de hoje só conta se já existia). Lida depois do lock: dois pedidos em paralelo
        # não usam a mesma referência.
        anterior = (VideoWatchLog.objects.filter(user=user, chapter=chapter).exclude(pk=registo.pk)
                    .aggregate(m=Max('updated_at'))['m'])
        referencias = [r for r in (aberta_em(user, chapter), anterior,
                                   None if criado else registo.updated_at) if r is not None]
        if not referencias:
            pedido = 0
        else:
            passou = (agora - max(referencias)).total_seconds() + FOLGA_SEGUNDOS
            pedido = min(pedido, max(0, int(passou)))
        novo = max(0, min(pedido, limite - registo.seconds))
        # Grava sempre (updated_at = agora): o envio passa a ser a referência do seguinte.
        registo.seconds += novo
        registo.save(update_fields=['seconds', 'updated_at'])
        if novo <= 0:
            return 0

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
