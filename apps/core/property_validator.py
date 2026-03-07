"""
Data validation for property owners before allowing publish.
Ensures all required data is present before hotel goes live.
"""
from django.core.exceptions import ValidationError


class PropertyDataValidator:
    """
    Validates that property owner has supplied all required data
    before property can be published to marketplace.
    """
    
    REQUIRED_FIELDS = {
        'hotel_images': 'At least 3 hotel images required',
        'room_images': 'At least 2 room images per room type required',
        'base_price': 'Base price must be set',
        'amenities': 'At least 3 amenities must be specified',
        'meal_plans': 'At least 1 meal plan required',
    }
    
    @classmethod
    def validate_hotel_for_publish(cls, hotel):
        """
        Validates hotel data before publish.
        Raises ValidationError with specific missing fields.
        
        Args:
            hotel: Hotel model instance
            
        Returns:
            dict: Validation result with status and errors
        """
        errors = []
        
        # Check hotel images
        image_count = hotel.images.filter(is_active=True).count()
        if image_count < 3:
            errors.append({
                'field': 'hotel_images',
                'message': cls.REQUIRED_FIELDS['hotel_images'],
                'current': f'{image_count} images',
                'required': '3 images'
            })
        
        # Check room images - iterate through all active rooms
        for room in hotel.rooms.filter(is_active=True):
            room_image_count = room.images.filter(is_active=True).count()
            if room_image_count < 2:
                errors.append({
                    'field': 'room_images',
                    'message': f'Room "{room.name}" needs at least 2 images',
                    'current': f'{room_image_count} images',
                    'required': '2 images per room'
                })
        
        # Check base price
        if not hotel.base_price or hotel.base_price <= 0:
            errors.append({
                'field': 'base_price',
                'message': cls.REQUIRED_FIELDS['base_price'],
                'current': str(hotel.base_price) if hotel.base_price else 'Not set',
                'required': 'Positive price value'
            })
        
        # Check amenities
        amenity_count = hotel.amenities.count()
        if amenity_count < 3:
            errors.append({
                'field': 'amenities',
                'message': cls.REQUIRED_FIELDS['amenities'],
                'current': f'{amenity_count} amenities',
                'required': '3 amenities'
            })
        
        # Check meal plans
        meal_count = hotel.meal_options.filter(is_active=True).count()
        if meal_count < 1:
            errors.append({
                'field': 'meal_plans',
                'message': cls.REQUIRED_FIELDS['meal_plans'],
                'current': f'{meal_count} meal plans',
                'required': '1 meal plan'
            })
        
        # Check discount (optional but must be valid if provided)
        if hotel.discount_percentage and (hotel.discount_percentage < 0 or hotel.discount_percentage > 100):
            errors.append({
                'field': 'discount',
                'message': 'Discount must be between 0-100%',
                'current': f'{hotel.discount_percentage}%',
                'required': '0-100%'
            })
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'error_count': len(errors)
        }
    
    @classmethod
    def get_completion_percentage(cls, hotel):
        """
        Calculate data completion percentage for property.
        
        Returns:
            int: Completion percentage (0-100)
        """
        checks = {
            'images': hotel.images.filter(is_active=True).count() >= 3,
            'rooms': hotel.rooms.filter(is_active=True).count() > 0,
            'price': hotel.base_price and hotel.base_price > 0,
            'amenities': hotel.amenities.count() >= 3,
            'meals': hotel.meal_options.filter(is_active=True).count() > 0,
            'description': bool(hotel.description and len(hotel.description) > 50),
            'location': bool(hotel.address and hotel.city),
            'contact': bool(hotel.phone_number or hotel.email),
        }
        
        completed = sum(1 for check in checks.values() if check)
        total = len(checks)
        
        return int((completed / total) * 100)