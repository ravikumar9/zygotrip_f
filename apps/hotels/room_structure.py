"""
PHASE 6: Room-Specific Structure Enforcement
Ensures room objects have required fields and displays room-specific data on cards.
DO NOT show property-level amenities on room card.
"""
from datetime import date as _today
from apps.rooms.models import RoomType, RoomAmenity, RoomInventory
import logging

logger = logging.getLogger(__name__)


class RoomStructureValidator:
    """Validates and enforces room-specific structure"""
    
    # Required fields for complete room record
    REQUIRED_FIELDS = {
        'name': 'Room name/type',
        'base_price': 'Base price',
        'occupancy_limit': 'Occupancy limit',
        'bed_type': 'Bed type (single, double, dorm, etc)',
        'bathroom_type': 'Bathroom type (private, shared, ensuite)',
    }
    
    # Recommended fields
    RECOMMENDED_FIELDS = {
        'cancellation_type': 'Cancellation policy (free, partial, non-refundable)',
        'room_specific_images': 'Room photos',
        'room_specific_amenities': 'Room amenities (separate from property)',
    }
    
    @staticmethod
    def validate_room_completeness(room_type):
        """
        Check if room has all required fields.
        Returns: {complete: bool, missing_fields: []}
        """
        missing = []
        
        for field, description in RoomStructureValidator.REQUIRED_FIELDS.items():
            if not getattr(room_type, field, None):
                missing.append({
                    'field': field,
                    'description': description,
                    'current_value': getattr(room_type, field, None)
                })
        
        return {
            'complete': len(missing) == 0,
            'missing_fields': missing,
            'field_count': len(RoomStructureValidator.REQUIRED_FIELDS),
            'populated_count': len(RoomStructureValidator.REQUIRED_FIELDS) - len(missing),
        }
    
    @staticmethod
    def get_room_display_data(room_type, include_images=True, include_amenities=True):
        """
        Get complete room data for display on room cards.
        CRITICAL: Returns only ROOM-SPECIFIC data, NOT property-level.
        
        Returns:
            {
                'id': int,
                'name': str,
                'base_price': decimal,
                'occupancy_limit': int,
                'bed_type': str,
                'bathroom_type': str,
                'cancellation_type': str,
                'amenities': [...],  # ROOM-specific only!
                'images': [...],  # ROOM-specific only!
            }
        """
        data = {
            'id': room_type.id,
            'name': room_type.name or f"Room #{room_type.id}",
            'base_price': str(room_type.base_price),
            'occupancy_limit': room_type.occupancy or room_type.occupancy_limit if hasattr(room_type, 'occupancy_limit') else 2,
            'bed_type': getattr(room_type, 'bed_type', 'Not specified'),
            'bathroom_type': getattr(room_type, 'bathroom_type', 'Not specified'),
            'cancellation_type': getattr(room_type, 'cancellation_type', 'Non-refundable'),
        }
        
        # ROOM-SPECIFIC amenities only!
        if include_amenities:
            try:
                room_amenities = RoomAmenity.objects.filter(
                    room_type=room_type
                ).values_list('name', flat=True)
                data['amenities'] = list(room_amenities)
            except Exception as e:
                logger.warning(f"Failed to load room amenities: {str(e)}")
                data['amenities'] = []
        
        # ROOM-SPECIFIC images only!
        if include_images:
            try:
                room_images = room_type.roomimage_set.all().values_list(
                    'image_url', flat=True
                )
                data['images'] = list(room_images)
            except Exception as e:
                logger.warning(f"Failed to load room images: {str(e)}")
                data['images'] = []
        
        return data
    
    @staticmethod
    def get_all_rooms_for_property(property_obj, with_inventory=False):
        """
        Get all rooms for a property, properly structured.
        Each room card shows ONLY room-specific data.
        
        Returns: [{room_data}, ...]
        """
        rooms = []
        
        try:
            room_types = RoomType.objects.filter(
                property=property_obj
            ).prefetch_related(
                'roomamenity_set',
                'roomimage_set'
            )
            
            for room_type in room_types:
                room_data = RoomStructureValidator.get_room_display_data(room_type)
                
                # Add availability if requested — queries RoomInventory for today
                if with_inventory:
                    try:
                        inv = RoomInventory.objects.get(
                            room_type=room_type, date=_today.today()
                        )
                        if inv.is_closed or inv.available_rooms <= 0:
                            room_data['availability'] = 'Unavailable'
                        else:
                            room_data['availability'] = f'{inv.available_rooms} rooms left'
                    except RoomInventory.DoesNotExist:
                        # No inventory record for today — fall back to RoomType.available_count
                        count = room_type.available_count
                        room_data['availability'] = (
                            f'{count} rooms left' if count > 0 else 'Unavailable'
                        )
                
                rooms.append(room_data)
        
        except Exception as e:
            logger.error(f"Failed to load rooms for property: {str(e)}")
        
        return rooms
    
    @staticmethod
    def ensure_room_specific_context(context):
        """
        Validation filter: Ensures context doesn't mix property-level and room-level data.
        
        If template is showing room card, check:
        - Are property_amenities in context? (BAD - these should NOT be on room card)
        - Are room_amenities in context? (GOOD)
        - Is property_photo in context? (maybe OK if fallback)
        - Is room_photo in context? (GOOD - preferred)
        """
        issues = []
        
        # Check for contamination
        if 'property_amenities' in context and context.get('property_amenities'):
            issues.append({
                'severity': 'warning',
                'message': 'Property-level amenities found in room context. Should use room_amenities instead.'
            })
        
        if 'room_amenities' not in context or not context.get('room_amenities'):
            issues.append({
                'severity': 'warning',
                'message': 'Room-amenities missing. Room card should show room-specific amenities.'
            })
        
        if 'room_images' not in context or not context.get('room_images'):
            issues.append({
                'severity': 'info',
                'message': 'No room-specific images. Falling back to property image if available.'
            })
        
        return {
            'valid': len([i for i in issues if i['severity'] == 'error']) == 0,
            'issues': issues,
        }
