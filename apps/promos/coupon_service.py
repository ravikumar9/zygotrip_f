"""
PHASE 11: Coupon Structure
Auto-apply best coupon.
Show: Base price, Total discount, After discount, Service fee, Final total
"""
from datetime import datetime, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class CouponService:
    """Coupon management with auto-apply logic"""
    
    # Static seed coupons (can be replaced with database)
    AVAILABLE_COUPONS = [
        {
            'code': 'STAYSAVER',
            'description': 'Stay Saver Deal - 10% Off',
            'discount_percent': 10,
            'discount_type': 'percentage',
            'min_amount': 2000,
            'max_discount': 500,
            'valid_from': date(2026, 1, 1),
            'valid_until': date(2026, 12, 31),
            'usage_limit': 1000,
            'min_nights': 1,
            'max_nights': None,
        },
        {
            'code': 'GLOBAL10',
            'description': 'Global 10% Off',
            'discount_percent': 10,
            'discount_type': 'percentage',
            'min_amount': 1000,
            'max_discount': 1000,
            'valid_from': date(2026, 1, 1),
            'valid_until': date(2026, 12, 31),
            'usage_limit': 5000,
            'min_nights': 1,
            'max_nights': None,
        },
        {
            'code': 'WELCOME200',
            'description': 'First Booking - ₹200 Off',
            'discount_amount': 200,
            'discount_type': 'fixed',
            'min_amount': 1500,
            'valid_from': date(2026, 1, 1),
            'valid_until': date(2026, 12, 31),
            'usage_limit': 5000,
            'min_nights': 1,
            'max_nights': None,
            'first_booking_only': True,
        },
    ]
    
    @staticmethod
    def validate_coupon(coupon_code):
        """
        Validate coupon code.
        
        Returns:
            {
                'valid': bool,
                'coupon': {coupon data},
                'message': str
            }
        """
        coupon_code = str(coupon_code).strip().upper()
        
        for coupon in CouponService.AVAILABLE_COUPONS:
            if coupon['code'] == coupon_code:
                today = date.today()
                
                # Check validity dates
                if today < coupon['valid_from'] or today > coupon['valid_until']:
                    return {
                        'valid': False,
                        'coupon': None,
                        'message': 'Coupon has expired'
                    }
                
                return {
                    'valid': True,
                    'coupon': coupon,
                    'message': f"Applied: {coupon['description']}"
                }
        
        return {
            'valid': False,
            'coupon': None,
            'message': f'Invalid coupon code: {coupon_code}'
        }
    
    @staticmethod
    def apply_coupon(coupon_code, booking_price, nights=1, is_first_booking=False):
        """
        Apply coupon to booking price.
        
        Args:
            coupon_code: str (coupon code to apply)
            booking_price: Decimal (base price before discount)
            nights: int (used for min_nights validation)
            is_first_booking: bool (used for first-booking coupons)
            
        Returns:
            {
                'applied': bool,
                'coupon_code': str,
                'discount_amount': Decimal,
                'coupon_description': str,
                'message': str,
                'final_price': Decimal
            }
        """
        validation = CouponService.validate_coupon(coupon_code)
        
        if not validation['valid']:
            return {
                'applied': False,
                'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'coupon_description': None,
                'message': validation['message'],
                'final_price': booking_price
            }
        
        coupon = validation['coupon']
        booking_price = Decimal(str(booking_price))
        
        # Check minimum amount
        if booking_price < coupon.get('min_amount', 0):
            return {
                'applied': False,
                'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'coupon_description': coupon['description'],
                'message': f"Minimum amount ₹{coupon['min_amount']} required",
                'final_price': booking_price
            }
        
        # Check night range
        if nights < coupon.get('min_nights', 1):
            return {
                'applied': False,
                'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'message': f"Minimum {coupon['min_nights']} nights required",
                'final_price': booking_price
            }
        
        if coupon.get('max_nights') and nights > coupon['max_nights']:
            return {
                'applied': False,
                'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'message': f"Maximum {coupon['max_nights']} nights allowed",
                'final_price': booking_price
            }
        
        # Check first booking only
        if coupon.get('first_booking_only') and not is_first_booking:
            return {
                'applied': False,
                'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'message': "This coupon is only for first bookings",
                'final_price': booking_price
            }
        
        # Calculate discount
        if coupon['discount_type'] == 'percentage':
            discount = booking_price * (Decimal(str(coupon['discount_percent'])) / Decimal('100'))
            # Apply max discount cap if set
            if 'max_discount' in coupon:
                discount = min(discount, Decimal(str(coupon['max_discount'])))
        else:  # fixed amount
            discount = Decimal(str(coupon.get('discount_amount', 0)))
        
        final_price = booking_price - discount
        
        return {
            'applied': True,
            'coupon_code': coupon_code,
            'discount_amount': discount.quantize(Decimal('0.01')),
            'coupon_description': coupon['description'],
            'message': f"Coupon applied: {coupon['description']}",
            'final_price': final_price.quantize(Decimal('0.01'))
        }
    
    @staticmethod
    def auto_apply_best_coupon(booking_price, nights=1, is_first_booking=False):
        """
        Auto-apply best available coupon for user.
        Tries coupons in order of best discount value.
        
        Returns: {applied coupon result with highest discount}
        """
        best_result = {
            'applied': False,
            'coupon_code': None,
            'discount_amount': Decimal('0'),
            'coupon_description': 'No coupon applied',
            'message': 'No applicable coupon',
            'final_price': Decimal(str(booking_price))
        }
        
        for coupon in CouponService.AVAILABLE_COUPONS:
            result = CouponService.apply_coupon(
                coupon['code'], booking_price, nights, is_first_booking
            )
            
            if result['applied'] and result['discount_amount'] > best_result['discount_amount']:
                best_result = result
        
        return best_result
    
    @staticmethod
    def get_available_coupons():
        """Get list of all currently available coupons with descriptions"""
        today = date.today()
        available = []
        
        for coupon in CouponService.AVAILABLE_COUPONS:
            if today >= coupon['valid_from'] and today <= coupon['valid_until']:
                available.append({
                    'code': coupon['code'],
                    'description': coupon['description'],
                    'discount': coupon.get('discount_percent') or coupon.get('discount_amount'),
                    'min_amount': coupon.get('min_amount', 0),
                })
        
        return available
    
    @staticmethod
    def format_coupon_display(coupon_result):
        """
        Format coupon application for display on checkout page.
        
        Returns string like "STAYSAVER: ₹500 off"
        """
        if not coupon_result['applied']:
            return None
        
        return f"{coupon_result['coupon_code']}: ₹{coupon_result['discount_amount']} off"
