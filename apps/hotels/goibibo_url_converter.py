"""
Goibibo-style URL parameter conversion
Converts between YYYYMMDD dates and ISO format dates
Uses query parameters for property IDs instead of slugs
"""
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs


class GoibiboURLConverter:
    """Convert between Goibibo-style and ISO-format URLs"""
    
    @staticmethod
    def iso_to_goibibo_date(iso_date_str):
        """Convert ISO date (2026-02-26) to Goibibo format (20260226)"""
        if not iso_date_str:
            return None
        try:
            dt = datetime.strptime(iso_date_str, '%Y-%m-%d')
            return dt.strftime('%Y%m%d')
        except (ValueError, TypeError):
            return iso_date_str

    @staticmethod
    def goibibo_to_iso_date(goibibo_date_str):
        """Convert Goibibo format (20260226) to ISO date (2026-02-26)"""
        if not goibibo_date_str:
            return None
        try:
            dt = datetime.strptime(str(goibibo_date_str), '%Y%m%d')
            return dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return goibibo_date_str

    @staticmethod
    def build_goibibo_url(property_id, checkin_iso, checkout_iso, **kwargs):
        """
        Build Goibibo-style URL
        
        Format: /hotels/search/?id=<property_id>&checkin=<YYYYMMDD>&checkout=<YYYYMMDD>&rooms=1&adults=2
        """
        params = {
            'id': property_id,
            'checkin': GoibiboURLConverter.iso_to_goibibo_date(checkin_iso),
            'checkout': GoibiboURLConverter.iso_to_goibibo_date(checkout_iso),
            'rooms': kwargs.get('rooms', 1),
            'adults': kwargs.get('adults', 2),
        }
        
        if kwargs.get('children'):
            params['children'] = kwargs['children']
        
        # Add location if provided
        if kwargs.get('location'):
            params['location'] = kwargs['location']
        
        # Add filters if provided
        for key in ['min_price', 'max_price', 'sort', 'page']:
            if key in kwargs:
                params[key] = kwargs[key]
        
        return f"/hotels/search/?{urlencode(params)}"

    @staticmethod
    def parse_goibibo_params(request_get):
        """Parse Goibibo-style GET params and convert to ISO dates"""
        params = dict(request_get)
        
        # Convert dates if present
        if 'checkin' in params:
            params['checkin'] = GoibiboURLConverter.goibibo_to_iso_date(params['checkin'])
        
        if 'checkout' in params:
            params['checkout'] = GoibiboURLConverter.goibibo_to_iso_date(params['checkout'])
        
        return params


class GoibiboSearchView:
    """Helper for building Goibibo-style search parameters"""
    
    @staticmethod
    def format_search_result(property_obj):
        """Format property for Goibibo-style search response"""
        return {
            'id': property_obj.id,
            'name': property_obj.name,
            'city': property_obj.city.name if property_obj.city else '',
            'area': property_obj.area or '',
            'rating': property_obj.rating,
            'review_count': property_obj.review_count,
            'min_price': str(property_obj.min_room_price),
            'image_url': property_obj.display_image_url or '/static/images/placeholder.png',
            'property_type': property_obj.property_type,
        }
    
    @staticmethod
    def build_goibibo_booking_url(property_id, room_id, checkin_iso, checkout_iso, **kwargs):
        """
        Build Goibibo-style booking URL
        
        Format: /hotels/search/?id=<property_id>&room=<room_id>&checkin=<YYYYMMDD>&checkout=<YYYYMMDD>
        """
        params = {
            'id': property_id,
            'room': room_id,
            'checkin': GoibiboURLConverter.iso_to_goibibo_date(checkin_iso),
            'checkout': GoibiboURLConverter.iso_to_goibibo_date(checkout_iso),
            'rooms': kwargs.get('rooms', 1),
            'adults': kwargs.get('adults', 2),
        }
        
        if kwargs.get('children'):
            params['children'] = kwargs['children']
        
        return f"/hotels/search/?{urlencode(params)}"
