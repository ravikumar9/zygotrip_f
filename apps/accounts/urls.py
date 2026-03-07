from django.urls import path
from .views import LoginView, logout_view, profile, customer_dashboard, register_view

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', register_view, name='register'),
    path('profile/', profile, name='profile'),
    path('dashboard/', customer_dashboard, name='customer_dashboard'),
    path('logout/', logout_view, name='logout'),
]