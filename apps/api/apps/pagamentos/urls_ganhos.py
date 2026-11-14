"""Ganhos do professor: montado em /api/v1/teacher/ganhos/."""

from django.urls import path

from . import views_ganhos as v

app_name = 'ganhos'

urlpatterns = [
    path('', v.resumo, name='resumo'),
    path('exportar/', v.exportar, name='exportar'),
    path('bancos/', v.bancos, name='bancos'),
    path('conta/', v.alterar_conta, name='conta'),
    path('conta/confirmar/', v.confirmar_conta, name='conta-confirmar'),
    path('conta/pendente/', v.cancelar_alteracao, name='conta-pendente'),
]
