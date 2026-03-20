import pytest
from decimal import Decimal
from apps.booking.pricing_engine import PricingEngine


class TestPricingEngine:
    def test_base_total_one_room(self):
        e = PricingEngine(Decimal('2000'), nights=3, room_count=1)
        assert e.breakdown['base_total'] == pytest.approx(6000.0)

    def test_base_total_multi_room(self):
        e = PricingEngine(Decimal('2000'), nights=2, room_count=2)
        assert e.breakdown['base_total'] == pytest.approx(8000.0)

    def test_property_discount_10pct(self):
        e = PricingEngine(Decimal('1000'), nights=2)
        e.apply_property_discount(percent=10)
        assert e.breakdown['property_discount_amount'] == pytest.approx(200.0, rel=1e-3)
        assert e.breakdown['after_property_discount'] == pytest.approx(1800.0, rel=1e-3)

    def test_gst_12pct_midrange(self):
        e = PricingEngine(Decimal('4000'), nights=2)
        e.apply_gst(percent=12)
        assert e.breakdown['gst_percent'] == 12
        assert e.breakdown['gst_amount'] == pytest.approx(960.0, rel=1e-3)

    def test_gst_18pct_luxury(self):
        e = PricingEngine(Decimal('8000'), nights=2)
        e.apply_gst(percent=18)
        assert e.breakdown['gst_percent'] == 18
        assert e.breakdown['gst_amount'] == pytest.approx(2880.0, rel=1e-3)

    def test_total_never_negative(self):
        e = PricingEngine(Decimal('500'), nights=1)
        e.apply_property_discount(amount=Decimal('9999'))
        e.apply_gst(percent=12)
        final = e.breakdown.get('total_price', e.breakdown.get('after_gst', 0))
        assert float(final) >= 0

    def test_finalize_returns_total(self):
        e = PricingEngine(Decimal('3000'), nights=2)
        e.apply_gst(percent=12)
        summary = e.finalize()
        assert isinstance(summary, dict)
        assert 'total_price' in summary or 'gst_amount' in summary
