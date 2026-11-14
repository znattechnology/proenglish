"""Convites de professor, lado público (incluído em /api/v1/convites/)."""
from django.urls import path

from . import convites

urlpatterns = [
    path('<str:token>/', convites.publico, name='convite_publico'),
    path('<str:token>/aceitar/', convites.aceitar, name='convite_aceitar'),
]
