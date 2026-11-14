"""
Rotas antigas do CMS (/api/v1/cms/...): substituídas por /api/v1/site/ (público) e
/api/v1/admin/site/ (administração). Respondem sempre 410 Gone.
"""
from django.http import JsonResponse
from django.urls import re_path

from apps.core.exceptions import corpo_erro

app_name = 'cms'

MENSAGEM = 'Este endereço deixou de existir. O conteúdo do site está agora em /api/v1/site/.'


def removido(request, resto=''):
    return JsonResponse(corpo_erro(MENSAGEM, 'endpoint_removido', {}), status=410)


urlpatterns = [
    re_path(r'^(?P<resto>.*)$', removido, name='removido'),
]
