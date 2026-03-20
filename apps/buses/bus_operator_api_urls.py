from django.urls import path

from . import bus_operator_api

urlpatterns = [
    path('dashboard/', bus_operator_api.operator_dashboard, name='bus-operator-dashboard-v1'),
    path('buses/', bus_operator_api.buses_list, name='bus-operator-buses-list'),
    path('buses/create/', bus_operator_api.bus_create, name='bus-operator-buses-create'),
    path('buses/<int:bus_id>/update/', bus_operator_api.bus_update, name='bus-operator-buses-update'),
    path('buses/<int:bus_id>/delete/', bus_operator_api.bus_delete, name='bus-operator-buses-delete'),
]
