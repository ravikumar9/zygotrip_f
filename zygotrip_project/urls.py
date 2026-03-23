from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.views import serve as static_serve
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from apps.accounts.views import (
    LoginView, register_view, logout_view,
    register_traveler, register_property_owner, register_cab_owner,
    register_bus_operator, register_package_provider
)
from apps.search.views_production import cities_autocomplete, location_autocomplete, search_index_api
from apps.hotels.api import suggest_hotels
from apps.dashboard_owner.views import add_property
from apps.cabs.dashboards import cab_create
from apps.buses.dashboards import bus_create
from apps.promos.api_views import apply_promo
from apps.offers.api_views import featured_offers
from apps.core.notification_views import notification_list, mark_notifications_read, unread_count
from apps.core.health import health_check, health_check_detailed
from apps.core.health_checks import HealthCheckView, DetailedHealthCheckView, MetricsView
from apps.inventory.supplier_sync_api import supplier_webhook, trigger_supplier_sync, supplier_sync_status
from apps.hotels.rate_plan_api import rate_plans_api
from apps.pricing.views import price_quote

admin.site.site_header = 'ZygoTrip Control Center'
admin.site.site_title = 'ZygoTrip Admin'
admin.site.index_title = 'Platform Operations'

urlpatterns = [
    # ── Health checks (no auth, no middleware overhead) ─────────────────
    path('api/health/live/', health_check, name='health_liveness'),
    path('api/health/ready/', health_check_detailed, name='health_readiness'),
    # Section 20: Enhanced health & observability endpoints
    path('api/health/', HealthCheckView.as_view(), name='health_quick'),
    path('api/health/detailed/', DetailedHealthCheckView.as_view(), name='health_detailed'),
    path('api/metrics/', MetricsView.as_view(), name='prometheus_metrics'),

    # ── API Documentation (OpenAPI / Swagger / ReDoc) ──────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ── REST API v1 (highest priority) ─────────────────────────────────
    path('api/v1/pricing/quote/', price_quote, name='pricing_quote'),
    path('api/v1/', include('apps.hotels.api.v1.urls')),
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    path('api/v1/', include('apps.referrals.api.v1.urls')),
    path('api/v1/booking/', include('apps.booking.api.v1.urls')),
    path('api/v1/wallet/', include('apps.wallet.api.v1.urls')),
    path('api/v1/payment/', include('apps.payments.api.v1.urls')),
    path('api/v1/checkout/', include('apps.checkout.api.v1.urls')),
    path('api/v1/ai/', include('apps.ai.api.v1.urls')),
    path('api/v1/loyalty/', include('apps.loyalty.api.v1.urls')),
    path('api/v1/notifications/', include('apps.notifications.api.v1.urls')),
    path('api/v1/buses/', include('apps.buses.api_urls')),
    path('api/v1/cabs/', include('apps.cabs.api_urls')),
    path('api/v1/packages/', include('apps.packages.api_urls')),
    path('api/v1/flights/', include('apps.flights.api_urls')),
    path('api/v1/activities/', include('apps.activities.api_urls')),
    path('api/v1/support/', include('apps.support.api_urls')),
    path('api/v1/seo/', include('apps.search.seo_urls')),
    path('api/v1/dashboard/owner/', include('apps.dashboard_owner.api_urls')),
    path('api/v1/dashboard/owner-api/', include('apps.dashboard_owner.owner_api_urls')),
    path('api/v1/dashboard/bus-operator/', include('apps.buses.bus_operator_api_urls')),
    path('api/v1/dashboard/cab-owner/', include('apps.cabs.cab_owner_api_urls')),
    path('api/v1/dashboard/package-provider/', include('apps.packages.package_provider_api_urls')),
    path('api/v1/', include('apps.core.api_v1_urls')),
    path('api/v1/promo/apply/', apply_promo, name='api_promo_apply'),
    path('api/v1/offers/featured/', featured_offers, name='api_offers_featured'),

    # Notifications API
    path('api/v1/notifications/', notification_list, name='api_notifications'),
    path('api/v1/notifications/mark-read/', mark_notifications_read, name='api_notifications_mark_read'),
    path('api/v1/notifications/unread-count/', unread_count, name='api_notifications_unread'),

    # ── v1 aliases for health & metrics (Prometheus + healthcheck probes) ──
    path('api/v1/health/', HealthCheckView.as_view(), name='health_quick_v1'),
    path('api/v1/health/detailed/', DetailedHealthCheckView.as_view(), name='health_detailed_v1'),
    path('api/v1/metrics/', MetricsView.as_view(), name='prometheus_metrics_v1'),
    # ── Rate Plans API (System 3) ─────────────────────────────────────────
    path('api/v1/rate-plans/', rate_plans_api, name='api_rate_plans'),

    # ── Supplier Sync API (System 16) ─────────────────────────────────────
    path('api/v1/supplier/webhook/<str:provider>/', supplier_webhook, name='supplier_webhook'),
    path('api/v1/supplier/sync/<uuid:property_uuid>/', trigger_supplier_sync, name='supplier_sync_trigger'),
    path('api/v1/supplier/sync-status/', supplier_sync_status, name='supplier_sync_status'),

    # Legacy API endpoints
    path('api/hotels/suggest/', suggest_hotels, name='api_hotels_suggest'),
    path('api/search/', search_index_api, name='search_index_api'),
    path('api/cities/', cities_autocomplete, name='cities_autocomplete'),
    path('api/locations/', location_autocomplete, name='location_autocomplete'),

    # ── Core & Auth ─────────────────────────────────────────────────────
    path('', include('apps.core.urls')),
    path('login/', LoginView.as_view(), name='account_login'),
    path('logout/', logout_view, name='account_logout'),
    path('register/', register_view, name='account_register'),
    path('register/traveler/', register_traveler, name='register_traveler'),
    path('register/property-owner/', register_property_owner, name='register_property_owner'),
    path('register/cab-owner/', register_cab_owner, name='register_cab_owner'),
    path('register/bus-operator/', register_bus_operator, name='register_bus_operator'),
    path('register/package-provider/', register_package_provider, name='register_package_provider'),
    path('accounts/', include('apps.accounts.urls')),

    # ── Hotels, Search, Transport ────────────────────────────────────────
    path('hotels/', include('apps.hotels.urls')),
    path('search/', include('apps.search.urls')),
    path('buses/', include('apps.buses.urls')),
    path('packages/', include('apps.packages.urls')),
    path('cabs/', include('apps.cabs.urls')),

    # ── Booking & Payments ───────────────────────────────────────────────
    path('register/property/', include('apps.registration.urls')),
    path('booking/', include('apps.booking.urls')),
    path('invoice/', include('apps.payments.urls')),

    # ── Dashboards ───────────────────────────────────────────────────────
    path('owner/property/create/', add_property, name='owner_property_create'),
    path('vendor/cab/create/', cab_create, name='vendor_cab_create'),
    path('vendor/bus/create/', bus_create, name='vendor_bus_create'),
    path('owner/dashboard/', include('apps.dashboard_owner.urls')),
    path('admin/dashboard/', include('apps.dashboard_admin.urls')),
    path('finance/dashboard/', include('apps.dashboard_finance.urls')),
    path('admin/', admin.site.urls),

    # ── Legal ────────────────────────────────────────────────────────────
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy_policy'),
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms_of_service'),
]

handler403 = 'apps.core.views.permission_denied'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if not settings.DEBUG:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", static_serve, kwargs={"insecure": True}),
    ]
