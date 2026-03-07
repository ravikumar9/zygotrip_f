"""
Autocomplete Engine - Grouped & Smart Autocomplete
Provides fast, grouped autocomplete results for OTA search
"""

from typing import List, Dict, Any
from django.db.models import Q, Count, Prefetch
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)


class AutocompleteEngine:
    """
    Grouped autocomplete with intelligent result ordering
    
    Result Groups (in order):
    ─────────────────────────
    1. Cities (max 5)
    2. Areas/Localities (max 5)
    3. Properties (max 5)
    4. Landmarks (max 3)
    
    Total: max 18 results
    """
    
    MAX_CITIES = 5
    MAX_LOCALITIES = 5
    MAX_PROPERTIES = 5
    MAX_LANDMARKS = 3
    
    def __init__(self):
        self.min_query_length = 2
    
    def autocomplete(self, query: str, limit: int = 18) -> Dict[str, Any]:
        """
        Get grouped autocomplete results
        
        Args:
            query: Search query (minimum 2 characters)
            limit: Total result limit
            
        Returns:
            {
                "groups": [
                    {
                        "type": "city",
                        "label": "Cities",
                        "items": [
                            {
                                "label": "New Delhi",
                                "type": "city",
                                "id": 1,
                                "slug": "new-delhi",
                                "count": 150,  # property count
                                "thumbnail": null
                            }
                        ]
                    },
                    ...
                ]
            }
        """
        if not query or len(query) < self.min_query_length:
            return self._get_popular_cities()
        
        query = query.strip()
        
        try:
            groups = []
            
            # 1. Search cities
            cities = self._search_cities(query)
            if cities:
                groups.append({
                    "type": "city",
                    "label": "Cities",
                    "items": cities
                })
            
            # 2. Search localities/areas
            localities = self._search_localities(query)
            if localities:
                groups.append({
                    "type": "area",
                    "label": "Areas",
                    "items": localities
                })
            
            # 3. Search properties
            properties = self._search_properties(query)
            if properties:
                groups.append({
                    "type": "property",
                    "label": "Properties",
                    "items": properties
                })
            
            # 4. Search landmarks
            landmarks = self._search_landmarks(query)
            if landmarks:
                groups.append({
                    "type": "landmark",
                    "label": "Landmarks",
                    "items": landmarks
                })
            
            return {"groups": groups}
            
        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return {"groups": []}
    
    def _search_cities(self, query: str) -> List[Dict[str, Any]]:
        """Search cities with property counts"""
        try:
            from apps.core.models import City
            from apps.hotels.models import Property
            
            cities = City.objects.filter(
                Q(name__icontains=query) |
                Q(name__istartswith=query)
            ).annotate(
                property_count=Count('property', distinct=True)
            ).filter(
                property_count__gt=0
            ).order_by(
                '-property_count',
                'name'
            )[:self.MAX_CITIES]
            
            return [
                {
                    "label": city.name,
                    "type": "city",
                    "id": city.id,
                    "slug": city.slug if hasattr(city, 'slug') else city.name.lower().replace(' ', '-'),
                    "count": city.property_count,
                    "thumbnail": None,
                    "subtitle": f"{city.property_count} properties"
                }
                for city in cities
            ]
            
        except Exception as e:
            logger.error(f"City search error: {e}")
            return []
    
    def _search_localities(self, query: str) -> List[Dict[str, Any]]:
        """Search localities/areas with property counts"""
        try:
            from apps.core.models import Locality
            
            localities = Locality.objects.filter(
                Q(name__icontains=query) |
                Q(name__istartswith=query)
            ).select_related('city').annotate(
                property_count=Count('property', distinct=True)
            ).filter(
                property_count__gt=0
            ).order_by(
                '-property_count',
                'name'
            )[:self.MAX_LOCALITIES]
            
            return [
                {
                    "label": locality.name,
                    "type": "area",
                    "id": locality.id,
                    "slug": locality.slug if hasattr(locality, 'slug') else locality.name.lower().replace(' ', '-'),
                    "count": locality.property_count,
                    "thumbnail": None,
                    "subtitle": f"{locality.city.name}, {locality.property_count} properties"
                }
                for locality in localities
            ]
            
        except Exception as e:
            logger.error(f"Locality search error: {e}")
            return []
    
    def _search_properties(self, query: str) -> List[Dict[str, Any]]:
        """Search properties by name"""
        try:
            from apps.hotels.models import Property
            
            properties = Property.objects.filter(
                Q(name__icontains=query) |
                Q(name__istartswith=query),
                is_active=True
            ).select_related('city').order_by(
                '-rating',
                'name'
            )[:self.MAX_PROPERTIES]
            
            return [
                {
                    "label": prop.name,
                    "type": "property",
                    "id": prop.id,
                    "slug": prop.slug if hasattr(prop, 'slug') else str(prop.id),
                    "count": None,
                    "thumbnail": self._get_property_thumbnail(prop),
                    "subtitle": f"{prop.city.name} · ★{prop.rating:.1f}" if hasattr(prop, 'rating') else prop.city.name,
                    "price": prop.base_price if hasattr(prop, 'base_price') else None
                }
                for prop in properties
            ]
            
        except Exception as e:
            logger.error(f"Property search error: {e}")
            return []
    
    def _search_landmarks(self, query: str) -> List[Dict[str, Any]]:
        """Search landmarks (if landmark model exists)"""
        # Note: Implement landmark search if Landmark model exists
        # For now, return empty
        return []
    
    def _get_property_thumbnail(self, property_obj) -> str:
        """Get property thumbnail URL"""
        try:
            if hasattr(property_obj, 'images') and property_obj.images.exists():
                first_image = property_obj.images.first()
                if first_image and hasattr(first_image, 'image'):
                    return first_image.image.url
        except Exception:
            pass
        
        return '/static/img/placeholder-hotel.jpg'
    
    def _get_popular_cities(self) -> Dict[str, Any]:
        """Get popular cities when query is empty"""
        try:
            from apps.core.models import City
            
            cities = City.objects.annotate(
                property_count=Count('property', distinct=True)
            ).filter(
                property_count__gt=0
            ).order_by('-property_count')[:10]
            
            items = [
                {
                    "label": city.name,
                    "type": "city",
                    "id": city.id,
                    "slug": city.slug if hasattr(city, 'slug') else city.name.lower().replace(' ', '-'),
                    "count": city.property_count,
                    "thumbnail": None,
                    "subtitle": f"{city.property_count} properties"
                }
                for city in cities
            ]
            
            return {
                "groups": [
                    {
                        "type": "city",
                        "label": "Popular Destinations",
                        "items": items
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Popular cities error: {e}")
            return {"groups": []}


