"""
Section 13 — Conversion Signals

Social-proof and urgency signals that drive booking conversion:
  - rooms_left         (live inventory scarcity)
  - booked_today       (social proof)
  - viewing_now        (live activity)
  - price_trend        (going up / stable / going down)
  - last_booked_ago    (recency)
  - demand_level       (low / moderate / high / very_high)

These signals are computed server-side and included in property listing / detail
API responses.  They are NEVER exposed to frontend calculation — the backend
provides the final display-ready values.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('zygotrip.conversion')


class ConversionSignals:
    """
    Compute conversion signals for a property + optional date range.
    Results are cached for 2 minutes.
    """
    CACHE_TTL = 120

    @classmethod
    def for_property(cls, property_obj, check_in: date | None = None,
                     check_out: date | None = None) -> dict:
        """
        Return conversion signals dict for a single property.
        Suitable for injection into property detail API responses.
        """
        prop_id = property_obj.id
        cache_key = f"convsig:{prop_id}:{check_in}:{check_out}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        signals = {
            'rooms_left': cls._rooms_left(property_obj, check_in, check_out),
            'booked_today': cls._booked_today(prop_id),
            'viewing_now': cls._viewing_now(prop_id),
            'price_trend': cls._price_trend(property_obj, check_in),
            'last_booked_ago': cls._last_booked_ago(prop_id),
            'demand_level': cls._demand_level(property_obj, check_in),
            'great_deal': cls._great_deal(property_obj, check_in),
        }
        signals['messages'] = cls._display_messages(signals)
        cache.set(cache_key, signals, cls.CACHE_TTL)
        return signals

    @classmethod
    def for_listing(cls, property_ids: list[int], check_in: date | None = None,
                    check_out: date | None = None) -> dict[int, dict]:
        """
        Bulk signals for search results. Keys are property IDs.
        Optimised to avoid N+1 queries.
        """
        result = {}
        for pid in property_ids:
            cache_key = f"convsig:{pid}:{check_in}:{check_out}"
            cached = cache.get(cache_key)
            if cached:
                result[pid] = cached
            else:
                result[pid] = cls._quick_signals(pid, check_in)
                cache.set(cache_key, result[pid], cls.CACHE_TTL)
        return result

    # ── Individual signals ───────────────────────────────────────────────

    @staticmethod
    def _rooms_left(property_obj, check_in, check_out):
        """Min rooms available across the stay dates."""
        if not check_in:
            return None
        try:
            from apps.inventory.models import InventoryPool
            pools = InventoryPool.objects.filter(
                room_type__property=property_obj,
                date__gte=check_in,
                date__lt=check_out or check_in + timedelta(days=1),
                is_closed=False,
            ).values_list('total_available', flat=True)
            if pools.exists():
                return min(pools)
        except Exception:
            pass
        # Fallback to InventoryCalendar
        try:
            from apps.inventory.models import InventoryCalendar
            cals = InventoryCalendar.objects.filter(
                room_type__property=property_obj,
                date__gte=check_in,
                date__lt=check_out or check_in + timedelta(days=1),
                is_closed=False,
            ).values_list('available_rooms', flat=True)
            if cals.exists():
                return min(cals)
        except Exception:
            pass
        return None

    @staticmethod
    def _booked_today(prop_id):
        """Number of confirmed bookings created today for this property."""
        try:
            from django.apps import apps
            Booking = apps.get_model('booking', 'Booking')
            return Booking.objects.filter(
                property_id=prop_id,
                created_at__date=date.today(),
                status__in=['confirmed', 'hold', 'pending'],
            ).count()
        except Exception:
            return 0

    @staticmethod
    def _viewing_now(prop_id):
        """
        Approximate concurrent viewers.
        Uses analytics events from last 5 min as a proxy.
        """
        try:
            from apps.core.analytics import AnalyticsEvent
            cutoff = timezone.now() - timedelta(minutes=5)
            return AnalyticsEvent.objects.filter(
                property_id=prop_id,
                event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
                created_at__gte=cutoff,
            ).values('session_id').distinct().count()
        except Exception:
            return 0

    @staticmethod
    def _price_trend(property_obj, check_in):
        """
        Price direction: 'rising', 'falling', 'stable'.
        Compares 7-day-ago price to current price.
        """
        if not check_in:
            return 'stable'
        try:
            from apps.inventory.models import PriceHistory
            old_date = check_in - timedelta(days=7)
            old = PriceHistory.objects.filter(
                room_type__property=property_obj, date=old_date,
            ).first()
            now = PriceHistory.objects.filter(
                room_type__property=property_obj, date=check_in,
            ).first()
            if old and now:
                if now.rate > old.rate:
                    return 'rising'
                elif now.rate < old.rate:
                    return 'falling'
        except Exception:
            pass
        return 'stable'

    @staticmethod
    def _last_booked_ago(prop_id):
        """
        Minutes since last confirmed booking at this property.
        Returns None if no recent bookings.
        """
        try:
            from django.apps import apps
            Booking = apps.get_model('booking', 'Booking')
            last = Booking.objects.filter(
                property_id=prop_id,
                status='confirmed',
            ).order_by('-created_at').values_list('created_at', flat=True).first()
            if last:
                delta = timezone.now() - last
                return int(delta.total_seconds() / 60)
        except Exception:
            pass
        return None

    @staticmethod
    def _demand_level(property_obj, check_in):
        """
        Qualitative demand label based on occupancy.
        """
        if not check_in:
            return 'moderate'
        try:
            from apps.inventory.models import InventoryCalendar
            cals = InventoryCalendar.objects.filter(
                room_type__property=property_obj, date=check_in,
            )
            total = sum(c.total_rooms for c in cals) or 1
            used = sum(c.booked_rooms + c.held_rooms for c in cals)
            occ = used / total * 100
            if occ >= 90:
                return 'very_high'
            if occ >= 70:
                return 'high'
            if occ >= 40:
                return 'moderate'
            return 'low'
        except Exception:
            return 'moderate'

    @staticmethod
    def _great_deal(property_obj, check_in):
        """
        Compare property's base rate to city average.
        Returns a 'great deal' badge if savings >= 15%.
        """
        if not check_in:
            return {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''}
        try:
            from apps.search.models import PropertySearchIndex
            idx = PropertySearchIndex.objects.filter(property_id=property_obj.id).first()
            if not idx or not idx.price_min:
                return {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''}

            prop_price = float(idx.price_min)

            # Get city average from the same index
            city_id = idx.city_id
            if not city_id:
                return {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''}

            from django.db.models import Avg
            city_avg = PropertySearchIndex.objects.filter(
                city_id=city_id,
            ).exclude(
                price_min__isnull=True,
            ).aggregate(avg=Avg('price_min'))['avg']

            if not city_avg or float(city_avg) <= 0:
                return {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''}

            savings = ((float(city_avg) - prop_price) / float(city_avg)) * 100
            if savings >= 15:
                return {
                    'is_great_deal': True,
                    'savings_percent': round(savings, 0),
                    'badge_text': f'{int(round(savings, 0))}% below city avg',
                }
        except Exception:
            pass
        return {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''}

    @staticmethod
    def _quick_signals(prop_id, check_in):
        """Lightweight signals for listing cards (no heavy DB reads)."""
        signals = {
            'rooms_left': None,
            'booked_today': ConversionSignals._booked_today(prop_id),
            'viewing_now': ConversionSignals._viewing_now(prop_id),
            'price_trend': 'stable',
            'last_booked_ago': ConversionSignals._last_booked_ago(prop_id),
            'demand_level': 'moderate',
            'great_deal': {'is_great_deal': False, 'savings_percent': 0, 'badge_text': ''},
        }
        try:
            from apps.search.models import PropertySearchIndex
            idx = PropertySearchIndex.objects.filter(property_id=prop_id).only(
                'rooms_left', 'recent_bookings'
            ).first()
            if idx:
                signals['rooms_left'] = idx.rooms_left or None
                if idx.recent_bookings:
                    signals['booked_today'] = max(signals['booked_today'], int(idx.recent_bookings))
        except Exception:
            pass

        signals['messages'] = ConversionSignals._display_messages(signals)
        return signals

    @staticmethod
    def _display_messages(signals):
        messages = []

        rooms_left = signals.get('rooms_left')
        if rooms_left is not None and rooms_left > 0:
            if rooms_left <= 3:
                messages.append(f'Only {rooms_left} rooms left')
            elif rooms_left <= 8:
                messages.append(f'{rooms_left} rooms left')

        viewers = signals.get('viewing_now') or 0
        if viewers >= 2:
            messages.append(f'{viewers} people viewing this hotel')

        booked = signals.get('booked_today') or 0
        if booked >= 1:
            messages.append(f'Booked {booked} time{"s" if booked != 1 else ""} today')

        great_deal = signals.get('great_deal') or {}
        if great_deal.get('is_great_deal') and great_deal.get('badge_text'):
            messages.append(great_deal['badge_text'])

        return messages[:4]
