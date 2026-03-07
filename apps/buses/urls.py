from django.urls import path
from . import views
from . import dashboards

app_name = 'buses'

urlpatterns = [
    path('', views.list_buses, name='list'),
    path('<int:bus_id>/', views.bus_detail, name='detail'),
    path('<int:bus_id>/book/', views.bus_booking, name='booking'),
    path('booking/<uuid:booking_uuid>/', views.booking_review, name='review'),
    path('booking/<uuid:booking_uuid>/success/', views.booking_success, name='booking-success'),

    # Dashboard
    path('dashboard/', dashboards.bus_dashboard, name='dashboard'),
    path('dashboard/buses/<int:bus_id>/', dashboards.bus_detail, name='dashboard_detail'),
    path('dashboard/buses/create/', dashboards.bus_create, name='dashboard_create'),
    
    # Owner route
    path('owner/register/', views.owner_bus_add, name='owner-add'),
]