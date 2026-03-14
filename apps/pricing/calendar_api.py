"""
Calendar Pricing API — System 1: Dynamic Calendar Pricing.

GET /api/v1/properties/price-calendar/
Returns per-date price, availability, season, holiday info for a property.

Called by the PriceCalendar.tsx frontend component.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Q, Min, Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.pricing.calendar')
DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 365
CALENDAR_CACHE_TTL = 900


# ── Helpers ──────────────────────────────────────────────────────────────────

def _weekend_days(property_obj):
    try:
        wp = property_obj.weekend_pricing
        if wp and wp.is_active and wp.weekend_days:
            return set(wp.weekend_days)
    except Exception:
        pass
    return {5, 6}  # Fri + Sat isoweekday


def _seasonal_info(property_obj, d):
    """Return (multiplier:float, season_type:str|None) for a date."""
    from apps.pricing.models import SeasonalPricing, EventPricing
    try:
        ev = EventPricing.objects.filter(property=property_obj, date=d, is_active=True).first()
        if ev:
            return float(ev.multiplier), 'event'
    except Exception:
        pass
    try:
        sp = SeasonalPricing.objects.filter(
            property=property_obj,
            start_date__lte=d,
            end_date__gte=d,
            is_active=True,
        ).order_by('-multiplier').first()
        if sp:
            return float(sp.multiplier), sp.season_type
    except Exception:
        pass
    return 1.0, None


def _holiday_info(d, city_id=None, state=''):
    """Return (is_holiday:bool, name:str|None, multiplier:float)."""
    try:
        from apps.core.models import HolidayCalendar
        qs = HolidayCalendar.objects.filter(date=d, country='IN', is_active=True)
        if state:
            qs = qs.filter(Q(state='') | Q(state=state))
        h = qs.order_by('-demand_multiplier').first()
        if h:
            return True, h.holiday_name, float(h.demand_multiplier)
    except Exception:
        pass
    return False, None, 1.0


def _availability(property_obj, d, room_type_id=None):
    """Available rooms for a given date."""
    try:
        from apps.inventory.models import InventoryCalendar
        qs = InventoryCalendar.objects.filter(
            room_type__property=property_obj,
            date=d,
            is_closed=False,
        )
        if room_type_id:
            qs = qs.filter(room_type_id=room_type_id)
        row = qs.aggregate(available=Sum('available_rooms'))
        if row.get('available') is not None:
            return int(row['available'] or 0)
    except Exception:
        pass
    try:
        from apps.rooms.models import RoomInventory
        qs = RoomInventory.objects.filter(room_type__property=property_obj, date=d)
        if room_type_id:
            qs = qs.filter(room_type_id=room_type_id)
        return sum(r.available_rooms for r in qs if r.available_rooms)
    except Exception:
        pass
    try:
        from apps.inventory.models import PropertyInventory
        inv = PropertyInventory.objects.get(property=property_obj)
        return max(0, inv.available_rooms)
    except Exception:
        return 0


def _resolve_room_type(property_obj, room_type_id=None):
    from apps.rooms.models import RoomType

    try:
        if room_type_id:
            return RoomType.objects.get(id=room_type_id, property=property_obj)
    except Exception:
        pass
    try:
        return RoomType.objects.filter(property=property_obj).order_by('base_price', 'id').first()
    except Exception:
        pass
    return None


def _base_price(property_obj, room_type_id=None):
    rt = _resolve_room_type(property_obj, room_type_id)
    if rt:
        return float(rt.base_price or getattr(rt, 'price_per_night', 0) or 0)
    return 0.0


def _calendar_base_price(property_obj, d, room_type_id=None):
    try:
        from apps.inventory.models import InventoryCalendar
        qs = InventoryCalendar.objects.filter(room_type__property=property_obj, date=d)
        if room_type_id:
            qs = qs.filter(room_type_id=room_type_id)
        override = qs.exclude(rate_override__isnull=True).aggregate(m=Min('rate_override'))['m']
        if override is not None:
            return float(override)
    except Exception:
        pass
    return _base_price(property_obj, room_type_id)


def _load_calendar_context(property_obj, start_date, end_date, room_type_id=None, state=''):
    context = {
        'inventory': {},
        'events': {},
        'seasonals': [],
        'holidays': {},
        'forecasts': {},
        'recent_velocity': 0,
    }

    try:
        from apps.inventory.models import InventoryCalendar

        inv_qs = InventoryCalendar.objects.filter(
            room_type__property=property_obj,
            date__range=(start_date, end_date),
        )
        if room_type_id:
            inv_qs = inv_qs.filter(room_type_id=room_type_id)

        inv_rows = (
            inv_qs.values('date')
            .annotate(
                available=Sum('available_rooms'),
                total=Sum('total_rooms'),
                override=Min('rate_override'),
            )
        )
        context['inventory'] = {row['date']: row for row in inv_rows}
    except Exception:
        pass

    try:
        from apps.pricing.models import EventPricing, SeasonalPricing

        event_qs = EventPricing.objects.filter(
            property=property_obj,
            date__range=(start_date, end_date),
            is_active=True,
        ).values('date', 'multiplier', 'event_name')
        context['events'] = {row['date']: row for row in event_qs}

        context['seasonals'] = list(
            SeasonalPricing.objects.filter(
                property=property_obj,
                start_date__lte=end_date,
                end_date__gte=start_date,
                is_active=True,
            ).order_by('-multiplier')
        )
    except Exception:
        pass

    try:
        from apps.core.models import HolidayCalendar

        holiday_qs = HolidayCalendar.objects.filter(
            date__range=(start_date, end_date),
            country='IN',
            is_active=True,
        )
        if state:
            holiday_qs = holiday_qs.filter(Q(state='') | Q(state=state))

        for holiday in holiday_qs.order_by('date', '-demand_multiplier'):
            context['holidays'].setdefault(holiday.date, holiday)
    except Exception:
        pass

    try:
        from apps.core.intelligence import DemandForecast

        forecasts = DemandForecast.objects.filter(
            property=property_obj,
            date__range=(start_date, end_date),
        ).values('date', 'predicted_occupancy', 'predicted_demand_score')
        context['forecasts'] = {row['date']: row for row in forecasts}
    except Exception:
        pass

    try:
        from apps.search.models import PropertySearchIndex

        idx = PropertySearchIndex.objects.filter(property=property_obj).only('recent_bookings').first()
        if idx and idx.recent_bookings:
            context['recent_velocity'] = int(idx.recent_bookings)
    except Exception:
        pass

    if not context['recent_velocity']:
        context['recent_velocity'] = int(getattr(property_obj, 'bookings_today', 0) or 0)

    return context


def _resolve_property(property_ref):
    from apps.hotels.models import Property

    if hasattr(property_ref, 'id'):
        return property_ref

    qs = Property.objects.select_related('city', 'weekend_pricing')
    ref = str(property_ref).strip()
    if not ref:
        return None

    if ref.isdigit():
        try:
            return qs.get(id=int(ref))
        except Property.DoesNotExist:
            pass

    try:
        return qs.get(slug=ref)
    except Property.DoesNotExist:
        return None


def _parse_int(raw, default=None):
    if raw in (None, ''):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_calendar_request(params):
    start_raw = params.get('start_date') or params.get('start')
    end_raw = params.get('end_date') or params.get('end')
    days_raw = params.get('days')
    room_type_raw = params.get('room_type_id')

    if start_raw:
        try:
            start = date.fromisoformat(start_raw)
        except ValueError:
            return None, {'error': 'start_date must be YYYY-MM-DD'}, 400
    else:
        start = date.today()

    room_type_id = _parse_int(room_type_raw)
    if room_type_raw and room_type_id is None:
        return None, {'error': 'room_type_id must be an integer'}, 400

    if end_raw:
        try:
            end = date.fromisoformat(end_raw)
        except ValueError:
            return None, {'error': 'end_date must be YYYY-MM-DD'}, 400
        if days_raw:
            parsed_days = _parse_int(days_raw)
            if parsed_days is None or parsed_days < 1:
                return None, {'error': 'days must be a positive integer'}, 400
    else:
        parsed_days = _parse_int(days_raw, DEFAULT_RANGE_DAYS)
        if parsed_days is None or parsed_days < 1:
            return None, {'error': 'days must be a positive integer'}, 400
        end = start + timedelta(days=parsed_days - 1)

    if end < start:
        return None, {'error': 'end_date must be >= start_date'}, 400

    total_days = (end - start).days + 1
    if total_days > MAX_RANGE_DAYS:
        return None, {'error': f'Range cannot exceed {MAX_RANGE_DAYS} days'}, 400

    return {
        'start': start,
        'end': end,
        'days': total_days,
        'room_type_id': room_type_id,
    }, None, 200


def build_calendar(property_obj, start_date, end_date, room_type_id=None):
    """Build per-date price + availability list."""
    wknd_days = _weekend_days(property_obj)
    state, city_id = '', None
    try:
        city_id = property_obj.city_id
        city = property_obj.city
        state = getattr(city, 'state_code', '') or ''
    except Exception:
        pass

    base = _base_price(property_obj, room_type_id)
    prop_disc_pct = float(getattr(property_obj, 'discount_percentage', 0) or 0)
    context = _load_calendar_context(property_obj, start_date, end_date, room_type_id=room_type_id, state=state)

    try:
        wp = property_obj.weekend_pricing
        wknd_mult = float(wp.weekend_multiplier) if (wp and wp.is_active) else 1.1
    except Exception:
        wknd_mult = 1.1

    results = []
    cur = start_date
    while cur <= end_date:
        event_row = context['events'].get(cur)
        if event_row:
            sea_mult = float(event_row['multiplier'])
            sea_type = 'event'
        else:
            sea_mult = 1.0
            sea_type = None
            for season in context['seasonals']:
                if season.start_date <= cur <= season.end_date:
                    sea_mult = float(season.multiplier)
                    sea_type = season.season_type
                    break

        is_wknd = cur.isoweekday() in wknd_days
        w_mult = wknd_mult if is_wknd else 1.0
        holiday = context['holidays'].get(cur)
        if holiday:
            is_hol, hol_name, hol_mult = True, holiday.holiday_name, float(holiday.demand_multiplier)
        else:
            is_hol, hol_name, hol_mult = False, None, 1.0

        # Compound multiplier — highest single factor wins (no double-stacking)
        demand_mult = max(sea_mult, hol_mult, w_mult)
        pricing_source = 'calendar_fallback'
        pricing_breakdown = {
            'fallback_multiplier': round(demand_mult, 2),
        }

        inv_row = context['inventory'].get(cur)
        nightly_base = float(inv_row['override']) if inv_row and inv_row.get('override') is not None else base
        seasonal_price = round(nightly_base * demand_mult, 2)
        final_nightly = seasonal_price
        pricing_source = 'bulk_calendar_engine'

        occupancy_adj = 0.0
        scarcity_adj = 0.0
        forecast_adj = 0.0
        velocity_adj = 0.0
        available_rooms = None
        total_rooms = None

        if inv_row:
            available_rooms = int(inv_row.get('available') or 0)
            total_rooms = int(inv_row.get('total') or 0)
            if total_rooms > 0:
                occupancy_ratio = 1 - (available_rooms / total_rooms)
                if occupancy_ratio >= 0.95:
                    occupancy_adj = final_nightly * 0.28
                elif occupancy_ratio >= 0.80:
                    occupancy_adj = final_nightly * 0.20
                elif occupancy_ratio <= 0.30:
                    occupancy_adj = final_nightly * -0.10

                if available_rooms <= 3:
                    scarcity_adj = final_nightly * 0.35

        forecast_row = context['forecasts'].get(cur)
        if forecast_row and forecast_row.get('predicted_occupancy') is not None:
            predicted = float(forecast_row['predicted_occupancy'])
            if predicted >= 0.90:
                forecast_adj = final_nightly * 0.12
            elif predicted >= 0.75:
                forecast_adj = final_nightly * 0.06

        recent_velocity = context['recent_velocity']
        if recent_velocity >= 8:
            velocity_adj = final_nightly * 0.12
        elif recent_velocity >= 4:
            velocity_adj = final_nightly * 0.06

        final_nightly = round(final_nightly + occupancy_adj + scarcity_adj + forecast_adj + velocity_adj, 2)
        pricing_breakdown = {
            'fallback_multiplier': round(demand_mult, 2),
            'occupancy_adj': round(occupancy_adj, 2),
            'scarcity_adj': round(scarcity_adj, 2),
            'forecast_adj': round(forecast_adj, 2),
            'velocity_adj': round(velocity_adj, 2),
            'available_rooms': available_rooms,
            'total_rooms': total_rooms,
        }

        discount_amt = round(final_nightly * prop_disc_pct / 100, 2)
        final = round(final_nightly - discount_amt, 2)

        avail = _availability(property_obj, cur, room_type_id)

        results.append({
            'date':          cur.strftime('%Y-%m-%d'),
            'base_price':    round(nightly_base, 2),
            'seasonal_price': round(final_nightly, 2),
            'discount':      discount_amt,
            'final_price':   final,
            'availability':  avail,
            'season_type':   sea_type,
            'is_weekend':    is_wknd,
            'is_holiday':    is_hol,
            'holiday_name':  hol_name,
            'demand_mult':   round(demand_mult, 2),
            'pricing_source': pricing_source,
            'pricing_breakdown': pricing_breakdown,
        })
        cur += timedelta(days=1)
    return results


def get_price_calendar_payload(property_ref, params):
    prop = _resolve_property(property_ref)
    if prop is None:
        return {'error': 'Property not found'}, 404

    parsed, error_payload, error_status = _parse_calendar_request(params)
    if error_payload is not None:
        return error_payload, error_status

    start = parsed['start']
    end = parsed['end']
    days = parsed['days']
    room_type_id = parsed['room_type_id']

    cache_key = f'pcal:v2:{prop.id}:{room_type_id or "all"}:{start.isoformat()}:{end.isoformat()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            'property_id': prop.id,
            'property_name': prop.name,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'days': days,
            'dates': cached,
            'cached': True,
        }, 200

    try:
        data = build_calendar(prop, start, end, room_type_id=room_type_id)
    except Exception as exc:
        logger.error('price calendar build failed property=%s: %s', prop.id, exc, exc_info=True)
        return {'error': 'Calendar build failed'}, 500

    cache.set(cache_key, data, timeout=CALENDAR_CACHE_TTL)
    return {
        'property_id': prop.id,
        'property_name': prop.name,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'days': days,
        'dates': data,
        'cached': False,
    }, 200


# ── Views ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def price_calendar_api(request):
    """
    GET /api/v1/properties/price-calendar/
    ?property_id=&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&days=&room_type_id=
    """
    pid = request.GET.get('property_id')
    if not pid:
        return Response({'error': 'property_id is required'}, status=400)

    payload, status_code = get_price_calendar_payload(pid, request.GET)
    return Response(payload, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def holiday_calendar_api(request):
    """
    GET /api/v1/pricing/holidays/
    ?start_date=&end_date=&country=IN&state=
    """
    s_str   = request.GET.get('start_date')
    e_str   = request.GET.get('end_date')
    country = request.GET.get('country', 'IN')
    state   = request.GET.get('state', '')

    if not all([s_str, e_str]):
        return Response({'error': 'start_date and end_date required'}, status=400)
    try:
        start = date.fromisoformat(s_str)
        end   = date.fromisoformat(e_str)
    except ValueError:
        return Response({'error': 'Invalid date format'}, status=400)

    try:
        from apps.core.models import HolidayCalendar
        holidays = HolidayCalendar.get_holidays_for_range(start, end, country, state)
        data = [
            {
                'date':             h.date.strftime('%Y-%m-%d'),
                'name':             h.holiday_name,
                'type':             h.holiday_type,
                'demand_multiplier': float(h.demand_multiplier),
                'country':          h.country,
                'state':            h.state,
            }
            for h in holidays
        ]
        return Response({'holidays': data, 'count': len(data)})
    except Exception as exc:
        logger.error('holiday_calendar_api error: %s', exc)
        return Response({'error': 'Failed to fetch holidays'}, status=500)
