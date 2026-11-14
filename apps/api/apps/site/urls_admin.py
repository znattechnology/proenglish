from django.urls import path

from . import admin_api as a

app_name = 'site_admin'

urlpatterns = [
    path('', a.estado, name='estado'),
    path('topo/', a.topo, name='topo'),
    path('precos/', a.precos, name='precos'),
    path('definicoes/', a.definicoes, name='definicoes'),
    path('publicar/', a.publicar, name='publicar'),
    path('descartar/', a.descartar, name='descartar'),
    path('manutencao/', a.manutencao, name='manutencao'),
    path('empresas/<int:pk>/logo/', a.logo, name='empresa_logo'),
]
for _s in a.LISTAS:
    urlpatterns += [
        path(f'{_s}/', a.VISTAS_LISTA[_s], name=f'{_s}'),
        path(f'{_s}/ordem/', a.VISTAS_ORDEM[_s], name=f'{_s}_ordem'),
        path(f'{_s}/<int:pk>/', a.VISTAS_ITEM[_s], name=f'{_s}_item'),
    ]
