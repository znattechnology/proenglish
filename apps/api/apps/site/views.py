"""
Site público (sem sessão).

- GET /api/v1/site/            conteúdo publicado + dados vivos (5 min em cache)
- GET /api/v1/site/manutencao/ {activa, mensagem, volta_em} (para o proxy da web; sem cache)
"""
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import conteudo as ct


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def site(request):
    return Response(ct.publico())


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def manutencao(request):
    return Response(ct.manutencao(publico=True))
