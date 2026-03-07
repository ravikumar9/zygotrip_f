"""Hotels API v1 URL configuration"""
from django.urls import path
from . import views
from . import review_views

app_name = 'hotels_api_v1'

urlpatterns = [
    # Property listing + full-text search
    path('properties/', views.property_list_api, name='property_list'),
    path('search/', views.property_search_api, name='search'),

    # Property detail — accepts BOTH numeric IDs and slugs.
    # <slug:property_id> matches [-a-zA-Z0-9_]+ which includes plain integers,
    # so a single pattern handles /properties/42/ and /properties/coorg-valley-resort/.
    path('properties/<slug:property_id>/', views.property_detail_api, name='property_detail'),
    path('properties/<slug:property_id>/availability/', views.property_availability_api, name='property_availability'),
    path('properties/<slug:property_id>/reviews/', review_views.property_reviews, name='property_reviews'),

    # Price calendar (Step 10)
    path('properties/<slug:property_id>/price-calendar/', views.price_calendar_api, name='price_calendar'),

    # Conversion signals (Step 11)
    path('properties/<slug:property_id>/signals/', views.conversion_signals_api, name='conversion_signals'),

    # Reviews
    path('reviews/', review_views.submit_review, name='submit_review'),
    path('reviews/my/', review_views.my_reviews, name='my_reviews'),

    # Pricing quote
    path('pricing/quote/', views.pricing_quote_api, name='pricing_quote'),

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
