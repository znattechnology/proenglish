"""
Teste do nível básico (requisito dos cursos de sector). Regras em apps/courses/teste_basico.py.

GET  /api/v1/student/teste-basico/?nivel=A2        estado: tem o nível? pode tentar? tentativa em curso
POST /api/v1/student/teste-basico/iniciar/ {nivel} abre a tentativa e devolve as perguntas (sem respostas)

`nivel` é opcional (A2, o nível básico, por omissão); A1, B1 e B2 são os testes de colocação.
POST /api/v1/student/teste-basico/<id>/entregar/   {respostas: {pergunta: índice}} -> corrige no servidor
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.courses import teste_basico as svc


def _erro(e):
    return Response(corpo_erro(e.mensagem, e.codigo), status=e.status)


def _nivel(valor):
    nivel = str(valor or svc.NIVEL_BASICO).strip().upper()
    if not svc.nivel_valido(nivel):
        raise svc.ErroTeste('validation_error', 'Não há teste para este nível.')
    return nivel


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estado(request):
    try:
        return Response(svc.estado(request.user, _nivel(request.query_params.get('nivel'))))
    except svc.ErroTeste as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar(request):
    try:
        t = svc.iniciar(request.user, _nivel(request.data.get('nivel')))
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
    return Response({**svc._tentativa_dict(t), 'estado': svc.estado(request.user, t.nivel)})
