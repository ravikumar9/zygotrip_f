from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from .models import Promo, PromoUsage


def calculate_promo_discount(promo, amount):
    """Calculate absolute discount amount for a promo code."""
    if not promo:
        return Decimal('0.00')
    amount = Decimal(str(amount))
    if promo.discount_type == Promo.TYPE_PERCENT:
        discount = (amount * promo.value / Decimal('100.0')).quantize(Decimal('0.01'))
        # Honour max_discount cap
        if promo.max_discount and discount > promo.max_discount:
            return promo.max_discount
        return discount
    return min(promo.value, amount)  # Fixed discount cannot exceed amount


class CouponService:
    """Service for finding and applying best available coupons."""

    @staticmethod
    def get_best_coupon(user, module, base_price):
        """
        Get best coupon for user across all modules.

        Args:
            user: User instance
            module: 'hotels', 'buses', 'cabs', 'packages'
            base_price: Price to calculate discount on

        Returns:
            dict with coupon details or None
        """
        now = timezone.now().date()

        # Filter active promos applicable to module, using correct field 'ends_at'
        active_promos = Promo.objects.filter(
            is_active=True,
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        ).filter(
            Q(applicable_module='all') | Q(applicable_module=module),
        ).order_by('-value')

        if not active_promos.exists():
            return None

        best_promo = active_promos.first()

        # Check max_uses limit
        if best_promo.max_uses and best_promo.max_uses > 0:
            usage_count = PromoUsage.objects.filter(promo=best_promo).count()
            if usage_count >= best_promo.max_uses:
                return None

        discount = calculate_promo_discount(best_promo, base_price)

        return {
            'code': best_promo.code,
            'discount_amount': float(discount),
            'description': f"Save ₹{int(discount)}",
            'promo_id': best_promo.id,
        }

    @staticmethod
    def validate_coupon(coupon_code, user, module, base_price):
        """Validate if coupon is usable for the given module and price."""
        try:
            now = timezone.now().date()
            coupon = Promo.objects.get(code=coupon_code.upper(), is_active=True)

            # Check date range using correct field names
            if coupon.starts_at and coupon.starts_at > now:
                return False, None, Decimal('0')
            if coupon.ends_at and coupon.ends_at < now:
                return False, None, Decimal('0')

            # Check module applicability
            if coupon.applicable_module not in ('all', module):
                return False, None, Decimal('0')

            # Check max_uses
            if coupon.max_uses and coupon.max_uses > 0:
                usage_count = PromoUsage.objects.filter(promo=coupon).count()
                if usage_count >= coupon.max_uses:
                    return False, None, Decimal('0')

            discount = calculate_promo_discount(coupon, base_price)
            return True, coupon, discount
        except Promo.DoesNotExist:
            return False, None, Decimal('0')