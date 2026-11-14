from django.urls import path

from . import views

app_name = 'pagamentos'

urlpatterns = [
    path('orcamento/', views.orcamento, name='orcamento'),
    path('multicaixa/', views.criar_pagamento_multicaixa, name='multicaixa-criar'),
    path('teste/', views.iniciar_teste, name='teste'),
    path('sem-pagamento/', views.ativar_sem_pagamento, name='sem-pagamento'),
    path('recibos/<str:numero>/', views.recibo, name='recibo'),
    path('<uuid:pk>/', views.detalhe_pagamento, name='detalhe'),
    path('<uuid:pk>/cancelar/', views.cancelar_pagamento, name='cancelar'),
    path('<uuid:pk>/simular/', views.simular_pagamento, name='simular'),
]
