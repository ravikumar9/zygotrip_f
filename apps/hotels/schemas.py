"""
Data validation schemas for hotels domain
PHASE 2: Domain standardization
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date


def validate_property_data(data):
    """Validate property creation/update data"""
    errors = {}
    
    # Required fields
    if not data.get('name'):
        errors['name'] = 'Property name is required'
    
    if not data.get('city'):
        errors['city'] = 'City is required'
    
    # Rating range
    rating = data.get('rating')
    if rating is not None:
        if not (0 <= rating <= 5):
            errors['rating'] = 'Rating must be between 0 and 5'
    
    # Coordinates validation
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if latitude is not None:
        if not (-90 <= latitude <= 90):
            errors['latitude'] = 'Latitude must be between -90 and 90'
    
    if longitude is not None:
        if not (-180 <= longitude <= 180):
            errors['longitude'] = 'Longitude must be between -180 and 180'
    
    if errors:
        raise ValidationError(errors)
    
    return data


def validate_room_search(data):
    """Validate room search parameters"""
    errors = {}
    
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    
    if check_in and check_out:
        if check_in >= check_out:
            errors['check_out'] = 'Check-out must be after check-in'
        
        if check_in < date.today():
            errors['check_in'] = 'Check-in date cannot be in the past'
    
    guests = data.get('guests')
    if guests and guests < 1:
        errors['guests'] = 'Must have at least 1 guest'
    
    if errors:
        raise ValidationError(errors)
    
    return data


def validate_booking_dates(check_in, check_out):
    """Validate booking date range"""
    today = timezone.now().date()
    
    if check_in < today:
        raise ValidationError('Check-in date cannot be in the past')
    
    if check_out <= check_in:
        raise ValidationError('Check-out must be after check-in')
    
    # Maximum stay: 30 days
    if (check_out - check_in).days > 30:
        raise ValidationError('Maximum stay is 30 days')
    
    return True