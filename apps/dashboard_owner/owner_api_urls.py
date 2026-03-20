from django.urls import path

from . import owner_api

urlpatterns = [
    path('summary/', owner_api.owner_dashboard_summary, name='owner-api-summary'),
    path('properties/', owner_api.owner_properties_list, name='owner-api-properties-list'),
    path('properties/create/', owner_api.owner_property_create, name='owner-api-properties-create'),
    path('properties/<int:property_id>/update/', owner_api.owner_property_update, name='owner-api-properties-update'),
    path('properties/<int:property_id>/delete/', owner_api.owner_property_delete, name='owner-api-properties-delete'),
]
