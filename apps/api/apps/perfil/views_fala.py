"""
Quanto o aluno fala (fase 3). Montado em /api/v1/student/fala/.

  GET   resumo/      frase do painel, hoje vs meta de fala, últimos 7 dias
  GET   progresso/   últimas 8 semanas (minutos, palavras por minuto, palavras por resposta,
                     pausas longas por minuto) e palavras a treinar
  GET   meta/        {meta_fala_min, opcoes}
  PATCH meta/        {meta_fala_min: 3 | 5 | 10 | 15}
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import fala
from .views_revisao import SoAlunos


@api_view(['GET'])
@permission_classes([IsAuthenticated, SoAlunos])
def resumo(request):
    return Response(fala.resumo_painel(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated, SoAlunos])
def progresso(request):
    return Response(fala.progresso(request.user))


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, SoAlunos])
def meta(request):
    if request.method == 'PATCH':
        valor = request.data.get('meta_fala_min') if hasattr(request.data, 'get') else None
        try:
            fala.definir_meta(request.user, valor)
        except ValueError as e:
            return Response({'codigo': 'meta_invalida', 'mensagem': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'meta_fala_min': fala.meta_de(request.user), 'opcoes': fala.metas_validas()})
