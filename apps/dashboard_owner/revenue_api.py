"""
Owner Revenue Intelligence API — System 7: Owner Dashboard Analytics.

Provides property owners with:
  - Market price comparison vs competitors
  - Booking demand trends (last 30 days)
  - Search impressions and conversion rates
  - 30-day demand forecast (holiday + seasonal aware)
  - RevPAR and occupancy metrics

RULES:
  - All price suggestions are ADVISORY — never auto-modify prices
  - Only return data for properties owned by the authenticated user
  - Cache results for 1 hour
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean

from django.core.cache import cache
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.dashboard.owner.revenue')


def _owner_props(user):
    from apps.hotels.models import Property
    return Property.objects.filter(owner=user, status='approved')


# ── Analytics helpers ─────────────────────────────────────────────────────────

def _market_comparison(prop) -> dict:
    from apps.pricing.models import CompetitorPrice
    from apps.rooms.models import RoomType
    from apps.hotels.models import Property

    today = date.today()

    # Cheapest room price for this property
    my_room = RoomType.objects.filter(property=prop).order_by('base_price').first()
    my_price = float(my_room.base_price) if my_room else 0.0

    # Competitor snapshot avg (last 7 days)
    comp_avg = CompetitorPrice.objects.filter(
        property=prop,
        date__gte=today - timedelta(days=7),
        is_available=True,
    ).aggregate(avg=Avg('price_per_night'))['avg']

    # Nearby peers (same city + star category)
    peers = Property.objects.filter(
        city=prop.city,
        star_category=prop.star_category,
        status='approved',
    ).exclude(id=prop.id)
    city_avg = RoomType.objects.filter(
        property__in=peers
    ).aggregate(avg=Avg('base_price'))['avg'] or 0

    market_avg = float(comp_avg or city_avg or 0)
    comp_index = round(my_price / market_avg, 2) if market_avg > 0 else 1.0

    if comp_index > 1.15:
        suggestion = {
            'type': 'price_high',
            'message': (f'Your price is {round((comp_index-1)*100)}% above market average. '
                        f'Consider ₹{round(market_avg*1.05, 0)}/night to improve bookings.'),
            'recommended_price': round(market_avg * 1.05, 0),
        }
    elif comp_index < 0.85:
        suggestion = {
            'type': 'price_low',
            'message': (f'Your price is {round((1-comp_index)*100)}% below average. '
                        f'Consider raising to ₹{round(market_avg*0.95, 0)}/night.'),
            'recommended_price': round(market_avg * 0.95, 0),
        }
    else:
        suggestion = {
            'type': 'price_optimal',
            'message': 'Your pricing is competitive.',
            'recommended_price': None,
        }

    cheaper = peers.filter(room_types__base_price__lt=my_price).distinct().count()
    return {
        'my_price':          my_price,
        'market_avg':        round(market_avg, 2),
        'city_peers_count':  peers.count(),
        'price_rank':        cheaper + 1,
        'competitive_index': comp_index,
        'pricing_suggestion': suggestion,
    }


def _booking_trends(prop, days=30) -> list:
    from apps.booking.models import Booking
    start = date.today() - timedelta(days=days)
    rows = (
        Booking.objects
        .filter(
            property=prop,
            created_at__date__gte=start,
            status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
        )
        .values('created_at__date')
        .annotate(count=Count('id'), revenue=Sum('gross_amount'))
        .order_by('created_at__date')
    )
    return [
        {
            'date':     str(r['created_at__date']),
            'bookings': r['count'],
            'revenue':  float(r['revenue'] or 0),
        }
        for r in rows
    ]


def _search_analytics(prop) -> dict:
    try:
        from apps.search.models import PropertySearchIndex
        idx = PropertySearchIndex.objects.get(property=prop)
        imp   = idx.total_impressions or 0
        clicks= idx.total_clicks or 0
        bks   = idx.total_bookings or 0
        ctr   = round(clicks / imp * 100, 2) if imp > 0 else 0.0
        conv  = round(bks / clicks * 100, 2) if clicks > 0 else 0.0
        return {
            'impressions':            imp,
            'clicks':                 clicks,
            'bookings_from_search':   bks,
            'click_through_rate_pct': ctr,
            'conversion_rate_pct':    conv,
        }
    except Exception:
        return {
            'impressions': 0, 'clicks': 0, 'bookings_from_search': 0,
            'click_through_rate_pct': 0.0, 'conversion_rate_pct': 0.0,
        }


def _demand_forecast(prop, days=30) -> list:
    today = date.today()
    try:
        wp = prop.weekend_pricing
        wknd_mult = float(wp.weekend_multiplier) if (wp and wp.is_active) else 1.15
        wknd_days = set(wp.weekend_days) if (wp and wp.weekend_days) else {5, 6}
    except Exception:
        wknd_mult, wknd_days = 1.15, {5, 6}

    forecast = []
    for i in range(days):
        d = today + timedelta(days=i)
        is_wknd = d.isoweekday() in wknd_days

        # Holiday
        hol_name, hol_mult = None, 1.0
        try:
            from apps.core.models import HolidayCalendar
            h = HolidayCalendar.objects.filter(date=d, country='IN', is_active=True)\
                    .order_by('-demand_multiplier').first()
            if h:
                hol_name = h.holiday_name
                hol_mult = float(h.demand_multiplier)
        except Exception:
            pass

        # Seasonal
        sea_mult = 1.0
        try:
            from apps.pricing.models import SeasonalPricing
            sp = SeasonalPricing.objects.filter(
                property=prop, start_date__lte=d, end_date__gte=d, is_active=True,
            ).order_by('-multiplier').first()
            if sp:
                sea_mult = float(sp.multiplier)
        except Exception:
            pass

        w_m   = wknd_mult if is_wknd else 1.0
        level = max(hol_mult, sea_mult, w_m)
        label = (
            'very_high' if level >= 1.8 else
            'high'      if level >= 1.4 else
            'medium'    if level >= 1.1 else
            'normal'
        )
        forecast.append({
            'date':             str(d),
            'is_weekend':       is_wknd,
            'is_holiday':       hol_name is not None,
            'holiday_name':     hol_name,
            'demand_multiplier': round(level, 2),
            'demand_level':     label,
        })
    return forecast


def _revenue_stats(prop) -> dict:
    from apps.booking.models import Booking
    today = date.today()
    start = today - timedelta(days=30)
    bks = Booking.objects.filter(
        property=prop,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
        check_in__gte=start,
    )
    total_rev = bks.aggregate(s=Sum('gross_amount'))['s'] or Decimal('0')
    total_bks = bks.count()

    nights_sold = sum(
        (b.check_out - b.check_in).days
        for b in bks
        if b.check_in and b.check_out
    )
    from apps.rooms.models import RoomType
    room_types_count = RoomType.objects.filter(property=prop).count()
    total_room_nights = max(1, room_types_count) * 30
    occupancy = round(nights_sold / total_room_nights * 100, 1) if total_room_nights else 0.0
    revpar    = round(float(total_rev) / total_room_nights, 2)   if total_room_nights else 0.0

    return {
        'period':               '30_days',
        'total_revenue':        float(total_rev),
        'total_bookings':       total_bks,
        'nights_sold':          nights_sold,
        'occupancy_rate_pct':   occupancy,
        'revpar':               revpar,
        'avg_booking_value':    round(float(total_rev) / max(1, total_bks), 2),
    }


def _conversion_summary(prop, days=30) -> dict:
    from apps.core.analytics import get_property_analytics

    analytics = get_property_analytics(prop.id, days=days)
    search = _search_analytics(prop)
    return {
        'period_days': days,
        'property_views': analytics.get('views', 0),
        'room_selects': analytics.get('room_selects', 0),
        'bookings': analytics.get('bookings', 0),
        'detail_view_to_booking_rate_pct': analytics.get('conversion_rate', 0),
        'search_impressions': search.get('impressions', 0),
        'search_clicks': search.get('clicks', 0),
        'search_ctr_pct': search.get('click_through_rate_pct', 0),
        'search_click_to_booking_rate_pct': search.get('conversion_rate_pct', 0),
    }


def _supply_quality_summary(prop) -> dict:
    rating_score = min(100.0, float(prop.rating or 0) * 20)
    review_count = int(getattr(prop, 'review_count', 0) or 0)
    review_confidence = min(100.0, review_count)
    cancellation_rate = 0.0
    availability_reliability = 0.9

    try:
        from apps.search.models import PropertySearchIndex

        idx = PropertySearchIndex.objects.filter(property=prop).first()
        if idx:
            cancellation_rate = float(idx.cancellation_rate or 0)
            availability_reliability = float(idx.availability_reliability or 0.9)
    except Exception:
        pass

    cancellation_score = max(0.0, 100.0 - min(100.0, cancellation_rate * 200.0))
    reliability_score = max(0.0, min(100.0, availability_reliability * 100.0))
    complaint_signal_score = 70.0

    overall = round(
        rating_score * 0.35
        + review_confidence * 0.10
        + cancellation_score * 0.25
        + reliability_score * 0.20
        + complaint_signal_score * 0.10,
        1,
    )

    if overall >= 85:
        grade = 'excellent'
    elif overall >= 70:
        grade = 'strong'
    elif overall >= 55:
        grade = 'watch'
    else:
        grade = 'at_risk'

    return {
        'overall_score': overall,
        'grade': grade,
        'rating_score': round(rating_score, 1),
        'review_confidence_score': round(review_confidence, 1),
        'cancellation_score': round(cancellation_score, 1),
        'availability_reliability_score': round(reliability_score, 1),
        'complaint_signal_score': complaint_signal_score,
        'cancellation_rate': round(cancellation_rate * 100, 2),
        'availability_reliability': round(availability_reliability, 4),
    }


def _cancellation_prediction(prop, days=90) -> dict:
    from apps.booking.models import Booking

    start = date.today() - timedelta(days=days)
    bookings = Booking.objects.filter(
        property=prop,
        created_at__date__gte=start,
    )
    total = bookings.count()
    cancelled = bookings.filter(status__in=['cancelled', 'refunded', 'refund_pending']).count()
    probability = round((cancelled / total) * 100, 2) if total else 0.0

    if probability >= 25:
        risk = 'high'
    elif probability >= 12:
        risk = 'medium'
    else:
        risk = 'low'

    return {
        'period_days': days,
        'predicted_cancellation_probability_pct': probability,
        'risk_level': risk,
        'historical_bookings': total,
        'historical_cancellations': cancelled,
    }


def _dynamic_commission_summary(prop, market: dict, conversion: dict, demand_forecast: list[dict]) -> dict:
    current_commission = float(getattr(prop, 'commission_percentage', 10) or 10)
    competitive_index = float(market.get('competitive_index', 1.0) or 1.0)
    booking_rate = float(conversion.get('detail_view_to_booking_rate_pct', 0) or 0)
    avg_demand = round(mean([row.get('demand_multiplier', 1.0) for row in demand_forecast[:7]]) if demand_forecast else 1.0, 2)

    recommended = current_commission
    rationale = 'Maintain current commission and ranking posture.'

    if booking_rate < 2.0 and competitive_index > 1.10 and avg_demand < 1.20:
        recommended = max(8.0, current_commission - 1.5)
        rationale = 'Conversion is weak while pricing is above market. A temporary commission reduction can improve merchandising competitiveness.'
    elif booking_rate >= 4.0 and avg_demand >= 1.25:
        recommended = min(22.0, current_commission + 1.0)
        rationale = 'Demand and conversion are strong. Commission can be increased modestly without materially harming ranking performance.'

    delta = round(recommended - current_commission, 2)
    if delta > 0:
        action = 'increase'
    elif delta < 0:
        action = 'decrease'
    else:
        action = 'hold'

    return {
        'current_commission_pct': round(current_commission, 2),
        'recommended_commission_pct': round(recommended, 2),
        'commission_delta_pct': delta,
        'action': action,
        'avg_7_day_demand_multiplier': avg_demand,
        'rationale': rationale,
    }


def _command_center_alerts(market: dict, conversion: dict, quality: dict, cancellation: dict, dynamic_commission: dict) -> list[dict]:
    alerts = []

    if market.get('competitive_index', 1.0) > 1.15:
        alerts.append({
            'severity': 'high',
            'type': 'pricing',
            'message': 'Property is materially above market average and may lose conversion share.',
        })

    if conversion.get('detail_view_to_booking_rate_pct', 0) < 2.0:
        alerts.append({
            'severity': 'medium',
            'type': 'conversion',
            'message': 'Detail-page to booking conversion is below target and should be improved with price, cancellation, or merchandising changes.',
        })

    if quality.get('grade') in {'watch', 'at_risk'}:
        alerts.append({
            'severity': 'high' if quality.get('grade') == 'at_risk' else 'medium',
            'type': 'supply_quality',
            'message': 'Supply quality score is below preferred threshold and may suppress ranking.',
        })

    if cancellation.get('risk_level') == 'high':
        alerts.append({
            'severity': 'high',
            'type': 'cancellation_risk',
            'message': 'Historical cancellation behavior indicates elevated cancellation risk.',
        })

    if dynamic_commission.get('action') != 'hold':
        alerts.append({
            'severity': 'medium',
            'type': 'commission',
            'message': dynamic_commission.get('rationale', ''),
        })

    return alerts


# ── Endpoints ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_intelligence_api(request):
    """
    GET /api/v1/dashboard/owner/revenue-intelligence/?property_id=
    Full analytics dashboard for a property owner.
    """
    pid = request.GET.get('property_id')
    try:
        prop = _owner_props(request.user).select_related(
            'city', 'weekend_pricing',
        ).get(id=pid) if pid else _owner_props(request.user).first()
        if not prop:
            return Response({'error': 'No approved properties found'}, status=404)
    except Exception:
        return Response({'error': 'Property not found or access denied'}, status=404)

    ck = f'rev_intel:{prop.id}:{request.user.id}'
    cached = cache.get(ck)
    if cached:
        return Response({**cached, 'cached': True})

    try:
        data = {
            'property': {
                'id':           prop.id,
                'name':         prop.name,
                'city':         str(prop.city) if prop.city else '',
                'star_category': prop.star_category,
                'rating':       float(prop.rating or 0),
            },
            'market_comparison': _market_comparison(prop),
            'revenue_stats':     _revenue_stats(prop),
            'search_analytics':  _search_analytics(prop),
            'booking_trends':    _booking_trends(prop, days=30),
            'demand_forecast':   _demand_forecast(prop, days=30),
        }
        cache.set(ck, data, timeout=3600)
        return Response(data)
    except Exception as exc:
        logger.error('revenue_intelligence_api error: %s', exc, exc_info=True)
        return Response({'error': 'Failed to load revenue intelligence'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def market_comparison_api(request):
    """GET /api/v1/dashboard/owner/market-comparison/?property_id="""
    pid = request.GET.get('property_id')
    try:
        prop = _owner_props(request.user).get(id=pid)
    except Exception:
        return Response({'error': 'Property not found or access denied'}, status=404)
    try:
        return Response(_market_comparison(prop))
    except Exception as exc:
        return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def demand_forecast_api(request):
    """GET /api/v1/dashboard/owner/demand-forecast/?property_id=&days=30"""
    pid  = request.GET.get('property_id')
    days = min(int(request.GET.get('days', 30)), 90)
    try:
        prop = _owner_props(request.user).get(id=pid)
    except Exception:
        return Response({'error': 'Property not found or access denied'}, status=404)
    return Response({'forecast': _demand_forecast(prop, days), 'days': days})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_command_center_api(request):
    """
    GET /api/v1/dashboard/owner/command-center/?property_id=

    Consolidated owner intelligence surface for revenue, conversion,
    demand, supply quality, cancellation risk, and commission guidance.
    """
    pid = request.GET.get('property_id')
    try:
        prop = _owner_props(request.user).select_related('city', 'weekend_pricing').get(id=pid)
    except Exception:
        return Response({'error': 'Property not found or access denied'}, status=404)

    cache_key = f'owner_cmd_center:{request.user.id}:{prop.id}'
    cached = cache.get(cache_key)
    if cached:
        return Response({**cached, 'cached': True})

    market = _market_comparison(prop)
    revenue = _revenue_stats(prop)
    search = _search_analytics(prop)
    booking_trends = _booking_trends(prop, days=30)
    demand = _demand_forecast(prop, days=14)
    conversion = _conversion_summary(prop, days=30)
    quality = _supply_quality_summary(prop)
    cancellation = _cancellation_prediction(prop, days=90)
    commission = _dynamic_commission_summary(prop, market, conversion, demand)
    alerts = _command_center_alerts(market, conversion, quality, cancellation, commission)

    payload = {
        'property': {
            'id': prop.id,
            'name': prop.name,
            'city': str(prop.city) if prop.city else '',
            'rating': float(prop.rating or 0),
            'star_category': prop.star_category,
            'commission_percentage': float(getattr(prop, 'commission_percentage', 0) or 0),
        },
        'market_comparison': market,
        'revenue_stats': revenue,
        'search_analytics': search,
        'booking_trends': booking_trends,
        'demand_forecast': demand,
        'conversion_optimization': conversion,
        'supply_quality': quality,
        'cancellation_prediction': cancellation,
        'dynamic_commission': commission,
        'alerts': alerts,
    }
    cache.set(cache_key, payload, timeout=1800)
    return Response(payload)
