"""
Web Push (VAPID) para os avisos do aluno.

* Desligado quando faltam ``VAPID_PUBLIC_KEY`` / ``VAPID_PRIVATE_KEY`` nas
  settings: os avisos in-app continuam a funcionar.
* ``enviar_push`` nunca lança exceções para o chamador; subscrições que o
  serviço de push dá como inexistentes (404/410) são apagadas.
* ``agendar_push`` corre o envio depois do commit, numa thread de fundo, para
  não atrasar o pedido HTTP (``AVISOS_PUSH_SINCRONO=True`` envia logo, útil
  em testes). A thread pool é esperada à saída do processo, por isso os
  comandos de gestão (cron) também entregam os pushes.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 5
TTL_SEGUNDOS = 60 * 60 * 12  # o serviço de push guarda a mensagem até 12 h

# Só aceitamos endpoints dos serviços de push dos navegadores (evita SSRF:
# o servidor faz POST para o endpoint que o navegador envia).
SUFIXOS_PUSH_PERMITIDOS = (
    'fcm.googleapis.com',               # Chrome, Edge (Android), Opera
    'android.googleapis.com',
    'push.services.mozilla.com',        # Firefox
    'notify.windows.com',               # Edge (Windows)
    'push.apple.com',                   # Safari (macOS / iOS)
)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='webpush')


def push_disponivel():
    return bool(getattr(settings, 'VAPID_PUBLIC_KEY', '') and getattr(settings, 'VAPID_PRIVATE_KEY', ''))


def chave_publica():
    return settings.VAPID_PUBLIC_KEY if push_disponivel() else None


def endpoint_permitido(endpoint):
    try:
        url = urlparse(endpoint)
    except ValueError:
        return False
    host = (url.hostname or '').lower()
    if url.scheme != 'https' or not host:
        return False
    return any(host == s or host.endswith('.' + s) for s in SUFIXOS_PUSH_PERMITIDOS)


def _claims():
    email = getattr(settings, 'VAPID_CLAIMS_EMAIL', '') or 'suporte@proenglish.ao'
    if not email.startswith('mailto:'):
        email = f'mailto:{email}'
    return {'sub': email}


def enviar_push(user, title, body='', link='', tag=None):
    """Envia o push para todos os navegadores do aluno. Devolve quantos foram entregues."""
    if not push_disponivel():
        return 0
    try:
        from pywebpush import WebPushException, webpush
        from .models import PushSubscription

        payload = json.dumps({
            'title': title, 'body': body or '', 'link': link or '/user/notifications',
            'tag': tag or 'proenglish',
        }, ensure_ascii=False)
        entregues = 0
        for sub in list(PushSubscription.objects.filter(user=user)):
            try:
                webpush(
                    subscription_info={'endpoint': sub.endpoint, 'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims=dict(_claims()),  # webpush altera o dict (aud/exp)
                    timeout=TIMEOUT_SEGUNDOS,
                    ttl=TTL_SEGUNDOS,
                )
            except WebPushException as e:
                codigo = getattr(getattr(e, 'response', None), 'status_code', None)
                if codigo in (404, 410):
                    sub.delete()
                    logger.info('Subscrição push expirada removida (user=%s)', user.pk)
                else:
                    logger.warning('Falha no web push (user=%s, estado=%s): %s', user.pk, codigo, e)
                continue
            except Exception:
                logger.exception('Erro inesperado no web push (user=%s)', user.pk)
                continue
            entregues += 1
            PushSubscription.objects.filter(pk=sub.pk).update(last_used_at=timezone.now())
        return entregues
    except Exception:
        logger.exception('Falha ao enviar web push (user=%s)', getattr(user, 'pk', None))
        return 0


def _enviar_em_fundo(user_id, title, body, link, tag):
    try:
        from .models import User
        user = User.objects.filter(pk=user_id).first()
        if user is not None:
            enviar_push(user, title, body, link, tag)
    except Exception:
        logger.exception('Falha no envio de push em fundo (user=%s)', user_id)
    finally:
        connection.close()  # a thread é reutilizada; não deixar ligações abertas


def agendar_push(user, notification):
    """Agenda o push de uma Notification acabada de criar (após o commit)."""
    if not push_disponivel():
        return

    def _depois_do_commit():
        try:
            from .models import PushSubscription
            if not PushSubscription.objects.filter(user=user).exists():
                return
            args = (user.pk, notification.title, notification.body, notification.link,
                    f'{notification.kind}-{notification.pk}')
            if getattr(settings, 'AVISOS_PUSH_SINCRONO', False):
                enviar_push(user, *args[1:])
            else:
                _executor.submit(_enviar_em_fundo, *args)
        except Exception:
            logger.exception('Falha ao agendar web push (user=%s)', user.pk)

    transaction.on_commit(_depois_do_commit)
