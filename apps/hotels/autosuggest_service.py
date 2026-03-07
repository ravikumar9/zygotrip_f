"""
PHASE 8: Autosuggest Hardening
Response format: {cities: [{name, count}], areas: [{name, count}], properties: [{name, slug}]}
Must show counts like Goibibo
"""
from django.db.models import Count
from apps.hotels.models import Property
import logging

logger = logging.getLogger(__name__)


class AutosuggestService:
    """Provides search suggestions with counts (like Goibibo)"""
    
    @staticmethod
    def get_suggestions(query_string, limit=10):
        """
        Get autosuggest results for query.
        
        Returns:
            {
                'query': str,
                'cities': [{'name': str, 'count': int}, ...],
                'areas': [{'name': str, 'count': int}, ...],
                'properties': [{'name': str, 'slug': str, 'city': str}, ...],
            }
        """
        if not query_string or len(query_string) < 2:
            return {
                'query': query_string,
                'cities': [],
                'areas': [],
                'properties': [],
                'message': 'Query too short (min 2 chars)'
            }
        
        query = query_string.strip().lower()
        
        # Get approved properties only
        approved_properties = Property.objects.filter(
            status='approved',
            agreement_signed=True
        )
        
        # Get matching cities with counts
        cities = AutosuggestService._get_matching_cities(
            query, approved_properties, limit
        )
        
        # Get matching areas with counts
        areas = AutosuggestService._get_matching_areas(
            query, approved_properties, limit
        )
        
        # Get matching properties
        properties = AutosuggestService._get_matching_properties(
            query, approved_properties, limit
        )
        
        return {
            'query': query_string,
            'cities': cities,
            'areas': areas,
            'properties': properties,
        }
    
    @staticmethod
    def _get_matching_cities(query, approved_properties, limit):
        """
        Get distinct cities matching query with property count.
        
        Returns: [{'name': str, 'state': str, 'code': str, 'count': int, 'latitude': float, 'longitude': float}, ...]
        """
        try:
            from apps.core.models import City
            from django.db.models import Q, Count as DjangoCount
            
            # Search cities by name or alternate names
            cities = City.objects.filter(
                Q(name__icontains=query) | Q(alternate_names__icontains=query),
                is_active=True
            ).select_related('state').annotate(
                property_count=DjangoCount('hotels')
            ).order_by('-property_count', '-popularity_score')[:limit]
            
            return [
                {
                    'name': city.name,
                    'state': city.state.name,
                    'code': city.code,
                    'count': city.property_count,
                    'latitude': float(city.latitude),
                    'longitude': float(city.longitude),
                    'type': 'city',
                    'display': f"{city.name}, {city.state.name} ({city.property_count} properties)"
                }
                for city in cities
            ]
        
        except Exception as e:
            logger.error(f"Error getting cities: {str(e)}")
            return []
    
    @staticmethod
    def _get_matching_areas(query, approved_properties, limit):
        """
        Get distinct areas matching query with property count.

        Primary:  Locality model (structured geographic entities)
        Fallback: Property.area CharField — filters out short/road fragments
                  (must be ≥ 5 chars and not contain digits/road keywords)
        """
        results = []
        seen_names: set = set()

        # ── 1. Structured Locality model (preferred) ────────────────────
        try:
            from apps.core.models import Locality
            from django.db.models import Q, Count as DjangoCount

            localities = Locality.objects.filter(
                Q(name__icontains=query) | Q(landmarks__icontains=query),
                is_active=True,
            ).select_related('city__state').annotate(
                property_count=DjangoCount('hotels')
            ).order_by('-property_count', '-popularity_score')[:limit]

            for locality in localities:
                name_lower = locality.name.lower()
                if name_lower in seen_names:
                    continue
                # Only block the fallback for this name if we have real FK-linked properties.
                # If property_count == 0 (properties use Property.area text field instead of
                # the locality FK), skip adding to seen_names so the fallback path can find
                # the real count via Property.area CharField.
                if locality.property_count == 0:
                    continue
                seen_names.add(name_lower)
                results.append({
                    'name': locality.name,
                    'city': locality.city.name,
                    'state': locality.city.state.name,
                    'count': locality.property_count,
                    'latitude': float(locality.latitude),
                    'longitude': float(locality.longitude),
                    'type': 'area',
                })
        except Exception as e:
            logger.warning(f"Locality area lookup failed: {e}")

        # ── 2. Property.area fallback — real neighbourhood names only ────
        # Filter: must be >= 5 chars, no street-number patterns, no road keywords
        import re as _re
        _ROAD_PATTERN = _re.compile(r'\b(road|rd|street|st|nagar|colony|sector|block|phase|cross)\b', _re.I)
        _DIGIT_PATTERN = _re.compile(r'\d')

        if len(results) < limit:
            try:
                from django.db.models import Q as DQ, Count as DC
                area_rows = (
                    approved_properties
                    .filter(area__icontains=query)
                    .exclude(area='')
                    .values('area', 'city__name', 'city__state__name')
                    .annotate(count=DC('id'))
                    .order_by('-count')[:limit * 2]
                )
                for row in area_rows:
                    area = (row['area'] or '').strip()
                    # Skip: too short, contains digits, looks like a road fragment
                    if (
                        len(area) < 5
                        or _DIGIT_PATTERN.search(area)
                        or _ROAD_PATTERN.search(area)
                        or area.lower() in seen_names
                    ):
                        continue
                    seen_names.add(area.lower())
                    results.append({
                        'name': area,
                        'city': row['city__name'] or '',
                        'state': row['city__state__name'] or '',
                        'count': row['count'],
                        'latitude': 0,
                        'longitude': 0,
                        'type': 'area',
                    })
                    if len(results) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Property.area fallback failed: {e}")

        return results[:limit]
    
    @staticmethod
    def _get_matching_properties(query, approved_properties, limit):
        """
        Get distinct properties matching query.
        
        Returns: [{'name': str, 'slug': str, 'city': str, 'state': str, 'latitude': float, 'longitude': float}, ...]
        """
        try:
            properties = approved_properties.filter(
                name__icontains=query
            ).select_related('city__state').values(
                'id', 'name', 'slug', 'city__name', 'city__state__name', 'latitude', 'longitude'
            )[:limit]
            
            return [
                {
                    'name': prop['name'],
                    'slug': prop['slug'],
                    'city': prop['city__name'],
                    'state': prop['city__state__name'],
                    'latitude': float(prop['latitude']),
                    'longitude': float(prop['longitude']),
                    'type': 'property',
                    'display': f"{prop['name']} - {prop['city__name']}"
                }
                for prop in properties
            ]
        
        except Exception as e:
            logger.error(f"Error getting properties: {str(e)}")
            return []

    @staticmethod
    def get_popular_destinations(limit=10):
        """
        Get most popular destinations (by property count).
        Shown in UI when user hasn't typed anything.
        
        Returns: [{'name': str, 'count': int, 'type': 'city'}, ...]
        """
        try:
            approved = Property.objects.filter(
                status='approved',
                agreement_signed=True
            )
            
            cities = approved.values('location').annotate(
                count=Count('id')
            ).order_by('-count')[:limit]
            
            return [
                {
                    'name': city['location'],
                    'count': city['count'],
                    'type': 'city'
                }
                for city in cities
            ]
        
        except Exception as e:
            logger.error(f"Error getting popular destinations: {str(e)}")
            return []
    
    @staticmethod
    def get_trending_searches(limit=5):
        """
        Get trending searches (would require logging searches).
        For now, returns most-booked properties.
        
        Returns: [{'name': str, 'slug': str}, ...]
        """
        try:
            # Could integrate with search logging in future
            approved = Property.objects.filter(
                status='approved',
                agreement_signed=True
            ).order_by('-rating')[:limit]
            
            return [
                {
                    'name': prop.name,
                    'slug': prop.slug,
                }
                for prop in approved
            ]
        
        except Exception as e:
            logger.error(f"Error getting trending: {str(e)}")
            return []
