from django.urls import path
from . import api_views

app_name = 'buses_api'

urlpatterns = [
    path('search/', api_views.search_buses, name='search'),
    path('routes/', api_views.popular_routes, name='routes'),
    path('<int:bus_id>/book/', api_views.create_booking, name='book'),
    path('<int:bus_id>/', api_views.bus_detail, name='detail'),
    path('<int:bus_id>/seats/', api_views.bus_seats, name='seats'),
    path('<int:bus_id>/seat-map/', api_views.seat_map_layout, name='seat-map'),
    path('<int:bus_id>/points/', api_views.boarding_dropping_points, name='points'),
    path('<int:bus_id>/lock-seats/', api_views.lock_seats, name='lock-seats'),
    path('<int:bus_id>/release-seats/', api_views.release_seats, name='release-seats'),
    path('bookings/<uuid:booking_uuid>/', api_views.booking_detail, name='booking-detail'),
    path('bookings/<uuid:booking_uuid>/tracking/', api_views.booking_tracking, name='booking-tracking'),
    path('bookings/<uuid:booking_uuid>/cancel/', api_views.cancel_booking, name='booking-cancel'),
]
