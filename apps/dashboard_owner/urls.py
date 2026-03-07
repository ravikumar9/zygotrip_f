from django.urls import path
from .views import (
    add_meal, add_property, add_room, dashboard, set_price, submit_approval,
    add_property_image, add_room_image, update_ratings, edit_property_features,
    add_offer, add_room_amenity, delete_room_amenity, cancellation_policy
)
from .owner_views import (
    booking_list, revenue_dashboard, checkin_management, inventory_management,
    export_bookings_csv, api_booking_checkin, api_booking_checkout, api_booking_cancel
)

app_name = 'dashboard_owner'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    
    # Property management
    path('properties/add/', add_property, name='add_property'),
    path('properties/<int:property_id>/edit/', edit_property_features, name='edit_property'),
    path('properties/<int:property_id>/rooms/add/', add_room, name='add_room'),
    path('properties/<int:property_id>/meals/add/', add_meal, name='add_meal'),
    path('properties/<int:property_id>/images/add/', add_property_image, name='add_property_image'),
    path('properties/<int:property_id>/offers/add/', add_offer, name='add_offer'),
    path('properties/<int:property_id>/ratings/update/', update_ratings, name='update_ratings'),
    path('properties/<int:property_id>/cancellation-policy/', cancellation_policy, name='cancellation_policy'),
    path('properties/<int:property_id>/submit/', submit_approval, name='submit_approval'),
    
    # Room management
    path('rooms/<int:room_id>/price/', set_price, name='set_price'),
    path('rooms/<int:room_id>/images/add/', add_room_image, name='add_room_image'),
    path('rooms/<int:room_id>/amenities/add/', add_room_amenity, name='add_room_amenity'),
    path('amenities/<int:amenity_id>/delete/', delete_room_amenity, name='delete_room_amenity'),
    
    # Business dashboard (new views)
    path('bookings/', booking_list, name='booking_list'),
    path('bookings/export/', export_bookings_csv, name='export_bookings'),
    path('revenue/', revenue_dashboard, name='revenue_dashboard'),
    path('checkins/', checkin_management, name='checkin_management'),
    path('inventory/', inventory_management, name='inventory_general'),
    
    # Property-specific inventory (legacy)
    path('properties/<int:property_id>/inventory/', inventory_management, name='inventory_management'),
    
    # API endpoints
    path('api/booking/<int:booking_id>/checkin/', api_booking_checkin, name='api_booking_checkin'),
    path('api/booking/<int:booking_id>/checkout/', api_booking_checkout, name='api_booking_checkout'),
    path('api/booking/<int:booking_id>/cancel/', api_booking_cancel, name='api_booking_cancel'),
]