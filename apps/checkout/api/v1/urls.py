"""Checkout API v1 URL routing — mounted at /api/v1/checkout/"""
from django.urls import path
from . import views

app_name = 'checkout-api-v1'

urlpatterns = [
    # Session lifecycle
    path('start/', views.start_checkout, name='checkout-start'),
    path('<uuid:session_id>/', views.get_session, name='checkout-session'),
    path('<uuid:session_id>/guest-details/', views.submit_guest_details, name='checkout-guest-details'),
    path('<uuid:session_id>/payment-options/', views.payment_options, name='checkout-payment-options'),
    path('<uuid:session_id>/pay/', views.initiate_payment, name='checkout-pay'),
    path('<uuid:session_id>/callback/', views.payment_callback, name='checkout-callback'),
    path('<uuid:session_id>/retry/', views.retry_payment, name='checkout-retry'),
]
