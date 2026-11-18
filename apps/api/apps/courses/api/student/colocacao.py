"""
Colocação no curso geral (regras em apps/courses/colocacao.py).

GET  /api/v1/student/colocacao/            níveis A1 a C1, o teste que cada um pede e o curso de cada nível
POST /api/v1/student/colocacao/ {nivel}    aplica: guarda o nível e inscreve no curso geral desse nível
                                           409 teste_necessario {teste} se falta o teste do nível anterior
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.courses import colocacao as svc


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def colocacao(request):
    if request.method == 'GET':
        return Response(svc.estado(request.user))
    try:
        return Response(svc.colocar(request.user, request.data.get('nivel')))
    except svc.ErroColocacao as e:
        return Response({**corpo_erro(e.mensagem, e.codigo), **e.extra}, status=e.status)
