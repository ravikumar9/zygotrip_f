"""Auth and User API URLs — mounted at /api/v1/"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from . import otp_views

urlpatterns = [
    # Auth — email/password
    path('auth/register/', views.register_view, name='api_auth_register'),
    path('auth/login/', views.login_view, name='api_auth_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('auth/logout/', views.logout_view, name='api_auth_logout'),

    # Auth — OTP (phone-based)
    path('auth/otp/send/', otp_views.otp_send, name='api_auth_otp_send'),
    path('auth/otp/verify/', otp_views.otp_verify, name='api_auth_otp_verify'),

    # User profile
    path('users/me/', views.me_view, name='api_users_me'),
]
