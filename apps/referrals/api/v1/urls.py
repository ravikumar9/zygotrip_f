from django.urls import path

from . import views


urlpatterns = [
    path('referrals/me/', views.my_referral_profile, name='referrals_me'),
    path('referrals/history/', views.my_referral_history, name='referrals_history'),
    path('referrals/redeem/', views.redeem_referral_code, name='referrals_redeem'),
    path('referrals/complete-first-booking/', views.complete_first_booking, name='referrals_complete_first_booking'),
]
