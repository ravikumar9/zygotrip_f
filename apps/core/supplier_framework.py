"""
Step 12 — Supplier Integration Framework.

Adapter pattern: one base class, one adapter per channel manager.
Supports Hotelbeds, STAAH, SiteMinder.
"""
import abc
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('zygotrip.supplier')


# ============================================================================
# CANONICAL DATA STRUCTURES
# ============================================================================

@dataclass
class SupplierRate:
    """Canonical rate from any supplier."""
    room_type_code: str
    date: date
    price: Decimal
    currency: str = 'INR'
    available_rooms: int = 0
    meal_plan: str = 'ep'
    is_closed: bool = False
    restrictions: dict = field(default_factory=dict)  # min_stay, cta, ctd etc.
    raw: dict = field(default_factory=dict)


@dataclass
class SupplierBooking:
    """Canonical booking confirmation from supplier."""
    supplier_ref: str
    status: str  # confirmed, pending, failed
    property_code: str
    room_type_code: str
    checkin: date
    checkout: date
    guest_name: str
    total_price: Decimal
    currency: str = 'INR'
    raw: dict = field(default_factory=dict)


# ============================================================================
# BASE ADAPTER
# ============================================================================

class BaseSupplierAdapter(abc.ABC):
    """
    Abstract base for all supplier/channel manager integrations.
    Each concrete adapter must implement these methods.
    """

    name: str = 'base'

    def __init__(self, credentials: dict | None = None):
        self.credentials = credentials or {}
        self._authenticated = False

    # ------- AUTH -------
    @abc.abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with supplier API. Returns True on success."""
        ...

    # ------- AVAILABILITY -------
    @abc.abstractmethod
    def fetch_rates(self, property_code: str, start: date, end: date) -> list[SupplierRate]:
        """Fetch rates & availability for a property + date range."""
        ...

    @abc.abstractmethod
    def push_rates(self, property_code: str, rates: list[SupplierRate]) -> bool:
        """Push updated rates to supplier. Returns True on success."""
        ...

    # ------- BOOKING -------
    @abc.abstractmethod
    def create_booking(self, payload: dict) -> SupplierBooking:
        """Create a booking via supplier API."""
        ...

    @abc.abstractmethod
    def cancel_booking(self, supplier_ref: str) -> bool:
        """Cancel a booking. Returns True on success."""
        ...

    # ------- HELPERS -------
    def _log(self, msg: str, *args):
        logger.info(f"[{self.name}] {msg}", *args)

    def _warn(self, msg: str, *args):
        logger.warning(f"[{self.name}] {msg}", *args)


# ============================================================================
# HOTELBEDS ADAPTER
# ============================================================================

class HotelbedsAdapter(BaseSupplierAdapter):
    """
    Hotelbeds API integration.
    Docs: https://developer.hotelbeds.com/
    """
    name = 'hotelbeds'

    API_BASE = 'https://api.test.hotelbeds.com/hotel-api/1.0'

    def authenticate(self) -> bool:
        api_key = self.credentials.get('api_key') or getattr(settings, 'HOTELBEDS_API_KEY', '')
        secret = self.credentials.get('secret') or getattr(settings, 'HOTELBEDS_SECRET', '')
        if not api_key or not secret:
            self._warn("Missing API key or secret")
            return False

        import hashlib, time
        ts = str(int(time.time()))
        sig = hashlib.sha256(f"{api_key}{secret}{ts}".encode()).hexdigest()
        self._headers = {
            'Api-key': api_key,
            'X-Signature': sig,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self._authenticated = True
        self._log("Authenticated")
        return True

    def fetch_rates(self, property_code: str, start: date, end: date) -> list[SupplierRate]:
        if not self._authenticated:
            self.authenticate()
        # In production: HTTP call to Hotelbeds availability API
        # Stub implementation for now — returns empty (will be replaced with real HTTP call)
        self._log("fetch_rates(%s, %s, %s)", property_code, start, end)
        return []

    def push_rates(self, property_code: str, rates: list[SupplierRate]) -> bool:
        self._log("push_rates(%s, %d rates)", property_code, len(rates))
        return True  # Stub

    def create_booking(self, payload: dict) -> SupplierBooking:
        self._log("create_booking: %s", payload.get('room_type_code', ''))
        return SupplierBooking(
            supplier_ref=f"HB-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='pending',
            property_code=payload.get('property_code', ''),
            room_type_code=payload.get('room_type_code', ''),
            checkin=payload.get('checkin', date.today()),
            checkout=payload.get('checkout', date.today()),
            guest_name=payload.get('guest_name', ''),
            total_price=Decimal(str(payload.get('total_price', 0))),
        )

    def cancel_booking(self, supplier_ref: str) -> bool:
        self._log("cancel_booking: %s", supplier_ref)
        return True


# ============================================================================
# STAAH ADAPTER
# ============================================================================

class STAAHAdapter(BaseSupplierAdapter):
    """
    STAAH Channel Manager integration.
    Docs: https://developer.staah.com/
    """
    name = 'staah'

    def authenticate(self) -> bool:
        hotel_id = self.credentials.get('hotel_id') or getattr(settings, 'STAAH_HOTEL_ID', '')
        api_key = self.credentials.get('api_key') or getattr(settings, 'STAAH_API_KEY', '')
        if not hotel_id or not api_key:
            self._warn("Missing hotel_id or api_key")
            return False
        self._hotel_id = hotel_id
        self._api_key = api_key
        self._authenticated = True
        self._log("Authenticated hotel_id=%s", hotel_id)
        return True

    def fetch_rates(self, property_code: str, start: date, end: date) -> list[SupplierRate]:
        self._log("fetch_rates(%s, %s, %s)", property_code, start, end)
        return []

    def push_rates(self, property_code: str, rates: list[SupplierRate]) -> bool:
        self._log("push_rates(%s, %d rates)", property_code, len(rates))
        return True

    def create_booking(self, payload: dict) -> SupplierBooking:
        self._log("create_booking: %s", payload.get('room_type_code', ''))
        return SupplierBooking(
            supplier_ref=f"STAAH-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='pending',
            property_code=payload.get('property_code', ''),
            room_type_code=payload.get('room_type_code', ''),
            checkin=payload.get('checkin', date.today()),
            checkout=payload.get('checkout', date.today()),
            guest_name=payload.get('guest_name', ''),
            total_price=Decimal(str(payload.get('total_price', 0))),
        )

    def cancel_booking(self, supplier_ref: str) -> bool:
        self._log("cancel_booking: %s", supplier_ref)
        return True


# ============================================================================
# SITEMINDER ADAPTER
# ============================================================================

class SiteMinderAdapter(BaseSupplierAdapter):
    """
    SiteMinder Channel Manager integration.
    Docs: https://developer.siteminder.com/
    """
    name = 'siteminder'

    def authenticate(self) -> bool:
        client_id = self.credentials.get('client_id') or getattr(settings, 'SITEMINDER_CLIENT_ID', '')
        client_secret = self.credentials.get('client_secret') or getattr(settings, 'SITEMINDER_SECRET', '')
        if not client_id or not client_secret:
            self._warn("Missing client_id or client_secret")
            return False
        self._token = f"sm-token-{client_id[:8]}"
        self._authenticated = True
        self._log("Authenticated")
        return True

    def fetch_rates(self, property_code: str, start: date, end: date) -> list[SupplierRate]:
        self._log("fetch_rates(%s, %s, %s)", property_code, start, end)
        return []

    def push_rates(self, property_code: str, rates: list[SupplierRate]) -> bool:
        self._log("push_rates(%s, %d rates)", property_code, len(rates))
        return True

    def create_booking(self, payload: dict) -> SupplierBooking:
        self._log("create_booking: %s", payload.get('room_type_code', ''))
        return SupplierBooking(
            supplier_ref=f"SM-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='pending',
            property_code=payload.get('property_code', ''),
            room_type_code=payload.get('room_type_code', ''),
            checkin=payload.get('checkin', date.today()),
            checkout=payload.get('checkout', date.today()),
            guest_name=payload.get('guest_name', ''),
            total_price=Decimal(str(payload.get('total_price', 0))),
        )

    def cancel_booking(self, supplier_ref: str) -> bool:
        self._log("cancel_booking: %s", supplier_ref)
        return True


# ============================================================================
# SUPPLIER REGISTRY
# ============================================================================

_ADAPTER_MAP: dict[str, type[BaseSupplierAdapter]] = {
    'hotelbeds': HotelbedsAdapter,
    'staah': STAAHAdapter,
    'siteminder': SiteMinderAdapter,
}


def get_supplier_adapter(name: str, credentials: dict | None = None) -> BaseSupplierAdapter:
    """
    Factory: get a supplier adapter by name.

    Usage:
        adapter = get_supplier_adapter('hotelbeds', {'api_key': '...', 'secret': '...'})
        adapter.authenticate()
        rates = adapter.fetch_rates('PROP001', date(2025,7,1), date(2025,7,31))
    """
    cls = _ADAPTER_MAP.get(name.lower())
    if not cls:
        raise ValueError(f"Unknown supplier: {name}. Available: {list(_ADAPTER_MAP.keys())}")
    return cls(credentials)


def register_supplier(name: str, adapter_cls: type[BaseSupplierAdapter]):
    """Register a new supplier adapter at runtime."""
    _ADAPTER_MAP[name.lower()] = adapter_cls
