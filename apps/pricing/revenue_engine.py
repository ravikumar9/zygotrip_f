"""
Section 6 — Revenue Optimization Engine

Demand-based dynamic pricing engine that runs alongside the unified
pricing pipeline (apps.pricing.pricing_service).

Responsibilities:
  1. Real‑time demand multiplier    (occupancy + velocity)
  2. Advance-booking discount curve
  3. Last‑minute premium
  4. Day-of-week seasonality
  5. Event / holiday surge detection
  6. Competitor parity guard-rail  (never >10 % above avg competitor)

This engine is called BY pricing_service._demand_adjustment() and can
also be invoked standalone for owner dashboards / simulations.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('zygotrip.pricing.revenue')


class RevenueOptimizationEngine:
    """
    Compute dynamic pricing multipliers for a given (property, room_type, date).
    Returns a multiplier (e.g. 1.12 = +12 %) and an explanation breakdown.
    """

    # Cache TTL — optimisation results valid for 5 min
    CACHE_TTL = 300

    # ──────────────────────────────────────────────────────────────────────
    # Day-of-week base modifiers (Fri/Sat premium, mid-week discount)
    # ──────────────────────────────────────────────────────────────────────
    DOW_MODIFIERS = {
        0: Decimal('-0.05'),   # Monday
        1: Decimal('-0.05'),   # Tuesday
        2: Decimal('-0.03'),   # Wednesday
        3: Decimal('0'),       # Thursday
        4: Decimal('0.08'),    # Friday
        5: Decimal('0.12'),    # Saturday
        6: Decimal('0.05'),    # Sunday
    }

    def compute_multiplier(self, property_obj, room_type, target_date,
                           *, occupancy_pct=None, competitor_avg=None):
        """
        Compute revenue-optimised multiplier for a single date.

        Args:
            property_obj: Property instance
            room_type:    RoomType instance
            target_date:  date
            occupancy_pct: override occupancy (0-100). If None, fetched from DB.
            competitor_avg: override competitor avg rate. If None, fetched from DB.

        Returns:
            dict {
                'multiplier': Decimal,  # e.g. 1.15
                'breakdown': {
                    'demand': Decimal,
                    'advance': Decimal,
                    'dow': Decimal,
                    'event': Decimal,
                    'competitor_cap': Decimal,
                },
                'explanation': str,
            }
        """
        cache_key = f"revenueopt:{property_obj.id}:{room_type.id}:{target_date}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        demand = self._demand_factor(property_obj, room_type, target_date, occupancy_pct)
        advance = self._advance_factor(target_date)
        dow = self._dow_factor(target_date)
        event = self._event_factor(property_obj, target_date)
        raw = Decimal('1') + demand + advance + dow + event

        # Competitor parity cap
        comp_cap = Decimal('0')
        if competitor_avg:
            max_allowed = Decimal(str(competitor_avg)) * Decimal('1.10')
            base_price = Decimal(str(room_type.base_price))
            proposed = base_price * raw
            if proposed > max_allowed and max_allowed > 0:
                raw = max_allowed / base_price
                comp_cap = raw - (Decimal('1') + demand + advance + dow + event)

        # Floor — never discount more than 20 %
        raw = max(raw, Decimal('0.80'))
        # Ceiling — never surge more than 50 %
        raw = min(raw, Decimal('1.50'))

        result = {
            'multiplier': raw.quantize(Decimal('0.01')),
            'breakdown': {
                'demand': demand.quantize(Decimal('0.001')),
                'advance': advance.quantize(Decimal('0.001')),
                'dow': dow.quantize(Decimal('0.001')),
                'event': event.quantize(Decimal('0.001')),
                'competitor_cap': comp_cap.quantize(Decimal('0.001')),
            },
            'explanation': self._explain(demand, advance, dow, event, comp_cap, raw),
        }

        cache.set(cache_key, result, self.CACHE_TTL)
        return result

    def simulate_range(self, property_obj, room_type, start_date, end_date):
        """
        Compute multipliers for a date range (useful for owner dashboard).
        Returns list of {date, multiplier, breakdown, explanation}.
        """
        results = []
        current = start_date
        while current <= end_date:
            m = self.compute_multiplier(property_obj, room_type, current)
            results.append({'date': current, **m})
            current += timedelta(days=1)
        return results

    # ──────────────────────────────────────────────────────────────────────
    # Component factors
    # ──────────────────────────────────────────────────────────────────────

    def _demand_factor(self, property_obj, room_type, target_date, occupancy_pct):
        """
        Occupancy-based demand surge.
          ≥95 % → +0.15
          ≥85 % → +0.10
          ≥75 % → +0.05
          <50 % → −0.05  (demand discount)
        """
        if occupancy_pct is None:
            occupancy_pct = self._fetch_occupancy(room_type, target_date)

        if occupancy_pct >= 95:
            return Decimal('0.15')
        if occupancy_pct >= 85:
            return Decimal('0.10')
        if occupancy_pct >= 75:
            return Decimal('0.05')
        if occupancy_pct < 50:
            return Decimal('-0.05')
        return Decimal('0')

    def _advance_factor(self, target_date):
        """
        How far ahead the check-in is.
          ≥ 60 days → −0.07  (early-bird discount)
          ≥ 30 days → −0.04
          ≤  1 day  → +0.10  (last-minute premium)
          ≤  3 days → +0.05
        """
        days_out = (target_date - date.today()).days
        if days_out >= 60:
            return Decimal('-0.07')
        if days_out >= 30:
            return Decimal('-0.04')
        if days_out <= 1:
            return Decimal('0.10')
        if days_out <= 3:
            return Decimal('0.05')
        return Decimal('0')

    def _dow_factor(self, target_date):
        """Day-of-week seasonality modifier."""
        return self.DOW_MODIFIERS.get(target_date.weekday(), Decimal('0'))

    def _event_factor(self, property_obj, target_date):
        """
        Holiday / local-event surge.
        Looks for EventSurge records (if model exists), otherwise returns 0.
        """
        try:
            from apps.pricing.models import EventSurge
            es = EventSurge.objects.filter(
                start_date__lte=target_date,
                end_date__gte=target_date,
            ).first()
            if es:
                return Decimal(str(es.multiplier_delta))
        except Exception:
            pass
        return Decimal('0')

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_occupancy(room_type, target_date):
        """Read real occupancy % from InventoryCalendar."""
        try:
            from apps.inventory.models import InventoryCalendar
            cal = InventoryCalendar.objects.get(room_type=room_type, date=target_date)
            total = cal.total_rooms or 1
            used = cal.booked_rooms + cal.held_rooms + cal.blocked_rooms
            return min(100, int(used / total * 100))
        except Exception:
            return 50  # neutral fallback

    @staticmethod
    def _explain(demand, advance, dow, event, comp_cap, final):
        parts = []
        if demand != 0:
            parts.append(f"demand:{demand:+.1%}")
        if advance != 0:
            parts.append(f"advance:{advance:+.1%}")
        if dow != 0:
            parts.append(f"dow:{dow:+.1%}")
        if event != 0:
            parts.append(f"event:{event:+.1%}")
        if comp_cap != 0:
            parts.append(f"comp_cap:{comp_cap:+.1%}")
        return f"final={final:.2f}x ({', '.join(parts) or 'neutral'})"
