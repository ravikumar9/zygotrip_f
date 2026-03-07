"""
Section 20 — Health Check & Observability API

Production health endpoints suitable for load-balancer probes, Kubernetes
liveness/readiness checks, and monitoring dashboards.

Endpoints:
  /api/health/           → quick liveness (DB, cache, 200/503)
  /api/health/detailed/  → full component check (DB, Redis, Celery, inventory)
  /api/metrics/          → Prometheus-compatible metrics (staff only)
"""
import logging
import time
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

logger = logging.getLogger('zygotrip.health')


class HealthCheckView(View):
    """
    Quick liveness probe. Returns 200 if DB and cache are reachable.
    Used by load balancers — must be fast (<500ms).
    """

    def get(self, request):
        start = time.time()
        checks = {}

        # DB
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks['database'] = 'ok'
        except Exception as e:
            checks['database'] = f'error: {e}'

        # Cache
        try:
            cache.set('healthcheck', 'ok', 10)
            val = cache.get('healthcheck')
            checks['cache'] = 'ok' if val == 'ok' else 'miss'
        except Exception as e:
            checks['cache'] = f'error: {e}'

        all_ok = all(v == 'ok' for v in checks.values())
        status = 200 if all_ok else 503
        elapsed_ms = int((time.time() - start) * 1000)

        return JsonResponse({
            'status': 'healthy' if all_ok else 'unhealthy',
            'checks': checks,
            'elapsed_ms': elapsed_ms,
            'timestamp': timezone.now().isoformat(),
        }, status=status)


class DetailedHealthCheckView(View):
    """
    Comprehensive health check for monitoring dashboards.
    Returns individual component statuses.
    """

    def get(self, request):
        start = time.time()
        components = {}

        # 1. Database
        components['database'] = self._check_database()

        # 2. Redis / cache
        components['cache'] = self._check_cache()

        # 3. Celery
        components['celery'] = self._check_celery()

        # 4. Inventory system
        components['inventory'] = self._check_inventory()

        # 5. Supplier health
        components['suppliers'] = self._check_suppliers()

        # 6. Recent error rate
        components['error_rate'] = self._check_error_rate()

        all_ok = all(c.get('status') == 'ok' for c in components.values())
        degraded = any(c.get('status') == 'degraded' for c in components.values())
        elapsed_ms = int((time.time() - start) * 1000)

        overall = 'healthy'
        http_status = 200
        if not all_ok and not degraded:
            overall = 'unhealthy'
            http_status = 503
        elif degraded:
            overall = 'degraded'
            http_status = 200  # still accept traffic

        return JsonResponse({
            'status': overall,
            'components': components,
            'elapsed_ms': elapsed_ms,
            'timestamp': timezone.now().isoformat(),
        }, status=http_status)

    @staticmethod
    def _check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return {'status': 'ok'}
        except Exception as e:
            return {'status': 'error', 'detail': str(e)}

    @staticmethod
    def _check_cache():
        try:
            test_key = 'health:cache_check'
            cache.set(test_key, 'value', 10)
            if cache.get(test_key) == 'value':
                return {'status': 'ok'}
            return {'status': 'degraded', 'detail': 'cache miss on write-read'}
        except Exception as e:
            return {'status': 'error', 'detail': str(e)}

    @staticmethod
    def _check_celery():
        """Check if Celery is responsive by inspecting recent task results."""
        from django.conf import settings
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            return {'status': 'ok', 'detail': 'eager mode (dev)'}
        try:
            from celery import current_app
            insp = current_app.control.inspect(timeout=2)
            active = insp.active()
            if active is not None:
                workers = len(active)
                return {'status': 'ok', 'workers': workers}
            return {'status': 'degraded', 'detail': 'no workers responding'}
        except Exception as e:
            return {'status': 'degraded', 'detail': str(e)}

    @staticmethod
    def _check_inventory():
        """Check if inventory system has recent updates."""
        try:
            from apps.inventory.models import InventoryCalendar
            cutoff = timezone.now() - timedelta(hours=24)
            recent = InventoryCalendar.objects.filter(updated_at__gte=cutoff).exists()
            if recent:
                return {'status': 'ok'}
            return {'status': 'degraded', 'detail': 'no inventory updates in 24h'}
        except Exception:
            return {'status': 'ok', 'detail': 'inventory check skipped'}

    @staticmethod
    def _check_suppliers():
        """Check SupplierHealth for any disabled suppliers."""
        try:
            from apps.inventory.models import SupplierHealth
            total = SupplierHealth.objects.count()
            healthy = SupplierHealth.objects.filter(is_healthy=True).count()
            if total == 0:
                return {'status': 'ok', 'detail': 'no suppliers configured'}
            if healthy == total:
                return {'status': 'ok', 'healthy': healthy, 'total': total}
            return {
                'status': 'degraded',
                'healthy': healthy,
                'total': total,
                'detail': f'{total - healthy} supplier(s) degraded',
            }
        except Exception:
            return {'status': 'ok', 'detail': 'supplier check skipped'}

    @staticmethod
    def _check_error_rate():
        """Check recent API error rate from PerformanceLog."""
        try:
            from apps.core.observability import PerformanceLog
            cutoff = timezone.now() - timedelta(hours=1)
            total = PerformanceLog.objects.filter(start_time__gte=cutoff).count()
            errors = PerformanceLog.objects.filter(
                start_time__gte=cutoff, status='error',
            ).count()
            rate = (errors / total * 100) if total > 0 else 0
            if rate < 5:
                return {'status': 'ok', 'error_rate': f'{rate:.1f}%', 'total_ops': total}
            if rate < 20:
                return {'status': 'degraded', 'error_rate': f'{rate:.1f}%', 'total_ops': total}
            return {'status': 'error', 'error_rate': f'{rate:.1f}%', 'total_ops': total}
        except Exception:
            return {'status': 'ok', 'detail': 'error rate check skipped'}


class MetricsView(View):
    """
    Prometheus-compatible metrics endpoint.
    Returns key metrics in text/plain format.
    Staff-only access.
    """

    def get(self, request):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        lines = []
        try:
            from apps.core.observability import SystemMetrics
            m = SystemMetrics.get_latest()
            if m:
                lines.extend([
                    f'# HELP zygo_bookings_total Total bookings',
                    f'# TYPE zygo_bookings_total gauge',
                    f'zygo_bookings_total {m.total_bookings}',
                    f'zygo_bookings_confirmed {m.confirmed_bookings}',
                    f'zygo_bookings_failed {m.failed_bookings}',
                    f'zygo_bookings_per_minute {m.bookings_per_minute}',
                    f'zygo_error_rate_percent {m.error_rate_percent}',
                    f'zygo_revenue_total {m.total_revenue}',
                    f'zygo_inventory_mismatches {m.inventory_mismatches}',
                    f'zygo_rooms_available {m.rooms_available}',
                ])
        except Exception:
            pass

        try:
            from apps.inventory.models import SupplierHealth
            for sh in SupplierHealth.objects.all():
                prefix = f'zygo_supplier_{sh.supplier_name}'
                lines.extend([
                    f'{prefix}_error_rate {sh.error_rate}',
                    f'{prefix}_latency_ms {sh.avg_latency_ms}',
                    f'{prefix}_healthy {1 if sh.is_healthy else 0}',
                ])
        except Exception:
            pass

        # S15: Include Prometheus registry metrics (request counters, histograms, business metrics)
        try:
            from apps.core.metrics import registry, collect_business_metrics
            collect_business_metrics()
            registry_output = registry.render()
            if registry_output.strip():
                lines.append('')
                lines.append(registry_output)
        except Exception:
            pass

        from django.http import HttpResponse
        return HttpResponse(
            '\n'.join(lines) + '\n',
            content_type='text/plain; version=0.0.4; charset=utf-8',
        )
