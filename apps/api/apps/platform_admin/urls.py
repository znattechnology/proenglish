"""
APIs de administração (/api/v1/admin/).

As novas (painel, utilizadores, convites, opiniões, testemunhos) estão em apps.users.admin_api.
As rotas antigas (dashboard/, users/, stats/, system/health/) respondem 410 com o caminho novo.
"""

from django.urls import include, path

from . import views

urlpatterns = [
    path('', include('apps.users.admin_api.urls')),

    # Rotas antigas (410)
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users_list, name='admin_users_list'),
    path('users/<str:user_id>/', views.admin_user_legacy, name='admin_user_detail'),
    path('users/<str:user_id>/status/', views.admin_user_legacy, name='admin_user_status'),
    path('users/<str:user_id>/role/', views.admin_user_legacy, name='admin_user_role'),
    path('users/<str:user_id>/delete/', views.admin_user_legacy, name='admin_user_delete'),
    path('stats/', views.admin_stats, name='admin_stats'),
    path('system/health/', views.admin_system_health, name='admin_system_health'),
]
