from django.urls import path

from . import views_revisao as v

urlpatterns = [
    path('resumo/', v.Resumo.as_view(), name='revisao_resumo'),
    path('hoje/', v.Hoje.as_view(), name='revisao_hoje'),
    path('responder/', v.Responder.as_view(), name='revisao_responder'),
    path('falar/', v.Falar.as_view(), name='revisao_falar'),
    path('saltar/', v.Saltar.as_view(), name='revisao_saltar'),
    path('terminar/', v.Terminar.as_view(), name='revisao_terminar'),
]
