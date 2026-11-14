"""Editor de cursos de prática da área do professor: /api/v1/teacher/pratica/ (ver pratica.py)."""
from django.urls import path

from . import gerar_licao, pratica

app_name = 'teacher_pratica'

urlpatterns = [
    path('<uuid:curso_id>/estrutura/', pratica.estrutura, name='estrutura'),
    path('<uuid:curso_id>/unidades/', pratica.criar_unidade, name='unidades'),
    path('<uuid:curso_id>/unidades/ordem/', pratica.ordenar_unidades, name='unidades-ordem'),
    path('<uuid:curso_id>/gerar-licao/', gerar_licao.gerar_licao, name='gerar-licao'),
    path('unidades/<uuid:unidade_id>/', pratica.unidade, name='unidade'),
    path('unidades/<uuid:unidade_id>/licoes/', pratica.criar_licao, name='licoes'),
    path('unidades/<uuid:unidade_id>/licoes/ordem/', pratica.ordenar_licoes, name='licoes-ordem'),
    path('unidades/<uuid:unidade_id>/licoes/com-exercicios/', pratica.criar_licao_com_exercicios,
         name='licoes-com-exercicios'),
    path('licoes/<uuid:licao_id>/', pratica.licao, name='licao'),
    path('licoes/<uuid:licao_id>/exercicios/', pratica.exercicios, name='exercicios'),
    path('licoes/<uuid:licao_id>/exercicios/ordem/', pratica.ordenar_exercicios, name='exercicios-ordem'),
    path('exercicios/<uuid:exercicio_id>/', pratica.exercicio, name='exercicio'),
    path('exercicios/<uuid:exercicio_id>/audio/', pratica.audio, name='exercicio-audio'),
]
