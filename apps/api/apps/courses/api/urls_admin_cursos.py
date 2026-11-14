"""Cursos na administração: /api/v1/admin/cursos/... (lista, análise, revisão, detalhe e arquivo)."""
from django.urls import path

from . import admin_cursos, admin_painel_cursos

app_name = 'admin_cursos'

urlpatterns = [
    path('', admin_painel_cursos.lista, name='lista'),
    path('analise/', admin_painel_cursos.analise, name='analise'),
    path('analise/exportar/', admin_painel_cursos.exportar_analise, name='analise-exportar'),
    path('revisao/', admin_cursos.lista_revisao, name='revisao'),
    path('<uuid:curso_id>/', admin_painel_cursos.detalhe, name='detalhe'),
    path('<uuid:curso_id>/aprovar/', admin_cursos.aprovar, name='aprovar'),
    path('<uuid:curso_id>/recusar/', admin_cursos.recusar, name='recusar'),
    path('<uuid:curso_id>/arquivar/', admin_painel_cursos.arquivar, name='arquivar'),
]
