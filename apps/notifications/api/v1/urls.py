from django.urls import path
from . import views

urlpatterns = [
    path('device/register/', views.RegisterDeviceView.as_view(), name='notif-device-register-v2'),
    path('device/', views.register_device_token, name='notif-device-register'),
    path('device/unregister/', views.unregister_device_token, name='notif-device-unregister'),
    path('history/', views.notification_history, name='notif-history'),
    path('preferences/', views.update_preferences, name='notif-preferences'),
]
