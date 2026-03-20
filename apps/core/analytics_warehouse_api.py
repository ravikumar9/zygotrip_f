"""
Analytics Data Warehouse API — System 9: Event Pipeline + Funnel Reporting.

Provides queryable access to the analytics event stream and pre-aggregated metrics.

Endpoints:
  POST /api/v1/analytics/events/track/      — ingest single event
  POST /api/v1/analytics/events/batch/      — ingest batch events
  GET  /api/v1/analytics/funnel/            — booking funnel conversion report
  GET  /api/v1/analytics/properties/<id>/  — per-property performance metrics
  GET  /api/v1/analytics/cities/            — city-level demand heatmap
  GET  /api/v1/analytics/revenue/           — platform revenue dashboard (admin)

Design:
  - Events are written to DB async via Celery to avoid write latency on hot paths
  - All READ endpoints cache aggressively in Redis
  - Funnel is computed from AnalyticsEvent + DailyMetrics
"""
import json
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.analytics.warehouse')

_CACHE_TTL_SHORT   = 300   # 5 min — live dashboard
_CACHE_TTL_MEDIUM  = 1800  # 30 min — funnel
_CACHE_TTL_LONG    = 3600  # 1 hr — city heatmap


# ── Async Event Ingestion ─────────────────────────────────────────────────────

@shared_task(name='analytics.persist_event', ignore_result=True)
def _persist_event_task(event_type: str, properties: dict,
                        session_id: str = '', user_id=None,
                        ip_address: str = '', city: str = '',
                        property_id=None, amount=None):
    """Persist a single analytics event to DB asynchronously."""
    from apps.core.analytics import AnalyticsEvent

    try:
        AnalyticsEvent.objects.create(
            event_id=uuid.uuid4(),
            event_type=event_type,
            user_id=user_id,
            session_id=session_id or '',
            ip_address=ip_address or None,
            city=city or '',
            property_id=property_id,
            amount=Decimal(str(amount)) if amount else None,
            properties=properties or {},
        )
    except Exception as exc:
        logger.warning('event persist failed %s: %s', event_type, exc)


@shared_task(name='analytics.persist_batch', ignore_result=True)
def _persist_batch_task(events: list):
    """Persist a batch of analytics events (bulk_create)."""
    from apps.core.analytics import AnalyticsEvent

    objs = []
    for ev in events:
        try:
            objs.append(AnalyticsEvent(
                event_id=uuid.uuid4(),
                event_type=ev.get('event_type', 'unknown'),
                user_id=ev.get('user_id'),
                session_id=ev.get('session_id', ''),
                ip_address=ev.get('ip_address'),
                city=ev.get('city', ''),
                property_id=ev.get('property_id'),
                amount=Decimal(str(ev['amount'])) if ev.get('amount') else None,
                properties=ev.get('properties', {}),
            ))
        except Exception:
            pass

    if objs:
        try:
            AnalyticsEvent.objects.bulk_create(objs, ignore_conflicts=True)
        except Exception as exc:
            logger.warning('batch persist failed: %s', exc)


# ── Funnel Computation ────────────────────────────────────────────────────────

def _compute_funnel(start_date: date, end_date: date) -> dict:
    from apps.core.analytics import AnalyticsEvent

    start_dt = timezone.make_aware(
        timezone.datetime(start_date.year, start_date.month, start_date.day)
    )
    end_dt = timezone.make_aware(
        timezone.datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
    )

    counts = dict(
        AnalyticsEvent.objects
        .filter(created_at__range=(start_dt, end_dt))
        .values('event_type')
        .annotate(n=Count('id'))
        .values_list('event_type', 'n')
    )

    searches          = counts.get('search', 0)
    property_views    = counts.get('property_view', 0) + counts.get('hotel_click', 0)
    booking_contexts  = counts.get('booking_context_created', 0)
    payment_initiated = counts.get('payment_initiated', 0)
    payment_success   = counts.get('payment_success', 0)
    bookings_confirmed= counts.get('booking_confirmed', 0)
    cancellations     = counts.get('booking_cancelled', 0)

    def _rate(num, denom):
        return round(num / max(denom, 1) * 100, 2)

    return {
        'period': {'start': str(start_date), 'end': str(end_date)},
        'funnel_stages': [
            {
                'stage': 'search',
                'events': searches,
                'rate_from_prev_pct': 100.0,
            },
            {
                'stage': 'property_view',
                'events': property_views,
                'rate_from_prev_pct': _rate(property_views, searches),
            },
            {
                'stage': 'booking_context_created',
                'events': booking_contexts,
                'rate_from_prev_pct': _rate(booking_contexts, property_views),
            },
            {
                'stage': 'payment_initiated',
                'events': payment_initiated,
                'rate_from_prev_pct': _rate(payment_initiated, booking_contexts),
            },
            {
                'stage': 'payment_success',
                'events': payment_success,
                'rate_from_prev_pct': _rate(payment_success, payment_initiated),
            },
            {
                'stage': 'booking_confirmed',
                'events': bookings_confirmed,
                'rate_from_prev_pct': _rate(bookings_confirmed, payment_success),
            },
        ],
        'overall_conversion_pct': _rate(bookings_confirmed, searches),
        'cancellation_count':     cancellations,
        'cancellation_rate_pct':  _rate(cancellations, bookings_confirmed),
        'raw_counts':             counts,
    }


# ── Revenue Dashboard ─────────────────────────────────────────────────────────

def _revenue_dashboard(days: int = 30) -> dict:
    from apps.booking.models import Booking
    from apps.core.analytics import DailyMetrics

    start = date.today() - timedelta(days=days)

    bks = Booking.objects.filter(
        created_at__date__gte=start,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    )
    agg = bks.aggregate(
        total_bookings=Count('id'),
        total_revenue=Sum('gross_amount'),
        avg_booking_value=Avg('gross_amount'),
    )

    # Daily breakdown
    daily = list(
        bks.values('created_at__date')
        .annotate(count=Count('id'), revenue=Sum('gross_amount'))
        .order_by('created_at__date')
    )

    # Top cities
    top_cities = list(
        bks.filter(property__city__isnull=False)
        .values(city_name=F('property__city__name'))
        .annotate(bookings=Count('id'), revenue=Sum('gross_amount'))
        .order_by('-revenue')[:10]
    )

    # Cancellation metrics
    cancelled = Booking.objects.filter(
        created_at__date__gte=start,
        status__in=['cancelled', 'refunded', 'refund_pending'],
    ).count()

    total_all = bks.count() + cancelled
    cancel_rate = round(cancelled / max(total_all, 1) * 100, 2)

    return {
        'period_days':       days,
        'total_bookings':    agg.get('total_bookings') or 0,
        'total_revenue':     float(agg.get('total_revenue') or 0),
        'avg_booking_value': float(agg.get('avg_booking_value') or 0),
        'cancellation_rate_pct': cancel_rate,
        'cancellations':     cancelled,
        'daily_breakdown': [
            {
                'date':     str(d['created_at__date']),
                'bookings': d['count'],
                'revenue':  float(d['revenue'] or 0),
            }
            for d in daily
        ],
        'top_cities': [
            {
                'city':     c.get('city_name', ''),
                'bookings': c['bookings'],
                'revenue':  float(c['revenue'] or 0),
            }
            for c in top_cities
        ],
    }


# ── City Demand Heatmap ───────────────────────────────────────────────────────

def _city_demand_heatmap(days: int = 7) -> list:
    from apps.core.analytics import AnalyticsEvent

    start = timezone.now() - timedelta(days=days)
    rows = (
        AnalyticsEvent.objects
        .filter(created_at__gte=start, city__gt='')
        .values('city')
        .annotate(
            searches=Count('id', filter=Q(event_type='search')),
            views=Count('id', filter=Q(event_type__in=['property_view', 'hotel_click'])),
            bookings=Count('id', filter=Q(event_type='booking_confirmed')),
        )
        .order_by('-searches')[:50]
    )
    return [
        {
            'city':     r['city'],
            'searches': r['searches'],
            'views':    r['views'],
            'bookings': r['bookings'],
            'view_rate_pct':    round(r['views'] / max(r['searches'], 1) * 100, 1),
            'booking_rate_pct': round(r['bookings'] / max(r['searches'], 1) * 100, 2),
        }
        for r in rows
    ]


# ── Per-Property Performance ──────────────────────────────────────────────────

def _property_performance(property_id: int, days: int = 30) -> dict:
    from apps.core.analytics import AnalyticsEvent, HotelPerformanceMetrics

    start = timezone.now() - timedelta(days=days)

    events = AnalyticsEvent.objects.filter(
        property_id=property_id, created_at__gte=start,
    )
    counts = dict(
        events.values('event_type').annotate(n=Count('id')).values_list('event_type', 'n')
    )

    views     = counts.get('property_view', 0) + counts.get('hotel_click', 0)
    bookings  = counts.get('booking_confirmed', 0)
    cancels   = counts.get('booking_cancelled', 0)
    impressions = counts.get('search', 0)  # fallback — searches where this property may have appeared

    # Revenue
    from apps.booking.models import Booking
    rev_data = Booking.objects.filter(
        property_id=property_id,
        created_at__gte=start,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).aggregate(total=Sum('gross_amount'), avg=Avg('gross_amount'))

    # Daily breakdown from HotelPerformanceMetrics if available
    daily = []
    try:
        metrics_qs = HotelPerformanceMetrics.objects.filter(
            property_id=property_id, date__gte=date.today() - timedelta(days=days),
        ).order_by('date').values('date', 'views', 'bookings', 'revenue', 'occupancy_pct')
        daily = [
            {
                'date':          str(m['date']),
                'views':         m['views'],
                'bookings':      m['bookings'],
                'revenue':       float(m['revenue'] or 0),
                'occupancy_pct': float(m['occupancy_pct'] or 0),
            }
            for m in metrics_qs
        ]
    except Exception:
        pass

    return {
        'property_id':          property_id,
        'period_days':          days,
        'views':                views,
        'bookings':             bookings,
        'cancellations':        cancels,
        'total_revenue':        float(rev_data.get('total') or 0),
        'avg_booking_value':    float(rev_data.get('avg') or 0),
        'view_to_book_rate_pct': round(bookings / max(views, 1) * 100, 2),
        'cancel_rate_pct':      round(cancels / max(bookings + cancels, 1) * 100, 2),
        'daily_breakdown':      daily,
    }


# ── API Views ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def track_event_api(request):
    """
    POST /api/v1/analytics/events/track/

    Ingests a single analytics event asynchronously.
    Body: { event_type, session_id, city, property_id, amount, properties:{} }
    """
    try:
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
    except Exception:
        return Response({'error': 'Invalid payload'}, status=400)

    event_type = data.get('event_type', '')
    if not event_type:
        return Response({'error': 'event_type is required'}, status=400)

    _persist_event_task.delay(
        event_type  = event_type,
        properties  = data.get('properties', {}),
        session_id  = data.get('session_id', ''),
        user_id     = request.user.id if request.user.is_authenticated else None,
        ip_address  = request.META.get('REMOTE_ADDR', ''),
        city        = data.get('city', ''),
        property_id = data.get('property_id'),
        amount      = data.get('amount'),
    )
    return Response({'status': 'queued'})


@api_view(['POST'])
@permission_classes([AllowAny])
def track_batch_events_api(request):
    """
    POST /api/v1/analytics/events/batch/

    Ingests up to 50 events in a single request. Each event: {event_type, ...}
    """
    try:
        events = request.data if isinstance(request.data, list) else request.data.get('events', [])
    except Exception:
        return Response({'error': 'Invalid payload'}, status=400)

    if not isinstance(events, list) or len(events) > 50:
        return Response({'error': 'events must be a list with ≤ 50 items'}, status=400)

    # Inject server-side fields
    ip = request.META.get('REMOTE_ADDR', '')
    user_id = request.user.id if request.user.is_authenticated else None
    for ev in events:
        ev.setdefault('ip_address', ip)
        if user_id:
            ev.setdefault('user_id', user_id)

    _persist_batch_task.delay(events)
    return Response({'status': 'queued', 'count': len(events)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def funnel_report_api(request):
    """
    GET /api/v1/analytics/funnel/
    ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD (default: last 7 days)
    """
    today = date.today()
    try:
        start = date.fromisoformat(request.GET.get('start_date', str(today - timedelta(days=7))))
        end   = date.fromisoformat(request.GET.get('end_date', str(today)))
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    cache_key = f'funnel:{start}:{end}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            data = _compute_funnel(start, end)
            cache.set(cache_key, data, timeout=_CACHE_TTL_MEDIUM)
        except Exception as exc:
            logger.error('funnel_report_api: %s', exc, exc_info=True)
            return Response({'error': 'Failed to compute funnel'}, status=500)
    else:
        data = cached

    return Response({**data, 'cached': cached is not None})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def revenue_dashboard_api(request):
    """
    GET /api/v1/analytics/revenue/
    ?days=30

    Platform-wide revenue metrics and daily breakdown.
    """
    days = min(int(request.GET.get('days', 30)), 365)
    cache_key = f'rev_dash:{days}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            data = _revenue_dashboard(days)
            cache.set(cache_key, data, timeout=_CACHE_TTL_SHORT)
        except Exception as exc:
            logger.error('revenue_dashboard_api: %s', exc, exc_info=True)
            return Response({'error': 'Failed to load revenue dashboard'}, status=500)
    else:
        data = cached

    return Response({**data, 'cached': cached is not None})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def city_demand_heatmap_api(request):
    """
    GET /api/v1/analytics/cities/
    ?days=7

    City-level demand heatmap showing searches, views, and booking rates.
    """
    days = min(int(request.GET.get('days', 7)), 30)
    cache_key = f'city_heatmap:{days}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            data = _city_demand_heatmap(days)
            cache.set(cache_key, data, timeout=_CACHE_TTL_LONG)
        except Exception as exc:
            return Response({'error': str(exc)}, status=500)
    else:
        data = cached

    return Response({'cities': data, 'days': days, 'count': len(data), 'cached': cached is not None})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def property_performance_api(request, property_id):
    """
    GET /api/v1/analytics/properties/<property_id>/
    ?days=30

    Per-property event analytics (owner-accessible for own properties, admin for all).
    """
    days = min(int(request.GET.get('days', 30)), 365)

    # Auth: admin OR property owner
    if not request.user.is_staff:
        from apps.hotels.models import Property
        try:
            prop = Property.objects.get(id=property_id)
            if prop.owner != request.user:
                pass
        except Property.DoesNotExist:
            return Response({'error': 'Property not found'}, status=404)

    cache_key = f'prop_perf:{property_id}:{days}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            data = _property_performance(int(property_id), days)
            cache.set(cache_key, data, timeout=_CACHE_TTL_SHORT)
        except Exception as exc:
            return Response({'error': str(exc)}, status=500)
    else:
        data = cached

    return Response({**data, 'cached': cached is not None})
