"""APIs de administração de utilizadores, convites e opiniões (incluídas em /api/v1/admin/)."""
from django.urls import path

from . import convites, opinioes, utilizadores

urlpatterns = [
    path('painel/', utilizadores.painel, name='admin_painel'),
    path('utilizadores/', utilizadores.lista, name='admin_utilizadores'),
    path('utilizadores/email/', utilizadores.email_varios, name='admin_utilizadores_email'),
    path('utilizadores/<uuid:user_id>/', utilizadores.detalhe, name='admin_utilizador'),
    path('utilizadores/<uuid:user_id>/suspender/', utilizadores.suspender, name='admin_utilizador_suspender'),
    path('utilizadores/<uuid:user_id>/reactivar/', utilizadores.reactivar, name='admin_utilizador_reactivar'),
    path('utilizadores/<uuid:user_id>/terminar-sessoes/', utilizadores.terminar_sessoes,
         name='admin_utilizador_terminar_sessoes'),
    path('utilizadores/<uuid:user_id>/obrigar-mudar-senha/', utilizadores.obrigar_mudar_senha,
         name='admin_utilizador_obrigar_mudar_senha'),
    path('convites/', convites.convites, name='admin_convites'),
    path('convites/<int:convite_id>/', convites.cancelar, name='admin_convite'),
    path('convites/<int:convite_id>/reenviar/', convites.reenviar, name='admin_convite_reenviar'),
    path('opinioes/', opinioes.opinioes, name='admin_opinioes'),
    path('opinioes/<uuid:opiniao_id>/', opinioes.opiniao, name='admin_opiniao'),
    path('testemunhos/', opinioes.testemunhos, name='admin_testemunhos'),
    path('testemunhos/ordem/', opinioes.ordem, name='admin_testemunhos_ordem'),
    path('testemunhos/<uuid:opiniao_id>/', opinioes.testemunho, name='admin_testemunho'),
]
