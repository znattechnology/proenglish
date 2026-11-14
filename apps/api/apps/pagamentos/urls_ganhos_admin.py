"""Ganhos dos professores (administração): montado em /api/v1/admin/ganhos/."""

from django.urls import path

from . import views_ganhos as v

app_name = 'ganhos_admin'

urlpatterns = [
    path('', v.admin_lista, name='lista'),
    path('<int:pk>/iban/', v.admin_iban, name='iban'),
    path('<int:pk>/pago/', v.admin_marcar_pago, name='pago'),
]
