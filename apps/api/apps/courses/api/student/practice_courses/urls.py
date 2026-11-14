"""
URL configuration for student practice courses API.

This module defines URL patterns for student practice course consumption,
maintaining the same structure and response format as the Express API.
"""

from django.urls import path
from . import views
from .jogar import jogar_licao, trilho_curso
from .conversa_licao import comecar_conversa_licao
from apps.practice.responder import ResponderEmVozView
from . import study_views

app_name = 'student_practice_courses'

urlpatterns = [
    # ========================================================================
    # FRONTEND COMPATIBILITY ENDPOINTS - MUST BE FIRST to avoid conflicts
    # ========================================================================
    
    # Test endpoints for verification
    path(
        'test-units/', 
        views.test_units_simple, 
        name='test-units'
    ),
    path(
        'test-lessons/', 
        views.test_lessons_simple, 
        name='test-lessons'
    ),
    path(
        'test-challenges/', 
        views.test_challenges_simple, 
        name='test-challenges'
    ),

    # ========================================================================
    # CORE PRACTICE ENDPOINTS
    # ========================================================================

    # List all courses
    path(
        'courses/', 
        views.CoursesListView.as_view(), 
        name='courses-list'
    ),
    
    # Practice course detail with the requesting user's progress
    path(
        'courses/<uuid:course_id>/',
        study_views.get_practice_course_detail,
        name='course-detail'
    ),

    # Course units endpoint
    # Maps to getCourse query from client project
    path(
        'courses/<uuid:course_id>/units/', 
        views.CourseUnitsView.as_view(), 
        name='course-units'
    ),
    
    # Course units with progress (enhanced version)
    path(
        'courses/<uuid:course_id>/units-with-progress/', 
        views.get_units_with_progress, 
        name='course-units-with-progress'
    ),
    
    # Lesson detail for quiz page
    # Maps to getLesson query from client project
    path(
        'lessons/<uuid:lesson_id>/', 
        views.LessonDetailView.as_view(), 
        name='lesson-detail'
    ),
    
    # Lesson completion percentage
    # Lição para o ecrã novo, sem revelar respostas
    path('lessons/<uuid:lesson_id>/jogar/', jogar_licao, name='lesson-jogar'),
    # Exercício "Responder": gravação da resposta, avaliada com Whisper + Claude
    path('challenges/<uuid:challenge_id>/responder/', ResponderEmVozView.as_view(), name='challenge-responder'),
    # Conversa curta no fim da lição (exercício VAPI_CONVERSATION)
    path('challenges/<uuid:challenge_id>/conversa/', comecar_conversa_licao, name='challenge-conversa'),
    path('courses/<uuid:course_id>/trilho/', trilho_curso, name='course-trilho'),
    path(
        'lessons/<uuid:lesson_id>/percentage/', 
        views.get_lesson_percentage, 
        name='lesson-percentage'
    ),
    
    # User progress management
    # Maps to getUserProgress query from client project
    path(
        'user-progress/', 
        views.UserProgressView.as_view(), 
        name='user-progress'
    ),
    
    # Challenge completion
    # Maps to upsertChallengeProgress action from client project
    path(
        'challenge-progress/', 
        views.ChallengeProgressView.as_view(), 
        name='challenge-progress'
    ),
    
    # Text answer validation for fill-blank challenges
    path(
        'validate-text-answer/',
        views.ValidateTextAnswerView.as_view(),
        name='validate-text-answer'
    ),
    
    # Hearts management
    # Maps to reduceHearts action from client project
    path(
        'reduce-hearts/', 
        views.ReduceHeartsView.as_view(), 
        name='reduce-hearts'
    ),
    
    # Hearts refill (premium feature)
    path(
        'refill-hearts/', 
        views.RefillHeartsView.as_view(), 
        name='refill-hearts'
    ),
    
    # ========================================================================
    # STUDY TRACKING ENDPOINTS - streak, daily goal, hearts, lessons, review
    # ========================================================================

    path('study-streak/', study_views.get_study_streak, name='study-streak'),
    path('study-goal/', study_views.study_goal, name='study-goal'),
    path('hearts-status/', study_views.get_hearts_status, name='hearts-status'),
    path('complete-lesson/', study_views.complete_lesson, name='complete-lesson'),
    path('review-words/', study_views.get_review_words, name='review-words'),
    path('student-analytics/', study_views.get_student_analytics, name='student-analytics'),
    path('estatisticas/', study_views.get_estatisticas, name='estatisticas'),
    path('liga/semana/', study_views.get_liga_semanal, name='liga-semanal'),

    # In-app notifications (distinct from achievements/notifications/ below)
    path('notifications/', study_views.list_notifications, name='notifications-list'),
    path('notifications/unread-count/', study_views.notifications_unread_count, name='notifications-unread-count'),
    path('notifications/read-all/', study_views.mark_all_notifications_read, name='notifications-read-all'),
    path(
        'notifications/<uuid:notification_id>/read/',
        study_views.mark_notification_read,
        name='notifications-read'
    ),

    # ========================================================================
    # LEADERBOARD ENDPOINTS - Competition and ranking system
    # ========================================================================
    
    # Global leaderboard
    path(
        'leaderboard/global/', 
        views.get_global_leaderboard, 
        name='leaderboard-global'
    ),
    
    # Leagues information
    path(
        'leaderboard/leagues/', 
        views.get_leagues_info, 
        name='leaderboard-leagues'
    ),
    
    # Active competitions
    path(
        'leaderboard/competitions/', 
        views.get_active_competitions, 
        name='leaderboard-competitions'
    ),
    
    # User position in leaderboard
    path(
        'leaderboard/user-position/', 
        views.get_user_leaderboard_position, 
        name='leaderboard-user-position'
    ),
    
    # Join competition
    path(
        'leaderboard/competitions/<uuid:competition_id>/join/', 
        views.join_competition, 
        name='join-competition'
    ),
    
    # Update user streak
    path(
        'leaderboard/update-streak/', 
        views.update_user_streak, 
        name='update-user-streak'
    ),
    
    # ========================================================================
    # ACHIEVEMENT ENDPOINTS - Gamification and badge system
    # ========================================================================
    
    # Get user achievements with progress
    path(
        'achievements/',
        views.get_user_achievements,
        name='user-achievements'
    ),
    
    # Get achievement statistics
    path(
        'achievements/stats/',
        views.get_achievement_stats,
        name='achievement-stats'
    ),
    
    # Get achievement categories
    path(
        'achievements/categories/',
        views.get_achievement_categories,
        name='achievement-categories'
    ),
    
    # Get achievement notifications
    path(
        'achievements/notifications/',
        views.get_achievement_notifications,
        name='achievement-notifications'
    ),
    
    # Mark notification as read
    path(
        'achievements/notifications/<uuid:notification_id>/read/',
        views.mark_notification_read,
        name='mark-notification-read'
    ),
    
    # Mark achievement as celebrated
    path(
        'achievements/<uuid:achievement_id>/celebrate/',
        views.mark_achievement_celebrated,
        name='mark-achievement-celebrated'
    ),
    
    # ========================================================================
    # 🚀 VAPI AI CONVERSATION PRACTICE ENDPOINTS
    # ========================================================================
    # 
    # Note: Traditional speaking/listening endpoints removed in favor of unified
    # Vapi-based conversation practice which handles both speaking and listening
    # in a single, superior AI conversation experience.
    #
    # All speaking/listening functionality is now handled through:
    # - apps/practice/services/vapi_client.py
    # - apps/practice/services/conversation_ai.py  
    # - apps/practice/views/vapi_views.py
    # ========================================================================
    
    # Start Vapi conversation
    path(
        'conversations/start/',
        views.start_vapi_conversation,
        name='vapi-conversation-start'
    ),
    
    # End Vapi conversation with feedback
    path(
        'conversations/<str:conversation_id>/end/',
        views.end_vapi_conversation,
        name='vapi-conversation-end'
    ),
    
    # Get conversation feedback and analysis
    path(
        'conversations/<str:conversation_id>/feedback/',
        views.get_conversation_feedback,
        name='vapi-conversation-feedback'
    ),
    
    # AI Translation validation with detailed feedback
    path(
        'validate-ai-translation/',
        views.AITranslationValidationView.as_view(),
        name='validate-ai-translation'
    ),

]