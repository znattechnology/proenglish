from django.urls import path

from apps.courses.api.teacher.envios import iniciar_fotografia

from . import professor

urlpatterns = [
    path('', professor.meu_perfil, name='perfil_professor'),
    path('fotografia/', professor.tirar_fotografia, name='perfil_professor_tirar_fotografia'),
    path('fotografia/enviar/', iniciar_fotografia, name='perfil_professor_fotografia'),
]
