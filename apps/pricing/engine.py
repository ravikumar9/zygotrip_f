"""REMOVED — Use apps.pricing.pricing_service.calculate() for ALL pricing."""
import warnings
from datetime import date, timedelta
from decimal import Decimal

warnings.warn('engine.py removed. Use apps.pricing.pricing_service.calculate.', DeprecationWarning, stacklevel=2)
from apps.pricing.pricing_service import calculate, calculate_from_amounts, get_gst_rate, _q  # noqa: F401

# ── Demand Surge Tiers (legacy compat) ─────────────────────────────────────
# List of (occupancy_threshold, multiplier) in DESCENDING threshold order.
# Used by pricing_service._demand_adjustment() internally — exported here
# for backward-compatible test imports.
DEMAND_SURGE_TIERS = [
    (Decimal('0.95'), Decimal('1.15')),   # ≥95 % → +15 %
    (Decimal('0.85'), Decimal('1.10')),   # ≥85 % → +10 %
    (Decimal('0.75'), Decimal('1.05')),   # ≥75 % → +5 %
]


class PricingEngine:
    """
    Legacy compatibility shim. Tests reference PricingEngine._get_advance_booking_modifier().
    New code should use pricing_service.calculate() or pricing.revenue_engine directly.
    """

    @staticmethod
    def _get_advance_booking_modifier(checkin_date):
        """
        Advance-booking modifier (legacy interface).
        Returns a Decimal fraction:
          ≥60 days out → +0.05  (early-bird: value passed to discount logic)
          ≥30 days out → +0.03
          ≤1 day out   → −0.05  (last-minute: applied as surcharge)
          otherwise    →  0.00
        """
        if checkin_date is None:
            return Decimal('0')
        days_out = (checkin_date - date.today()).days
        if days_out >= 60:
            return Decimal('0.05')
        if days_out >= 30:
            return Decimal('0.03')
        if days_out <= 1:
            return Decimal('-0.05')
        return Decimal('0.00')
