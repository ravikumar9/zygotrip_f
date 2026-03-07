"""Google Maps integration with proper async loading.

Phase 6: Fix Google Maps implementation using callback pattern.
"""

import os
from django.conf import settings
from django.templatetags.static import static


def get_google_maps_context():
    """Get Google Maps context for templates.
    
    Returns: {
        'api_key': 'xxx',
        'maps_script_src': 'https://...',
        'enabled': bool,
    }
    """
    api_key = settings.GOOGLE_MAPS_API_KEY if hasattr(settings, 'GOOGLE_MAPS_API_KEY') else None
    
    if not api_key:
        return {
            'enabled': False,
            'api_key': None,
            'maps_script_src': None,
        }
    
    return {
        'enabled': True,
        'api_key': api_key,
        'maps_script_src': f'https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap',
    }


def get_hotel_map_coordinates(hotel):
    """Get coordinates for hotel detail map.
    
    Returns: {
        'latitude': float,
        'longitude': float,
        'zoom': int,
    }
    """
    return {
        'latitude': float(hotel.latitude) if hotel.latitude else 28.6139,
        'longitude': float(hotel.longitude) if hotel.longitude else 77.2090,
        'zoom': 15,
    }