"""
Unified Pricing Engine — Single Source of Truth for the entire OTA platform.

ALL pricing (search, detail, availability, checkout, invoicing) MUST flow
through ``calculate()`` in this module.  No other pricing module is authoritative.

Pipeline (15 steps):
  1.  Base room price (tariff × nights × rooms)
  2.  Meal plan add-on (RoomMealPlan.price_modifier resolution)
  3.  Property discount (owner-configured percentage)
  4.  Platform discount (admin-configured percentage)
  5.  Promo / coupon discount (absolute amount)
  6.  Service fee (5 % of subtotal, capped ₹500)
  7.  Demand adjustment (occupancy-based surge from DemandForecast)
  8.  Advance booking modifier (early-bird / last-minute)
  9.  Competitor price cap (stay within 5 % of market average)
  10. Wallet credit deduction
  11. GST (Indian accommodation tax: 5 % ≤ ₹7500/night, 18 % above)
  12. Loyalty point redemption (₹0.25/pt, max 15 % of total)
  13. OTA commission split (informational, not guest-facing)
  14. Redis cache write
  15. Final dict assembly

GST SLABS (Indian accommodation tax law):
  Room tariff  < ₹1000/night →  0 % GST (exempt)
  Room tariff ≤ ₹7500/night  →  5 % GST
  Room tariff  > ₹7500/night →  18 % GST
  NO 12 % slab anywhere in the codebase.

SERVICE FEE & GST POLICY:
  Service fee and GST are always calculated on the ORIGINAL room price
  + meal amount (pre-discount).  Promo, property, and platform discounts
  must NOT reduce the service fee or GST base.
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models

logger = logging.getLogger('zygotrip.pricing')


# ── Pricing step exception (structured failure tracking) ─────────────────────

class PricingStepError(Exception):
    """
    Raised internally when a non-critical pricing step fails.

    Non-critical steps (demand, advance booking, competitor cap, LOS, occupancy)
    catch this exception, log it, and fall back to zero-adjustment so the
    pipeline NEVER crashes. Critical steps (base price, GST, service fee) do
    NOT catch this exception — they propagate to the caller.

    Attributes:
        step:     Step name (e.g. 'demand_adjustment', 'competitor_cap')
        original: The original exception that caused this
    """
    def __init__(self, step: str, original: Exception):
        self.step = step
        self.original = original
        super().__init__(f"Pricing step '{step}' failed: {original}")

    def __repr__(self):
        return f"PricingStepError(step={self.step!r}, original={self.original!r})"

# ── Constants ────────────────────────────────────────────────────────────────
_SERVICE_FEE_RATE = Decimal('0.05')
_SERVICE_FEE_CAP = Decimal('500.00')
_GST_EXEMPT_THRESHOLD = Decimal('1000.00')   # No GST if room tariff < ₹1000/night
_GST_LOW_THRESHOLD = Decimal('7500.00')
_GST_LOW_RATE = Decimal('0.05')
_GST_HIGH_RATE = Decimal('0.18')
_LOYALTY_POINT_VALUE = Decimal('0.25')
_MAX_LOYALTY_DISCOUNT_PCT = Decimal('0.15')


# ── Helpers ──────────────────────────────────────────────────────────────────
def _q(value):
    """Round to 2 decimal places (half-up) — INR standard."""
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_gst_rate(tariff_per_night):
    tariff = Decimal(str(tariff_per_night))
    if tariff < _GST_EXEMPT_THRESHOLD:
        return Decimal('0')          # No GST for rooms below ₹1000/night
    return _GST_LOW_RATE if tariff <= _GST_LOW_THRESHOLD else _GST_HIGH_RATE


def get_gst_percentage(tariff_per_night):
    tariff = Decimal(str(tariff_per_night))
    if tariff < _GST_EXEMPT_THRESHOLD:
        return '0'                    # No GST for rooms below ₹1000/night
    return '5' if tariff <= _GST_LOW_THRESHOLD else '18'


# ── Meal plan resolution ────────────────────────────────────────────────────
_MEAL_CODE_MAP = {
    'breakfast': 'R+B', 'room_breakfast': 'R+B',
    'half_board': 'R+B+L/D', 'halfboard': 'R+B+L/D',
    'full_board': 'R+A', 'fullboard': 'R+A',
    'all_inclusive': 'R+A', 'all_meals': 'R+A',
}


def resolve_meal_plan_price(room_type, meal_plan_code):
    """Resolve meal plan code → price_modifier per room per night."""
    if not meal_plan_code or meal_plan_code in ('', 'none', 'room_only', 'R'):
        return Decimal('0.00')
    try:
        from apps.rooms.models import RoomMealPlan
        mp = RoomMealPlan.objects.filter(
            room_type=room_type, code=meal_plan_code, is_available=True,
        ).first()
        if mp:
            return _q(mp.price_modifier)
        mapped = _MEAL_CODE_MAP.get(meal_plan_code.lower().strip())
        if mapped:
            mp = RoomMealPlan.objects.filter(
                room_type=room_type, code=mapped, is_available=True,
            ).first()
            if mp:
                return _q(mp.price_modifier)
    except Exception as exc:
        logger.warning('meal plan resolve failed %r room=%s: %s',
                       meal_plan_code, getattr(room_type, 'id', '?'), exc)
    return Decimal('0.00')


# ── Intelligence helpers (safe — never crash pricing) ────────────────────────
def _demand_adjustment(property_obj, checkin_date, subtotal):
    """Demand adjustment DISABLED — no auto price hike allowed.
    Prices only change when property owner or admin explicitly updates them.
    Dynamic discounts (cashback, offers) are handled separately.
    """
    return Decimal('0'), None


def _advance_booking_modifier(checkin_date, subtotal):
    """DISABLED — no auto price hike/discount based on booking timing.
    Early-bird discounts and last-minute surcharges are disabled.
    Only manual offers/coupons by admin or property owner are allowed.
    """
    return Decimal('0')


def _los_modifier(property_obj, nights):
    """DISABLED — no auto LOS discount/surcharge. Only manual pricing allowed."""
    return Decimal('1.00'), ''
    # DISABLED original code below:
    if not property_obj or nights <= 1:
        return Decimal('1.00'), ''
    try:
        from apps.pricing.models import LOSPricing
        los = LOSPricing.objects.filter(
            property=property_obj,
            min_nights__lte=nights,
            is_active=True,
        ).filter(
            models.Q(max_nights__gte=nights) | models.Q(max_nights__isnull=True),
        ).order_by('-min_nights').first()
        if los:
            return _q(los.multiplier), los.label or f'{nights}-night rate'
    except Exception as exc:
        logger.warning(
            'Pricing step [los_modifier] failed — using 1.0x multiplier: '
            'property=%s nights=%s error=%s',
            getattr(property_obj, 'id', '?'), nights, exc,
        )
    return Decimal('1.00'), ''


def _occupancy_charges(room_type, nights, adults=2, children=0, infants=0):
    """Extra occupancy charges for adults/children/infants beyond base occupancy."""
    if not room_type:
        return Decimal('0'), {}
    try:
        from apps.pricing.models import OccupancyPricing
        occ = OccupancyPricing.objects.filter(
            room_type=room_type, is_active=True,
        ).first()
        if occ:
            details = occ.calculate_extra_charges(adults, children, infants, nights)
            return _q(details['total_extra']), details
    except Exception as exc:
        logger.warning(
            'Pricing step [occupancy_charges] failed — using zero charge: '
            'room_type=%s adults=%s children=%s infants=%s error=%s',
            getattr(room_type, 'id', '?'), adults, children, infants, exc,
        )
    return Decimal('0'), {}


def _competitor_price_cap(property_obj, nights, rooms, subtotal):
    """DISABLED — no competitor-based price adjustments."""
    return subtotal, False
    # DISABLED original code below:
    if not property_obj:
        return subtotal, False
    try:
        from apps.pricing.models import CompetitorPrice
        from django.db.models import Avg
        avg = CompetitorPrice.objects.filter(
            property=property_obj, is_available=True,
        ).aggregate(a=Avg('price_per_night'))['a']
        if avg:
            cap = _q(Decimal(str(avg)) * Decimal('1.05') * nights * rooms)
            if subtotal > cap:
                return cap, True
    except Exception as exc:
        logger.warning(
            'Pricing step [competitor_price_cap] failed — cap not applied: '
            'property=%s nights=%s rooms=%s error=%s',
            getattr(property_obj, 'id', '?'), nights, rooms, exc,
        )
    return subtotal, False


def _loyalty_discount(user, points, total):
    """₹0.25/pt, max 15 % of total."""
    if not points or points <= 0 or not user:
        return Decimal('0')
    try:
        raw = _q(Decimal(str(points)) * _LOYALTY_POINT_VALUE)
        cap = _q(total * _MAX_LOYALTY_DISCOUNT_PCT)
        return min(raw, cap)
    except Exception:
        return Decimal('0')


def _wallet_credit(user, total):
    """Deduct available wallet balance (capped at total)."""
    if not user:
        return Decimal('0')
    try:
        from apps.wallet.models import Wallet
        w = Wallet.objects.filter(user=user).first()
        if w and w.balance and w.balance > 0:
            return min(_q(w.balance), total)
    except Exception:
        pass
    return Decimal('0')


# ═════════════════════════════════════════════════════════════════════════════
# PRIMARY ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def calculate(
    room_type,
    nights,
    rooms=1,
    meal_plan_price=Decimal('0.00'),
    meal_plan_code='',
    promo_discount=Decimal('0.00'),
    property_discount_percent=Decimal('0'),
    platform_discount_percent=Decimal('0'),
    checkin_date=None,
    user=None,
    loyalty_points=0,
    wallet_deduct=False,
    adults=2,
    children=0,
    infants=0,
):
    """
    Unified 17-step pricing pipeline.  ALL callers MUST use this function.

    Returns canonical dict:
      tariff_per_night, nights, rooms, base_price,
      meal_plan_price, meal_price_per_room_night,
      los_multiplier, los_label, occupancy_charges, occupancy_details,
      property_discount, platform_discount, promo_discount,
      demand_adjustment, advance_modifier, competitor_cap_applied,
      loyalty_discount, wallet_credit,
      service_fee, gst_percentage, gst_amount,
      total_before_tax, total_after_tax, final_total,
      ota_commission, net_to_hotel
    """
    room_type_id = getattr(room_type, 'id', None)

    # ── Cache lookup ─────────────────────────────────────────────────────
    try:
        from apps.search.engine.cache_manager import price_cache
        cached = price_cache.get_price(
            room_type_id, int(nights), int(rooms), meal_plan_code, checkin_date,
            promo_discount=promo_discount,
        )
        if cached is not None:
            logger.debug('pricing cache HIT room=%s', room_type_id)
            return cached
    except Exception:
        pass

    property_obj = getattr(room_type, 'property', None)
    tariff = _q(room_type.base_price)

    # 1. Base price
    base_price = _q(tariff * int(nights) * int(rooms))

    # 2. Meal plan
    meal_per_night = _q(Decimal(str(meal_plan_price)))
    if meal_per_night == Decimal('0') and meal_plan_code:
        meal_per_night = resolve_meal_plan_price(room_type, meal_plan_code)
    meal_total = _q(meal_per_night * int(nights) * int(rooms))

    # 2a. LOS (Length-of-Stay) modifier — applied to base price
    los_mult, los_label = _los_modifier(property_obj, int(nights))
    los_adjusted_base = _q(base_price * los_mult)
    los_discount = _q(base_price - los_adjusted_base)

    # 2b. Occupancy charges — extra adults/children/infants
    occ_charges, occ_details = _occupancy_charges(
        room_type, int(nights), adults=adults, children=children, infants=infants,
    )
    occ_total = _q(occ_charges * int(rooms))

    # 3. Property discount
    prop_disc = _q(los_adjusted_base * Decimal(str(property_discount_percent)) / Decimal('100'))
    subtotal = los_adjusted_base - prop_disc

    # 4. Platform discount
    plat_disc = _q(subtotal * Decimal(str(platform_discount_percent)) / Decimal('100'))
    subtotal -= plat_disc

    # 5. Promo discount
    promo_disc = _q(Decimal(str(promo_discount)))
    subtotal = subtotal + meal_total + occ_total - promo_disc
    if subtotal < Decimal('0'):
        subtotal = Decimal('0')

    # 6. Service fee — calculated on ORIGINAL room price + meals + occupancy (pre-discount)
    #    Promo/coupon discounts must NOT reduce service fee or GST.
    pre_discount_base = _q(base_price + meal_total + occ_total)
    svc_fee = _q(pre_discount_base * _SERVICE_FEE_RATE)
    if svc_fee > _SERVICE_FEE_CAP:
        svc_fee = _SERVICE_FEE_CAP
    subtotal_with_fee = subtotal + svc_fee

    # 7. Demand adjustment
    demand_adj, demand_occ = _demand_adjustment(property_obj, checkin_date, subtotal_with_fee)
    subtotal_with_fee += demand_adj

    # 8. Advance booking modifier
    adv_mod = _advance_booking_modifier(checkin_date, subtotal_with_fee)
    subtotal_with_fee += adv_mod

    # 9. Competitor price cap
    subtotal_with_fee, comp_cap = _competitor_price_cap(
        property_obj, int(nights), int(rooms), subtotal_with_fee,
    )

    # 10. Wallet credit (before tax)
    w_credit = Decimal('0')
    if wallet_deduct and user:
        w_credit = _wallet_credit(user, subtotal_with_fee)
        subtotal_with_fee -= w_credit

    total_before_tax = _q(subtotal_with_fee)
    if total_before_tax < Decimal('0'):
        total_before_tax = Decimal('0')

    # 11. GST — calculated on ORIGINAL room price + meals + service fee (pre-discount)
    #    Discounts (promo, property, platform) must NOT reduce GST base.
    gst_rate = get_gst_rate(tariff)
    gst_pct = get_gst_percentage(tariff)
    gst_base = _q(pre_discount_base + svc_fee)   # original amounts, not discounted
    gst_amount = _q(gst_base * gst_rate)
    total_after_tax = _q(total_before_tax + gst_amount)

    # 12. Loyalty
    loy_disc = _loyalty_discount(user, loyalty_points, total_after_tax)
    final_total = _q(total_after_tax - loy_disc)

    # 13. OTA commission (informational — not added to guest price)
    try:
        comm_rate = Decimal(str(getattr(property_obj, 'commission_percentage', 15) or 15))
        ota_comm = _q(final_total * comm_rate / Decimal('100'))
        net_hotel = _q(final_total - ota_comm)
    except Exception:
        ota_comm = _q(final_total * Decimal('0.15'))
        net_hotel = _q(final_total - ota_comm)

    # Round final total to nearest rupee for INR
    final_total = _q(final_total.quantize(Decimal('1'), rounding='ROUND_HALF_UP'))

    logger.debug('pricing: room=%s final=%s demand=%s comp_cap=%s',
                 room_type_id, final_total, demand_adj, comp_cap)

    result = {
        'tariff_per_night': tariff,
        'nights': int(nights),
        'rooms': int(rooms),
        'adults': adults,
        'children': children,
        'infants': infants,
        'base_price': _q(base_price),
        'meal_plan_price': _q(meal_total),
        'meal_price_per_room_night': _q(meal_per_night),
        'los_multiplier': str(los_mult),
        'los_label': los_label,
        'los_discount': _q(los_discount),
        'occupancy_charges': _q(occ_total),
        'occupancy_details': occ_details,
        'property_discount': _q(prop_disc),
        'platform_discount': _q(plat_disc),
        'promo_discount': _q(promo_disc),
        'demand_adjustment': _q(demand_adj),
        'advance_modifier': _q(adv_mod),
        'competitor_cap_applied': comp_cap,
        'loyalty_discount': _q(loy_disc),
        'wallet_credit': _q(w_credit),
        'service_fee': _q(svc_fee),
        'gst_percentage': gst_pct,
        'gst_amount': _q(gst_amount),
        'total_before_tax': total_before_tax,
        'total_after_tax': _q(total_after_tax),
        'final_total': _q(final_total),
        'ota_commission': ota_comm,
        'net_to_hotel': net_hotel,
    }

    # 14. Cache write
    try:
        from apps.search.engine.cache_manager import price_cache
        price_cache.set_price(
            room_type_id, int(nights), int(rooms), meal_plan_code, checkin_date, result,
            promo_discount=promo_discount,
        )
    except Exception:
        pass

    return result


# ═════════════════════════════════════════════════════════════════════════════
# SIMPLIFIED (amounts already known — used by create_booking service)
# ═════════════════════════════════════════════════════════════════════════════
def calculate_from_amounts(
    base_amount,
    meal_amount=Decimal('0.00'),
    promo_discount=Decimal('0.00'),
    tariff_per_night=None,
):
    base_amount = _q(Decimal(str(base_amount)))
    meal_amount = _q(Decimal(str(meal_amount)))
    promo_discount = _q(Decimal(str(promo_discount)))

    total_before_tax = _q(base_amount + meal_amount - promo_discount)
    if total_before_tax < Decimal('0'):
        total_before_tax = Decimal('0')

    # Service fee on ORIGINAL amounts (pre-discount), not discounted subtotal
    pre_discount_base = _q(base_amount + meal_amount)
    svc_fee = _q(pre_discount_base * _SERVICE_FEE_RATE)
    if svc_fee > _SERVICE_FEE_CAP:
        svc_fee = _SERVICE_FEE_CAP

    # GST on ORIGINAL amounts + service fee (pre-discount), not discounted subtotal
    slab = _q(tariff_per_night) if tariff_per_night is not None else base_amount
    gst_rate = get_gst_rate(slab)
    gst_pct = get_gst_percentage(slab)
    gst_base = _q(pre_discount_base + svc_fee)   # original amounts, not discounted
    gst_amount = _q(gst_base * gst_rate)
    total_after_tax = _q(total_before_tax + svc_fee + gst_amount)

    return {
        'base_amount': base_amount,
        'meal_amount': meal_amount,
        'service_fee': svc_fee,
        'gst': gst_amount,
        'gst_percentage': gst_pct,
        'promo_discount': promo_discount,
        'total_amount': total_after_tax,
    }


# ═════════════════════════════════════════════════════════════════════════════
# DATE-AWARE PRICING
# ═════════════════════════════════════════════════════════════════════════════
def get_date_multiplier(property_obj, target_date):
    """Priority: event → seasonal → weekend → 1.0."""
    from apps.pricing.models import EventPricing, SeasonalPricing, WeekendPricing

    event = EventPricing.objects.filter(
        property=property_obj, date=target_date, is_active=True,
    ).first()
    if event:
        return _q(event.multiplier), f'event:{event.event_name}'

    seasonal = SeasonalPricing.objects.filter(
        property=property_obj,
        start_date__lte=target_date,
        end_date__gte=target_date,
        is_active=True,
    ).order_by('-multiplier').first()
    if seasonal:
        return _q(seasonal.multiplier), f'season:{seasonal.name}'

    try:
        weekend = WeekendPricing.objects.get(property=property_obj, is_active=True)
        if target_date.isoweekday() in (weekend.weekend_days or [5, 6]):
            return _q(weekend.weekend_multiplier), 'weekend'
    except WeekendPricing.DoesNotExist:
        pass

    return Decimal('1.00'), 'base'


def calculate_date_range(
    room_type, check_in, check_out, rooms=1,
    meal_plan_price=Decimal('0.00'), promo_discount=Decimal('0.00'),
    property_discount_percent=Decimal('0'), platform_discount_percent=Decimal('0'),
):
    """Per-night date-aware pricing with full breakdown."""
    nights = (check_out - check_in).days
    if nights <= 0:
        raise ValueError("check_out must be after check_in")

    property_obj = room_type.property
    tariff = _q(room_type.base_price)
    meal_price = _q(Decimal(str(meal_plan_price)))

    per_night = []
    total_base = Decimal('0')
    total_meal = Decimal('0')
    current = check_in

    while current < check_out:
        mult, source = get_date_multiplier(property_obj, current)
        eff = _q(tariff * mult)
        night_base = _q(eff * rooms)
        night_meal = _q(meal_price * rooms)
        per_night.append({
            'date': str(current), 'base_rate': tariff, 'multiplier': mult,
            'effective_rate': eff, 'source': source, 'night_total': night_base + night_meal,
        })
        total_base += night_base
        total_meal += night_meal
        current += timedelta(days=1)

    prop_disc = _q(total_base * Decimal(str(property_discount_percent)) / Decimal('100'))
    plat_disc = _q((total_base - prop_disc) * Decimal(str(platform_discount_percent)) / Decimal('100'))
    promo_disc = _q(Decimal(str(promo_discount)))

    total_before_tax = _q(total_base + total_meal - prop_disc - plat_disc - promo_disc)
    if total_before_tax < Decimal('0'):
        total_before_tax = Decimal('0')

    # Service fee on ORIGINAL amounts (pre-discount)
    pre_discount_base = _q(total_base + total_meal)
    svc_fee = _q(pre_discount_base * _SERVICE_FEE_RATE)
    if svc_fee > _SERVICE_FEE_CAP:
        svc_fee = _SERVICE_FEE_CAP

    # GST on ORIGINAL amounts + service fee (pre-discount)
    gst_rate = get_gst_rate(tariff)
    gst_pct = get_gst_percentage(tariff)
    gst_base = _q(pre_discount_base + svc_fee)
    gst_amount = _q(gst_base * gst_rate)
    total_after_tax = _q(total_before_tax + svc_fee + gst_amount)

    return {
        'tariff_per_night': tariff, 'nights': nights, 'rooms': rooms,
        'base_price': total_base, 'meal_plan_price': total_meal,
        'property_discount': prop_disc, 'platform_discount': plat_disc,
        'promo_discount': promo_disc, 'total_before_tax': total_before_tax,
        'service_fee': svc_fee, 'gst_percentage': gst_pct, 'gst_amount': gst_amount,
        'total_after_tax': total_after_tax, 'final_total': total_after_tax,
        'per_night_breakdown': per_night,
    }
