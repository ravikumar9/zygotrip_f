"""Flight API URL routing."""
from django.urls import path
from . import api_views

app_name = 'flights'

urlpatterns = [
    path('search/', api_views.flight_search, name='flight_search'),
    path('fare-calendar/', api_views.flight_fare_calendar, name='fare_calendar'),
    path('airports/', api_views.airport_search, name='airport_search'),
    path('book/', api_views.flight_book, name='flight_book'),
    path('my-bookings/', api_views.flight_my_bookings, name='flight_my_bookings'),
    path('booking/<str:pnr>/', api_views.flight_booking_detail, name='flight_booking_detail'),
    path('cancel/<str:pnr>/', api_views.flight_cancel, name='flight_cancel'),
]
