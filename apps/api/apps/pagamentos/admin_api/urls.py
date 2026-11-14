"""Administração de subscrições, pagamentos e relatórios: montado em /api/v1/admin/."""

from django.urls import path

from . import views as v

app_name = 'pagamentos_admin'

urlpatterns = [
    path('subscricoes/resumo/', v.resumo, name='subscricoes-resumo'),
    path('subscricoes/', v.subscricoes, name='subscricoes'),
    path('pagamentos/falhados/', v.falhados, name='pagamentos-falhados'),
    path('pagamentos/<uuid:pk>/novo-pedido/', v.novo_pedido, name='pagamentos-novo-pedido'),
    path('pagamentos/<uuid:pk>/lembrete/', v.lembrete, name='pagamentos-lembrete'),
    path('pagamentos/', v.pagamentos, name='pagamentos'),
    path('relatorios/exportar/', v.relatorios_exportar, name='relatorios-exportar'),
    path('relatorios/', v.relatorios, name='relatorios'),
]
