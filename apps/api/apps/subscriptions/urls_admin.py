"""Planos e códigos promocionais (administração): montado em /api/v1/admin/."""

from django.urls import path

from . import admin_api as v

app_name = 'subscricoes_admin'

urlpatterns = [
    path('planos/', v.planos, name='planos'),
    path('planos/<uuid:pk>/', v.plano_detalhe, name='plano'),
    path('codigos/', v.codigos, name='codigos'),
    path('codigos/<uuid:pk>/', v.codigo_detalhe, name='codigo'),
    path('codigos/<uuid:pk>/activar/', v.codigo_activar, name='codigo-activar'),
    path('codigos/<uuid:pk>/desligar/', v.codigo_desligar, name='codigo-desligar'),
]
