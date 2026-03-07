"""
URL parameter validation and normalization for OTA listing/detail/booking pages.
Ensures all params are in canonical form (ISO dates, numeric values, etc).
PHASE 2: Date Engine Hardening - supports hourly stays (stay_type, times)
"""
from datetime import datetime, date, timedelta, time
from django.http import QueryDict
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class URLParamValidator:
    """Validates and normalizes URL parameters to canonical form"""
    
    # Canonical ordering for listing URL
    LISTING_PARAM_ORDER = [
        'location', 'checkin', 'checkout', 'rooms', 'adults', 'children',
        'min_price', 'max_price', 'star', 'rating', 'property_type',
        'sort', 'page'
    ]
    
    # Stay types: 'night' (traditional) or 'hourly' (new)
    VALID_STAY_TYPES = ['night', 'hourly']
    
    @staticmethod
    def validate_iso_date(date_str):
        """Validate date is in YYYY-MM-DD format and not in past"""
        if not date_str:
            return None
        try:
            parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
            return parsed.isoformat()
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
    
    @staticmethod
    def validate_time(time_str):
        """Validate time is in HH:MM format (24-hour)"""
        if not time_str:
            return None
        try:
            parsed = datetime.strptime(time_str, '%H:%M').time()
            return parsed.isoformat()
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid time format: {time_str}. Use HH:MM")
    
    @staticmethod
    def validate_dates_logic(checkin_str, checkout_str):
        """Validate checkin < checkout, both future, and checkout > checkin"""
        if not (checkin_str and checkout_str):
            return None, None
        
        try:
            checkin = datetime.strptime(checkin_str, '%Y-%m-%d').date()
            checkout = datetime.strptime(checkout_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            raise ValidationError("Invalid date format")
        
        today = date.today()
        
        # Allow same-day bookings (hourly stays)
        if checkin < today:
            raise ValidationError("Check-in cannot be in the past")
        
        # checkout must be >= checkin
        if checkout < checkin:
            raise ValidationError("Check-out must be on or after check-in")
        
        return checkin.isoformat(), checkout.isoformat()
    
    @staticmethod
    def validate_stay_type(stay_type):
        """PHASE 2: Validate stay_type is 'night' or 'hourly'"""
        if not stay_type:
            return 'night'  # Default to traditional night stay
        
        stay_type = str(stay_type).strip().lower()
        if stay_type not in URLParamValidator.VALID_STAY_TYPES:
            raise ValidationError(f"Invalid stay_type: {stay_type}. Must be 'night' or 'hourly'")
        
        return stay_type
    
    @staticmethod
    def validate_hourly_times(checkin_time_str, checkout_time_str, stay_type='night'):
        """PHASE 2: Validate times for hourly stays"""
        if stay_type != 'hourly':
            return None, None  # Not needed for night stays
        
        if not (checkin_time_str and checkout_time_str):
            # Default times for hourly: 12:00 to 13:00
            return '12:00', '13:00'
        
        checkin_time = URLParamValidator.validate_time(checkin_time_str)
        checkout_time = URLParamValidator.validate_time(checkout_time_str)
        
        # Validate checkout_time > checkin_time
        try:
            t_in = datetime.strptime(checkin_time, '%H:%M:%S').time()
            t_out = datetime.strptime(checkout_time, '%H:%M:%S').time()
            
            if t_out <= t_in:
                raise ValidationError("Checkout time must be after checkin time for hourly stays")
        except Exception as e:
            raise ValidationError(f"Invalid time values: {str(e)}")
        
        return checkin_time, checkout_time
    
    @staticmethod
    def validate_positive_int(value, min_val=0, max_val=None, field_name="Value"):
        """Validate integer is positive"""
        if not value:
            return None
        try:
            val = int(value)
            if val < min_val:
                raise ValidationError(f"{field_name} must be >= {min_val}")
            if max_val and val > max_val:
                raise ValidationError(f"{field_name} must be <= {max_val}")
            return val
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be an integer")
    
    @staticmethod
    def normalize_listing_params(request_get):
        """
        Normalize listing URL params to canonical form.
        Returns dict with validated/normalized values.
        """
        params = {}
        
        # Location (required for meaningful search)
        location = request_get.get('location', '').strip()
        if location:
            params['location'] = location
        
        # Dates (defaults to today/tomorrow if missing)
        checkin = request_get.get('checkin', '').strip()
        checkout = request_get.get('checkout', '').strip()
        
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        if not checkin:
            checkin = today
        if not checkout:
            checkout = tomorrow
        
        try:
            validated_checkin, validated_checkout = URLParamValidator.validate_dates_logic(checkin, checkout)
            params['checkin'] = validated_checkin
            params['checkout'] = validated_checkout
        except ValidationError as e:
            logger.warning(f"Date validation error: {e}")
            params['checkin'] = today
            params['checkout'] = tomorrow
        
        # Guests/Rooms
        try:
            rooms = URLParamValidator.validate_positive_int(
                request_get.get('rooms'), min_val=1, max_val=10, field_name="Rooms"
            ) or 1
            params['rooms'] = rooms
        except ValidationError:
            params['rooms'] = 1
        
        try:
            adults = URLParamValidator.validate_positive_int(
                request_get.get('adults'), min_val=1, max_val=10, field_name="Adults"
            ) or 1
            params['adults'] = adults
        except ValidationError:
            params['adults'] = 1
        
        try:
            children = URLParamValidator.validate_positive_int(
                request_get.get('children'), min_val=0, max_val=10, field_name="Children"
            ) or 0
            params['children'] = children
        except ValidationError:
            params['children'] = 0
        
        # Prices (optional filters)
        try:
            min_price = request_get.get('min_price', '').strip()
            if min_price:
                params['min_price'] = URLParamValidator.validate_positive_int(min_price)
        except ValidationError:
            pass
        
        try:
            max_price = request_get.get('max_price', '').strip()
            if max_price:
                params['max_price'] = URLParamValidator.validate_positive_int(max_price)
        except ValidationError:
            pass
        
        # Star rating (optional)
        try:
            star = request_get.get('star', '').strip()
            if star:
                params['star'] = URLParamValidator.validate_positive_int(
                    star, min_val=1, max_val=5, field_name="Star"
                )
        except ValidationError:
            pass
        
        # User rating (optional)
        try:
            rating = request_get.get('rating', '').strip()
            if rating:
                params['rating'] = float(rating)
                if params['rating'] < 0 or params['rating'] > 5:
                    del params['rating']
        except (ValueError, TypeError):
            pass
        
        # Property type (string filter)
        property_type = request_get.get('property_type', '').strip()
        if property_type:
            params['property_type'] = property_type
        
        # Sort (validated list)
        sort = request_get.get('sort', 'popular').lower().strip()
        valid_sorts = ['popular', 'price_asc', 'price_desc', 'rating', 'newest']
        params['sort'] = sort if sort in valid_sorts else 'popular'
        
        # Pagination (default 1)
        try:
            page = URLParamValidator.validate_positive_int(
                request_get.get('page', '1'), min_val=1, field_name="Page"
            ) or 1
            params['page'] = page
        except ValidationError:
            params['page'] = 1
        
        return params
    
    @staticmethod
    def normalize_detail_params(request_get):
        """
        Normalize detail page params (add checkin/checkout to URL).
        PHASE 2: Support hourly stays with stay_type, checkin_time, checkout_time
        If missing, redirect to list page with defaults.
        """
        params = {}
        
        # PHASE 2: Stay type (night or hourly)
        try:
            stay_type = URLParamValidator.validate_stay_type(request_get.get('stay_type', 'night'))
            params['stay_type'] = stay_type
        except ValidationError:
            stay_type = 'night'
            params['stay_type'] = stay_type
        
        # Dates are optional on detail, but if provided must be valid
        checkin = request_get.get('checkin', '').strip()
        checkout = request_get.get('checkout', '').strip()
        
        if checkin or checkout:
            today = date.today().isoformat()
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            
            if not checkin:
                checkin = today
            if not checkout:
                checkout = tomorrow
            
            try:
                validated_checkin, validated_checkout = URLParamValidator.validate_dates_logic(checkin, checkout)
                params['checkin'] = validated_checkin
                params['checkout'] = validated_checkout
            except ValidationError:
                pass
        
        # PHASE 2: Hourly stay times (if stay_type='hourly')
        if stay_type == 'hourly':
            try:
                checkin_time = request_get.get('checkin_time', '').strip()
                checkout_time = request_get.get('checkout_time', '').strip()
                
                t_in, t_out = URLParamValidator.validate_hourly_times(
                    checkin_time, checkout_time, 'hourly'
                )
                params['checkin_time'] = t_in
                params['checkout_time'] = t_out
            except ValidationError as e:
                logger.warning(f"Invalid hourly times: {str(e)}")
                params['checkin_time'] = '12:00'
                params['checkout_time'] = '13:00'
        
        # Guests for detail page
        try:
            adults = URLParamValidator.validate_positive_int(
                request_get.get('adults'), min_val=1, max_val=10, field_name="Adults"
            ) or 1
            params['adults'] = adults
        except ValidationError:
            params['adults'] = 1
        
        try:
            children = URLParamValidator.validate_positive_int(
                request_get.get('children'), min_val=0, max_val=10, field_name="Children"
            ) or 0
            params['children'] = children
        except ValidationError:
            params['children'] = 0
        
        try:
            rooms = URLParamValidator.validate_positive_int(
                request_get.get('rooms'), min_val=1, max_val=10, field_name="Rooms"
            ) or 1
            params['rooms'] = rooms
        except ValidationError:
            params['rooms'] = 1
        
        return params
    
    @staticmethod
    def normalize_booking_params(request_get, slug):
        """
        Normalize booking page params.
        Must have: slug, room_type, checkin, checkout, rooms, adults
        PHASE 2: Support hourly stays with stay_type and times
        """
        params = {'slug': slug}
        
        # PHASE 2: Stay type (night or hourly)
        try:
            stay_type = URLParamValidator.validate_stay_type(request_get.get('stay_type', 'night'))
            params['stay_type'] = stay_type
        except ValidationError:
            stay_type = 'night'
            params['stay_type'] = stay_type
        
        # Room type ID (required)
        try:
            room_type_id = URLParamValidator.validate_positive_int(
                request_get.get('room_type'), min_val=1, field_name="Room Type"
            )
            if room_type_id:
                params['room_type'] = room_type_id
            else:
                raise ValidationError("Room type is required")
        except ValidationError as e:
            raise ValidationError(f"Invalid room_type: {e}")
        
        # Dates (required)
        checkin = request_get.get('checkin', '').strip()
        checkout = request_get.get('checkout', '').strip()
        
        if not (checkin and checkout):
            raise ValidationError("Check-in and check-out dates are required")
        
        try:
            validated_checkin, validated_checkout = URLParamValidator.validate_dates_logic(checkin, checkout)
            params['checkin'] = validated_checkin
            params['checkout'] = validated_checkout
        except ValidationError as e:
            raise ValidationError(f"Invalid dates: {e}")
        
        # PHASE 2: Hourly stay times (if stay_type='hourly')
        if stay_type == 'hourly':
            try:
                checkin_time = request_get.get('checkin_time', '').strip()
                checkout_time = request_get.get('checkout_time', '').strip()
                
                t_in, t_out = URLParamValidator.validate_hourly_times(
                    checkin_time, checkout_time, 'hourly'
                )
                params['checkin_time'] = t_in
                params['checkout_time'] = t_out
            except ValidationError as e:
                logger.warning(f"Invalid hourly times: {str(e)}")
                params['checkin_time'] = '12:00'
                params['checkout_time'] = '13:00'
        
        # Guests (required)
        try:
            adults = URLParamValidator.validate_positive_int(
                request_get.get('adults'), min_val=1, max_val=10, field_name="Adults"
            )
            if adults:
                params['adults'] = adults
            else:
                raise ValidationError("Adults count is required")
        except ValidationError as e:
            raise ValidationError(f"Invalid adults: {e}")
        
        try:
            rooms = URLParamValidator.validate_positive_int(
                request_get.get('rooms'), min_val=1, max_val=10, field_name="Rooms"
            )
            if rooms:
                params['rooms'] = rooms
            else:
                raise ValidationError("Rooms count is required")
        except ValidationError as e:
            raise ValidationError(f"Invalid rooms: {e}")
        
        # Optional children
        try:
            children = URLParamValidator.validate_positive_int(
                request_get.get('children', '0'), min_val=0, max_val=10, field_name="Children"
            ) or 0
            params['children'] = children
        except ValidationError:
            params['children'] = 0
        
        return params
