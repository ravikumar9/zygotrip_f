from django.urls import path
from . import views
from . import dashboards

app_name = 'cabs'

urlpatterns = [
    # Public listing
    path('', views.cab_list, name='list'),
    path('<int:cab_id>/', views.cab_detail, name='detail'),
    path('<int:cab_id>/book/', views.cab_booking, name='booking'),
    path('booking/<int:booking_id>/success/', views.booking_success, name='booking-success'),

    # Dashboard
    path('dashboard/', dashboards.cab_dashboard, name='dashboard'),
    path('dashboard/cabs/<int:cab_id>/', dashboards.cab_detail, name='dashboard_detail'),
    path('dashboard/cabs/create/', dashboards.cab_create, name='dashboard_create'),
    
    # Owner management
    path('owner/register/', views.owner_cab_add, name='owner-add'),
    path('owner/all/', views.owner_cab_list, name='owner-list'),
    path('owner/<int:cab_id>/edit/', views.owner_cab_edit, name='owner-edit'),
    path('owner/<int:cab_id>/delete/', views.owner_cab_delete, name='owner-delete'),
]