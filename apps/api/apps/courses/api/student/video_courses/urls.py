"""
URL configuration for student video courses API.

This module defines URL patterns for student video course consumption,
maintaining the same structure and response format as the Express API.
"""

from django.urls import path
from . import views
from . import certificados_views
from . import fala_aula

app_name = 'student_video_courses'

urlpatterns = [
    # Course discovery for students
    path('', views.CourseListView.as_view(), name='course_list'),
    path('<uuid:courseId>/', views.CourseDetailView.as_view(), name='course_detail'),
    
    # Course enrollment status
    path('<uuid:courseId>/enrollment-status/', views.check_course_enrollment_status, name='enrollment_status'),
    
    # Course sections (read-only for students)
    path('<uuid:courseId>/sections/', views.CourseSectionListView.as_view(), name='section_list'),
    path('sections/<uuid:sectionId>/', views.CourseSectionDetailView.as_view(), name='section_detail'),
    
    # Course chapters (read-only for students)
    path('sections/<uuid:sectionId>/chapters/', views.ChapterListView.as_view(), name='chapter_list'),
    path('chapters/<uuid:chapterId>/', views.ChapterDetailView.as_view(), name='chapter_detail'),
    
    # Chapter comments
    # Falar depois do vídeo (frases da aula, repetir em voz alta, conversa de 3 minutos)
    path('chapters/<uuid:chapterId>/fala/', fala_aula.FalaDaAula.as_view(), name='chapter_fala'),
    path('chapters/<uuid:chapterId>/frases/<int:fraseId>/falar/', fala_aula.FalarFrase.as_view(),
         name='chapter_frase_falar'),
    path('chapters/<uuid:chapterId>/conversa/', fala_aula.ConversaDaAula.as_view(), name='chapter_conversa'),

    path('chapters/<uuid:chapterId>/comments/', views.ChapterCommentListCreateView.as_view(), name='chapter_comments'),
    
    # Transactions
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transactions/create/', views.create_transaction, name='transaction_create'),
    
    # User course progress
    path('users/<uuid:userId>/enrolled/', views.get_user_enrolled_courses, name='user_enrolled_courses'),
    path('users/<uuid:userId>/progress/<uuid:courseId>/', views.get_user_course_progress, name='user_course_progress'),
    path('users/<uuid:userId>/progress/<uuid:courseId>/update/', views.update_user_course_progress, name='update_user_course_progress'),
    
    # Stripe payments
    
    # Chapter resources (read-only for students)
    path('chapters/<uuid:chapterId>/resources/', 
         views.ChapterResourceListView.as_view(), name='chapter_resources'),
    path('chapters/<uuid:chapterId>/resources/<uuid:resourceId>/', 
         views.ChapterResourceDetailView.as_view(), name='chapter_resource_detail'),
    
    # Chapter quizzes (read-only for students)
    path('chapters/<uuid:chapterId>/quiz/', 
         views.ChapterQuizListView.as_view(), name='chapter_quiz'),
    path('chapters/<uuid:chapterId>/quiz/<uuid:quizId>/', 
         views.ChapterQuizDetailView.as_view(), name='chapter_quiz_detail'),
    
    # Quiz attempts
    path('chapters/<uuid:chapterId>/quiz/attempts/', 
         views.StudentQuizAttemptListCreateView.as_view(), name='quiz_attempts'),
    path('chapters/<uuid:chapterId>/quiz/summary/',
         views.get_student_quiz_summary, name='quiz_summary'),

    # Notas (as views já existiam mas não tinham rota)
    path('grades/all/', views.get_all_student_grades, name='all_student_grades'),
    path('<uuid:courseId>/grade/', views.get_course_grade, name='course_grade'),

    # Certificados (verificação pública: /api/v1/certificados/verificar/<numero>/)
    path('certificados/', certificados_views.listar_certificados, name='certificados'),
    path('certificados/<uuid:certificadoId>/pdf/', certificados_views.descarregar_pdf, name='certificado_pdf'),
    path('<uuid:courseId>/certificado/', certificados_views.emitir_certificado, name='emitir_certificado'),
]