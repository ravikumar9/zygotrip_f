# promos/hardening.py - Coupon engine hardening with strict validation

from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from .models import Promo, PromoUsage


# Configuration constants
MAX_DISCOUNT_PERCENTAGE = 80  # Maximum discount: 80% of order
MAX_DISCOUNT_AMOUNT = Decimal('5000.00')  # Maximum discount: ₹5000
MAX_COUPONS_PER_USER = 10  # Limit coupon uses per user
COUPON_CACHE_TTL = 300  # Cache coupon validity for 5 minutes


class CouponValidationError(Exception):
    """Raised when coupon validation fails"""
    pass


class CouponHardener:
    """Hardened coupon validation engine"""
    
    @staticmethod
    def check_coupon_expiry(coupon):
        """Check if coupon has expired"""
        now = timezone.now()
        if coupon.expires_at and coupon.expires_at < now:
            raise CouponValidationError(
                f"Coupon '{coupon.code}' has expired ({coupon.expires_at.date()})"
            )
        return True
    
    @staticmethod
    def check_coupon_active(coupon):
        """Check if coupon is active"""
        if not coupon.is_active:
            raise CouponValidationError(f"Coupon '{coupon.code}' is not active")
        return True
    
    @staticmethod
    def check_module_match(coupon, module):
        """Check if coupon is applicable to the module"""
        VALID_MODULES = ['hotels', 'buses', 'cabs', 'packages']
        
        if module not in VALID_MODULES:
            raise CouponValidationError(f"Invalid module: '{module}'")
        
        # If coupon has applicable_module field, check it
        if hasattr(coupon, 'applicable_module') and coupon.applicable_module:
            if module not in coupon.applicable_module.split(','):
                raise CouponValidationError(
                    f"Coupon '{coupon.code}' is not applicable to {module}"
                )
        
        return True
    
    @staticmethod
    def check_per_user_limit(coupon, user):
        """Check if user has exceeded their coupon usage limit"""
        if not user or not user.is_authenticated:
            return True  # Guest users can use coupons
        
        usage_count = PromoUsage.objects.filter(
            promo=coupon,
            user=user
        ).count()
        
        if usage_count >= MAX_COUPONS_PER_USER:
            raise CouponValidationError(
                f"You have exceeded the maximum uses ({MAX_COUPONS_PER_USER}) for this coupon"
            )
        
        return True
    
    @staticmethod
    def check_minimum_order_value(coupon, base_price):
        """Check if order meets minimum value requirement"""
        min_value = getattr(coupon, 'min_order_value', Decimal('0.00'))
        
        if base_price < min_value:
            raise CouponValidationError(
                f"Order must be at least ₹{min_value} to use this coupon "
                f"(current: ₹{base_price})"
            )
        
        return True
    
    @staticmethod
    def calculate_discount(coupon, base_price):
        """Calculate discount with cap enforcement"""
        if coupon.discount_type == Promo.TYPE_PERCENT:
            # Percentage discount
            discount = (base_price * coupon.value / Decimal('100')).quantize(Decimal('0.01'))
            
            # Cap percentage-based discounts at MAX_DISCOUNT_PERCENTAGE
            max_allowed_discount = (base_price * MAX_DISCOUNT_PERCENTAGE / Decimal('100')).quantize(Decimal('0.01'))
            discount = min(discount, max_allowed_discount)
        else:
            # Fixed amount discount
            discount = coupon.value
        
        # Never exceed MAX_DISCOUNT_AMOUNT
        discount = min(discount, MAX_DISCOUNT_AMOUNT)
        
        return max(Decimal('0.00'), discount)  # Never negative
    
    @staticmethod
    def validate_coupon_comprehensive(coupon_code, user, module, base_price):
        """
        Comprehensive coupon validation with all rules.
        
        Args:
            coupon_code: Coupon code (string)
            user: User object (can be None for guests)
            module: Module name ('hotels', 'buses', 'cabs', 'packages')
            base_price: Order value (Decimal)
        
        Returns:
            dict: {
                'valid': bool,
                'coupon': Promo or None,
                'discount': Decimal,
                'error': str or None
            }
        """
        cache_key = f"coupon:{coupon_code}:{module}:{user.id if user else 'guest'}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Rule 1: Coupon exists
            coupon = Promo.objects.filter(
                code=coupon_code.upper(),
            ).first()
            
            if not coupon:
                raise CouponValidationError(f"Coupon '{coupon_code}' not found")
            
            # Rule 2: Coupon is active
            CouponHardener.check_coupon_active(coupon)
            
            # Rule 3: Coupon has not expired (ENFORCED)
            CouponHardener.check_coupon_expiry(coupon)
            
            # Rule 4: Module validation (ENFORCED)
            CouponHardener.check_module_match(coupon, module)
            
            # Rule 5: Per-user limit (ENFORCED)
            CouponHardener.check_per_user_limit(coupon, user)
            
            # Rule 6: Minimum order value
            CouponHardener.check_minimum_order_value(coupon, base_price)
            
            # Rule 7: Calculate discount with caps (ENFORCED)
            discount = CouponHardener.calculate_discount(coupon, base_price)
            
            # Single coupon per order validation (enforced at booking level)
            # This ensures only ONE coupon is applied per order
            
            result = {
                'valid': True,
                'coupon': coupon,
                'discount': discount,
                'error': None,
            }
            
            # Cache result for 5 minutes
            cache.set(cache_key, result, COUPON_CACHE_TTL)
            return result
            
        except CouponValidationError as e:
            result = {
                'valid': False,
                'coupon': None,
                'discount': Decimal('0.00'),
                'error': str(e),
            }
            # Cache error for shorter time (1 minute)
            cache.set(cache_key, result, 60)
            return result
        except Exception as e:
            result = {
                'valid': False,
                'coupon': None,
                'discount': Decimal('0.00'),
                'error': f"Coupon validation error: {str(e)}",
            }
            return result
    
    @staticmethod
    def log_coupon_usage(coupon, user, booking_id, discount_amount):
        """Log coupon usage for audit trail and limit enforcement"""
        if not coupon or not user or not booking_id:
            return None
        
        usage = PromoUsage.objects.create(
            promo=coupon,
            user=user,
            discount_amount=discount_amount,
            booking_id=booking_id,  # Store reference to booking/order
        )
        
        return usage