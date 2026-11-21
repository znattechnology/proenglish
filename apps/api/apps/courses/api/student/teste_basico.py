"""
Teste do nível básico (requisito dos cursos de sector). Regras em apps/courses/teste_basico.py.

GET  /api/v1/student/teste-basico/                 estado: tem o nível? pode tentar? tentativa em curso
POST /api/v1/student/teste-basico/iniciar/         abre a tentativa e devolve as perguntas (sem respostas)

/anular/ e /entregar/ servem também os testes de colocação (abertos em /student/colocacao/teste/).
POST /api/v1/student/teste-basico/<id>/anular/     {pergunta} -> o aluno saiu do ecrã: a pergunta conta como errada
POST /api/v1/student/teste-basico/<id>/entregar/   {respostas: {pergunta: índice}} -> corrige no servidor
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.courses import teste_basico as svc


def _erro(e):
    return Response(corpo_erro(e.mensagem, e.codigo), status=e.status)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estado(request):
    return Response(svc.estado(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar(request):
    try:
        t = svc.iniciar(request.user)
    except svc.ErroTeste as e:
        return _erro(e)
    return Response(svc._tentativa_dict(t, com_perguntas=True), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def entregar(request, teste_id):
    try:
        t = svc.submeter(request.user, teste_id, request.data.get('respostas'))
    except svc.ErroTeste as e:
        return _erro(e)
    return Response({**svc._tentativa_dict(t), 'estado': svc.estado(request.user)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anular(request, teste_id):
    try:
        t = svc.anular(request.user, teste_id, str(request.data.get('pergunta') or ''))
    except svc.ErroTeste as e:
        return _erro(e)
    return Response({'anuladas': list(t.anuladas)})
