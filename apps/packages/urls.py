"""
Packages URL configuration
"""
from django.urls import path
from .views import package_list, package_detail, package_booking

app_name = "packages"

urlpatterns = [
    path("", package_list, name="list"),
    path("<int:package_id>/", package_detail, name="detail"),
    path("<int:package_id>/book/", package_booking, name="booking"),
]