from django.urls import path
from . import api_views
from apps.dashboard_owner.revenue_api import (
    revenue_intelligence_api, market_comparison_api, demand_forecast_api,
    owner_command_center_api,
)

urlpatterns = [
    # ── Revenue Intelligence (System 7) ──────────────────────────────────
    path('command-center/',       owner_command_center_api,    name='owner-command-center'),
    path('revenue-intelligence/', revenue_intelligence_api, name='owner-revenue-intelligence'),
    path('market-comparison/',    market_comparison_api,    name='owner-market-comparison'),
    path('demand-forecast/',      demand_forecast_api,      name='owner-demand-forecast'),

    # Hotel Owner (existing)
    path('summary/', api_views.owner_dashboard_summary, name='owner-dashboard-summary'),
    path('inventory/', api_views.owner_inventory_calendar, name='owner-inventory-calendar'),
    path('bulk-price/', api_views.owner_bulk_price_update, name='owner-bulk-price-update'),
    path('analytics/', api_views.owner_booking_analytics, name='owner-booking-analytics'),
    path('revenue/', api_views.owner_revenue_dashboard, name='owner-revenue-dashboard'),
    # Bus Operator
    path('bus/dashboard/', api_views.bus_operator_dashboard, name='bus-operator-dashboard'),
    path('bus/schedules/', api_views.bus_schedule_management, name='bus-schedule-management'),
    # Cab Fleet
    path('cab/dashboard/', api_views.cab_fleet_dashboard, name='cab-fleet-dashboard'),
    # Package Provider
    path('package/dashboard/', api_views.package_provider_dashboard, name='package-provider-dashboard'),
]
