"""
IP do cliente para os limites de pedidos (django_ratelimit e throttles do DRF).

Atrás do nginx, REMOTE_ADDR é o IP do proxy: todos os alunos partilhavam o mesmo limite.
Os cabeçalhos X-Real-IP / X-Forwarded-For só são lidos com TRUSTED_PROXY=True, porque sem
proxy à frente qualquer cliente os pode inventar para fugir aos limites.

* X-Real-IP: o nginx grava-o com $remote_addr (substitui o que o cliente enviar).
* X-Forwarded-For: usa-se a entrada TRUSTED_PROXY_COUNT a contar do fim (a que o nosso
  proxy acrescentou); as da esquerda vêm do cliente e não contam.
"""

from django.conf import settings


def ip_do_cliente(request):
    meta = request.META
    remoto = meta.get('REMOTE_ADDR') or ''
    if not getattr(settings, 'TRUSTED_PROXY', False):
        return remoto

    real = (meta.get('HTTP_X_REAL_IP') or '').strip()
    if real:
        return real
    xff = meta.get('HTTP_X_FORWARDED_FOR') or ''
    entradas = [e.strip() for e in xff.split(',') if e.strip()]
    if entradas:
        n = max(1, int(getattr(settings, 'TRUSTED_PROXY_COUNT', 1) or 1))
        return entradas[-min(n, len(entradas))]
    return remoto


def _get_ident_drf(self, request):
    return ip_do_cliente(request)


def ligar_ao_drf():
    """Os throttles do DRF (AnonRateThrottle, UserRateThrottle sem sessão, ScopedRateThrottle)
    passam a usar o mesmo IP que o django_ratelimit."""
    from rest_framework.throttling import BaseThrottle
    BaseThrottle.get_ident = _get_ident_drf
