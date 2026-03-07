"""
DEPRECATED: Use apps.pricing.pricing_service instead.

This module is kept ONLY for backwards compatibility with imports.
All new code MUST use pricing_service.calculate() or pricing_service.calculate_from_amounts().
"""
import warnings
from decimal import Decimal

warnings.warn(
    "pricing.services is deprecated. Use pricing.pricing_service instead.",
    DeprecationWarning,
    stacklevel=2,
)


def calculate_price_breakdown(base_amount, meal_amount, service_fee_rate, gst_rate, promo_discount):
    """DEPRECATED: Use pricing_service.calculate_from_amounts()."""
    from apps.pricing.pricing_service import calculate_from_amounts
    return calculate_from_amounts(
        base_amount=base_amount,
        meal_amount=meal_amount,
        promo_discount=promo_discount,
    )