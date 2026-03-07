"""Booking API URLs — mounted at /api/v1/booking/"""
from django.urls import path
from . import views

urlpatterns = [
    # BookingContext (price lock)
    path('context/', views.create_booking_context, name='api_booking_context_create'),
    # UUID lookup (preferred) — frontend must use this
    path('context/<uuid:context_uuid>/', views.get_booking_context, name='api_booking_context_detail'),
    # Legacy numeric lookup (kept for backward compat)
    path('context/<int:context_id>/', views.get_booking_context_by_id, name='api_booking_context_detail_legacy'),

    # Bookings
    path('', views.create_booking_view, name='api_booking_create'),
    path('my/', views.my_bookings, name='api_booking_my'),
    path('<uuid:booking_uuid>/', views.booking_detail, name='api_booking_detail'),
    path('<uuid:booking_uuid>/cancel/', views.cancel_booking, name='api_booking_cancel'),
]
