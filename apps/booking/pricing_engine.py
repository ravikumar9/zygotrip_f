"""
Pricing Engine for structured price breakdowns
Manages all price calculations in one place (not in templates)
"""
from decimal import Decimal
from django.utils import timezone


class PricingEngine:
    """
    Centralized pricing calculations for bookings
    
    Ensures no template arithmetic, all pricing logic in one place
    
    Example output:
    {
        'base_price_per_night': 5000,
        'nights': 2,
        'base_total': 10000,
        'property_discount_amount': 1000,
        'property_discount_percent': 10,
        'after_property_discount': 9000,
        'platform_discount_amount': 900,
        'platform_discount_percent': 10,
        'after_platform_discount': 8100,
        'coupon_discount_amount': 500,
        'coupon_discount_percent': None,
        'subtotal_after_discounts': 7600,
        'gst_percent': 5,
        'gst_amount': 380,
        'total_price': 7980,
    }
    """
    
    def __init__(self, base_price_per_night, nights, room_count=1):
        """
        Args:
            base_price_per_night: Decimal or int (price from RoomType or RoomInventory)
            nights: int (checkout_date - checkin_date).days
            room_count: int (number of rooms booked)
        """
        self.base_price_per_night = Decimal(str(base_price_per_night))
        self.nights = int(nights)
        self.room_count = int(room_count)
        self.base_total = self.base_price_per_night * self.nights * self.room_count
        
        # Initialize breakdown dict
        self.breakdown = {
            'base_price_per_night': float(self.base_price_per_night),
            'nights': self.nights,
            'room_count': self.room_count,
            'base_total': float(self.base_total),
        }
    
    def apply_property_discount(self, percent=None, amount=None):
        """Apply property-level discount (e.g., early booking, loyalty)"""
        discount_amount = Decimal('0')
        discount_percent = Decimal('0')
        
        if percent:
            discount_percent = Decimal(str(percent))
            discount_amount = (self.base_total * discount_percent) / 100
        elif amount:
            discount_amount = Decimal(str(amount))
            discount_percent = (discount_amount / self.base_total * 100) if self.base_total else Decimal('0')
        
        self.breakdown['property_discount_amount'] = float(discount_amount)
        self.breakdown['property_discount_percent'] = float(discount_percent)
        self.base_total -= discount_amount
        self.breakdown['after_property_discount'] = float(self.base_total)
        return self
    
    def apply_platform_discount(self, percent=None, amount=None):
        """Apply platform-level discount (day sale, promotion)"""
        discount_amount = Decimal('0')
        discount_percent = Decimal('0')
        
        if percent:
            discount_percent = Decimal(str(percent))
            discount_amount = (self.base_total * discount_percent) / 100
        elif amount:
            discount_amount = Decimal(str(amount))
            discount_percent = (discount_amount / self.base_total * 100) if self.base_total else Decimal('0')
        
        self.breakdown['platform_discount_amount'] = float(discount_amount)
        self.breakdown['platform_discount_percent'] = float(discount_percent)
        self.base_total -= discount_amount
        self.breakdown['after_platform_discount'] = float(self.base_total)
        return self
    
    def apply_coupon(self, coupon_code, percent=None, amount=None):
        """Apply coupon discount"""
        discount_amount = Decimal('0')
        discount_percent = None
        
        if percent:
            discount_percent = Decimal(str(percent))
            discount_amount = (self.base_total * discount_percent) / 100
        elif amount:
            discount_amount = Decimal(str(amount))
        
        self.breakdown['coupon_code'] = coupon_code
        self.breakdown['coupon_discount_amount'] = float(discount_amount)
        self.breakdown['coupon_discount_percent'] = float(discount_percent) if discount_percent else None
        self.base_total -= discount_amount
        self.breakdown['after_coupon'] = float(self.base_total)
        return self
    
    def apply_gst(self, percent=5):
        """Apply GST/tax on the discounted amount"""
        gst_percent = Decimal(str(percent))
        gst_amount = (self.base_total * gst_percent) / 100
        
        self.breakdown['gst_percent'] = float(gst_percent)
        self.breakdown['gst_amount'] = float(gst_amount)
        
        total_price = self.base_total + gst_amount
        self.breakdown['total_price'] = float(total_price)
        self.breakdown['subtotal_before_gst'] = float(self.base_total)
        return self
    
    def add_service_fee(self, amount):
        """Add service/convenience fee"""
        fee = Decimal(str(amount))
        self.breakdown['service_fee'] = float(fee)
        
        # Service fee is typically added after GST
        current_total = self.breakdown.get('total_price', float(self.base_total))
        self.breakdown['total_price'] = current_total + float(fee)
        return self
    
    def finalize(self):
        """Ensure total_price is set if GST wasn't applied"""
        if 'total_price' not in self.breakdown:
            self.breakdown['total_price'] = float(self.base_total)
        return self.breakdown
    
    def get_summary_line(self):
        """Get simple summary for display (e.g., "₹7,980 for 2 nights")"""
        total = self.breakdown.get('total_price', float(self.base_total))
        return f"₹{total:,.0f} for {self.nights} nights"
    
    def get_display_format(self):
        """Get breakdown formatted for UI display"""
        breakdown = self.breakdown.copy()
        # Round all rupees to nearest integer
        for key in breakdown:
            if key not in ['nights', 'room_count', 'gst_percent', 'coupon_discount_percent', 'property_discount_percent', 'platform_discount_percent', 'coupon_code']:
                if isinstance(breakdown[key], float):
                    breakdown[key] = int(round(breakdown[key]))
        return breakdown
