"""
Production Distance/Routing Engine
Real routing API integration with caching, fallback, ETA and toll estimates.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple

import requests
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip')


class RouteCache(TimeStampedModel):
    """Cache for routing results"""
    
    from_location = models.CharField(max_length=255, db_index=True)
    to_location = models.CharField(max_length=255, db_index=True)
    
    distance_km = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    
    estimated_toll = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Route details
    route_polyline = models.TextField(blank=True)  # Encoded polyline
    has_highways = models.BooleanField(default=False)
    has_toll_roads = models.BooleanField(default=False)
    
    # Source
    source = models.CharField(max_length=50)  # 'google_maps', 'graphhopper', 'manual', 'osrm'
    is_fallback = models.BooleanField(default=False)
    
    # Tracking
    last_used = models.DateTimeField(auto_now=True, db_index=True)
    cached_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('from_location', 'to_location')
        indexes = [
            models.Index(fields=['from_location', 'to_location']),
            models.Index(fields=['last_used']),
        ]
    
    def __str__(self):
        return f"{self.from_location} → {self.to_location}: {self.distance_km}km / {self.duration_minutes}min"
    
    @property
    def is_stale(self) -> bool:
        """Check if cache is older than 7 days"""
        return (timezone.now() - self.cached_at) > timedelta(days=7)
    
    def refresh(self):
        """Refresh the cache by updating last_used"""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])


class RoutingAPIAdapter:
    """Base class for routing API adapters"""
    
    def __init__(self, api_key: str = ''):
        self.api_key = api_key
        self.timeout = 10
        self.name = self.__class__.__name__
    
    def calculate_route(self, from_location: str, to_location: str) -> Optional[Dict]:
        """
        Calculate route between two locations.
        Returns dict with distance, duration, toll, etc.
        """
        raise NotImplementedError
    
    def _make_request(self, url: str, params: Dict) -> Optional[Dict]:
        """Make HTTP request with error handling"""
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"{self.name} API error: {str(e)}")
            return None


class GoogleMapsAdapter(RoutingAPIAdapter):
    """Google Maps Distance Matrix API"""
    
    API_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    def calculate_route(self, from_location: str, to_location: str) -> Optional[Dict]:
        """Get distance from Google Maps"""
        params = {
            'origins': from_location,
            'destinations': to_location,
            'key': self.api_key,
            'units': 'metric',
        }
        
        data = self._make_request(self.API_URL, params)
        if not data or data.get('status') != 'OK':
            return None
        
        try:
            element = data['rows'][0]['elements'][0]
            if element['status'] != 'OK':
                return None
            
            return {
                'distance_km': element['distance']['value'] / 1000,
                'duration_minutes': element['duration']['value'] / 60,
                'source': 'google_maps',
            }
        except (KeyError, IndexError):
            return None


class GraphHopperAdapter(RoutingAPIAdapter):
    """GraphHopper Routing API"""
    
    API_URL = "https://graphhopper.com/api/1/route"
    
    def calculate_route(self, from_location: str, to_location: str) -> Optional[Dict]:
        """Get distance from GraphHopper"""
        # Parse coordinates from location string (assumes "lat,lng" format)
        try:
            from_coords = from_location.split(',')
            to_coords = to_location.split(',')
            
            params = {
                'point': [f"{from_coords[0]},{from_coords[1]}", f"{to_coords[0]},{to_coords[1]}"],
                'vehicle': 'car',
                'locale': 'en',
                'key': self.api_key,
            }
            
            data = self._make_request(self.API_URL, params)
            if not data or 'paths' not in data or not data['paths']:
                return None
            
            path = data['paths'][0]
            
            return {
                'distance_km': path['distance'] / 1000,
                'duration_minutes': path['time'] / 60000,
                'route_polyline': path.get('points', ''),
                'source': 'graphhopper',
            }
        except Exception as e:
            logger.error(f"GraphHopper parsing error: {str(e)}")
            return None


class OSRMAdapter(RoutingAPIAdapter):
    """Open Source Routing Machine (OSRM)"""
    
    API_URL = "http://router.project-osrm.org/route/v1/driving"
    
    def calculate_route(self, from_location: str, to_location: str) -> Optional[Dict]:
        """Get distance from OSRM (free, no API key needed)"""
        try:
            from_coords = from_location.split(',')
            to_coords = to_location.split(',')
            
            url = f"{self.API_URL}/{from_coords[1]},{from_coords[0]};{to_coords[1]},{to_coords[0]}"
            
            params = {'overview': 'full', 'steps': 'true'}
            
            data = self._make_request(url, params)
            if not data or 'routes' not in data or not data['routes']:
                return None
            
            route = data['routes'][0]
            
            return {
                'distance_km': route['distance'] / 1000,
                'duration_minutes': route['duration'] / 60,
                'route_polyline': route.get('geometry', ''),
                'source': 'osrm',
            }
        except Exception as e:
            logger.error(f"OSRM parsing error: {str(e)}")
            return None


class TollEstimator:
    """Estimate toll costs for Indian highways"""
    
    # Major toll routes in India
    TOLL_ROUTES = {
        ('delhi', 'jaipur'): {
            'base_toll': Decimal('300'),
            'vehicle_type_multiplier': {
                'car': 1.0,
                'suv': 1.2,
                'bus': 1.5,
            }
        },
        ('mumbai', 'pune'): {
            'base_toll': Decimal('750'),
            'vehicle_type_multiplier': {'car': 1.0, 'suv': 1.2, 'bus': 1.5}
        },
        ('bangalore', 'hyderabad'): {
            'base_toll': Decimal('850'),
            'vehicle_type_multiplier': {'car': 1.0, 'suv': 1.2, 'bus': 1.5}
        },
    }
    
    @classmethod
    def estimate_toll(cls, from_location: str, to_location: str, vehicle_type: str = 'car') -> Optional[Decimal]:
        """Estimate toll for route"""
        route_key = (from_location.lower(), to_location.lower())
        reverse_key = (to_location.lower(), from_location.lower())
        
        toll_data = cls.TOLL_ROUTES.get(route_key) or cls.TOLL_ROUTES.get(reverse_key)
        
        if toll_data:
            multiplier = toll_data['vehicle_type_multiplier'].get(vehicle_type, 1.0)
            return toll_data['base_toll'] * Decimal(str(multiplier))
        
        return None


class DistanceEngineProduction:
    """Production distance/routing engine with caching and fallback"""
    
    def __init__(self):
        self.google_adapter = GoogleMapsAdapter(api_key=settings.GOOGLE_MAPS_API_KEY if hasattr(settings, 'GOOGLE_MAPS_API_KEY') else '')
        self.graphhopper_adapter = GraphHopperAdapter(api_key=settings.GRAPHHOPPER_API_KEY if hasattr(settings, 'GRAPHHOPPER_API_KEY') else '')
        self.osrm_adapter = OSRMAdapter()  # Free, no key needed
        
        self.adapters = [
            self.osrm_adapter,  # Try free OSRM first
            self.graphhopper_adapter,
            self.google_adapter,
        ]
        self.logger = logging.getLogger('zygotrip')
    
    def calculate_distance(
        self,
        from_location: str,
        to_location: str,
        vehicle_type: str = 'car',
        skip_cache: bool = False,
    ) -> Dict:
        """
        Calculate distance with caching and fallback.
        Returns dict with distance, duration, toll, ETA, etc.
        """
        
        # Try cache first
        if not skip_cache:
            cached = self._get_cached_route(from_location, to_location)
            if cached:
                return cached
        
        # Try each adapter in order
        for adapter in self.adapters:
            try:
                result = adapter.calculate_route(from_location, to_location)
                if result:
                    # Calculate additional metrics
                    route_data = self._enrich_route_data(result, from_location, to_location, vehicle_type)
                    
                    # Cache the result
                    self._cache_route(from_location, to_location, route_data)
                    
                    self.logger.info(f"Route calculated via {adapter.name}: {result['distance_km']:.1f}km")
                    return route_data
            except Exception as e:
                self.logger.warning(f"Error with {adapter.name}: {str(e)}")
                continue
        
        # All adapters failed, return fallback
        self.logger.error(f"All routing adapters failed for {from_location} → {to_location}")
        return self._get_fallback_route(from_location, to_location)
    
    def _cache_route(self, from_location: str, to_location: str, route_data: Dict):
        """Cache route in database"""
        try:
            # Try to update existing cache entry
            RouteCache.objects.update_or_create(
                from_location=from_location,
                to_location=to_location,
                defaults={
                    'distance_km': route_data['distance_km'],
                    'duration_minutes': route_data['duration_minutes'],
                    'estimated_toll': route_data.get('estimated_toll'),
                    'source': route_data.get('source', 'unknown'),
                    'is_fallback': route_data.get('is_fallback', False),
                }
            )
        except Exception as e:
            self.logger.warning(f"Error caching route: {str(e)}")
    
    def _get_cached_route(self, from_location: str, to_location: str) -> Optional[Dict]:
        """Get cached route if available"""
        try:
            cache_entry = RouteCache.objects.get(
                from_location=from_location,
                to_location=to_location
            )
            
            # Use cache if less than 7 days old
            if not cache_entry.is_stale:
                cache_entry.refresh()
                return {
                    'distance_km': float(cache_entry.distance_km),
                    'duration_minutes': cache_entry.duration_minutes,
                    'estimated_toll': float(cache_entry.estimated_toll) if cache_entry.estimated_toll else None,
                    'eta': self._calculate_eta(cache_entry.duration_minutes),
                    'source': cache_entry.source,
                    'cached': True,
                }
        except RouteCache.DoesNotExist:
            pass
        
        return None
    
    def _enrich_route_data(self, route_data: Dict, from_location: str, to_location: str, vehicle_type: str) -> Dict:
        """Add ETA, toll estimate, and other metrics"""
        duration_minutes = route_data['duration_minutes']
        
        return {
            **route_data,
            'eta': self._calculate_eta(duration_minutes),
            'estimated_toll': float(TollEstimator.estimate_toll(from_location, to_location, vehicle_type) or 0),
            'fare_estimate': self._calculate_fare_estimate(
                Decimal(str(route_data['distance_km'])),
                vehicle_type
            ),
            'cached': False,
        }
    
    def _calculate_eta(self, duration_minutes: int) -> str:
        """Calculate ETA time"""
        eta_time = timezone.now() + timedelta(minutes=duration_minutes)
        return eta_time.strftime('%H:%M')
    
    def _calculate_fare_estimate(self, distance_km: Decimal, vehicle_type: str) -> Dict:
        """Calculate estimated fare"""
        # Base rates for India
        rates = {
            'car': {'base': Decimal('50'), 'per_km': Decimal('8')},
            'suv': {'base': Decimal('75'), 'per_km': Decimal('10')},
            'bus': {'base': Decimal('100'), 'per_km': Decimal('5')},
        }
        
        rate = rates.get(vehicle_type, rates['car'])
        
        base_fare = rate['base']
        distance_fare = distance_km * rate['per_km']
        total_fare = base_fare + distance_fare
        
        # Add 5% platform margin
        platform_margin = total_fare * Decimal('0.05')
        final_fare = total_fare + platform_margin
        
        return {
            'base_fare': float(base_fare),
            'distance_fare': float(distance_fare),
            'platform_margin': float(platform_margin),
            'total_fare': float(final_fare),
        }
    
    def _get_fallback_route(self, from_location: str, to_location: str) -> Dict:
        """Return fallback route data using simple calculation"""
        # Simple fallback: estimate 1km per minute travel
        estimated_distance = 50  # km
        estimated_duration = 50  # minutes
        
        # Try to get from cache if exists
        try:
            cache_entry = RouteCache.objects.get(
                from_location=from_location,
                to_location=to_location,
                is_fallback=True
            )
            estimated_distance = float(cache_entry.distance_km)
            estimated_duration = cache_entry.duration_minutes
        except RouteCache.DoesNotExist:
            pass
        
        toll = TollEstimator.estimate_toll(from_location, to_location)
        
        return {
            'distance_km': estimated_distance,
            'duration_minutes': estimated_duration,
            'eta': self._calculate_eta(estimated_duration),
            'estimated_toll': float(toll) if toll else 0,
            'source': 'fallback',
            'is_fallback': True,
            'cached': False,
            'fare_estimate': self._calculate_fare_estimate(Decimal(str(estimated_distance)), 'car'),
        }


def get_default_distance_engine() -> DistanceEngineProduction:
    """Get default distance engine instance"""
    return DistanceEngineProduction()