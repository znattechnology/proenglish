"""
Endpoints DRF da conversa com o tutor: /api/v1/practice/conversa/...

Autenticação: JWT (cookie HttpOnly -> cabeçalho, ver JWTCookieAuthenticationMiddleware),
permissão IsAuthenticated. Erros de negócio: {"codigo", "mensagem"} (+ "campos" nos 400).
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import servico
from .servico import ErroConversa


class _Limite(UserRateThrottle):
    setting = None

    def get_rate(self):
        return getattr(settings, self.setting)


class LimiteAjuste(_Limite):
    scope = 'conversa_ajuste'
    setting = 'CONVERSA_LIMITE_AJUSTE'


class LimiteResponder(_Limite):
    scope = 'conversa_responder'
    setting = 'CONVERSA_LIMITE_RESPONDER'


class LimiteSessoes(_Limite):
    scope = 'conversa_sessoes'
    setting = 'CONVERSA_LIMITE_SESSOES'


def _erro(e):
    corpo = {'codigo': e.codigo, 'mensagem': e.mensagem}
    if e.campos:
        corpo['campos'] = e.campos
    return Response(corpo, status=e.status)


def _corpo(request):
    return request.data if isinstance(request.data, dict) else {}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preparar(request):
    return Response(servico.preparar(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteSessoes])
def criar_sessao(request):
    try:
        return Response(servico.criar_sessao(request.user, _corpo(request)), status=status.HTTP_201_CREATED)
    except ErroConversa as e:
        return _erro(e)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessao(request, sessao_id):
    try:
        return Response(servico.obter_resumo(request.user, sessao_id))
    except ErroConversa as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ligada(request, sessao_id):
    try:
        return Response(servico.ligada(request.user, sessao_id, _corpo(request).get('call_id')))
    except ErroConversa as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteResponder])
def responder(request, sessao_id):
    try:
        corpo = _corpo(request)
        return Response(servico.responder(request.user, sessao_id, corpo.get('texto'), corpo.get('escrito') is True))
    except ErroConversa as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteAjuste])
def ajuste(request, sessao_id):
    try:
        return Response(servico.ajuste(request.user, sessao_id, _corpo(request).get('frase')))
    except ErroConversa as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def terminar(request, sessao_id):
    try:
        corpo = _corpo(request)
        return Response(servico.terminar(request.user, sessao_id, corpo.get('transcricao'),
                                         call_id=corpo.get('call_id'), reveladas=corpo.get('reveladas')))
    except ErroConversa as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteAjuste])
def ajuda(request, sessao_id):
    """Durante a conversa: {escrito: texto} (o aluno escreveu em vez de falar) ou {revelada: frase}
    (viu a frase-alvo em inglês). Só baixa o resultado dessas frases (no máximo 'com_ajuda')."""
    corpo = _corpo(request)
    try:
        return Response(servico.registar_ajuda(request.user, sessao_id, escrito=corpo.get('escrito'),
                                               revelada=corpo.get('revelada')))
    except ErroConversa as e:
        return _erro(e)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def progresso(request):
    return Response(servico.progresso(request.user))


# ---------------------------------------------------------------------------
# Teste de nível falado (primeira entrada, conversa/diagnostico.py)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def diagnostico_estado(request):
    from . import diagnostico
    return Response({**diagnostico.estado(request.user), 'modo': servico.modo()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteSessoes])
def diagnostico_comecar(request):
    from . import diagnostico
    try:
        return Response(diagnostico.comecar(request.user), status=status.HTTP_201_CREATED)
    except ErroConversa as e:
        return _erro(e)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def diagnostico_resultado(request, sessao_id):
    from . import diagnostico
    try:
        return Response(diagnostico.resultado(request.user, sessao_id))
    except ErroConversa as e:
        return _erro(e)
