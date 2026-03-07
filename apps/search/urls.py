from django.urls import path
from .views_production import search_list, search_autocomplete, search_api

app_name = "search"

urlpatterns = [
    path("", search_list, name="list"),
    path("autocomplete/", search_autocomplete, name="autocomplete"),
    path("api/", search_api, name="api_search"),
]