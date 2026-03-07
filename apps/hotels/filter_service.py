"""
PHASE 9: Filter Parity with Goibibo
Dynamic filter counts calculated from actual hotel listings and inventory.
Mandatory filters: Star, Rating, Price buckets, Property type, Room amenities, 
House rules, Chains, Payment modes, Entire property, Free cancellation, Breakfast
"""
from django.db.models import Count, Q, Min, Max, F
from apps.hotels.models import Property
from apps.rooms.models import RoomType, RoomAmenity
import logging

logger = logging.getLogger(__name__)


class FilterService:
    """Provides dynamic filter options with counts"""
    
    PRICE_BUCKETS = [
        {'min': 0, 'max': 1000, 'label': 'Under ₹1,000'},
        {'min': 1000, 'max': 2500, 'label': '₹1,000 - ₹2,500'},
        {'min': 2500, 'max': 5000, 'label': '₹2,500 - ₹5,000'},
        {'min': 5000, 'max': 10000, 'label': '₹5,000 - ₹10,000'},
        {'min': 10000, 'max': float('inf'), 'label': '₹10,000+'},
    ]
    
    PROPERTY_TYPES = [
        'Hotel', 'Resort', 'Homestay', 'Guest House', 'Hostel', 'Villa', 'Cottage'
    ]
    
    ROOM_AMENITIES = [
        'WiFi', 'AC', 'TV', 'Parking', 'Bathroom', 'Kitchen', 'Balcony', 'Safe',
        'Food Delivery', 'Pet Friendly', 'Gym', 'Pool'
    ]
    
    @staticmethod
    def get_all_filters(queryset=None, checkin=None, checkout=None):
        """
        Get all available filters with dynamic counts.
        
        Returns:
            {
                'star_ratings': [{'stars': int, 'count': int}, ...],
                'user_ratings': [{'rating': str, 'count': int}, ...],
                'price_buckets': [{'min': int, 'max': int, 'label': str, 'count': int}, ...],
                'property_types': [{'type': str, 'count': int}, ...],
                'amenities': [{'name': str, 'count': int}, ...],
                'payment_modes': [{'mode': str, 'count': int}, ...],
                'features': [
                    {'name': 'Free Cancellation', 'count': int},
                    {'name': 'Breakfast Included', 'count': int},
                    {'name': 'Entire Property', 'count': int},
                ]
            }
        """
        if queryset is None:
            queryset = Property.objects.filter(status='approved', agreement_signed=True)
        
        return {
            'star_ratings': FilterService._get_star_filters(queryset),
            'user_ratings': FilterService._get_rating_filters(queryset),
            'price_buckets': FilterService._get_price_filters(queryset, checkin, checkout),
            'property_types': FilterService._get_property_type_filters(queryset),
            'amenities': FilterService._get_amenity_filters(queryset),
            'payment_modes': FilterService._get_payment_mode_filters(queryset),
            'features': FilterService._get_feature_filters(queryset),
        }
    
    @staticmethod
    def _get_star_filters(queryset):
        """Star category counts (1-5)"""
        stars = []
        for star in range(5, 0, -1):
            count = queryset.filter(star_category=star).count()
            if count > 0:
                stars.append({
                    'stars': star,
                    'label': f"{star}★ Hotels",
                    'count': count,
                })
        return stars
    
    @staticmethod
    def _get_rating_filters(queryset):
        """User rating thresholds (4.5+, 4.0+, 3.0+)"""
        ratings = [
            {'threshold': 4.5, 'label': '4.5+ Rating'},
            {'threshold': 4.0, 'label': '4.0+ Rating'},
            {'threshold': 3.0, 'label': '3.0+ Rating'},
        ]
        
        result = []
        for rating_filter in ratings:
            count = queryset.filter(rating__gte=rating_filter['threshold']).count()
            if count > 0:
                result.append({
                    'rating': rating_filter['label'],
                    'threshold': rating_filter['threshold'],
                    'count': count,
                })
        
        return result
    
    @staticmethod
    def _get_price_filters(queryset, checkin=None, checkout=None):
        """Price bucket counts based on room base_price"""
        result = []
        
        for bucket in FilterService.PRICE_BUCKETS:
            count = queryset.filter(
                roomtype__base_price__gte=bucket['min'],
                roomtype__base_price__lt=bucket['max']
            ).distinct().count()
            
            if count > 0:
                result.append({
                    'min': bucket['min'],
                    'max': bucket['max'],
                    'label': bucket['label'],
                    'count': count,
                })
        
        return result
    
    @staticmethod
    def _get_property_type_filters(queryset):
        """Property type counts"""
        result = []
        
        for prop_type in FilterService.PROPERTY_TYPES:
            count = queryset.filter(property_type__icontains=prop_type).count()
            if count > 0:
                result.append({
                    'type': prop_type,
                    'count': count,
                })
        
        return result
    
    @staticmethod
    def _get_amenity_filters(queryset):
        """Room amenity counts (room-specific, not property)"""
        result = []
        
        # Get properties in queryset
        prop_ids = queryset.values_list('id', flat=True)
        
        # Count each amenity across room_type's of those properties
        for amenity_name in FilterService.ROOM_AMENITIES:
            count = RoomAmenity.objects.filter(
                name__icontains=amenity_name,
                room_type__property_id__in=prop_ids
            ).values('room_type_id').distinct().count()
            
            if count > 0:
                result.append({
                    'name': amenity_name,
                    'count': count,
                })
        
        return result
    
    @staticmethod
    def _get_payment_mode_filters(queryset):
        """Payment modes – derived from the Property model's pay_at_property flag.

        Returns only modes that have at least one matching property in the queryset.
        """
        result = []
        # Pay at hotel: properties that allow offline payment
        pay_at_property_count = queryset.filter(pay_at_hotel=True).count()
        if pay_at_property_count > 0:
            result.append({'mode': 'Pay at Property', 'count': pay_at_property_count})
        # Card / UPI: all OTA bookings support online payment
        online_count = queryset.count()
        if online_count > 0:
            result.append({'mode': 'Card Payment', 'count': online_count})
            result.append({'mode': 'UPI/Wallet', 'count': online_count})
        return result
    
    @staticmethod
    def _get_feature_filters(queryset):
        """Special features (cancellation, breakfast, etc)"""
        return [
            {
                'name': 'Free Cancellation',
                'count': queryset.filter(
                    roomtype__cancellation_type__icontains='free'
                ).distinct().count()
            },
            {
                'name': 'Breakfast Included',
                'count': queryset.filter(
                    roomtype__roomamenity__name__icontains='breakfast'
                ).distinct().count()
            },
            {
                'name': 'Entire Property',
                'count': queryset.filter(property_type__icontains='villa').count()
            },
        ]
