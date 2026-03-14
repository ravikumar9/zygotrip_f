"""
Bus & Activity Supplier Adapters.

Extends the core supplier_framework with:
  - RedBus/AbhiBus-style bus aggregator adapter
  - Viator/GetYourGuide-style activity supplier adapter
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.core.supplier_framework import (
    BaseSupplierAdapter, SupplierRate, SupplierBooking,
)

logger = logging.getLogger('zygotrip.supplier.transport')


# ============================================================================
# BUS AGGREGATOR ADAPTER
# ============================================================================

@dataclass
class BusSupplierResult:
    """Canonical bus search result from an aggregator."""
    operator_name: str
    bus_type: str
    from_city: str
    to_city: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    price: Decimal
    available_seats: int
    amenities: list = field(default_factory=list)
    rating: Decimal = Decimal('0')
    supplier_ref: str = ''
    raw: dict = field(default_factory=dict)


class BusAggregatorAdapter(BaseSupplierAdapter):
    """Generic bus aggregator API adapter (RedBus / AbhiBus pattern).

    Provides search functionality for bus routes.
    """
    name = 'bus_aggregator'

    API_BASE = 'https://api.example-bus.com/v1'

    def authenticate(self) -> bool:
        api_key = self.credentials.get('api_key') or getattr(settings, 'BUS_AGGREGATOR_API_KEY', '')
        if not api_key:
            self._warn("Missing bus aggregator API key")
            return False
        self._headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
        }
        self._authenticated = True
        return True

    def search_buses(self, from_city, to_city, journey_date):
        """Search buses via aggregator API."""
        if not self._authenticated:
            self.authenticate()
        if not self._authenticated:
            return []
        try:
            data = self._api_call(
                'GET', f'{self.API_BASE}/search',
                params={
                    'from': from_city,
                    'to': to_city,
                    'date': journey_date.isoformat() if isinstance(journey_date, date) else journey_date,
                },
                headers=self._headers)
            results = []
            for bus in data.get('buses', []):
                results.append(BusSupplierResult(
                    operator_name=bus.get('operator', ''),
                    bus_type=bus.get('bus_type', 'seater'),
                    from_city=from_city,
                    to_city=to_city,
                    departure_time=bus.get('departure', ''),
                    arrival_time=bus.get('arrival', ''),
                    duration_minutes=bus.get('duration', 0),
                    price=Decimal(str(bus.get('fare', 0))),
                    available_seats=bus.get('available_seats', 0),
                    amenities=bus.get('amenities', []),
                    rating=Decimal(str(bus.get('rating', 0))),
                    supplier_ref=bus.get('id', ''),
                    raw=bus,
                ))
            return results
        except Exception as exc:
            self._warn("search_buses failed: %s", exc)
            return []

    # Hotel-interface compatibility
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
                supplier_ref=data.get('booking_id', ''),
                status='confirmed', property_code='', room_type_code='',
                checkin=date.today(), checkout=date.today(),
                guest_name=payload.get('passenger_name', ''),
                total_price=Decimal(str(data.get('total', 0))),
                raw=data,
            )
        except Exception as exc:
            return SupplierBooking(
                supplier_ref=f"BUS-ERR", status='failed',
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
                json={'booking_id': supplier_ref}, headers=self._headers)
            return True
        except Exception:
            return False


# ============================================================================
# ACTIVITY SUPPLIER ADAPTER (Viator / GetYourGuide pattern)
# ============================================================================

@dataclass
class ActivitySupplierResult:
    """Canonical activity from a supplier."""
    title: str
    supplier_code: str
    city: str
    duration_minutes: int
    adult_price: Decimal
    child_price: Decimal = Decimal('0')
    description: str = ''
    category: str = ''
    rating: Decimal = Decimal('0')
    review_count: int = 0
    image_url: str = ''
    is_instant_confirmation: bool = True
    raw: dict = field(default_factory=dict)


class ViatorAdapter(BaseSupplierAdapter):
    """Viator / TripAdvisor Experiences API adapter.

    Docs: https://developer.viator.com/
    """
    name = 'viator'

    @property
    def API_BASE(self):
        if getattr(settings, 'VIATOR_PRODUCTION', False):
            return 'https://api.viator.com/partner'
        return 'https://api.sandbox.viator.com/partner'

    def authenticate(self) -> bool:
        api_key = self.credentials.get('api_key') or getattr(settings, 'VIATOR_API_KEY', '')
        if not api_key:
            self._warn("Missing Viator API key")
            return False
        self._headers = {
            'exp-api-key': api_key,
            'Accept': 'application/json;version=2.0',
            'Accept-Language': 'en-US',
        }
        self._authenticated = True
        return True

    def search_activities(self, city, date_from=None, category=None):
        """Search activities/experiences by destination."""
        if not self._authenticated:
            self.authenticate()
        if not self._authenticated:
            return []
        try:
            params = {
                'destName': city,
                'currency': 'INR',
                'topX': '50',
            }
            if date_from:
                params['startDate'] = date_from.isoformat() if isinstance(date_from, date) else date_from
            if category:
                params['catId'] = category

            data = self._api_call(
                'GET', f'{self.API_BASE}/products/search',
                params=params, headers=self._headers)

            results = []
            for product in data.get('products', data.get('data', [])):
                results.append(ActivitySupplierResult(
                    title=product.get('title', ''),
                    supplier_code=product.get('productCode', ''),
                    city=city,
                    duration_minutes=product.get('duration', {}).get('fixedDurationInMinutes', 0),
                    adult_price=Decimal(str(product.get('pricing', {}).get('summary', {}).get('fromPrice', 0))),
                    description=product.get('description', ''),
                    category=product.get('primaryCategory', ''),
                    rating=Decimal(str(product.get('reviews', {}).get('combinedAverageRating', 0))),
                    review_count=product.get('reviews', {}).get('totalReviews', 0),
                    image_url=product.get('images', [{}])[0].get('variants', [{}])[0].get('url', '') if product.get('images') else '',
                    raw=product,
                ))
            self._log("Found %d activities in %s", len(results), city)
            return results
        except Exception as exc:
            self._warn("search_activities failed: %s", exc)
            return []

    # Hotel-interface compatibility
    def fetch_rates(self, property_code, start, end):
        return []

    def push_rates(self, property_code, rates):
        return True

    def create_booking(self, payload):
        if not self._authenticated:
            self.authenticate()
        try:
            data = self._api_call(
                'POST', f'{self.API_BASE}/bookings/book',
                json=payload, headers=self._headers)
            return SupplierBooking(
                supplier_ref=data.get('bookingRef', f"VIA-{timezone.now().strftime('%Y%m%d%H%M%S')}"),
                status=data.get('status', 'confirmed'),
                property_code='', room_type_code='',
                checkin=date.today(), checkout=date.today(),
                guest_name=payload.get('guest_name', ''),
                total_price=Decimal(str(data.get('total', 0))),
                raw=data,
            )
        except Exception as exc:
            return SupplierBooking(
                supplier_ref=f"VIA-ERR", status='failed',
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
                'POST', f'{self.API_BASE}/bookings/{supplier_ref}/cancel',
                headers=self._headers)
            return True
        except Exception:
            return False
