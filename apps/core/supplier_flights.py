"""
Flight GDS Supplier Adapters — Amadeus & TBO Air integration.

These plug into the core supplier_framework via register_supplier().
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.core.supplier_framework import (
    BaseSupplierAdapter, SupplierRate, SupplierBooking, CircuitBreaker,
)

logger = logging.getLogger('zygotrip.supplier.flights')


@dataclass
class FlightSupplierResult:
    """Canonical flight search result from a GDS."""
    flight_number: str
    airline_code: str
    origin: str
    destination: str
    departure: str
    arrival: str
    duration_minutes: int
    stops: int
    fare: Decimal
    taxes: Decimal
    cabin_type: str = 'economy'
    available_seats: int = 9
    fare_class: str = 'Y'
    is_refundable: bool = True
    baggage_kg: int = 15
    raw: dict = field(default_factory=dict)

    @property
    def total_fare(self):
        return self.fare + self.taxes


class AmadeusFlightAdapter(BaseSupplierAdapter):
    """Amadeus GDS integration for flight search and booking.

    Docs: https://developers.amadeus.com/
    Auth: OAuth2 client_credentials grant.
    """
    name = 'amadeus'

    @property
    def API_BASE(self):
        if getattr(settings, 'AMADEUS_PRODUCTION', False):
            return 'https://api.amadeus.com'
        return 'https://test.api.amadeus.com'

    def authenticate(self) -> bool:
        client_id = self.credentials.get('client_id') or getattr(settings, 'AMADEUS_CLIENT_ID', '')
        client_secret = self.credentials.get('client_secret') or getattr(settings, 'AMADEUS_CLIENT_SECRET', '')
        if not client_id or not client_secret:
            self._warn("Missing Amadeus client_id or client_secret")
            return False

        try:
            data = self._api_call(
                'POST',
                f'{self.API_BASE}/v1/security/oauth2/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret,
                })
            self._access_token = data.get('access_token', '')
            self._headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
            }
            self._authenticated = True
            self._log("Authenticated via OAuth2")
            return True
        except Exception as exc:
            self._warn("Auth failed: %s", exc)
            return False

    def search_flights(self, origin, destination, departure_date,
                       adults=1, cabin='ECONOMY'):
        """Search flights via Amadeus Flight Offers Search API."""
        if not self._authenticated:
            self.authenticate()
        if not self._authenticated:
            return []

        try:
            data = self._api_call(
                'GET',
                f'{self.API_BASE}/v2/shopping/flight-offers',
                params={
                    'originLocationCode': origin,
                    'destinationLocationCode': destination,
                    'departureDate': departure_date.isoformat() if isinstance(departure_date, date) else departure_date,
                    'adults': adults,
                    'travelClass': cabin,
                    'max': 50,
                    'currencyCode': 'INR',
                },
                headers=self._headers)

            results = []
            for offer in data.get('data', []):
                for itinerary in offer.get('itineraries', []):
                    segments = itinerary.get('segments', [])
                    if not segments:
                        continue
                    first_seg = segments[0]
                    last_seg = segments[-1]
                    price_info = offer.get('price', {})
                    results.append(FlightSupplierResult(
                        flight_number=first_seg.get('number', ''),
                        airline_code=first_seg.get('carrierCode', ''),
                        origin=first_seg.get('departure', {}).get('iataCode', origin),
                        destination=last_seg.get('arrival', {}).get('iataCode', destination),
                        departure=first_seg.get('departure', {}).get('at', ''),
                        arrival=last_seg.get('arrival', {}).get('at', ''),
                        duration_minutes=self._parse_duration(itinerary.get('duration', '')),
                        stops=len(segments) - 1,
                        fare=Decimal(str(price_info.get('base', '0'))),
                        taxes=Decimal(str(price_info.get('grandTotal', '0'))) - Decimal(str(price_info.get('base', '0'))),
                        cabin_type=cabin.lower(),
                        is_refundable='NON_REFUNDABLE' not in str(offer.get('pricingOptions', {})),
                        raw=offer,
                    ))
            self._log("Found %d flight offers %s→%s", len(results), origin, destination)
            return results
        except Exception as exc:
            self._warn("search_flights failed: %s", exc)
            return []

    def _parse_duration(self, iso_duration):
        """Parse ISO 8601 duration PT2H30M → 150 minutes."""
        if not iso_duration:
            return 0
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            return h * 60 + m
        return 0

    # Hotel-interface compatibility (required by BaseSupplierAdapter)
    def fetch_rates(self, property_code, start, end):
        return []

    def push_rates(self, property_code, rates):
        return True

    def create_booking(self, payload):
        """Create flight booking via Amadeus Flight Orders API."""
        if not self._authenticated:
            self.authenticate()
        try:
            data = self._api_call(
                'POST',
                f'{self.API_BASE}/v1/booking/flight-orders',
                json=payload,
                headers=self._headers)
            order = data.get('data', {})
            return SupplierBooking(
                supplier_ref=order.get('id', f"AM-{timezone.now().strftime('%Y%m%d%H%M%S')}"),
                status='confirmed',
                property_code=payload.get('origin', ''),
                room_type_code='',
                checkin=date.today(),
                checkout=date.today(),
                guest_name=payload.get('guest_name', ''),
                total_price=Decimal(str(order.get('price', {}).get('grandTotal', 0))),
                raw=order,
            )
        except Exception as exc:
            self._warn("create_booking failed: %s", exc)
            return SupplierBooking(
                supplier_ref=f"AM-ERR-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status='failed', property_code='', room_type_code='',
                checkin=date.today(), checkout=date.today(),
                guest_name='', total_price=Decimal('0'),
                raw={'error': str(exc)},
            )

    def cancel_booking(self, supplier_ref):
        if not self._authenticated:
            self.authenticate()
        try:
            self._api_call(
                'DELETE',
                f'{self.API_BASE}/v1/booking/flight-orders/{supplier_ref}',
                headers=self._headers)
            return True
        except Exception:
            return False


class TBOAirAdapter(BaseSupplierAdapter):
    """TBO Air (TripJack/TBO) flight API adapter.

    TBO is commonly used in Indian OTA market.
    """
    name = 'tbo_air'

    API_BASE = 'https://api.tbo.com/air/v1'

    def authenticate(self) -> bool:
        username = self.credentials.get('username') or getattr(settings, 'TBO_AIR_USERNAME', '')
        password = self.credentials.get('password') or getattr(settings, 'TBO_AIR_PASSWORD', '')
        if not username or not password:
            self._warn("Missing TBO Air credentials")
            return False

        try:
            data = self._api_call(
                'POST',
                f'{self.API_BASE}/authenticate',
                json={'username': username, 'password': password})
            self._token = data.get('token', '')
            self._headers = {
                'Authorization': f'Bearer {self._token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
            self._authenticated = True
            return True
        except Exception as exc:
            self._warn("Auth failed: %s", exc)
            return False

    def search_flights(self, origin, destination, departure_date,
                       adults=1, cabin='economy'):
        if not self._authenticated:
            self.authenticate()
        if not self._authenticated:
            return []
        try:
            data = self._api_call(
                'POST',
                f'{self.API_BASE}/search',
                json={
                    'origin': origin,
                    'destination': destination,
                    'departure_date': departure_date.isoformat() if isinstance(departure_date, date) else departure_date,
                    'adults': adults,
                    'cabin_class': cabin,
                    'currency': 'INR',
                },
                headers=self._headers)
            results = []
            for flight in data.get('flights', []):
                results.append(FlightSupplierResult(
                    flight_number=flight.get('flight_number', ''),
                    airline_code=flight.get('airline', ''),
                    origin=flight.get('origin', origin),
                    destination=flight.get('destination', destination),
                    departure=flight.get('departure_time', ''),
                    arrival=flight.get('arrival_time', ''),
                    duration_minutes=flight.get('duration', 0),
                    stops=flight.get('stops', 0),
                    fare=Decimal(str(flight.get('base_fare', 0))),
                    taxes=Decimal(str(flight.get('taxes', 0))),
                    cabin_type=cabin,
                    available_seats=flight.get('seats_available', 9),
                    raw=flight,
                ))
            return results
        except Exception as exc:
            self._warn("search_flights failed: %s", exc)
            return []

    def fetch_rates(self, property_code, start, end):
        return []

    def push_rates(self, property_code, rates):
        return True

    def create_booking(self, payload):
        if not self._authenticated:
            self.authenticate()
        try:
            data = self._api_call(
                'POST', f'{self.API_BASE}/book',
                json=payload, headers=self._headers)
            return SupplierBooking(
                supplier_ref=data.get('pnr', f"TBO-{timezone.now().strftime('%Y%m%d%H%M%S')}"),
                status='confirmed', property_code='', room_type_code='',
                checkin=date.today(), checkout=date.today(),
                guest_name=payload.get('guest_name', ''),
                total_price=Decimal(str(data.get('total_price', 0))),
                raw=data,
            )
        except Exception as exc:
            return SupplierBooking(
                supplier_ref=f"TBO-ERR", status='failed',
                property_code='', room_type_code='',
                checkin=date.today(), checkout=date.today(),
                guest_name='', total_price=Decimal('0'),
                raw={'error': str(exc)},
            )

    def cancel_booking(self, supplier_ref):
        if not self._authenticated:
            self.authenticate()
        try:
            self._api_call(
                'POST', f'{self.API_BASE}/cancel',
                json={'pnr': supplier_ref}, headers=self._headers)
            return True
        except Exception:
            return False
