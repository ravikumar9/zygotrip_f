from django.urls import path
from .views import dashboard

app_name = 'dashboard_finance'

urlpatterns = [
    path('', dashboard, name='dashboard'),
]