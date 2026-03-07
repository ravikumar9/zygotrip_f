"""
Price Engine — Backward-compatible wrapper around pricing_service.

All pricing MUST use ``apps.pricing.pricing_service.calculate()``.
This module exists solely so legacy ``from apps.pricing.price_engine import PriceEngine``
import statements continue to work.
"""
from decimal import Decimal, ROUND_HALF_UP
from apps.pricing.pricing_service import (
    calculate as _ps_calculate,
    _q,
    get_gst_rate,
    get_gst_percentage,
)


class PriceEngine:
    """Thin wrapper — delegates entirely to pricing_service.calculate()."""

    @staticmethod
    def calculate(room_type, nights, rooms=1,
                  property_discount_percent=0, platform_discount_percent=0,
                  coupon_discount_percent=0, add_ons=None,
                  service_fee_percent=None, gst_percent=None,
                  checkin_date=None, user=None, loyalty_points=0):
        # Convert coupon_discount_percent to a flat promo_discount amount
        base = Decimal(str(room_type.base_price)) * rooms * nights
        promo_discount = _q(base * Decimal(str(coupon_discount_percent)) / 100) if coupon_discount_percent else Decimal('0')

        result = _ps_calculate(
            room_type=room_type,
            nights=nights,
            rooms=rooms,
            property_discount_percent=Decimal(str(property_discount_percent)),
            platform_discount_percent=Decimal(str(platform_discount_percent)),
            promo_discount=promo_discount,
            checkin_date=checkin_date,
            user=user,
            loyalty_points=loyalty_points,
        )
        # Map to legacy shape expected by old callers
        return {
            'base_price': result['base_price'],
            'property_discount': result['property_discount'],
            'platform_discount': result['platform_discount'],
            'coupon_discount': promo_discount,
            'add_ons_total': Decimal('0'),
            'service_fee': result['service_fee'],
            'demand_adjustment': result.get('demand_adjustment', Decimal('0')),
            'advance_modifier': result.get('advance_modifier', Decimal('0')),
            'competitor_cap_applied': result.get('competitor_cap_applied', False),
            'loyalty_discount': result.get('loyalty_discount', Decimal('0')),
            'gst': result['gst_amount'],
            'gst_percentage': result['gst_percentage'],
            'final_price': result['final_total'],
            'ota_commission': result.get('ota_commission', Decimal('0')),
            'net_to_hotel': result.get('net_to_hotel', Decimal('0')),
            'breakdown': {
                'base_price': str(result['base_price']),
                'nights': nights,
                'rooms': rooms,
                'room_tariff_per_night': str(result['tariff_per_night']),
                'property_discount_percent': property_discount_percent,
                'platform_discount_percent': platform_discount_percent,
                'coupon_discount_percent': coupon_discount_percent,
                'gst_percent': result['gst_percentage'],
            },
        }

    @staticmethod
    def format_for_display(price_calc):
        return {
            'base': price_calc['base_price'],
            'property_discount': price_calc['property_discount'],
            'platform_discount': price_calc['platform_discount'],
            'service_fee': price_calc['service_fee'],
            'gst': price_calc.get('gst', price_calc.get('gst_amount', Decimal('0'))),
            'final': price_calc.get('final_price', price_calc.get('final_total', Decimal('0'))),
        }
