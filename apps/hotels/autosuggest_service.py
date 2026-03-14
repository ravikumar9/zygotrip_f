"""
PHASE 8 + GEO SEARCH HARDENING
Goibibo-level autosuggest: fuzzy matching, address search, district search,
bus/cab route cities, trigram similarity (pg_trgm).

Response format: {cities, areas, properties, landmarks, bus_cities, cab_cities}
"""
from django.db.models import Count, Q, Value, FloatField
from django.db.models.functions import Length
from apps.hotels.models import Property
import logging
import re as _re

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class AutosuggestService:
    """Provides search suggestions with counts — Goibibo-level geo search."""
    
    @staticmethod
    def get_suggestions(query_string, limit=10):
        """
        Get autosuggest results for query.

        Search order:
        1. Cities (exact → fuzzy → district → alternate_names)
        2. Areas / Localities
        3. Properties (name, address, formatted_address)
        4. Landmarks
        5. Bus route cities
        6. Cab cities

        Returns:
            {
                'query': str,
                'cities': [...], 'areas': [...], 'properties': [...],
                'landmarks': [...], 'bus_cities': [...], 'cab_cities': [...]
            }
        """
        if not query_string or len(query_string) < 2:
            return {
                'query': query_string,
                'cities': [], 'areas': [], 'properties': [],
                'landmarks': [], 'bus_cities': [], 'cab_cities': [],
                'message': 'Query too short (min 2 chars)'
            }
        
        query = query_string.strip()
        
        # Get approved properties only
        approved_properties = Property.objects.filter(
            status='approved',
            agreement_signed=True
        )
        
        cities = AutosuggestService._get_matching_cities(query, approved_properties, limit)
        areas = AutosuggestService._get_matching_areas(query, approved_properties, limit)
        properties = AutosuggestService._get_matching_properties(query, approved_properties, limit)
        landmarks = AutosuggestService._get_matching_landmarks(query, limit)
        bus_cities = AutosuggestService._get_matching_bus_cities(query, limit)
        cab_cities = AutosuggestService._get_matching_cab_cities(query, limit)
        
        return {
            'query': query_string,
            'cities': cities,
            'areas': areas,
            'properties': properties,
            'landmarks': landmarks,
            'bus_cities': bus_cities,
            'cab_cities': cab_cities,
        }
    
    @staticmethod
    def _get_matching_cities(query, approved_properties, limit):
        """
        Get distinct cities matching query with property count.

        Search strategy (Goibibo-level):
        1. Exact icontains on name / alternate_names / district
        2. Trigram similarity for fuzzy / typo tolerance
        3. Property address / formatted_address fallback
        """
        results = []
        seen_names: set = set()

        try:
            from apps.core.models import City
            from django.db.models import Count as DjangoCount

            # ── Phase 1: icontains on name, alternate_names, district ────
            exact_q = (
                Q(name__icontains=query) |
                Q(alternate_names__icontains=query) |
                Q(district__icontains=query) |
                Q(display_name__icontains=query)
            )
            cities = City.objects.filter(
                exact_q, is_active=True
            ).select_related('state').annotate(
                property_count=DjangoCount('hotels')
            ).order_by('-property_count', '-popularity_score')[:limit]

            for city in cities:
                key = city.name.lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                results.append({
                    'name': city.name,
                    'state': city.state.name if city.state else '',
                    'district': getattr(city, 'district', '') or '',
                    'code': city.code,
                    'count': city.property_count,
                    'latitude': float(city.latitude),
                    'longitude': float(city.longitude),
                    'type': 'city',
                    'display': f"{city.name}, {city.state.name}" + (
                        f" ({city.property_count} properties)" if city.property_count else ""
                    ),
                })

            # ── Phase 2: Trigram similarity (fuzzy / typo tolerance) ─────
            if len(results) < limit:
                try:
                    from django.contrib.postgres.search import TrigramSimilarity
                    fuzzy_cities = (
                        City.objects.filter(is_active=True)
                        .annotate(
                            similarity=TrigramSimilarity('name', query),
                            property_count=DjangoCount('hotels'),
                        )
                        .filter(similarity__gt=0.2)
                        .order_by('-similarity', '-property_count')
                        [:(limit - len(results)) * 2]
                    )
                    for city in fuzzy_cities.select_related('state'):
                        key = city.name.lower()
                        if key in seen_names:
                            continue
                        seen_names.add(key)
                        results.append({
                            'name': city.name,
                            'state': city.state.name if city.state else '',
                            'district': getattr(city, 'district', '') or '',
                            'code': city.code,
                            'count': city.property_count,
                            'latitude': float(city.latitude),
                            'longitude': float(city.longitude),
                            'type': 'city',
                            'display': f"{city.name}, {city.state.name}" + (
                                f" ({city.property_count} properties)" if city.property_count else ""
                            ),
                        })
                        if len(results) >= limit:
                            break
                except Exception as e:
                    logger.debug(f"Trigram search failed (pg_trgm may not be installed): {e}")

            # ── Phase 3: Property address/formatted_address fallback ─────
            if len(results) < limit:
                try:
                    addr_cities = (
                        approved_properties
                        .filter(
                            Q(address__icontains=query) |
                            Q(formatted_address__icontains=query)
                        )
                        .exclude(city__isnull=True)
                        .values('city__name', 'city__state__name', 'city__code',
                                'city__latitude', 'city__longitude')
                        .annotate(count=DjangoCount('id'))
                        .order_by('-count')[:limit]
                    )
                    for row in addr_cities:
                        key = (row['city__name'] or '').lower()
                        if not key or key in seen_names:
                            continue
                        seen_names.add(key)
                        results.append({
                            'name': row['city__name'],
                            'state': row['city__state__name'] or '',
                            'district': '',
                            'code': row['city__code'] or '',
                            'count': row['count'],
                            'latitude': float(row['city__latitude'] or 0),
                            'longitude': float(row['city__longitude'] or 0),
                            'type': 'city',
                            'display': f"{row['city__name']}, {row['city__state__name']}",
                        })
                        if len(results) >= limit:
                            break
                except Exception as e:
                    logger.warning(f"Address-based city lookup failed: {e}")

        except Exception as e:
            logger.error(f"Error getting cities: {str(e)}")

        return results[:limit]
    
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
        Get distinct properties matching query by name, address, or formatted_address.
        """
        try:
            properties = approved_properties.filter(
                Q(name__icontains=query) |
                Q(address__icontains=query) |
                Q(formatted_address__icontains=query) |
                Q(landmark__icontains=query)
            ).select_related('city__state').values(
                'id', 'name', 'slug', 'city__name', 'city__state__name',
                'latitude', 'longitude', 'area'
            ).distinct()[:limit]
            
            return [
                {
                    'name': prop['name'],
                    'slug': prop['slug'],
                    'city': prop['city__name'] or '',
                    'state': prop['city__state__name'] or '',
                    'area': prop['area'] or '',
                    'latitude': float(prop['latitude']),
                    'longitude': float(prop['longitude']),
                    'type': 'property',
                    'display': f"{prop['name']} - {prop['area']}, {prop['city__name']}" if prop['area'] else f"{prop['name']} - {prop['city__name']}"
                }
                for prop in properties
            ]
        
        except Exception as e:
            logger.error(f"Error getting properties: {str(e)}")
            return []

    @staticmethod
    def _get_matching_landmarks(query, limit):
        """
        Get landmarks matching query from Locality.landmarks field.
        
        Returns: [{'name': str, 'locality': str, 'city': str, 'state': str, 'type': 'landmark'}, ...]
        """
        results = []
        seen_names: set = set()
        
        try:
            from apps.core.models import Locality
            
            localities = Locality.objects.filter(
                landmarks__icontains=query,
                is_active=True,
            ).select_related('city__state')[:limit * 3]
            
            for locality in localities:
                for lm in locality.get_landmarks_list():
                    lm_clean = lm.strip()
                    if not lm_clean or len(lm_clean) < 3:
                        continue
                    if query.lower() not in lm_clean.lower():
                        continue
                    lm_lower = lm_clean.lower()
                    if lm_lower in seen_names:
                        continue
                    seen_names.add(lm_lower)
                    results.append({
                        'name': lm_clean,
                        'locality': locality.name,
                        'city': locality.city.name,
                        'state': locality.city.state.name,
                        'latitude': float(locality.latitude),
                        'longitude': float(locality.longitude),
                        'type': 'landmark',
                        'display': f"{lm_clean}, {locality.name} - {locality.city.name}",
                    })
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
        except Exception as e:
            logger.warning(f"Landmark lookup failed: {e}")
        
        return results[:limit]

    @staticmethod
    def _get_matching_bus_cities(query, limit):
        """
        Get bus route cities matching query.
        Searches Bus from_city / to_city and BoardingPoint/DroppingPoint city fields.
        """
        results = []
        seen: set = set()
        q_lower = query.lower()

        try:
            from apps.buses.models import Bus
            from django.db.models import Count as DC

            # Search bus from/to cities
            bus_cities = (
                Bus.objects
                .filter(
                    Q(from_city__icontains=query) | Q(to_city__icontains=query),
                    is_active=True,
                )
                .values('from_city', 'to_city')
            )
            city_counts: dict = {}
            for row in bus_cities:
                for field in ('from_city', 'to_city'):
                    name = (row[field] or '').strip()
                    if name and q_lower in name.lower():
                        key = name.lower()
                        city_counts[key] = city_counts.get(key, 0) + 1

            # Sort by route count
            for name_lower, count in sorted(city_counts.items(), key=lambda x: -x[1]):
                if name_lower in seen:
                    continue
                seen.add(name_lower)
                results.append({
                    'name': name_lower.title(),
                    'route_count': count,
                    'type': 'bus_city',
                    'display': f"{name_lower.title()} ({count} bus routes)",
                })
                if len(results) >= limit:
                    break

        except Exception as e:
            logger.warning(f"Bus city lookup failed: {e}")

        return results[:limit]

    @staticmethod
    def _get_matching_cab_cities(query, limit):
        """
        Get cab cities matching query from Cab model.
        """
        results = []
        q_lower = query.lower()

        try:
            from apps.cabs.models import Cab
            from django.db.models import Count as DC

            cab_cities = (
                Cab.objects
                .filter(city__icontains=query, is_active=True)
                .values('city')
                .annotate(count=DC('id'))
                .order_by('-count')[:limit]
            )

            seen: set = set()
            for row in cab_cities:
                name = (row['city'] or '').strip()
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    'name': name.title(),
                    'cab_count': row['count'],
                    'type': 'cab_city',
                    'display': f"{name.title()} ({row['count']} cabs available)",
                })

        except Exception as e:
            logger.warning(f"Cab city lookup failed: {e}")

        return results[:limit]

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
