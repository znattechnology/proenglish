"""
URL configuration for users app.
"""

from django.urls import path

from . import views
from . import views_avisos

app_name = 'users'

urlpatterns = [
    # Authentication
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('refresh-token/', views.CustomTokenRefreshView.as_view(), name='refresh_token'),
    
    # Profile management
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('provincias/', views.provincias, name='provincias'),
    path('get-avatar-upload-url/', views.get_avatar_upload_url, name='get_avatar_upload_url'),
    path('change-password/', views.PasswordChangeView.as_view(), name='change_password'),
    path('apagar-conta/', views.ApagarContaView.as_view(), name='apagar_conta'),
    
    # Addresses
    path('addresses/', views.UserAddressListCreateView.as_view(), name='address_list'),
    path('addresses/<uuid:pk>/', views.UserAddressDetailView.as_view(), name='address_detail'),
    
    # Notification settings
    path('notification-settings/', views.NotificationSettingsView.as_view(), name='notification_settings'),

    # Avisos do aluno (preferências + Web Push)
    path('avisos/', views_avisos.avisos, name='avisos'),
    path('avisos/push/', views_avisos.avisos_push, name='avisos_push'),
    
    # Password reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset-confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Email verification
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    # Email novo pedido pela administração (User.email_pendente)
    path('confirmar-email-novo/', views.ConfirmarEmailNovoView.as_view(), name='confirmar_email_novo'),
    
    # Google OAuth
    path('oauth/google/url/', views.GoogleOAuthURLView.as_view(), name='google_oauth_url'),
    path('oauth/google/login/', views.GoogleOAuthLoginView.as_view(), name='google_oauth_login'),
    
    # Admin endpoints
    path('admin/users/', views.AdminUsersListView.as_view(), name='admin_users_list'),
    path('admin/users/<uuid:id>/', views.AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('admin/users/<uuid:id>/update/', views.AdminUserUpdateView.as_view(), name='admin_user_update'),
    path('admin/users/<uuid:id>/role/', views.AdminUserRoleUpdateView.as_view(), name='admin_user_role_update'),
    path('admin/users/<uuid:id>/status/', views.AdminUserToggleStatusView.as_view(), name='admin_user_toggle_status'),
    path('admin/users/<uuid:id>/delete/', views.AdminUserDeleteView.as_view(), name='admin_user_delete'),

    # Feedback endpoints
    path('feedback/status/', views.FeedbackStatusView.as_view(), name='feedback_status'),
    path('feedback/submit/', views.SubmitFeedbackView.as_view(), name='feedback_submit'),
    path('feedback/dismiss/', views.DismissFeedbackPromptView.as_view(), name='feedback_dismiss'),
    path('feedback/my-feedback/', views.UserFeedbackListView.as_view(), name='my_feedback'),
    path('feedback/testimonials/', views.PublicTestimonialsView.as_view(), name='public_testimonials'),
    path('feedback/admin/list/', views.AdminFeedbackListView.as_view(), name='admin_feedback_list'),
    path('feedback/admin/stats/', views.AdminFeedbackStatsView.as_view(), name='admin_feedback_stats'),
    path('feedback/admin/<uuid:id>/', views.AdminFeedbackUpdateView.as_view(), name='admin_feedback_update'),
]