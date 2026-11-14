from django.urls import path

from . import views

app_name = 'site_publico'

urlpatterns = [
    path('', views.site, name='site'),
    path('manutencao/', views.manutencao, name='manutencao'),
]
