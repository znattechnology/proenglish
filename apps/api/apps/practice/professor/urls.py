"""Incluído em core/urls.py sob api/v1/teacher/."""
from django.urls import path

from . import competicoes, conquistas, situacoes

app_name = 'teacher_pratica_jogo'

urlpatterns = [
    path('situacoes/', situacoes.lista, name='situacoes'),
    path('situacoes/opcoes/', situacoes.opcoes, name='situacoes-opcoes'),
    path('situacoes/<int:situacao_id>/', situacoes.detalhe, name='situacao'),
    path('resultados/fala/', situacoes.resultados_fala, name='resultados-fala'),

    path('conquistas/', conquistas.lista, name='conquistas'),
    path('conquistas/opcoes/', conquistas.opcoes, name='conquistas-opcoes'),
    path('conquistas/<uuid:conquista_id>/', conquistas.detalhe, name='conquista'),

    path('competicoes/', competicoes.lista, name='competicoes'),
    path('competicoes/<uuid:competicao_id>/', competicoes.detalhe, name='competicao'),
    path('competicoes/<uuid:competicao_id>/classificacao/', competicoes.classificacao,
         name='competicao-classificacao'),
]
