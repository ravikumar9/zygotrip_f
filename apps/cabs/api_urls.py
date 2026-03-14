from django.urls import path
from . import api_views

app_name = 'cabs_api'

urlpatterns = [
    path('book/', api_views.book_cab, name='book'),
    path('bookings/<uuid:booking_uuid>/tracking/', api_views.booking_tracking, name='tracking'),
    path('search/', api_views.search_cabs, name='search'),
    path('cities/', api_views.available_cities, name='cities'),
    path('<int:cab_id>/', api_views.cab_detail, name='detail'),
    path('<int:cab_id>/availability/', api_views.cab_availability, name='availability'),
]
