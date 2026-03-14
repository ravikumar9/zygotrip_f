"""
Dynamic Pricing Engine — Computes final room price per night.

Applies modifiers in priority order:
  1. Event pricing (highest priority — festivals, concerts)
  2. Seasonal pricing (peak/high/shoulder/low)
  3. Weekend pricing (Fri/Sat or configured days)
  4. Occupancy-based adjustment (high demand → markup, low demand → discount)
  5. Competitor parity adjustment (if we're >10% above market)
  6. Last-minute discount (≤2 days to check-in, occupancy < 50%)

Returns a PricingResult dataclass with full breakdown.

Scheduled to recompute every 6 hours via Celery beat.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Sum, Q
from django.utils import timezone

logger = logging.getLogger('zygotrip.pricing')


@dataclass
class PricingResult:
    """Full pricing breakdown for a single room-night."""
    base_price: Decimal
    final_price: Decimal
    modifier_name: str  # which modifier was dominant
    multiplier: Decimal
    competitor_adjustment: Decimal
    occupancy_adjustment: Decimal
    last_minute_discount: Decimal
    breakdown: dict
    demand_adjustment: Decimal = Decimal('0')
    velocity_adjustment: Decimal = Decimal('0')
    scarcity_adjustment: Decimal = Decimal('0')


def calculate_dynamic_price(
    room_type,
    check_date: date,
    property_obj=None,
    base_price: Decimal | None = None,
) -> PricingResult:
    """
    Calculate the dynamic price for a single room-night.

    Args:
        room_type: RoomType instance (has base_price, property FK)
        check_date: the night for which to price
        property_obj: optional Property (auto-fetched from room_type if None)
        base_price: override base price (useful for batch processing)

    Returns:
        PricingResult with full breakdown
    """
    from apps.pricing.models import (
        EventPricing, SeasonalPricing, WeekendPricing, CompetitorPrice,
    )

    prop = property_obj or room_type.property
    price = base_price or Decimal(str(room_type.base_price))
    multiplier = Decimal('1.0')
    modifier_name = 'base'

    # ── 1. Event pricing (highest priority) ────────────────────────
    event = EventPricing.objects.filter(
        property=prop,
        date=check_date,
        is_active=True,
    ).first()

    if event:
        multiplier = event.multiplier
        modifier_name = f'event:{event.event_name}'
    else:
        # ── 2. Seasonal pricing ────────────────────────────────────
        seasonal = SeasonalPricing.objects.filter(
            property=prop,
            start_date__lte=check_date,
            end_date__gte=check_date,
            is_active=True,
        ).order_by('-multiplier').first()

        if seasonal:
            multiplier = seasonal.multiplier
            modifier_name = f'seasonal:{seasonal.season_type}'
        else:
            # ── 3. Weekend pricing ─────────────────────────────────
            try:
                weekend_cfg = WeekendPricing.objects.get(
                    property=prop,
                    is_active=True,
                )
                weekend_days = weekend_cfg.weekend_days or [5, 6]
                if check_date.isoweekday() in weekend_days:
                    multiplier = weekend_cfg.weekend_multiplier
                    modifier_name = 'weekend'
            except WeekendPricing.DoesNotExist:
                pass

    # Apply base multiplier
    after_modifier = (price * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # ── 4. Occupancy / scarcity / demand / velocity adjustments ─────
    occupancy_adj = Decimal('0')
    scarcity_adj = Decimal('0')
    demand_adj = Decimal('0')
    velocity_adj = Decimal('0')
    occupancy_pct = None
    available = None
    total = None
    try:
        from apps.inventory.models import InventoryCalendar
        cal = InventoryCalendar.objects.filter(
            room_type__property=prop,
            date=check_date,
        ).aggregate(
            total=Sum('total_rooms'),
            available=Sum('available_rooms'),
        )
        total = cal.get('total') or 0
        available = cal.get('available') or 0
        if total > 0:
            occupancy_pct = Decimal('1') - (Decimal(str(available)) / Decimal(str(total)))
            if occupancy_pct >= Decimal('0.95'):
                occupancy_adj = after_modifier * Decimal('0.28')
            elif occupancy_pct >= Decimal('0.80'):
                occupancy_adj = after_modifier * Decimal('0.20')
            elif occupancy_pct <= Decimal('0.30'):
                occupancy_adj = after_modifier * Decimal('-0.10')

            if available is not None and available <= 3:
                scarcity_adj = after_modifier * Decimal('0.35')
    except Exception as exc:
        logger.debug('Occupancy lookup failed: %s', exc)

    try:
        from apps.core.intelligence import DemandForecast
        forecast = DemandForecast.objects.filter(property=prop, date=check_date).first()
        if forecast and forecast.predicted_occupancy is not None:
            predicted = Decimal(str(forecast.predicted_occupancy))
            if predicted >= Decimal('0.90'):
                demand_adj = after_modifier * Decimal('0.12')
            elif predicted >= Decimal('0.75'):
                demand_adj = after_modifier * Decimal('0.06')
    except Exception as exc:
        logger.debug('Demand forecast lookup failed: %s', exc)

    try:
        from apps.booking.models import Booking
        now = timezone.now()
        recent = Booking.objects.filter(
            property=prop,
            status__in=['confirmed', 'hold'],
            created_at__gte=now - timedelta(hours=24),
        ).count()
        previous = Booking.objects.filter(
            property=prop,
            status__in=['confirmed', 'hold'],
            created_at__gte=now - timedelta(hours=48),
            created_at__lt=now - timedelta(hours=24),
        ).count()
        ratio = Decimal(str(recent / max(previous, 1)))
        if recent >= 8 or ratio >= Decimal('2.0'):
            velocity_adj = after_modifier * Decimal('0.12')
        elif recent >= 4 or ratio >= Decimal('1.4'):
            velocity_adj = after_modifier * Decimal('0.06')
    except Exception as exc:
        logger.debug('Booking velocity lookup failed: %s', exc)

    after_occupancy = (
        after_modifier + occupancy_adj + scarcity_adj + demand_adj + velocity_adj
    ).quantize(Decimal('0.01'))

    # ── 5. Competitor parity adjustment ────────────────────────────
    competitor_adj = Decimal('0')
    try:
        avg_competitor = CompetitorPrice.objects.filter(
            property=prop,
            date__range=(check_date, check_date + timedelta(days=1)),
            is_available=True,
        ).aggregate(avg=Avg('price_per_night'))['avg']

        if avg_competitor:
            avg_comp = Decimal(str(avg_competitor))
            if after_occupancy > avg_comp * Decimal('1.10'):
                # We're >10% above market → bring closer to parity
                target = avg_comp * Decimal('1.05')  # cap at 5% above market
                competitor_adj = target - after_occupancy
                competitor_adj = max(competitor_adj, after_occupancy * Decimal('-0.15'))  # max 15% cut
    except Exception as exc:
        logger.debug('Competitor lookup failed: %s', exc)

    after_competitor = (after_occupancy + competitor_adj).quantize(Decimal('0.01'))

    # ── 6. Last-minute discount (≤2 days, low occupancy) ───────────
    last_minute = Decimal('0')
    days_until = (check_date - date.today()).days
    if days_until <= 2 and days_until >= 0:
        try:
            from apps.inventory.models import InventoryCalendar
            cal = InventoryCalendar.objects.filter(
                room_type__property=prop,
                date=check_date,
            ).aggregate(
                total=Sum('total_rooms'),
                available=Sum('available_rooms'),
            )
            total = cal.get('total') or 0
            available = cal.get('available') or 0
            if total > 0 and (available / total) > 0.50 and available > 3:
                last_minute = after_competitor * Decimal('-0.12')  # 12% last-minute discount
        except Exception:
            pass

    final_price = max(
        price * Decimal('0.50'),  # Floor: never go below 50% of base
        (after_competitor + last_minute).quantize(Decimal('0.01')),
    )

    return PricingResult(
        base_price=price,
        final_price=final_price,
        modifier_name=modifier_name,
        multiplier=multiplier,
        competitor_adjustment=competitor_adj.quantize(Decimal('0.01')),
        occupancy_adjustment=occupancy_adj.quantize(Decimal('0.01')),
        last_minute_discount=last_minute.quantize(Decimal('0.01')),
        demand_adjustment=demand_adj.quantize(Decimal('0.01')),
        velocity_adjustment=velocity_adj.quantize(Decimal('0.01')),
        scarcity_adjustment=scarcity_adj.quantize(Decimal('0.01')),
        breakdown={
            'base': float(price),
            'multiplier': float(multiplier),
            'after_modifier': float(after_modifier),
            'occupancy_adj': float(occupancy_adj),
            'scarcity_adj': float(scarcity_adj),
            'demand_adj': float(demand_adj),
            'velocity_adj': float(velocity_adj),
            'after_occupancy': float(after_occupancy),
            'competitor_adj': float(competitor_adj),
            'after_competitor': float(after_competitor),
            'last_minute': float(last_minute),
            'occupancy_pct': float(occupancy_pct) if occupancy_pct is not None else None,
            'available_rooms': int(available) if available is not None else None,
            'total_rooms': int(total) if total is not None else None,
            'final': float(final_price),
        },
    )


def recompute_dynamic_prices_for_property(property_obj, days_ahead: int = 30):
    """
    Recompute dynamic prices for all room types of a property
    for the next `days_ahead` days. Updates InventoryCalendar rate overrides.
    """
    from apps.rooms.models import RoomType
    from apps.inventory.models import InventoryCalendar

    today = date.today()
    room_types = RoomType.objects.filter(property=property_obj)
    updated = 0

    for rt in room_types:
        for day_offset in range(days_ahead):
            check_date = today + timedelta(days=day_offset)
            result = calculate_dynamic_price(rt, check_date, property_obj)

            # Update the InventoryCalendar rate_override if it differs
            InventoryCalendar.objects.filter(
                room_type=rt,
                date=check_date,
            ).update(rate_override=result.final_price)
            updated += 1

    return updated
