from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.views import serve as static_serve
from django.urls import include, path, re_path
from django.views.generic import TemplateView
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
from apps.core.notification_views import notification_list, mark_notifications_read, unread_count
from apps.core.health import health_check, health_check_detailed
from apps.core.health_checks import HealthCheckView, DetailedHealthCheckView, MetricsView

urlpatterns = [
    # ── Health checks (no auth, no middleware overhead) ─────────────────
    path('api/health/live/', health_check, name='health_liveness'),
    path('api/health/ready/', health_check_detailed, name='health_readiness'),
    # Section 20: Enhanced health & observability endpoints
    path('api/health/', HealthCheckView.as_view(), name='health_quick'),
    path('api/health/detailed/', DetailedHealthCheckView.as_view(), name='health_detailed'),
    path('api/metrics/', MetricsView.as_view(), name='prometheus_metrics'),

    # ── REST API v1 (highest priority) ─────────────────────────────────
    path('api/v1/', include('apps.hotels.api.v1.urls')),
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    path('api/v1/booking/', include('apps.booking.api.v1.urls')),
    path('api/v1/wallet/', include('apps.wallet.api.v1.urls')),
    path('api/v1/payment/', include('apps.payments.api.v1.urls')),
    path('api/v1/promo/apply/', apply_promo, name='api_promo_apply'),

    # Notifications API
    path('api/v1/notifications/', notification_list, name='api_notifications'),
    path('api/v1/notifications/mark-read/', mark_notifications_read, name='api_notifications_mark_read'),
    path('api/v1/notifications/unread-count/', unread_count, name='api_notifications_unread'),

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
