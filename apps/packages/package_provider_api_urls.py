from django.urls import path

from . import package_provider_api

urlpatterns = [
    path('dashboard/', package_provider_api.package_provider_dashboard, name='package-provider-dashboard-v1'),
    path('catalog/', package_provider_api.package_list, name='package-provider-catalog-list'),
    path('catalog/create/', package_provider_api.package_create, name='package-provider-catalog-create'),
    path('catalog/<int:package_id>/update/', package_provider_api.package_update, name='package-provider-catalog-update'),
    path('catalog/<int:package_id>/delete/', package_provider_api.package_delete, name='package-provider-catalog-delete'),
]
