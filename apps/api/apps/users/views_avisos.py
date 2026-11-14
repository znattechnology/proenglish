"""
Avisos do aluno: preferências e subscrições Web Push.

GET/PATCH /api/v1/users/avisos/
POST/DELETE /api/v1/users/avisos/push/
"""

import re
from datetime import time

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PreferenciasAvisos, PushSubscription
from .push import chave_publica, endpoint_permitido, push_disponivel

TIPOS_EDITAVEIS = ('meta', 'liga', 'certificados', 'cursos')
HORA_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def _erro(mensagem):
    # 'error' continua a ser o código (contrato antigo destas rotas); a mensagem vai em 'message'.
    return Response({'error': 'validation_error', 'message': mensagem}, status=status.HTTP_400_BAD_REQUEST)


def _preferencias(user):
    prefs, _ = PreferenciasAvisos.objects.get_or_create(user=user)
    return prefs


def _dados(user, prefs):
    return {
        'tipos': {
            'meta': prefs.meta,
            'liga': prefs.liga,
            'certificados': prefs.certificados,
            'cursos': prefs.cursos,
            'subscricao': True,  # avisos de serviço: não se podem desligar
        },
        'lembrete': {
            'ligado': prefs.lembrete_ligado,
            'hora': prefs.lembrete_hora.strftime('%H:%M'),
        },
        'push': {
            'disponivel': push_disponivel(),
            'chave_publica': chave_publica(),
            'subscricoes': PushSubscription.objects.filter(user=user).count(),
        },
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def avisos(request):
    prefs = _preferencias(request.user)
    if request.method == 'GET':
        return Response(_dados(request.user, prefs))

    dados = request.data if isinstance(request.data, dict) else {}
    campos = []

    tipos = dados.get('tipos')
    if tipos is not None:
        if not isinstance(tipos, dict):
            return _erro('"tipos" tem de ser um objecto.')
        for chave, valor in tipos.items():
            if chave == 'subscricao':
                continue  # ignorado: os avisos de subscrição estão sempre ligados
            if chave not in TIPOS_EDITAVEIS:
                return _erro(f'Tipo de aviso desconhecido: {chave}.')
            if not isinstance(valor, bool):
                return _erro(f'"tipos.{chave}" tem de ser verdadeiro ou falso.')
            setattr(prefs, chave, valor)
            campos.append(chave)

    lembrete = dados.get('lembrete')
    if lembrete is not None:
        if not isinstance(lembrete, dict):
            return _erro('"lembrete" tem de ser um objecto.')
        if 'ligado' in lembrete:
            if not isinstance(lembrete['ligado'], bool):
                return _erro('"lembrete.ligado" tem de ser verdadeiro ou falso.')
            prefs.lembrete_ligado = lembrete['ligado']
            campos.append('lembrete_ligado')
        if 'hora' in lembrete:
            m = HORA_RE.match(str(lembrete['hora'] or ''))
            if not m:
                return _erro('Hora inválida. Use o formato HH:MM (ex.: 19:00).')
            prefs.lembrete_hora = time(int(m.group(1)), int(m.group(2)))
            campos.append('lembrete_hora')

    if campos:
        prefs.save(update_fields=campos + ['updated_at'])
    return Response(_dados(request.user, prefs))


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def avisos_push(request):
    dados = request.data if isinstance(request.data, dict) else {}
    endpoint = (dados.get('endpoint') or request.query_params.get('endpoint') or '').strip()
    if not endpoint:
        return _erro('Falta o "endpoint" da subscrição.')

    if request.method == 'DELETE':
        removidas, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({
            'removidas': removidas,
            'subscricoes': PushSubscription.objects.filter(user=request.user).count(),
        })

    if not push_disponivel():
        return Response(
            {'error': 'push_indisponivel', 'message': 'As notificações push não estão disponíveis de momento.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if len(endpoint) > 1000 or not endpoint_permitido(endpoint):
        return _erro('Endpoint de push inválido.')
    chaves = dados.get('keys') if isinstance(dados.get('keys'), dict) else {}
    p256dh = str(chaves.get('p256dh') or '').strip()
    auth = str(chaves.get('auth') or '').strip()
    if not p256dh or not auth or len(p256dh) > 255 or len(auth) > 100:
        return _erro('Faltam as chaves da subscrição (keys.p256dh e keys.auth).')

    # O mesmo navegador pode passar para outra conta: a subscrição fica com quem tem a
    # sessão iniciada agora. Mas só se as chaves forem as mesmas (é mesmo esse navegador);
    # quem só conhece o endpoint de outra pessoa não fica com os avisos dela.
    existente = PushSubscription.objects.filter(endpoint=endpoint).exclude(user=request.user).first()
    if existente and (existente.p256dh != p256dh or existente.auth != auth):
        return Response(
            {'error': 'push_em_uso',
             'message': 'Esta subscrição de notificações pertence a outra sessão. '
                        'Desligue e volte a ligar as notificações neste navegador.'},
            status=status.HTTP_409_CONFLICT,
        )
    sub, criada = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user, 'p256dh': p256dh, 'auth': auth,
            'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:300],
        },
    )
    return Response(
        {'criada': criada, 'subscricoes': PushSubscription.objects.filter(user=request.user).count()},
        status=status.HTTP_201_CREATED if criada else status.HTTP_200_OK,
    )
