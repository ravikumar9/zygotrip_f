"""
PHASE 3: Inventory Validation Service
Validates room availability across all OTA pages (listing, detail, booking, payment)
Returns 409 Conflict if inventory mismatch detected
"""
from datetime import datetime, date
from django.core.exceptions import ValidationError
from apps.rooms.models import RoomType, RoomInventory
import logging

logger = logging.getLogger(__name__)


class InventoryValidator:
    """Validates room inventory availability for stay dates"""
    
    @staticmethod
    def check_availability(room_type, checkin_date_str, checkout_date_str):
        """
        Check if room_type has at least occupancy_limit rooms available
        for entire stay period (checkin <= date < checkout)
        
        Args:
            room_type: RoomType instance
            checkin_date_str: YYYY-MM-DD format
            checkout_date_str: YYYY-MM-DD format
            
        Returns:
            {
                'available': bool,
                'min_available': int (minimum rooms across all days),
                'dates_checked': int (number of days checked),
                'sold_out_dates': [list of dates where 0 rooms],
                'message': str
            }
            
        Raises:
            ValidationError if dates invalid or room_type missing
        """
        if not room_type:
            raise ValidationError("Room type required for inventory check")
        
        try:
            checkin = datetime.strptime(checkin_date_str, '%Y-%m-%d').date()
            checkout = datetime.strptime(checkout_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid date format: {str(e)}")
        
        if checkout <= checkin:
            raise ValidationError("Checkout must be after checkin")
        
        # Check inventory for each day of stay
        inventory_records = RoomInventory.objects.filter(
            room_type=room_type,
            date__gte=checkin,
            date__lt=checkout
        ).order_by('date')
        
        result = {
            'available': True,
            'min_available': 0,
            'dates_checked': 0,
            'sold_out_dates': [],
            'message': 'Available'
        }
        
        if not inventory_records.exists():
            result['available'] = False
            result['message'] = 'No inventory records for selected dates'
            return result
        
        # Find minimum available across all days
        min_available = float('inf')
        for record in inventory_records:
            result['dates_checked'] += 1
            available = record.available
            
            if available == 0:
                result['sold_out_dates'].append(record.date.isoformat())
                result['available'] = False
            
            min_available = min(min_available, available)
        
        result['min_available'] = min_available if min_available != float('inf') else 0
        
        if result['sold_out_dates']:
            result['message'] = f"Sold out on: {', '.join(result['sold_out_dates'][:3])}"
        elif result['min_available'] == 0:
            result['available'] = False
            result['message'] = 'No rooms available'
        elif result['min_available'] == 1:
            result['message'] = f'Only 1 room left'
        else:
            result['message'] = f'{result["min_available"]} rooms available'
        
        return result
    
    @staticmethod
    def check_availability_strict(room_type, checkin_date_str, checkout_date_str, rooms_requested=1):
        """
        Strict check: user needs rooms_requested rooms for entire stay.
        Used at booking page to prevent overbooking.
        
        Returns tuple: (is_available: bool, min_available: int)
        """
        try:
            check_result = InventoryValidator.check_availability(
                room_type, checkin_date_str, checkout_date_str
            )
            
            is_available = check_result['min_available'] >= rooms_requested
            return is_available, check_result['min_available']
        
        except ValidationError as e:
            logger.error(f"Inventory check failed: {str(e)}")
            return False, 0
    
    @staticmethod
    def get_availability_badge(room_type, checkin_date_str, checkout_date_str):
        """
        Get human-readable badge for detail page (e.g., "2 left", "Sold Out")
        
        Returns: str (badge text)
        """
        try:
            check_result = InventoryValidator.check_availability(
                room_type, checkin_date_str, checkout_date_str
            )
            
            min_available = check_result['min_available']
            
            if min_available == 0:
                return "Sold Out"
            elif min_available == 1:
                return "1 Left"
            elif min_available <= 3:
                return f"{min_available} Left"
            else:
                return "Available"
        
        except Exception as e:
            logger.error(f"Badge generation failed: {str(e)}")
            return "Check Availability"
    
    @staticmethod
    def validate_booking_inventory(room_type_id, property_slug, checkin_date_str, 
                                   checkout_date_str, rooms_requested=1):
        """
        Final inventory check before creating booking (validation at booking creation).
        Called from booking view.
        
        Raises:
            ValidationError with 409-appropriate message if inventory unavailable
        """
        try:
            room_type = RoomType.objects.select_related('property').get(
                id=room_type_id,
                property__slug=property_slug
            )
        except RoomType.DoesNotExist:
            raise ValidationError("Room type not found")
        
        is_available, min_available = InventoryValidator.check_availability_strict(
            room_type, checkin_date_str, checkout_date_str, rooms_requested
        )
        
        if not is_available:
            error_msg = f"Only {min_available} room(s) available, but {rooms_requested} requested"
            # This should trigger 409 in view layer
            raise ValidationError(error_msg)
        
        return True
    
    @staticmethod
    def reserve_inventory(room_type_id, checkin_date_str, checkout_date_str, rooms_to_reserve=1):
        """
        PHASE 3: Reserve inventory by decrementing available count.
        Called when booking is CONFIRMED (after payment).
        
        Decrements available rooms for each day of stay by rooms_to_reserve.
        """
        try:
            checkin = datetime.strptime(checkin_date_str, '%Y-%m-%d').date()
            checkout = datetime.strptime(checkout_date_str, '%Y-%m-%d').date()
            
            # Update inventory for each day
            updated = RoomInventory.objects.filter(
                room_type_id=room_type_id,
                date__gte=checkin,
                date__lt=checkout
            ).update(available=models.F('available') - rooms_to_reserve)
            
            logger.info(f"Reserved {rooms_to_reserve} rooms for {updated} days")
            return updated > 0
        
        except Exception as e:
            logger.error(f"Inventory reservation failed: {str(e)}")
            return False
    
    @staticmethod
    def release_inventory(room_type_id, checkin_date_str, checkout_date_str, rooms_to_release=1):
        """
        PHASE 3: Release reserved inventory (when booking is cancelled).
        Increments available rooms for each day of stay.
        """
        try:
            from django.db import models
            checkin = datetime.strptime(checkin_date_str, '%Y-%m-%d').date()
            checkout = datetime.strptime(checkout_date_str, '%Y-%m-%d').date()
            
            updated = RoomInventory.objects.filter(
                room_type_id=room_type_id,
                date__gte=checkin,
                date__lt=checkout
            ).update(available=models.F('available') + rooms_to_release)
            
            logger.info(f"Released {rooms_to_release} rooms for {updated} days")
            return updated > 0
        
        except Exception as e:
            logger.error(f"Inventory release failed: {str(e)}")
            return False


# Add to imports when fixing the import issue above
from django.db import models
