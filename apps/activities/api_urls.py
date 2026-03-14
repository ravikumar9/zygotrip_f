"""Activity API URL routing."""
from django.urls import path
from . import api_views

app_name = 'activities'

urlpatterns = [
    path('search/', api_views.activity_search, name='activity_search'),
    path('categories/', api_views.activity_categories, name='activity_categories'),
    path('detail/<slug:slug>/', api_views.activity_detail, name='activity_detail'),
    path('<int:pk>/slots/', api_views.activity_slots, name='activity_slots'),
    path('<int:pk>/reviews/', api_views.activity_reviews, name='activity_reviews'),
    path('book/', api_views.activity_book, name='activity_book'),
    path('my-bookings/', api_views.activity_my_bookings, name='activity_my_bookings'),
    path('booking/<str:ref>/', api_views.activity_booking_detail, name='activity_booking_detail'),
    path('cancel/<str:ref>/', api_views.activity_cancel, name='activity_cancel'),
]
