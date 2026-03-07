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
  Room tariff ≤ ₹7500/night  →  5 % GST
  Room tariff  > ₹7500/night →  18 % GST
  NO 12 % slab anywhere in the codebase.
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger('zygotrip.pricing')

# ── Constants ────────────────────────────────────────────────────────────────
_SERVICE_FEE_RATE = Decimal('0.05')
_SERVICE_FEE_CAP = Decimal('500.00')
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
    return _GST_LOW_RATE if Decimal(str(tariff_per_night)) <= _GST_LOW_THRESHOLD else _GST_HIGH_RATE


def get_gst_percentage(tariff_per_night):
    return '5' if Decimal(str(tariff_per_night)) <= _GST_LOW_THRESHOLD else '18'


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
    """Occupancy-based surge: ≥95 % → +15 %, ≥85 % → +10 %, ≥75 % → +5 %."""
    if not property_obj or not checkin_date:
        return Decimal('0'), None
    try:
        from apps.core.intelligence import DemandForecast
        fc = DemandForecast.objects.filter(property=property_obj, date=checkin_date).first()
        if fc and fc.predicted_occupancy:
            occ = float(fc.predicted_occupancy)
            if occ >= 0.95:
                return _q(subtotal * Decimal('0.15')), occ
            if occ >= 0.85:
                return _q(subtotal * Decimal('0.10')), occ
            if occ >= 0.75:
                return _q(subtotal * Decimal('0.05')), occ
    except Exception:
        pass
    return Decimal('0'), None


def _advance_booking_modifier(checkin_date, subtotal):
    """Early-bird: ≥60d → −5 %, ≥30d → −3 %; last-minute ≤1d → +5 %."""
    if not checkin_date:
        return Decimal('0')
    try:
        from django.utils import timezone
        days = (checkin_date - timezone.now().date()).days
        if days >= 60:
            return _q(subtotal * Decimal('-0.05'))
        if days >= 30:
            return _q(subtotal * Decimal('-0.03'))
        if days <= 1:
            return _q(subtotal * Decimal('0.05'))
    except Exception:
        pass
    return Decimal('0')


def _competitor_price_cap(property_obj, nights, rooms, subtotal):
    """Cap at avg competitor price + 5 %."""
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
    except Exception:
        pass
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
):
    """
    Unified 15-step pricing pipeline.  ALL callers MUST use this function.

    Returns canonical dict:
      tariff_per_night, nights, rooms, base_price,
      meal_plan_price, meal_price_per_room_night,
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

    # 3. Property discount
    prop_disc = _q(base_price * Decimal(str(property_discount_percent)) / Decimal('100'))
    subtotal = base_price - prop_disc

    # 4. Platform discount
    plat_disc = _q(subtotal * Decimal(str(platform_discount_percent)) / Decimal('100'))
    subtotal -= plat_disc

    # 5. Promo discount
    promo_disc = _q(Decimal(str(promo_discount)))
    subtotal = subtotal + meal_total - promo_disc
    if subtotal < Decimal('0'):
        subtotal = Decimal('0')

    # 6. Service fee
    svc_fee = _q(subtotal * _SERVICE_FEE_RATE)
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

    # 11. GST
    gst_rate = get_gst_rate(tariff)
    gst_pct = get_gst_percentage(tariff)
    gst_amount = _q(total_before_tax * gst_rate)
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

    logger.debug('pricing: room=%s final=%s demand=%s comp_cap=%s',
                 room_type_id, final_total, demand_adj, comp_cap)

    result = {
        'tariff_per_night': tariff,
        'nights': int(nights),
        'rooms': int(rooms),
        'base_price': _q(base_price),
        'meal_plan_price': _q(meal_total),
        'meal_price_per_room_night': _q(meal_per_night),
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

    svc_fee = _q(total_before_tax * _SERVICE_FEE_RATE)
    if svc_fee > _SERVICE_FEE_CAP:
        svc_fee = _SERVICE_FEE_CAP

    slab = _q(tariff_per_night) if tariff_per_night is not None else base_amount
    gst_rate = get_gst_rate(slab)
    gst_pct = get_gst_percentage(slab)
    gst_amount = _q((total_before_tax + svc_fee) * gst_rate)
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

    svc_fee = _q(total_before_tax * _SERVICE_FEE_RATE)
    if svc_fee > _SERVICE_FEE_CAP:
        svc_fee = _SERVICE_FEE_CAP

    gst_rate = get_gst_rate(tariff)
    gst_pct = get_gst_percentage(tariff)
    gst_amount = _q((total_before_tax + svc_fee) * gst_rate)
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
