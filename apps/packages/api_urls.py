from django.urls import path
from . import api_views

app_name = 'packages_api'

urlpatterns = [
    path('book/', api_views.package_book, name='book'),
    path('bookings/', api_views.booking_list, name='bookings-list'),
    path('bookings/<uuid:booking_uuid>/', api_views.booking_detail, name='booking-detail'),
    path('bookings/<uuid:booking_uuid>/cancel/', api_views.booking_cancel, name='booking-cancel'),
    path('search/', api_views.search_packages, name='search'),
    path('destinations/', api_views.popular_destinations, name='destinations'),
    path('categories/', api_views.package_categories, name='categories'),
    path('<int:package_id>/availability/', api_views.package_availability, name='availability'),
    path('<slug:slug>/', api_views.package_detail, name='detail'),
    path('<slug:slug>/bundle-pricing/', api_views.bundle_pricing, name='bundle-pricing'),
]
