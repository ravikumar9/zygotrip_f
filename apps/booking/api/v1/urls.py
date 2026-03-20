"""Booking API URLs — mounted at /api/v1/booking/"""
from django.urls import path
from . import views
from apps.booking.invoice_api import booking_invoice_api

urlpatterns = [
    # BookingContext (price lock)
    path('context/', views.create_booking_context, name='api_booking_context_create'),
    # UUID lookup (preferred) — frontend must use this
    path('context/<uuid:context_uuid>/', views.get_booking_context, name='api_booking_context_detail'),
    # Apply / remove promo code on an existing context (recalculates prices server-side)
    path('context/<uuid:context_uuid>/apply-promo/', views.apply_promo_to_context, name='api_booking_context_apply_promo'),
    # Legacy numeric lookup (kept for backward compat)
    path('context/<int:context_id>/', views.get_booking_context_by_id, name='api_booking_context_detail_legacy'),
    path('context/<int:context_id>/payment-options/', views.payment_options, name='api_booking_payment_options'),

    # Bookings
    path('', views.create_booking_view, name='api_booking_create'),
    path('my/', views.my_bookings, name='api_booking_my'),
    path('<uuid:booking_uuid>/', views.booking_detail, name='api_booking_detail'),
    path('<uuid:booking_uuid>/cancel/', views.cancel_booking, name='api_booking_cancel'),

    # Invoice
    path('<uuid:booking_uuid>/invoice/', booking_invoice_api, name='booking_invoice'),

    # Refund preview (no-op — read-only estimate for cancellation modal)
    path('<uuid:booking_uuid>/refund-preview/', views.refund_preview, name='api_booking_refund_preview'),
]
