from django.urls import path

from . import views_fala as v

urlpatterns = [
    path('resumo/', v.resumo, name='fala_resumo'),
    path('progresso/', v.progresso, name='fala_progresso'),
    path('meta/', v.meta, name='fala_meta'),
]
