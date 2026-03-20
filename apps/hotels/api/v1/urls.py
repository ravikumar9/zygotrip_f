"""Hotels API v1 URL configuration"""
from django.urls import path
from . import views
from . import review_views
from apps.pricing.calendar_api import price_calendar_api

app_name = 'hotels_api_v1'


# ── Wishlist lazy wrappers ─────────────────────────────────────────────────────
# Imported lazily to avoid circular import at module load time.

def _property_save_toggle(request, *args, **kwargs):
    from apps.hotels.wishlist_api import property_save_toggle
    return property_save_toggle(request, *args, **kwargs)

def _saved_properties_list(request, *args, **kwargs):
    from apps.hotels.wishlist_api import saved_properties_list
    return saved_properties_list(request, *args, **kwargs)

def _saved_property_ids(request, *args, **kwargs):
    from apps.hotels.wishlist_api import saved_property_ids
    return saved_property_ids(request, *args, **kwargs)


urlpatterns = [
    # Property listing + full-text search
    path('properties/', views.property_list_api, name='property_list'),
    path('search/', views.property_search_api, name='search'),

    # Top-level price calendar must come before the generic slug route,
    # otherwise "price-calendar" is captured as a property slug and 404s.
    path('properties/price-calendar/', price_calendar_api, name='price_calendar_global'),

    # -- Wishlist ---------------------------------------------------------------
    # These two routes must come before the generic <slug:property_id> pattern
    # so that "saved" and "saved/ids" are not captured as property slugs.
    path('properties/saved/', _saved_properties_list, name='saved_properties'),
    path('properties/saved/ids/', _saved_property_ids, name='saved_property_ids'),

    # Property detail — accepts BOTH numeric IDs and slugs.
    # <slug:property_id> matches [-a-zA-Z0-9_]+ which includes plain integers,
    # so a single pattern handles /properties/42/ and /properties/coorg-valley-resort/.
    path('properties/<str:property_id>/', views.property_detail_api, name='property_detail'),
    path('properties/<str:property_id>/availability/', views.property_availability_api, name='property_availability'),
    path('properties/<str:property_id>/reviews/', review_views.property_reviews, name='property_reviews'),

    # Price calendar (Step 10)
    path('properties/<str:property_id>/price-calendar/', views.price_calendar_api, name='price_calendar'),

    # Conversion signals (Step 11)
    path('properties/<str:property_id>/signals/', views.conversion_signals_api, name='conversion_signals'),

    # -- Wishlist save/unsave/check per-property --------------------------------
    path('properties/<str:property_id>/save/', _property_save_toggle, name='property_save_toggle'),

    # Reviews
    path('reviews/', review_views.submit_review, name='submit_review'),
    path('reviews/my/', review_views.my_reviews, name='my_reviews'),

    # Price intelligence (competitor benchmarking)
    path('pricing/intelligence/<uuid:property_uuid>/', views.pricing_intelligence_api, name='pricing_intelligence'),

    # Booking.com-style fast search (Step 5)
    path('booking-search/', views.booking_search_api, name='booking_search'),
    path('booking-search/facets/', views.booking_search_facets_api, name='booking_search_facets'),

    # Autosuggest (Goibibo-style) — canonical endpoint: /api/v1/autosuggest/
    path('autosuggest/', views.autosuggest_api, name='autosuggest'),

    # Aggregations (city/area counts for filter UI)
    # Both slash and no-slash variants (APPEND_SLASH=False; Next.js proxy strips trailing slashes)
    path('hotels/aggregations/', views.aggregations_api, name='aggregations'),
    path('hotels/aggregations', views.aggregations_api, name='aggregations_noslash'),
]
