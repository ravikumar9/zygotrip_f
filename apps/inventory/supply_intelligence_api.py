"""
Supply Intelligence API — System 7B: Supply Gap Detection.

Detects cities and areas where booking demand exceeds available hotel supply.
Generates prioritized alerts for the hotel onboarding team.

Endpoints:
  GET /api/v1/admin/supply/intelligence/   — city-level supply gaps
  GET /api/v1/admin/supply/city/<city_id>/ — per-city drill-down
  GET /api/v1/admin/supply/alerts/         — actionable onboarding alerts

Algorithm:
  supply_gap_score = (search_volume - (active_hotels * avg_availability)) / search_volume
  demand_intensity  = searches_last_7d / total_cities_avg_searches
  priority          = gap_score × demand_intensity × 100
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum, F
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.supply.intelligence')

SUPPLY_CACHE_TTL = 3600   # 1 hour — supply gaps don't change by the minute
MIN_SEARCHES_THRESHOLD = 10  # Ignore cities with very few searches


# ── Core analytics helpers ────────────────────────────────────────────────────

def _city_search_volumes(days: int = 7) -> dict:
    """Return {city_name: search_count} for recent searches."""
    from apps.core.analytics import AnalyticsEvent

    start = timezone.now() - timedelta(days=days)
    rows = (
        AnalyticsEvent.objects
        .filter(event_type='search', created_at__gte=start, city__gt='')
        .values('city')
        .annotate(searches=Count('id'))
        .order_by('-searches')
    )
    return {r['city']: r['searches'] for r in rows}


def _city_hotel_supply() -> dict:
    """Return {city_name: {hotels, avg_price, avg_rating, avg_availability}} from approved hotels."""
    from apps.hotels.models import Property
    from apps.rooms.models import RoomType

    rows = (
        Property.objects
        .filter(status='approved', is_active=True)
        .select_related('city')
        .values('city__name')
        .annotate(
            hotels=Count('id'),
            avg_price=Avg('room_types__base_price'),
            avg_rating=Avg('rating'),
        )
    )
    supply = {}
    for r in rows:
        city = r['city__name'] or ''
        if city:
            supply[city] = {
                'hotels': r['hotels'] or 0,
                'avg_price': float(r['avg_price'] or 0),
                'avg_rating': float(r['avg_rating'] or 0),
            }

    # Avg available rooms per city (today + next 7 days)
    try:
        from apps.inventory.models import InventoryCalendar

        today = date.today()
        end = today + timedelta(days=7)
        inv_rows = (
            InventoryCalendar.objects
            .filter(date__range=(today, end), is_closed=False)
            .values('room_type__property__city__name')
            .annotate(avg_avail=Avg('available_rooms'))
        )
        for r in inv_rows:
            city = r['room_type__property__city__name'] or ''
            if city and city in supply:
                supply[city]['avg_availability'] = float(r['avg_avail'] or 0)
    except Exception:
        pass

    return supply


def _compute_supply_gaps(search_volumes: dict, hotel_supply: dict) -> list:
    """
    Cross-reference search demand with hotel supply.
    Returns sorted list of gap dicts.
    """
    all_cities = set(search_volumes.keys()) | set(hotel_supply.keys())
    total_searches = sum(search_volumes.values()) or 1
    avg_searches = total_searches / max(len(search_volumes), 1)

    gaps = []
    for city in all_cities:
        searches = search_volumes.get(city, 0)
        supply = hotel_supply.get(city, {})
        hotels = supply.get('hotels', 0)

        if searches < MIN_SEARCHES_THRESHOLD and hotels > 0:
            continue  # Skip low-signal cities with supply

        # Supply gap: fraction of demand that can't be met
        effective_supply = hotels * supply.get('avg_availability', 5.0)
        if searches > 0:
            gap_score = max(0.0, (searches - effective_supply) / searches)
        elif hotels == 0:
            gap_score = 0.0  # No searches, no supply — not actionable
        else:
            gap_score = 0.0

        # Demand intensity vs platform average
        demand_intensity = searches / avg_searches if avg_searches > 0 else 0.0

        # Priority = gap_score × demand_intensity × 100 (0-100 scale)
        priority = round(gap_score * demand_intensity * 100, 1)

        # Classify urgency
        if priority >= 60:
            urgency = 'critical'
        elif priority >= 30:
            urgency = 'high'
        elif priority >= 10:
            urgency = 'medium'
        else:
            urgency = 'low'

        # Onboarding recommendation
        if hotels == 0:
            recommendation = f'No active hotels in {city}. Immediate onboarding required.'
        elif gap_score > 0.7:
            target = max(3, round(searches / 10))
            recommendation = f'Demand severely exceeds supply. Target: {target} additional hotels.'
        elif gap_score > 0.4:
            target = max(1, round(searches / 20))
            recommendation = f'Moderate supply gap. Recommend sourcing {target} more hotels.'
        else:
            recommendation = 'Supply sufficient — monitor for growth.'

        gaps.append({
            'city':                  city,
            'searches_7d':           searches,
            'active_hotels':         hotels,
            'avg_hotel_price':       round(supply.get('avg_price', 0), 2),
            'avg_hotel_rating':      round(supply.get('avg_rating', 0), 2),
            'avg_available_rooms':   round(supply.get('avg_availability', 0), 2),
            'supply_gap_score':      round(gap_score, 3),
            'demand_intensity':      round(demand_intensity, 2),
            'priority_score':        priority,
            'urgency':               urgency,
            'recommendation':        recommendation,
        })

    # Sort by priority descending
    gaps.sort(key=lambda x: x['priority_score'], reverse=True)
    return gaps


def _onboarding_alerts(gaps: list) -> list:
    """Extract actionable alerts from gap list (critical + high urgency only)."""
    return [
        {
            'city':        g['city'],
            'urgency':     g['urgency'],
            'searches_7d': g['searches_7d'],
            'hotels':      g['active_hotels'],
            'gap_score':   g['supply_gap_score'],
            'priority':    g['priority_score'],
            'action':      g['recommendation'],
        }
        for g in gaps
        if g['urgency'] in ('critical', 'high')
    ]


# ── City Drill-Down ───────────────────────────────────────────────────────────

def _city_drill_down(city_id: int) -> dict:
    """Detailed supply analysis for a single city."""
    from apps.core.location_models import City
    from apps.hotels.models import Property
    from apps.core.analytics import AnalyticsEvent

    try:
        city = City.objects.get(id=city_id)
    except Exception:
        return {}

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Properties in city
    props = Property.objects.filter(city=city, status='approved', is_active=True)
    hotel_count = props.count()

    star_breakdown = list(
        props.values('star_category').annotate(count=Count('id')).order_by('star_category')
    )

    # Search demand
    search_7d = AnalyticsEvent.objects.filter(
        event_type='search', city__iexact=city.name, created_at__gte=week_ago,
    ).count()
    search_30d = AnalyticsEvent.objects.filter(
        event_type='search', city__iexact=city.name, created_at__gte=month_ago,
    ).count()

    # Booking demand
    from apps.booking.models import Booking
    bookings_30d = Booking.objects.filter(
        property__city=city,
        created_at__gte=month_ago,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).count()

    # Revenue potential (avg city booking value)
    rev_data = Booking.objects.filter(
        property__city=city, created_at__gte=month_ago,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).aggregate(avg_val=Avg('gross_amount'), total_rev=Sum('gross_amount'))

    # Price range
    from apps.rooms.models import RoomType
    price_data = RoomType.objects.filter(
        property__city=city, property__status='approved', is_active=True,
    ).aggregate(
        min_price=Avg('base_price'),
        max_price=Avg('base_price'),
    )

    return {
        'city': {
            'id': city.id,
            'name': city.name,
            'state': str(getattr(city, 'state', '') or ''),
            'slug': getattr(city, 'slug', ''),
        },
        'supply': {
            'active_hotels': hotel_count,
            'star_breakdown': star_breakdown,
            'min_price': round(float(price_data.get('min_price') or 0), 2),
            'max_price': round(float(price_data.get('max_price') or 0), 2),
        },
        'demand': {
            'searches_7d':       search_7d,
            'searches_30d':      search_30d,
            'bookings_30d':      bookings_30d,
            'avg_booking_value': round(float(rev_data.get('avg_val') or 0), 2),
            'total_revenue_30d': round(float(rev_data.get('total_rev') or 0), 2),
        },
        'search_to_booking_rate_pct': round(
            bookings_30d / max(search_30d, 1) * 100, 2
        ),
    }


# ── API Endpoints ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def supply_intelligence_api(request):
    """
    GET /api/v1/admin/supply/intelligence/
    ?days=7&min_priority=0&urgency=critical,high,medium

    Returns city-level supply gap analysis for hotel onboarding teams.
    """
    days          = min(int(request.GET.get('days', 7)), 30)
    min_priority  = float(request.GET.get('min_priority', 0))
    urgency_filter = set(request.GET.get('urgency', '').split(',')) - {''}

    cache_key = f'supply_intel:v2:{days}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            search_volumes = _city_search_volumes(days=days)
            hotel_supply   = _city_hotel_supply()
            gaps           = _compute_supply_gaps(search_volumes, hotel_supply)
            cache.set(cache_key, gaps, timeout=SUPPLY_CACHE_TTL)
        except Exception as exc:
            logger.error('supply_intelligence_api error: %s', exc, exc_info=True)
            return Response({'error': 'Failed to compute supply intelligence'}, status=500)
    else:
        gaps = cached

    # Apply filters
    filtered = [g for g in gaps if g['priority_score'] >= min_priority]
    if urgency_filter:
        filtered = [g for g in filtered if g['urgency'] in urgency_filter]

    alerts = _onboarding_alerts(gaps)

    return Response({
        'summary': {
            'total_cities_analyzed': len(gaps),
            'critical_gaps':         sum(1 for g in gaps if g['urgency'] == 'critical'),
            'high_gaps':             sum(1 for g in gaps if g['urgency'] == 'high'),
            'cities_no_hotels':      sum(1 for g in gaps if g['active_hotels'] == 0),
            'analysis_period_days':  days,
        },
        'supply_gaps':       filtered,
        'onboarding_alerts': alerts,
        'cached':            cached is not None,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def supply_city_drilldown_api(request, city_id):
    """
    GET /api/v1/admin/supply/city/<city_id>/
    Detailed supply + demand analysis for a single city.
    """
    cache_key = f'supply_city:{city_id}'
    cached = cache.get(cache_key)
    if cached is None:
        try:
            data = _city_drill_down(int(city_id))
            if not data:
                return Response({'error': 'City not found'}, status=404)
            cache.set(cache_key, data, timeout=SUPPLY_CACHE_TTL)
        except Exception as exc:
            logger.error('supply_city_drilldown_api error: %s', exc, exc_info=True)
            return Response({'error': 'Failed to load city supply data'}, status=500)
    else:
        data = cached

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def supply_alerts_api(request):
    """
    GET /api/v1/admin/supply/alerts/
    Fast endpoint returning only actionable onboarding alerts (critical + high).
    """
    cache_key = 'supply_intel:v2:7'
    gaps = cache.get(cache_key)
    if gaps is None:
        try:
            search_volumes = _city_search_volumes(days=7)
            hotel_supply   = _city_hotel_supply()
            gaps           = _compute_supply_gaps(search_volumes, hotel_supply)
            cache.set(cache_key, gaps, timeout=SUPPLY_CACHE_TTL)
        except Exception as exc:
            return Response({'error': str(exc)}, status=500)

    alerts = _onboarding_alerts(gaps)
    return Response({
        'alerts':        alerts,
        'alert_count':   len(alerts),
        'critical_count': sum(1 for a in alerts if a['urgency'] == 'critical'),
        'high_count':    sum(1 for a in alerts if a['urgency'] == 'high'),
    })
