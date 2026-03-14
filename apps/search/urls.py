from django.urls import path
from .views_production import (
    search_list, search_autocomplete, search_api,
    track_search_click, nearby_hotels_api, geo_viewport_search,
)

app_name = "search"

urlpatterns = [
    path("", search_list, name="list"),
    path("autocomplete/", search_autocomplete, name="autocomplete"),
    path("api/", search_api, name="api_search"),
    path("api/track-click/", track_search_click, name="track_click"),
    path("api/nearby/", nearby_hotels_api, name="nearby_hotels"),
    path("api/geo/", geo_viewport_search, name="geo_viewport"),   # map viewport search
]