"""
Colocação no curso geral (regras em apps/courses/colocacao.py).

GET  /api/v1/student/colocacao/                 níveis A1 a C1, o que cada um pede, o teste em curso ou o último
POST /api/v1/student/colocacao/ {nivel}         aplica: guarda o nível e inscreve no curso geral desse nível
                                                409 teste_necessario se falta o teste de colocação
POST /api/v1/student/colocacao/teste/ {nivel}   abre o teste de colocação (perguntas de todos os níveis
                                                abaixo do escolhido); anular e entregar em /student/teste-basico/<id>/
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.courses import colocacao as svc
from apps.courses import teste_basico


def _erro(e):
    return Response({**corpo_erro(e.mensagem, e.codigo), **e.extra}, status=e.status)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def colocacao(request):
    if request.method == 'GET':
        return Response(svc.estado(request.user))
    try:
        return Response(svc.colocar(request.user, request.data.get('nivel')))
    except svc.ErroColocacao as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teste(request):
    try:
        t = svc.iniciar_teste(request.user, request.data.get('nivel'))
    except svc.ErroColocacao as e:
        return _erro(e)
    return Response(teste_basico._tentativa_dict(t, com_perguntas=True), status=201)
