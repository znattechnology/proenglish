"""Área do professor (base nova): /api/v1/teacher/painel/, cursos/, seccoes/, aulas/, materiais/ e envios/."""
from django.urls import path

from . import cursos, editor_video, envios

app_name = 'teacher_cursos'

urlpatterns = [
    path('painel/', cursos.painel, name='painel'),
    path('cursos/', cursos.lista_cursos, name='cursos'),
    path('cursos/opcoes/', editor_video.opcoes, name='opcoes'),
    path('cursos/<uuid:curso_id>/', cursos.curso_detalhe, name='curso'),
    path('cursos/<uuid:curso_id>/verificacao/', cursos.verificacao, name='verificacao'),
    path('cursos/<uuid:curso_id>/submeter/', cursos.submeter, name='submeter'),
    path('cursos/<uuid:curso_id>/cancelar-revisao/', cursos.cancelar_revisao, name='cancelar-revisao'),
    path('cursos/<uuid:curso_id>/arquivar/', cursos.arquivar, name='arquivar'),

    # Editor de cursos em vídeo
    path('cursos/<uuid:curso_id>/estrutura/', editor_video.estrutura, name='estrutura'),
    path('cursos/<uuid:curso_id>/licoes-pratica/', editor_video.licoes_pratica, name='licoes-pratica'),
    path('cursos/<uuid:curso_id>/seccoes/', editor_video.criar_seccao, name='seccoes'),
    path('cursos/<uuid:curso_id>/seccoes/ordem/', editor_video.ordenar_seccoes, name='seccoes-ordem'),
    path('cursos/<uuid:curso_id>/capa/', envios.iniciar_capa, name='capa'),
    path('seccoes/<uuid:seccao_id>/', editor_video.seccao, name='seccao'),
    path('seccoes/<uuid:seccao_id>/aulas/', editor_video.criar_aula, name='aulas'),
    path('seccoes/<uuid:seccao_id>/aulas/ordem/', editor_video.ordenar_aulas, name='aulas-ordem'),
    path('aulas/<uuid:aula_id>/', editor_video.aula, name='aula'),
    path('aulas/<uuid:aula_id>/video/', envios.iniciar_video, name='aula-video'),
    path('aulas/<uuid:aula_id>/materiais/', envios.iniciar_material, name='aula-materiais'),
    path('aulas/<uuid:aula_id>/questionario/', editor_video.questionario, name='aula-questionario'),
    path('materiais/<uuid:material_id>/', editor_video.material, name='material'),
    path('envios/confirmar/', envios.confirmar, name='envio-confirmar'),
    path('envios/<str:chave>/', envios.envio_local, name='envio-local'),
]
