from django.urls import path
from . import seo_api

app_name = 'seo_api'

urlpatterns = [
    path('cities/', seo_api.city_list_for_sitemap, name='cities'),
    path('city/<slug:city_slug>/', seo_api.city_seo_data, name='city'),
    path('city/<slug:city_slug>/meta/', seo_api.city_meta_data, name='city-meta'),
    path('city/<slug:city_slug>/<slug:segment>/', seo_api.segment_seo_data, name='segment'),
]
