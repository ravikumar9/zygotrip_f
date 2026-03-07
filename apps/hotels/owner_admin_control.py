"""
PHASE 5: Owner + Admin Control
- Owner controls: base room price, room amenities, room photos, cancellation, inventory
- Admin controls: platform fee, service fee, GST rules, global offers, featured tag
- Frontend displays only serialized values (read-only to regular users)
"""
from django.core.exceptions import PermissionDenied
from apps.accounts.selectors import user_has_role
import logging

logger = logging.getLogger(__name__)


class OwnerAdminControl:
    """Permission and control enforcement layer"""
    
    # Owner-controllable fields (property/room level)
    OWNER_FIELDS = {
        'base_price': 'Room base price',
        'room_amenities': 'Room-specific amenities',
        'room_photos': 'Room photos',
        'occupancy_limit': 'Room occupancy limit',
        'bed_type': 'Bed type',
        'bathroom_type': 'Bathroom type',
        'cancellation_type': 'Cancellation policy',
        'inventory': 'Room inventory',
        'discount_percent': 'Property-level discount',
    }
    
    # Admin-controllable fields (global/system level)
    ADMIN_FIELDS = {
        'platform_fee_percent': 'Platform fee percentage',
        'service_fee_percent': 'Service fee percentage',
        'gst_percent': 'GST percentage',
        'featured': 'Featured property status',
    }
    
    @staticmethod
    def check_owner_permission(user, property_obj, field_name=None):
        """
        Check if user is owner of property and can modify owner_fields.
        
        Args:
            user: User instance
            property_obj: Property instance
            field_name: Optional field to check (validates owner can modify this field)
            
        Returns: bool
        Raises: PermissionDenied if not owner
        """
        # Owner must be authenticated
        if not user or not user.is_authenticated:
            raise PermissionDenied("Must be logged in to modify property")
        
        # Owner must have 'property_owner' role
        if not user_has_role(user, 'property_owner'):
            raise PermissionDenied("Only property owners can modify this")
        
        # Owner must own the specific property
        if property_obj.owner_id != user.id:
            raise PermissionDenied("You don't own this property")
        
        # If field specified, ensure it's owner-controllable
        if field_name and field_name not in OwnerAdminControl.OWNER_FIELDS:
            raise PermissionDenied(f"Field '{field_name}' cannot be modified by owner")
        
        return True
    
    @staticmethod
    def check_admin_permission(user, field_name=None):
        """
        Check if user is admin and can modify admin_fields.
        
        Args:
            user: User instance
            field_name: Optional field to check
            
        Returns: bool
        Raises: PermissionDenied if not admin
        """
        # Admin must be authenticated
        if not user or not user.is_authenticated:
            raise PermissionDenied("Must be logged in to modify system settings")
        
        # Admin must have 'admin' role
        if not user_has_role(user, 'admin'):
            raise PermissionDenied("Only admins can modify system settings")
        
        # If field specified, ensure it's admin-controllable
        if field_name and field_name not in OwnerAdminControl.ADMIN_FIELDS:
            raise PermissionDenied(f"Field '{field_name}' cannot be modified by admin")
        
        return True
    
    @staticmethod
    def serialize_for_customer_view(property_obj, room_type=None):
        """
        Serialize property/room data for customer view.
        Only includes: price, amenities, ratings, photos, availability.
        Hides: internal costs, fee percentages, owner details.
        
        Returns: dict with customer-visible fields only
        """
        return {
            'id': property_obj.id,
            'slug': property_obj.slug,
            'name': property_obj.name,
            'location': property_obj.location,
            'rating': property_obj.rating,
            'review_count': property_obj.review_count,
            'star_category': property_obj.star_category,
            # Room data (if provided)
            'room_price': room_type.base_price if room_type else None,
            'room_amenities': list(
                room_type.roomamenity_set.values_list('name', flat=True)
            ) if room_type else [],
            'room_images': list(
                room_type.roomimage_set.values_list('image_url', flat=True)
            ) if room_type else [],
            # HIDDEN from customers:
            # - owner details
            # - cost breakdowns
            # - fee percentages
            # - inventory numbers
            # - admin controls
        }
    
    @staticmethod
    def serialize_for_owner_view(property_obj):
        """
        Serialize for owner dashboard.
        Includes: prices, amenities, photos, inventory, discount settings.
        Excludes: admin-level settings (platform fee, GST, featured status).
        """
        return {
            'id': property_obj.id,
            'slug': property_obj.slug,
            'name': property_obj.name,
            'owner_id': property_obj.owner_id,
            'location': property_obj.location,
            'rating': property_obj.rating,
            
            # Owner can see and modify:
            'base_price': None,  # Should aggregate from rooms
            'discount_percent': property_obj.discount_percent if hasattr(property_obj, 'discount_percent') else 0,
            'inventory_summary': {},  # Should fetch from RoomInventory
            'room_types': [
                {
                    'id': rt.id,
                    'name': rt.name,
                    'base_price': rt.base_price,
                    'occupancy': rt.occupancy,
                    'amenities': list(rt.roomamenity_set.values_list('name', flat=True)),
                    'images': list(rt.roomimage_set.values_list('image_url', flat=True)),
                }
                # Loop over property.roomtype_set.all()
            ],
            
            # HIDDEN from owner:
            # - platform fee percent
            # - service fee percent
            # - GST percent
            # - featured status
            # - admin overrides
        }
    
    @staticmethod
    def serialize_for_admin_view(property_obj):
        """
        Serialize for admin dashboard.
        Includes: all fields, cost structures, feepercent ages, overrides.
        """
        return {
            'id': property_obj.id,
            'slug': property_obj.slug,
            'name': property_obj.name,
            'owner_id': property_obj.owner_id,
            'status': property_obj.status,
            'agreement_signed': property_obj.agreement_signed,
            'featured': getattr(property_obj, 'featured', False),
            
            # Admin can see and modify global settings:
            'platform_fee_percent': 5.0,  # Should come from PlatformSettings model
            'service_fee_percent': 10.0,  # Should come from PlatformSettings model
            'gst_percent': 18.0,  # Should come from PlatformSettings model
            
            # Admin can see owner-level data (for auditing):
            'owner_discount_percent': property_obj.discount_percent if hasattr(property_obj, 'discount_percent') else 0,
            'room_prices': {},  # Aggregate
            
            # Admin visibility:
            'total_bookings': 0,  # Count from Booking model
            'total_revenue': 0,  # Sum from Booking model
        }
    
    @staticmethod
    def validate_price_modification(user, property_obj, new_price):
        """
        Validate that only owner can change base price (not admin with override).
        This enforces the business rule: "Admin cannot override room prices".
        """
        OwnerAdminControl.check_owner_permission(user, property_obj, 'base_price')
        
        # Validate new_price is reasonable
        if new_price <= 0:
            raise ValueError("Price must be > 0")
        
        return True
    
    @staticmethod
    def validate_inventory_modification(user, property_obj, room_type):
        """
        Only property owner can modify inventory for their rooms.
        """
        OwnerAdminControl.check_owner_permission(user, property_obj, 'inventory')
        
        # Verify room belongs to property
        if room_type.property_id != property_obj.id:
            raise PermissionDenied("Room doesn't belong to this property")
        
        return True
