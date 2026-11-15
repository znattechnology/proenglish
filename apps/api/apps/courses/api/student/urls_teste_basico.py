from django.urls import path

from . import teste_basico as v

urlpatterns = [
    path('', v.estado, name='teste_basico_estado'),
    path('iniciar/', v.iniciar, name='teste_basico_iniciar'),
    path('<uuid:teste_id>/entregar/', v.entregar, name='teste_basico_entregar'),
]
