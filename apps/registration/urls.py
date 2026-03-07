from django.urls import path
from .views import register_property, register_bus, register_cab

app_name = 'registration'

urlpatterns = [
	path('property/', register_property, name='property'),
	path('bus/', register_bus, name='bus'),
	path('cab/', register_cab, name='cab'),
]