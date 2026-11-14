"""
Verificação pública de certificados (sem autenticação). Montado em /api/v1/certificados/.
"""
from django.urls import path

from . import views

app_name = 'public_certificates'

urlpatterns = [
    path('verificar/<str:numero>/', views.verificar_certificado, name='verificar_certificado'),
]
