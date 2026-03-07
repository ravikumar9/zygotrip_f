from django.urls import path
from .views import create, payment, review, success, cancel, checkout, create_booking_from_form

app_name = 'booking'

urlpatterns = [
    path('property/<int:property_id>/', create, name='create'),
    path('<uuid:uuid>/review/', review, name='review'),
    path('<uuid:uuid>/payment/', payment, name='payment'),
    path('<uuid:uuid>/success/', success, name='success'),
    path('<uuid:uuid>/cancel/', cancel, name='cancel'),
    # PHASE 1: Payment page with booking reference
    path('checkout/<booking_reference>/', checkout, name='checkout'),
    # UUID-based booking creation from guest form
    path('create-booking/', create_booking_from_form, name='create_booking_from_form'),
]