"""Payment API v1 URL routing."""
from django.urls import path
from . import views

app_name = 'payments-api-v1'

urlpatterns = [
    # Payment initiation & status
    path('initiate/', views.initiate_payment, name='initiate-payment'),
    path('status/<str:transaction_id>/', views.payment_status, name='payment-status'),
    path('gateways/<uuid:booking_uuid>/', views.available_gateways, name='available-gateways'),

    # Webhook endpoints (signature-verified, no auth)
    path('webhook/cashfree/', views.webhook_cashfree, name='webhook-cashfree'),
    path('webhook/stripe/', views.webhook_stripe, name='webhook-stripe'),
    path('webhook/paytm/', views.webhook_paytm, name='webhook-paytm'),
]
