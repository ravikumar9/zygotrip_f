"""
Admin Monitoring & Alerting API — System 17: Admin Monitoring and Alerts.

Monitors:
  - Payment failure rate (alert if > 20% in last hour)
  - Booking spikes (alert if > 3× normal volume)
  - Inventory mismatches (negative available_rooms)
  - Supplier sync failures (unhealthy connections)
  - Pricing anomalies (> 50% price swing from yesterday)

GET /api/v1/admin/monitoring/alerts/  — current active alerts
GET /api/v1/admin/monitoring/health/  — platform health summary
"""
import logging
from datetime import timedelta

from django.db.models import Count, Avg, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.admin.monitoring')


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_payment_failure_rate() -> dict:
    try:
        from apps.payments.models import PaymentTransaction
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent  = PaymentTransaction.objects.filter(created_at__gte=one_hour_ago)
        total   = recent.count()
        failed  = recent.filter(status='failed').count()
        rate    = round(failed / total * 100, 1) if total else 0.0
        return {
            'check':     'payment_failure_rate',
            'value':     rate,
            'threshold': 20.0,
            'alert':     rate > 20.0,
            'severity':  'critical' if rate > 30 else 'warning',
            'message':   f'Payment failure rate {rate}% ({failed}/{total}) in last hour',
        }
    except Exception as exc:
        return {'check': 'payment_failure_rate', 'alert': False, 'message': str(exc)}


def _check_booking_spike() -> dict:
    try:
        from apps.booking.models import Booking
        now        = timezone.now()
        last_hour  = Booking.objects.filter(created_at__gte=now - timedelta(hours=1)).count()
        week_count = Booking.objects.filter(
            created_at__gte=now - timedelta(days=7),
            created_at__lt=now  - timedelta(hours=1),
        ).count()
        hourly_avg = week_count / (7 * 24)
        spike      = last_hour > (hourly_avg * 3) if hourly_avg > 0 else False
        return {
            'check':    'booking_spike',
            'value':    last_hour,
            'baseline': round(hourly_avg, 1),
            'alert':    spike,
            'severity': 'warning',
            'message':  f'Bookings last hour: {last_hour} (avg {round(hourly_avg,1)}/hr)',
        }
    except Exception as exc:
        return {'check': 'booking_spike', 'alert': False, 'message': str(exc)}


def _check_inventory_mismatches() -> dict:
    try:
        from apps.rooms.models import RoomInventory
        neg = RoomInventory.objects.filter(available_rooms__lt=0).count()
        return {
            'check':     'inventory_mismatches',
            'value':     neg,
            'threshold': 0,
            'alert':     neg > 0,
            'severity':  'critical' if neg > 5 else 'warning',
            'message':   f'{neg} room inventory records with negative availability',
        }
    except Exception as exc:
        return {'check': 'inventory_mismatches', 'alert': False, 'message': str(exc)}


def _check_supplier_sync() -> dict:
    try:
        from apps.inventory.models import SupplierHealth
        unhealthy = SupplierHealth.objects.filter(
            is_healthy=False,
            last_checked__gte=timezone.now() - timedelta(hours=2),
        ).count()
        return {
            'check':    'supplier_sync_failures',
            'value':    unhealthy,
            'alert':    unhealthy > 0,
            'severity': 'warning',
            'message':  f'{unhealthy} supplier connection(s) currently unhealthy',
        }
    except Exception as exc:
        return {'check': 'supplier_sync_failures', 'alert': False, 'message': str(exc)}


def _check_pricing_anomalies() -> dict:
    try:
        from apps.pricing.models import CompetitorPrice
        from datetime import date
        today     = date.today()
        yesterday = today - timedelta(days=1)

        anomalies = 0
        today_px  = {
            cp.property_id: float(cp.price_per_night)
            for cp in CompetitorPrice.objects.filter(date=today)
        }
        yest_px = {
            cp.property_id: float(cp.price_per_night)
            for cp in CompetitorPrice.objects.filter(date=yesterday)
        }
        for pid, tp in today_px.items():
            yp = yest_px.get(pid)
            if yp and yp > 0 and abs(tp - yp) / yp > 0.5:
                anomalies += 1

        return {
            'check':     'pricing_anomalies',
            'value':     anomalies,
            'threshold': 5,
            'alert':     anomalies > 5,
            'severity':  'warning',
            'message':   f'{anomalies} properties with >50% price change vs yesterday',
        }
    except Exception as exc:
        return {'check': 'pricing_anomalies', 'alert': False, 'message': str(exc)}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def monitoring_alerts_api(request):
    """GET /api/v1/admin/monitoring/alerts/"""
    checks  = [
        _check_payment_failure_rate(),
        _check_booking_spike(),
        _check_inventory_mismatches(),
        _check_supplier_sync(),
        _check_pricing_anomalies(),
    ]
    alerts = [c for c in checks if c.get('alert')]
    return Response({
        'total_checks':  len(checks),
        'active_alerts': len(alerts),
        'alerts':        alerts,
        'all_checks':    checks,
        'generated_at':  timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def platform_health_api(request):
    """GET /api/v1/admin/monitoring/health/"""
    from apps.booking.models import Booking
    from apps.payments.models import PaymentTransaction

    now   = timezone.now()
    last  = now - timedelta(hours=24)
    bks   = Booking.objects.filter(created_at__gte=last)
    pays  = PaymentTransaction.objects.filter(created_at__gte=last)

    return Response({
        'status': 'operational',
        'metrics': {
            'bookings_24h':        bks.count(),
            'confirmed_24h':       bks.filter(status='confirmed').count(),
            'cancelled_24h':       bks.filter(status='cancelled').count(),
            'payments_24h':        pays.count(),
            'payment_success_24h': pays.filter(status='success').count(),
            'payment_failed_24h':  pays.filter(status='failed').count(),
        },
        'generated_at': now.isoformat(),
    })
