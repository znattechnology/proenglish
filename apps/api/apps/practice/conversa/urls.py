from django.urls import path

from . import views

# Incluído em apps/practice/urls_minimal.py como "conversa/" -> /api/v1/practice/conversa/...
urlpatterns = [
    path('preparar/', views.preparar, name='conversa-preparar'),
    path('progresso/', views.progresso, name='conversa-progresso'),
    path('sessoes/', views.criar_sessao, name='conversa-sessoes'),
    path('diagnostico/', views.diagnostico_estado, name='conversa-diagnostico'),
    path('diagnostico/comecar/', views.diagnostico_comecar, name='conversa-diagnostico-comecar'),
    path('diagnostico/<str:sessao_id>/', views.diagnostico_resultado, name='conversa-diagnostico-resultado'),
    path('sessoes/<str:sessao_id>/', views.sessao, name='conversa-sessao'),
    path('sessoes/<str:sessao_id>/ligada/', views.ligada, name='conversa-ligada'),
    path('sessoes/<str:sessao_id>/responder/', views.responder, name='conversa-responder'),
    path('sessoes/<str:sessao_id>/ajuste/', views.ajuste, name='conversa-ajuste'),
    path('sessoes/<str:sessao_id>/terminar/', views.terminar, name='conversa-terminar'),
]
