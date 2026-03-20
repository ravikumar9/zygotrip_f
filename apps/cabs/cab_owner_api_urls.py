from django.urls import path

from . import cab_owner_api

urlpatterns = [
    path('dashboard/', cab_owner_api.cab_owner_dashboard, name='cab-owner-dashboard-v1'),
    path('fleet/', cab_owner_api.cabs_list, name='cab-owner-fleet-list'),
    path('fleet/create/', cab_owner_api.cab_create, name='cab-owner-fleet-create'),
    path('fleet/<int:cab_id>/update/', cab_owner_api.cab_update, name='cab-owner-fleet-update'),
    path('fleet/<int:cab_id>/delete/', cab_owner_api.cab_delete, name='cab-owner-fleet-delete'),
]
