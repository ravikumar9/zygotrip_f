import pytest
from decimal import Decimal
from apps.loyalty.services import earn_points_for_booking, redeem_points
from apps.loyalty.models import LoyaltyAccount, LoyaltyTier


class TestLoyaltyService:
    def test_earn_points_correct_ratio(self, booking):
        booking.total_amount = Decimal('1000')
        booking.save()
        pts = earn_points_for_booking(booking)
        assert pts == Decimal('100')

    def test_earn_points_large_amount(self, booking):
        booking.total_amount = Decimal('15000')
        booking.save()
        pts = earn_points_for_booking(booking)
        assert pts == Decimal('1500')

    def test_earn_zero_for_guest_booking(self, booking):
        booking.user = None
        booking.save()
        pts = earn_points_for_booking(booking)
        assert pts == Decimal('0')

    def test_redeem_reduces_balance(self, user):
        account, _ = LoyaltyAccount.objects.get_or_create(user=user)
        account.points_balance = Decimal('500')
        account.save()
        discount = redeem_points(user, Decimal('200'))
        account.refresh_from_db()
        assert account.points_balance == Decimal('300')
        assert discount == Decimal('2')

    def test_redeem_raises_if_insufficient(self, user):
        account, _ = LoyaltyAccount.objects.get_or_create(user=user)
        account.points_balance = Decimal('50')
        account.save()
        with pytest.raises(ValueError, match='[Ii]nsufficient'):
            redeem_points(user, Decimal('500'))

    def test_tier_upgrade_silver_to_gold(self, user):
        account, _ = LoyaltyAccount.objects.get_or_create(user=user)
        account.lifetime_points = Decimal('10000')
        account.save()
        upgraded, tier = account.recalculate_tier()
        assert tier == LoyaltyTier.GOLD
