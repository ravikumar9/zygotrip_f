"""
Core API v1 URL config — Places, Currency, Geo Search, Map, Analytics, Route, Email.
Includes: Push Notifications, Holiday Calendar, Admin Monitoring.
"""
from django.urls import path
from . import api_v1_views

# Lazy imports to avoid circular imports at startup
def _fcm_register(request, *args, **kwargs):
    from apps.core.fcm_api import register_device
    return register_device(request, *args, **kwargs)

def _fcm_unregister(request, *args, **kwargs):
    from apps.core.fcm_api import unregister_device
    return unregister_device(request, *args, **kwargs)

def _holiday_calendar(request, *args, **kwargs):
    from apps.pricing.calendar_api import holiday_calendar_api
    return holiday_calendar_api(request, *args, **kwargs)

def _monitoring_alerts(request, *args, **kwargs):
    from apps.dashboard_admin.monitoring_api import monitoring_alerts_api
    return monitoring_alerts_api(request, *args, **kwargs)

def _platform_health(request, *args, **kwargs):
    from apps.dashboard_admin.monitoring_api import platform_health_api
    return platform_health_api(request, *args, **kwargs)

# ── Supply Intelligence (System 7B) ─────────────────────────────────────────
def _supply_intelligence(request, *args, **kwargs):
    from apps.inventory.supply_intelligence_api import supply_intelligence_api
    return supply_intelligence_api(request, *args, **kwargs)

def _supply_city(request, *args, **kwargs):
    from apps.inventory.supply_intelligence_api import supply_city_drilldown_api
    return supply_city_drilldown_api(request, *args, **kwargs)

def _supply_alerts(request, *args, **kwargs):
    from apps.inventory.supply_intelligence_api import supply_alerts_api
    return supply_alerts_api(request, *args, **kwargs)

# ── Analytics Data Warehouse (System 9) ──────────────────────────────────────
def _analytics_track(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import track_event_api
    return track_event_api(request, *args, **kwargs)

def _analytics_batch(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import track_batch_events_api
    return track_batch_events_api(request, *args, **kwargs)

def _analytics_funnel_report(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import funnel_report_api
    return funnel_report_api(request, *args, **kwargs)

def _analytics_revenue(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import revenue_dashboard_api
    return revenue_dashboard_api(request, *args, **kwargs)

def _analytics_cities(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import city_demand_heatmap_api
    return city_demand_heatmap_api(request, *args, **kwargs)

def _analytics_property(request, *args, **kwargs):
    from apps.core.analytics_warehouse_api import property_performance_api
    return property_performance_api(request, *args, **kwargs)

app_name = "core_api_v1"

urlpatterns = [
    # ── Gateway Discovery ───────────────────────────────────────────────
    path("gateway/services/", api_v1_views.gateway_services, name="gateway_services"),

    # ── Places (Google Places + local hybrid) ──────────────────────────
    path("places/autocomplete/", api_v1_views.places_autocomplete, name="places_autocomplete"),
    path("places/details/", api_v1_views.places_details, name="places_details"),
    path("places/geocode/", api_v1_views.places_geocode, name="places_geocode"),

    # ── Currency ───────────────────────────────────────────────────────
    path("currency/rates/", api_v1_views.currency_rates, name="currency_rates"),
    path("currency/convert/", api_v1_views.currency_convert, name="currency_convert"),
    path("currency/supported/", api_v1_views.currency_supported, name="currency_supported"),
    path("currency/detect/", api_v1_views.currency_detect, name="currency_detect"),

    # ── Geo Search ─────────────────────────────────────────────────────
    path("geo-search/", api_v1_views.geo_search, name="geo_search"),
    path("geo-search/nearby/", api_v1_views.geo_search_nearby, name="geo_search_nearby"),

    # ── Map Discovery ──────────────────────────────────────────────────
    path("map/bounding-box/", api_v1_views.map_bounding_box, name="map_bounding_box"),
    path("map/hotel/<int:hotel_id>/", api_v1_views.map_hotel_detail, name="map_hotel_detail"),

    # ── Trust Signals ──────────────────────────────────────────────────
    path("trust-signals/<int:hotel_id>/", api_v1_views.trust_signals, name="trust_signals"),

    # ── Analytics ──────────────────────────────────────────────────────
    path("analytics/funnel/track/", api_v1_views.analytics_funnel_track, name="analytics_funnel_track"),
    path("analytics/funnel/", api_v1_views.analytics_funnel, name="analytics_funnel"),
    path("analytics/popular-destinations/", api_v1_views.analytics_popular_destinations, name="analytics_popular_destinations"),
    path("analytics/pricing/", api_v1_views.analytics_pricing_competitiveness, name="analytics_pricing"),
    path("analytics/user-behavior/", api_v1_views.analytics_user_behavior, name="analytics_user_behavior"),

    # ── A/B Testing ────────────────────────────────────────────────────
    path("ab-test/assign/", api_v1_views.ab_test_assign, name="ab_test_assign"),
    path("ab-test/results/", api_v1_views.ab_test_results, name="ab_test_results"),

    # ── Route calculation ──────────────────────────────────────────────
    path("route/calculate/", api_v1_views.cab_route_calculate, name="route_calculate"),

    # ── Email (staff-only) ─────────────────────────────────────────────
    path("email/test/", api_v1_views.send_test_email, name="email_test"),

    # ── Recommendations ────────────────────────────────────────────────
    path("recommendations/similar/<int:hotel_id>/", api_v1_views.recommendations_similar, name="recommendations_similar"),
    path("recommendations/popular/", api_v1_views.recommendations_popular, name="recommendations_popular"),
    path("recommendations/best-value/", api_v1_views.recommendations_best_value, name="recommendations_best_value"),
    path("recommendations/trending/", api_v1_views.recommendations_trending, name="recommendations_trending"),

    # ── Push Notification Device Registration (System 8) ───────────────
    path("devices/register/", _fcm_register, name="fcm_register"),
    path("devices/unregister/", _fcm_unregister, name="fcm_unregister"),

    # ── Holiday Calendar (System 2) ─────────────────────────────────────
    path("pricing/holidays/", _holiday_calendar, name="holiday_calendar"),

    # ── Admin Monitoring (System 17) ────────────────────────────────────
    path("admin/monitoring/alerts/", _monitoring_alerts, name="admin_monitoring_alerts"),
    path("admin/monitoring/health/", _platform_health, name="admin_platform_health"),

    # ── Supply Intelligence (System 7B) ──────────────────────────────────
    path("admin/supply/intelligence/",           _supply_intelligence, name="supply_intelligence"),
    path("admin/supply/city/<int:city_id>/",     _supply_city,         name="supply_city_drill"),
    path("admin/supply/alerts/",                 _supply_alerts,       name="supply_alerts"),

    # ── Analytics Data Warehouse (System 9) ──────────────────────────────
    path("analytics/events/track/",              _analytics_track,          name="analytics_event_track"),
    path("analytics/events/batch/",              _analytics_batch,          name="analytics_event_batch"),
    path("analytics/funnel/report/",             _analytics_funnel_report,  name="analytics_funnel_report"),
    path("analytics/revenue/",                   _analytics_revenue,        name="analytics_revenue_dash"),
    path("analytics/cities/",                    _analytics_cities,         name="analytics_city_heatmap"),
    path("analytics/properties/<int:property_id>/", _analytics_property,   name="analytics_prop_perf"),
]
