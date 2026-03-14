"""
System 15 — Prometheus-Compatible Metrics Endpoint.

Exposes /metrics in Prometheus text format with:
  - request_count, request_duration (by method, path, status)
  - db_query_count, db_query_duration
  - cache_hits, cache_misses
  - celery_tasks_active, celery_tasks_total
  - active_bookings, booking_conversions
  - error_rates (4xx, 5xx)
  - custom business metrics

Also provides:
  - MetricsMiddleware for automatic request instrumentation
  - Django view for /metrics endpoint
"""
import time
import threading
import logging
from collections import defaultdict
from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger('zygotrip.metrics')


class PrometheusRegistry:
    """
    Thread-safe metrics registry that can render Prometheus text format.
    Lightweight implementation — no external dependency needed.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters = defaultdict(float)
        self._gauges = defaultdict(float)
        self._histograms = defaultdict(list)  # label -> list of observed values
        self._help = {}
        self._type = {}

    def counter(self, name, value=1, labels=None, help_text=''):
        """Increment a counter metric."""
        key = self._label_key(name, labels)
        with self._lock:
            self._counters[key] += value
            if name not in self._help:
                self._help[name] = help_text
                self._type[name] = 'counter'

    def gauge(self, name, value, labels=None, help_text=''):
        """Set a gauge metric to an absolute value."""
        key = self._label_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            if name not in self._help:
                self._help[name] = help_text
                self._type[name] = 'gauge'

    def gauge_inc(self, name, value=1, labels=None, help_text=''):
        """Increment a gauge."""
        key = self._label_key(name, labels)
        with self._lock:
            self._gauges[key] += value
            if name not in self._help:
                self._help[name] = help_text
                self._type[name] = 'gauge'

    def gauge_dec(self, name, value=1, labels=None, help_text=''):
        """Decrement a gauge."""
        key = self._label_key(name, labels)
        with self._lock:
            self._gauges[key] -= value

    def histogram_observe(self, name, value, labels=None, help_text=''):
        """Record a histogram observation (for computing sum/count/buckets)."""
        key = self._label_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            if name not in self._help:
                self._help[name] = help_text
                self._type[name] = 'histogram'

    @staticmethod
    def _label_key(name, labels):
        if not labels:
            return name
        label_str = ','.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f'{name}{{{label_str}}}'

    def render(self):
        """Render all metrics in Prometheus text exposition format."""
        lines = []
        rendered_names = set()

        with self._lock:
            # Counters
            for key, value in sorted(self._counters.items()):
                name = key.split('{')[0]
                if name not in rendered_names:
                    if name in self._help:
                        lines.append(f'# HELP {name} {self._help[name]}')
                    lines.append(f'# TYPE {name} counter')
                    rendered_names.add(name)
                lines.append(f'{key} {value}')

            # Gauges
            for key, value in sorted(self._gauges.items()):
                name = key.split('{')[0]
                if name not in rendered_names:
                    if name in self._help:
                        lines.append(f'# HELP {name} {self._help[name]}')
                    lines.append(f'# TYPE {name} gauge')
                    rendered_names.add(name)
                lines.append(f'{key} {value}')

            # Histograms — render as _sum, _count
            hist_aggregates = defaultdict(lambda: {'sum': 0.0, 'count': 0})
            for key, values in self._histograms.items():
                name = key.split('{')[0]
                hist_aggregates[(name, key)]['sum'] = sum(values)
                hist_aggregates[(name, key)]['count'] = len(values)

            for (name, key), agg in sorted(hist_aggregates.items()):
                if name not in rendered_names:
                    if name in self._help:
                        lines.append(f'# HELP {name} {self._help[name]}')
                    lines.append(f'# TYPE {name} histogram')
                    rendered_names.add(name)
                # Replace closing brace for sum/count labels
                base_key = key.rstrip('}')
                if '{' in key:
                    lines.append(f'{base_key},le="+Inf"}} {agg["count"]}')
                    sum_key = key.replace('}', '') + '}'
                    lines.append(f'{name}_sum{key[len(name):]} {agg["sum"]:.6f}')
                    lines.append(f'{name}_count{key[len(name):]} {agg["count"]}')
                else:
                    lines.append(f'{name}_sum {agg["sum"]:.6f}')
                    lines.append(f'{name}_count {agg["count"]}')

        lines.append('')
        return '\n'.join(lines)


# Global registry
registry = PrometheusRegistry()


# ============================================================================
# MIDDLEWARE
# ============================================================================

class MetricsMiddleware:
    """
    Django middleware for automatic request instrumentation.

    Tracks:
      - zygotrip_http_requests_total{method, path, status}
      - zygotrip_http_request_duration_seconds{method, path}
      - zygotrip_http_requests_in_flight
    """

    SKIP_PATHS = {'/metrics', '/health', '/favicon.ico', '/static'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # Skip metrics/health/static endpoints
        if any(path.startswith(skip) for skip in self.SKIP_PATHS):
            return self.get_response(request)

        method = request.method
        # Normalize path to avoid cardinality explosion
        normalized_path = self._normalize_path(path)

        registry.gauge_inc('zygotrip_http_requests_in_flight',
                          labels={'method': method},
                          help_text='Number of HTTP requests currently being processed')

        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start

        status = str(response.status_code)
        labels = {'method': method, 'path': normalized_path, 'status': status}

        registry.counter('zygotrip_http_requests_total', labels=labels,
                        help_text='Total HTTP requests')
        registry.histogram_observe('zygotrip_http_request_duration_seconds',
                                  duration, labels={'method': method, 'path': normalized_path},
                                  help_text='HTTP request duration in seconds')

        registry.gauge_dec('zygotrip_http_requests_in_flight',
                          labels={'method': method})

        # Track error rates
        if response.status_code >= 500:
            registry.counter('zygotrip_http_errors_total',
                           labels={'method': method, 'path': normalized_path, 'type': '5xx'},
                           help_text='Total HTTP error responses')
        elif response.status_code >= 400:
            registry.counter('zygotrip_http_errors_total',
                           labels={'method': method, 'path': normalized_path, 'type': '4xx'},
                           help_text='Total HTTP error responses')

        return response

    @staticmethod
    def _normalize_path(path):
        """
        Replace dynamic segments (UUIDs, IDs) with placeholders
        to prevent label cardinality explosion.
        """
        import re
        # Replace UUID-like segments
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{uuid}', path, flags=re.IGNORECASE,
        )
        # Replace numeric IDs
        path = re.sub(r'/\d+(?=/|$)', '/{id}', path)
        return path


# ============================================================================
# BUSINESS METRICS COLLECTOR
# ============================================================================

def track_search_latency(duration_seconds: float, search_type: str = 'hotel'):
    """
    Record a search request latency observation.
    Call this from search views after computing results.

    Args:
        duration_seconds: Time taken to complete the search.
        search_type: hotel | bus | cab | package
    """
    registry.histogram_observe(
        'zygotrip_search_latency_seconds',
        duration_seconds,
        labels={'search_type': search_type},
        help_text='Search request latency in seconds',
    )


def track_booking_outcome(success: bool):
    """
    Increment the booking success or failure counter.
    Call this after a booking attempt resolves.
    """
    registry.counter(
        'zygotrip_booking_attempts_total',
        labels={'outcome': 'success' if success else 'failure'},
        help_text='Total booking attempts by outcome',
    )


def track_payment_outcome(success: bool, gateway: str = 'razorpay'):
    """
    Increment the payment success or failure counter.
    Call this after a payment transaction resolves.
    """
    registry.counter(
        'zygotrip_payment_attempts_total',
        labels={'outcome': 'success' if success else 'failure', 'gateway': gateway},
        help_text='Total payment attempts by outcome and gateway',
    )


def collect_business_metrics():
    """
    Collect current business metrics from DB.
    Called by the /metrics view to provide point-in-time gauges.
    """
    try:
        from apps.booking.models import Booking
        from django.db.models import Count, Q

        now = timezone.now()
        today = now.date()

        # Active bookings
        active = Booking.objects.filter(
            status__in=['confirmed', 'checked_in', 'hold', 'payment_pending'],
        ).count()
        registry.gauge('zygotrip_bookings_active', active,
                      help_text='Number of currently active bookings')

        # Today's bookings
        today_bookings = Booking.objects.filter(created_at__date=today).count()
        registry.gauge('zygotrip_bookings_today', today_bookings,
                      help_text='Bookings created today')

        # Conversion rate (contexts → bookings today)
        from apps.booking.models import BookingContext
        contexts_today = BookingContext.objects.filter(created_at__date=today).count()
        converted_today = BookingContext.objects.filter(
            created_at__date=today, context_status='converted',
        ).count()
        if contexts_today > 0:
            rate = round(converted_today / contexts_today * 100, 2)
        else:
            rate = 0
        registry.gauge('zygotrip_conversion_rate_percent', rate,
                      help_text='Booking context to booking conversion rate (%)')

        # ── Booking success rate (last 24h) ──
        last_24h = now - timezone.timedelta(hours=24)
        total_24h = Booking.objects.filter(created_at__gte=last_24h).count()
        confirmed_24h = Booking.objects.filter(
            created_at__gte=last_24h,
            status__in=['confirmed', 'checked_in'],
        ).count()
        failed_24h = Booking.objects.filter(
            created_at__gte=last_24h,
            status__in=['failed', 'payment_failed'],
        ).count()
        cancelled_24h = Booking.objects.filter(
            created_at__gte=last_24h,
            status='cancelled',
        ).count()

        registry.gauge('zygotrip_bookings_confirmed_24h', confirmed_24h,
                      help_text='Confirmed bookings in last 24h')
        registry.gauge('zygotrip_bookings_failed_24h', failed_24h,
                      help_text='Failed bookings in last 24h')
        registry.gauge('zygotrip_bookings_cancelled_24h', cancelled_24h,
                      help_text='Cancelled bookings in last 24h')

        if total_24h > 0:
            success_rate = round(confirmed_24h / total_24h * 100, 2)
        else:
            success_rate = 0
        registry.gauge('zygotrip_booking_success_rate_percent', success_rate,
                      help_text='Booking success rate in last 24h (%)')

    except Exception as exc:
        logger.warning('Business metrics collection failed: %s', exc)

    try:
        from apps.payments.models import PaymentTransaction
        pending_payments = PaymentTransaction.objects.filter(
            status='pending',
        ).count()
        registry.gauge('zygotrip_payments_pending', pending_payments,
                      help_text='Number of pending payment transactions')

        # ── Payment failure rate (last 24h) ──
        last_24h = timezone.now() - timezone.timedelta(hours=24)
        total_payments_24h = PaymentTransaction.objects.filter(
            created_at__gte=last_24h,
        ).count()
        failed_payments_24h = PaymentTransaction.objects.filter(
            created_at__gte=last_24h,
            status='failed',
        ).count()

        registry.gauge('zygotrip_payments_total_24h', total_payments_24h,
                      help_text='Total payment transactions in last 24h')
        registry.gauge('zygotrip_payments_failed_24h', failed_payments_24h,
                      help_text='Failed payment transactions in last 24h')

        if total_payments_24h > 0:
            fail_rate = round(failed_payments_24h / total_payments_24h * 100, 2)
        else:
            fail_rate = 0
        registry.gauge('zygotrip_payment_failure_rate_percent', fail_rate,
                      help_text='Payment failure rate in last 24h (%)')

    except Exception as exc:
        logger.warning('Payment metrics collection failed: %s', exc)

    # ── Inventory & supplier health ──
    try:
        from apps.inventory.models import SupplierHealth
        unhealthy = SupplierHealth.objects.filter(is_healthy=False).count()
        total_suppliers = SupplierHealth.objects.count()
        registry.gauge('zygotrip_suppliers_total', total_suppliers,
                      help_text='Total registered supplier connections')
        registry.gauge('zygotrip_suppliers_unhealthy', unhealthy,
                      help_text='Number of unhealthy supplier connections')
    except Exception as exc:
        logger.warning('Supplier metrics collection failed: %s', exc)


# ============================================================================
# VIEWS
# ============================================================================

def metrics_view(request):
    """
    Prometheus-compatible /metrics endpoint.
    Returns text/plain in Prometheus exposition format.
    """
    # Collect point-in-time business metrics
    collect_business_metrics()

    body = registry.render()
    return HttpResponse(body, content_type='text/plain; version=0.0.4; charset=utf-8')
