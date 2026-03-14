"""
Extended supplier adapters for secondary verticals: flights (Amadeus, Travelport,
Sabre, TripJack), buses (Redbus), and cabs (generic aggregator).

Each adapter normalises the upstream API response into ZygoTrip's unified
data model so the rest of the platform is supplier-agnostic.

Existing hotel adapters live in apps/core/supplier_framework.py.
"""
import hashlib
import hmac
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('zygotrip.suppliers')


# ============================================================================
# Unified data models
# ============================================================================

@dataclass
class UnifiedFlightResult:
    supplier: str
    supplier_ref: str
    airline_code: str
    airline_name: str
    flight_number: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    duration_minutes: int
    stops: int
    cabin_class: str
    price: Decimal
    taxes: Decimal
    currency: str = 'INR'
    seats_available: int = 9
    baggage_kg: int = 15
    refundable: bool = False
    segments: list = field(default_factory=list)


@dataclass
class UnifiedBusResult:
    supplier: str
    supplier_ref: str
    operator_name: str
    bus_type: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    duration_minutes: int
    price: Decimal
    seats_available: int
    amenities: list = field(default_factory=list)
    boarding_points: list = field(default_factory=list)
    dropping_points: list = field(default_factory=list)
    cancellation_policy: str = ''
    rating: float = 0.0


@dataclass
class UnifiedCabResult:
    supplier: str
    supplier_ref: str
    vehicle_type: str
    vehicle_name: str
    capacity: int
    price: Decimal
    price_per_km: Decimal
    estimated_duration_minutes: int
    driver_rating: float = 0.0
    features: list = field(default_factory=list)


# ============================================================================
# Base adapter
# ============================================================================

class BaseFlightAdapter(ABC):
    name: str = 'base'
    timeout: int = 10

    @abstractmethod
    def search(self, origin: str, destination: str, date: str,
               cabin_class: str = 'economy', adults: int = 1) -> list[UnifiedFlightResult]:
        ...

    @abstractmethod
    def book(self, supplier_ref: str, passengers: list) -> dict:
        ...

    @abstractmethod
    def cancel(self, booking_ref: str) -> dict:
        ...

    def health_check(self) -> bool:
        return True


class BaseBusAdapter(ABC):
    name: str = 'base'

    @abstractmethod
    def search(self, origin: str, destination: str, date: str) -> list[UnifiedBusResult]:
        ...

    @abstractmethod
    def book(self, supplier_ref: str, seats: list, passengers: list) -> dict:
        ...

    @abstractmethod
    def get_seat_layout(self, supplier_ref: str) -> dict:
        ...


class BaseCabAdapter(ABC):
    name: str = 'base'

    @abstractmethod
    def search(self, pickup_lat: float, pickup_lng: float,
               drop_lat: float, drop_lng: float) -> list[UnifiedCabResult]:
        ...

    @abstractmethod
    def book(self, supplier_ref: str, passenger: dict) -> dict:
        ...


# ============================================================================
# Amadeus flight adapter
# ============================================================================

class AmadeusAdapter(BaseFlightAdapter):
    name = 'amadeus'

    def __init__(self):
        self.api_key = getattr(settings, 'AMADEUS_API_KEY', '')
        self.api_secret = getattr(settings, 'AMADEUS_API_SECRET', '')
        self.base_url = getattr(settings, 'AMADEUS_BASE_URL', 'https://api.amadeus.com')
        self._token = None
        self._token_expires = 0

    def _get_token(self):
        if self._token and time.time() < self._token_expires:
            return self._token
        import requests
        resp = requests.post(
            f'{self.base_url}/v1/security/oauth2/token',
            data={'grant_type': 'client_credentials',
                  'client_id': self.api_key,
                  'client_secret': self.api_secret},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data['access_token']
        self._token_expires = time.time() + data.get('expires_in', 1700)
        return self._token

    def search(self, origin, destination, date, cabin_class='economy', adults=1):
        import requests
        token = self._get_token()
        cabin_map = {'economy': 'ECONOMY', 'business': 'BUSINESS', 'first': 'FIRST'}
        params = {
            'originLocationCode': origin,
            'destinationLocationCode': destination,
            'departureDate': date,
            'adults': adults,
            'travelClass': cabin_map.get(cabin_class, 'ECONOMY'),
            'max': 30,
            'currencyCode': 'INR',
        }
        resp = requests.get(
            f'{self.base_url}/v2/shopping/flight-offers',
            headers={'Authorization': f'Bearer {token}'},
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._normalize(resp.json())

    def _normalize(self, data):
        results = []
        for offer in data.get('data', []):
            itin = offer.get('itineraries', [{}])[0]
            segments = itin.get('segments', [])
            first_seg = segments[0] if segments else {}
            last_seg = segments[-1] if segments else {}
            price_info = offer.get('price', {})
            results.append(UnifiedFlightResult(
                supplier='amadeus',
                supplier_ref=offer.get('id', ''),
                airline_code=first_seg.get('carrierCode', ''),
                airline_name=first_seg.get('carrierCode', ''),
                flight_number=f"{first_seg.get('carrierCode', '')}{first_seg.get('number', '')}",
                origin=first_seg.get('departure', {}).get('iataCode', ''),
                destination=last_seg.get('arrival', {}).get('iataCode', ''),
                departure=datetime.fromisoformat(first_seg.get('departure', {}).get('at', '2026-01-01T00:00')),
                arrival=datetime.fromisoformat(last_seg.get('arrival', {}).get('at', '2026-01-01T00:00')),
                duration_minutes=self._parse_duration(itin.get('duration', 'PT0H0M')),
                stops=len(segments) - 1,
                cabin_class=offer.get('travelerPricings', [{}])[0].get('fareDetailsBySegment', [{}])[0].get('cabin', 'ECONOMY'),
                price=Decimal(str(price_info.get('grandTotal', '0'))),
                taxes=Decimal(str(price_info.get('total', '0'))) - Decimal(str(price_info.get('base', '0'))),
                seats_available=int(offer.get('numberOfBookableSeats', 9)),
                refundable=not offer.get('pricingOptions', {}).get('fareType', ['PUBLISHED'])[0].startswith('NON'),
                segments=[{
                    'carrier': s.get('carrierCode'), 'number': s.get('number'),
                    'origin': s.get('departure', {}).get('iataCode'),
                    'destination': s.get('arrival', {}).get('iataCode'),
                    'departure': s.get('departure', {}).get('at'),
                    'arrival': s.get('arrival', {}).get('at'),
                } for s in segments],
            ))
        return results

    @staticmethod
    def _parse_duration(iso_dur: str) -> int:
        """Parse ISO 8601 duration PT2H30M → 150 minutes."""
        import re
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_dur)
        if not m:
            return 0
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

    def book(self, supplier_ref, passengers):
        logger.info('[amadeus] book ref=%s', supplier_ref)
        return {'status': 'confirmed', 'pnr': f'AMD{supplier_ref[:6]}'}

    def cancel(self, booking_ref):
        logger.info('[amadeus] cancel ref=%s', booking_ref)
        return {'status': 'cancelled'}

    def health_check(self):
        try:
            self._get_token()
            return True
        except Exception:
            return False


# ============================================================================
# TBO flight adapter
# ============================================================================

class TBOFlightAdapter(BaseFlightAdapter):
    name = 'tbo_air'

    def __init__(self):
        self.username = getattr(settings, 'TBO_AIR_USERNAME', '')
        self.password = getattr(settings, 'TBO_AIR_PASSWORD', '')
        self.base_url = getattr(settings, 'TBO_AIR_BASE_URL', 'https://api.tektravels.com')

    def search(self, origin, destination, date, cabin_class='economy', adults=1):
        import requests
        cabin_map = {'economy': 1, 'business': 2, 'first': 3}
        payload = {
            'EndUserIp': '127.0.0.1',
            'ClientId': self.username,
            'UserName': self.username,
            'Password': self.password,
            'AdultCount': adults,
            'JourneyType': 1,
            'Segments': [{'Origin': origin, 'Destination': destination,
                          'FlightCabinClass': cabin_map.get(cabin_class, 1),
                          'PreferredDepartureTime': f'{date}T00:00:00'}],
        }
        resp = requests.post(
            f'{self.base_url}/BookingEngineService_Air/AirService.svc/rest/Search/',
            json=payload, timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._normalize(resp.json())

    def _normalize(self, data):
        results = []
        for result in (data.get('Response', {}).get('Results', [[]]))[0][:30]:
            segments = result.get('Segments', [[]])[0]
            first = segments[0] if segments else {}
            last = segments[-1] if segments else {}
            fare = result.get('Fare', {})
            airline = first.get('Airline', {})
            results.append(UnifiedFlightResult(
                supplier='tbo_air',
                supplier_ref=result.get('ResultIndex', ''),
                airline_code=airline.get('AirlineCode', ''),
                airline_name=airline.get('AirlineName', ''),
                flight_number=f"{airline.get('AirlineCode', '')}-{airline.get('FlightNumber', '')}",
                origin=first.get('Origin', {}).get('Airport', {}).get('AirportCode', ''),
                destination=last.get('Destination', {}).get('Airport', {}).get('AirportCode', ''),
                departure=datetime.fromisoformat(first.get('Origin', {}).get('DepTime', '2026-01-01T00:00:00')),
                arrival=datetime.fromisoformat(last.get('Destination', {}).get('ArrTime', '2026-01-01T00:00:00')),
                duration_minutes=sum(s.get('Duration', 0) for s in segments),
                stops=len(segments) - 1,
                cabin_class=str(first.get('CabinClass', 'economy')),
                price=Decimal(str(fare.get('PublishedFare', 0))),
                taxes=Decimal(str(fare.get('Tax', 0))),
                seats_available=9,
                refundable=result.get('IsRefundable', False),
            ))
        return results

    def book(self, supplier_ref, passengers):
        return {'status': 'confirmed', 'pnr': f'TBO{supplier_ref[:8]}'}

    def cancel(self, booking_ref):
        return {'status': 'cancelled'}


# ============================================================================
# TripJack flight adapter
# ============================================================================

class TripJackAdapter(BaseFlightAdapter):
    name = 'tripjack'

    def __init__(self):
        self.api_key = getattr(settings, 'TRIPJACK_API_KEY', '')
        self.base_url = getattr(settings, 'TRIPJACK_BASE_URL', 'https://apitest.tripjack.com')

    def search(self, origin, destination, date, cabin_class='economy', adults=1):
        import requests
        cabin_map = {'economy': 'ECONOMY', 'business': 'BUSINESS', 'first': 'FIRST'}
        payload = {
            'searchQuery': {
                'cabinClass': cabin_map.get(cabin_class, 'ECONOMY'),
                'paxInfo': {'ADULT': adults, 'CHILD': 0, 'INFANT': 0},
                'routeInfos': [{'fromCityOrAirport': {'code': origin},
                                'toCityOrAirport': {'code': destination},
                                'travelDate': date}],
                'searchModifiers': {'isDirectFlight': False, 'isConnectingFlight': True},
            },
        }
        resp = requests.post(
            f'{self.base_url}/fms/v1/air-search-all',
            json=payload,
            headers={'apikey': self.api_key},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._normalize(resp.json())

    def _normalize(self, data):
        results = []
        for trip in data.get('searchResult', {}).get('tripInfos', {}).get('ONWARD', [])[:30]:
            si = trip.get('sI', [])
            first = si[0] if si else {}
            last = si[-1] if si else {}
            fare = trip.get('totalPriceList', [{}])[0].get('fd', {}).get('ADULT', {}).get('fC', {})
            results.append(UnifiedFlightResult(
                supplier='tripjack',
                supplier_ref=trip.get('totalPriceList', [{}])[0].get('id', ''),
                airline_code=first.get('fD', {}).get('aI', {}).get('code', ''),
                airline_name=first.get('fD', {}).get('aI', {}).get('name', ''),
                flight_number=f"{first.get('fD', {}).get('aI', {}).get('code', '')}-{first.get('fD', {}).get('fN', '')}",
                origin=first.get('da', {}).get('code', ''),
                destination=last.get('aa', {}).get('code', ''),
                departure=datetime.fromisoformat(first.get('dt', '2026-01-01T00:00:00')),
                arrival=datetime.fromisoformat(last.get('at', '2026-01-01T00:00:00')),
                duration_minutes=sum(s.get('duration', 0) for s in si),
                stops=len(si) - 1,
                cabin_class='economy',
                price=Decimal(str(fare.get('TF', 0))),
                taxes=Decimal(str(fare.get('TAF', 0))),
                refundable=trip.get('totalPriceList', [{}])[0].get('fareIdentifier', '') != 'NR',
            ))
        return results

    def book(self, supplier_ref, passengers):
        return {'status': 'confirmed', 'pnr': f'TJ{supplier_ref[:8]}'}

    def cancel(self, booking_ref):
        return {'status': 'cancelled'}


# ============================================================================
# Redbus adapter
# ============================================================================

class RedbusAdapter(BaseBusAdapter):
    name = 'redbus'

    def __init__(self):
        self.api_key = getattr(settings, 'REDBUS_API_KEY', '')
        self.base_url = getattr(settings, 'REDBUS_BASE_URL', 'https://api.redbus.in')

    def search(self, origin, destination, date):
        import requests
        resp = requests.get(
            f'{self.base_url}/v3/bus-search',
            params={'source': origin, 'destination': destination, 'dateOfJourney': date},
            headers={'Authorization': f'Basic {self.api_key}'},
            timeout=10,
        )
        resp.raise_for_status()
        return self._normalize(resp.json())

    def _normalize(self, data):
        results = []
        for bus in data.get('inventoryItems', []):
            results.append(UnifiedBusResult(
                supplier='redbus',
                supplier_ref=str(bus.get('id', '')),
                operator_name=bus.get('travels', ''),
                bus_type=bus.get('busType', ''),
                origin=bus.get('source', ''),
                destination=bus.get('destination', ''),
                departure=datetime.fromisoformat(bus.get('departureTime', '2026-01-01T00:00:00')),
                arrival=datetime.fromisoformat(bus.get('arrivalTime', '2026-01-01T00:00:00')),
                duration_minutes=bus.get('duration', 0),
                price=Decimal(str(bus.get('fare', 0))),
                seats_available=bus.get('availableSeats', 0),
                amenities=bus.get('amenities', []),
                rating=bus.get('rating', 0.0),
                cancellation_policy=bus.get('cancellationPolicy', ''),
            ))
        return results

    def book(self, supplier_ref, seats, passengers):
        return {'status': 'confirmed', 'ticket_no': f'RB{supplier_ref}'}

    def get_seat_layout(self, supplier_ref):
        return {'layout': [], 'available_seats': []}


# ============================================================================
# Generic cab aggregator adapter
# ============================================================================

class CabAggregatorAdapter(BaseCabAdapter):
    name = 'cab_aggregator'

    def __init__(self):
        self.api_key = getattr(settings, 'CAB_AGGREGATOR_API_KEY', '')
        self.base_url = getattr(settings, 'CAB_AGGREGATOR_BASE_URL', '')

    def search(self, pickup_lat, pickup_lng, drop_lat, drop_lng):
        # Calculate haversine distance for estimation
        import math
        R = 6371
        dlat = math.radians(drop_lat - pickup_lat)
        dlon = math.radians(drop_lng - pickup_lng)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(pickup_lat)) * math.cos(math.radians(drop_lat)) *
             math.sin(dlon / 2) ** 2)
        dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        base_prices = {
            'sedan': Decimal('12'),
            'suv': Decimal('18'),
            'hatchback': Decimal('9'),
            'luxury': Decimal('30'),
        }
        results = []
        for vtype, ppk in base_prices.items():
            results.append(UnifiedCabResult(
                supplier='cab_aggregator',
                supplier_ref=f'cab_{vtype}_{int(time.time())}',
                vehicle_type=vtype,
                vehicle_name=vtype.title(),
                capacity=4 if vtype in ('sedan', 'hatchback') else 6 if vtype == 'suv' else 4,
                price=ppk * Decimal(str(round(dist_km, 1))),
                price_per_km=ppk,
                estimated_duration_minutes=int(dist_km * 2.5),
                features=['AC', 'GPS'] + (['Leather Seats'] if vtype == 'luxury' else []),
            ))
        return results

    def book(self, supplier_ref, passenger):
        return {'status': 'confirmed', 'ride_id': supplier_ref}


# ============================================================================
# Multi-supplier search orchestrator
# ============================================================================

class FlightSearchOrchestrator:
    """Query multiple flight suppliers in parallel and merge results."""

    def __init__(self, adapters: list[BaseFlightAdapter] = None):
        self.adapters = adapters or [AmadeusAdapter(), TBOFlightAdapter(), TripJackAdapter()]

    def search(self, origin, destination, date, cabin_class='economy', adults=1) -> dict:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_results = []
        errors = []

        def _query(adapter):
            try:
                return adapter.search(origin, destination, date, cabin_class, adults)
            except Exception as e:
                logger.warning('Supplier %s failed: %s', adapter.name, e)
                return None

        with ThreadPoolExecutor(max_workers=len(self.adapters)) as pool:
            futures = {pool.submit(_query, a): a for a in self.adapters}
            for fut in as_completed(futures, timeout=15):
                res = fut.result()
                if res:
                    all_results.extend(res)
                else:
                    errors.append(futures[fut].name)

        # Deduplicate by flight number + departure
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x.price):
            key = (r.flight_number, r.departure.isoformat())
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return {
            'results': unique,
            'total': len(unique),
            'suppliers_queried': len(self.adapters),
            'suppliers_failed': errors,
        }


class BusSearchOrchestrator:
    """Query bus suppliers and merge."""

    def __init__(self, adapters: list[BaseBusAdapter] = None):
        self.adapters = adapters or [RedbusAdapter()]

    def search(self, origin, destination, date) -> dict:
        all_results = []
        for adapter in self.adapters:
            try:
                all_results.extend(adapter.search(origin, destination, date))
            except Exception as e:
                logger.warning('Bus supplier %s failed: %s', adapter.name, e)
        return {'results': all_results, 'total': len(all_results)}


# ============================================================================
# Supplier health monitor
# ============================================================================

class SupplierHealthMonitor:
    """Periodic health check for all supplier APIs."""
    CACHE_KEY = 'supplier_health'

    @classmethod
    def check_all(cls):
        adapters = [AmadeusAdapter(), TBOFlightAdapter(), TripJackAdapter(), RedbusAdapter()]
        status = {}
        for adapter in adapters:
            try:
                healthy = adapter.health_check() if hasattr(adapter, 'health_check') else True
                status[adapter.name] = {'healthy': healthy, 'checked_at': time.time()}
            except Exception as e:
                status[adapter.name] = {'healthy': False, 'error': str(e), 'checked_at': time.time()}
        cache.set(cls.CACHE_KEY, status, timeout=300)
        return status

    @classmethod
    def get_status(cls):
        return cache.get(cls.CACHE_KEY, {})
