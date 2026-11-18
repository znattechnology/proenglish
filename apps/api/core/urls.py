"""
URL configuration for ProEnglish Platform.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve as media_serve
from django.conf import settings
from django.conf.urls.static import static

from apps.courses.api.student.colocacao import colocacao as colocacao_aluno
from apps.courses.api.student.colocacao import teste as teste_colocacao
from apps.practice.conversa.configuracao import tutor as configuracao_tutor
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health Check endpoints
    path('api/', include('apps.core.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API endpoints
    path('api/v1/users/', include('apps.users.urls')),
    
    # Admin APIs
    path('api/v1/admin/site/', include('apps.site.urls_admin')),
    path('api/v1/admin/tutor/', configuracao_tutor, name='admin_tutor'),
    path('api/v1/admin/cursos/', include('apps.courses.api.urls_admin_cursos')),
    path('api/v1/admin/ganhos/', include('apps.pagamentos.urls_ganhos_admin')),
    path('api/v1/admin/', include('apps.pagamentos.admin_api.urls')),
    path('api/v1/admin/', include('apps.subscriptions.urls_admin')),  # planos e códigos promocionais
    path('api/v1/admin/', include('apps.platform_admin.urls')),
    path('api/v1/convites/', include('apps.users.admin_api.urls_convites')),
    
    # Student APIs (organized)
    path('api/v1/student/video-courses/', include('apps.courses.api.student.video_courses.urls')),
    path('api/v1/student/practice-courses/', include('apps.courses.api.student.practice_courses.urls')),
    path('api/v1/student/teste-basico/', include('apps.courses.api.student.urls_teste_basico')),
    path('api/v1/student/colocacao/', colocacao_aluno, name='colocacao'),
    path('api/v1/student/colocacao/teste/', teste_colocacao, name='colocacao_teste'),
    path('api/v1/student/revisao/', include('apps.perfil.urls_revisao')),  # revisão de hoje
    path('api/v1/student/fala/', include('apps.perfil.urls_fala')),  # minutos a falar, meta de fala (fase 3)
    
    # Teacher APIs (organized)
    path('api/v1/teacher/video-courses/', include('apps.courses.api.teacher.video_courses.urls')),
    path('api/v1/teacher/practice-courses/', include('apps.courses.api.teacher.practice_courses.urls')),
    # Área do professor (base nova): painel, cursos e ciclo de vida
    path('api/v1/teacher/pratica/', include('apps.courses.api.teacher.urls_pratica')),
    path('api/v1/teacher/perfil/', include('apps.users.urls_professor')),
    path('api/v1/professores/<uuid:user_id>/', __import__('apps.users.professor', fromlist=['perfil_publico']).perfil_publico, name='perfil_publico_professor'),
    path('api/v1/teacher/ganhos/', include('apps.pagamentos.urls_ganhos')),
    path('api/v1/teacher/', include('apps.courses.api.teacher.urls_cursos')),
    path('api/v1/teacher/', include('apps.courses.api.teacher.urls_alunos')),
    path('api/v1/teacher/', include('apps.practice.professor.urls')),
    
    # Legacy endpoints (for backward compatibility)
    path('api/v1/courses/', include('apps.courses.urls')),
    path('api/v1/practice/', include('apps.practice.urls_minimal')),
    
    # Other endpoints
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/pagamentos/', include('apps.pagamentos.urls')),
    # Verificação pública de certificados (sem autenticação)
    path('api/v1/certificados/', include('apps.courses.api.public.urls')),
    # Conteúdo do site público (substitui o antigo /api/v1/cms/, que agora responde 410)
    path('api/v1/site/', include('apps.site.urls')),
    path('api/v1/cms/', include('apps.cms.urls')),

    # Chatbot (public, no auth required)
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
elif not getattr(settings, 'USE_S3', False):
    # Production without S3 and without nginx: uploads live in the media volume and
    # Django serves them. Fine for low traffic; switch USE_S3 on for anything heavier.
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
    ]
