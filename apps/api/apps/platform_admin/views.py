"""
Rotas antigas da administração (/api/v1/admin/dashboard/, users/, stats/, system/health/).

Devolviam números inventados (receita, cursos de topo, saúde do sistema). Foram substituídas
pelas APIs reais em apps.users.admin_api (painel/, utilizadores/...): estas respondem 410 com
o caminho novo, sempre só para administradores (EAdministrador).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador


def _substituida(novo):
    mensagem = f'Esta rota foi substituída por /api/v1/admin/{novo}.'
    return Response(corpo_erro(mensagem, 'rota_substituida', {}, substituida_por=f'/api/v1/admin/{novo}'),
                    status=410)


@api_view(['GET'])
@permission_classes([EAdministrador])
def admin_dashboard(request):
    return _substituida('painel/')


@api_view(['GET'])
@permission_classes([EAdministrador])
def admin_stats(request):
    return _substituida('painel/')


@api_view(['GET'])
@permission_classes([EAdministrador])
def admin_system_health(request):
    # A saúde do sistema real está em /api/health/ (apps.core.health).
    return _substituida('painel/')


@api_view(['GET'])
@permission_classes([EAdministrador])
def admin_users_list(request):
    return _substituida('utilizadores/')


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([EAdministrador])
def admin_user_legacy(request, user_id):
    return _substituida(f'utilizadores/{user_id}/')
