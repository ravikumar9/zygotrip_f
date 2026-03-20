"""Anthropic tool registry and execution helpers for the travel assistant."""
import logging
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

TRAVEL_TOOLS = [
    {
        'name': 'search_hotels',
        'description': 'Search active hotels in a city with optional price filter.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'city': {'type': 'string'},
                'min_price': {'type': 'number'},
                'max_price': {'type': 'number'},
            },
            'required': ['city'],
        },
    },
    {
        'name': 'get_price_quote',
        'description': 'Get detailed quote for a room and stay duration.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'room_type_id': {'type': 'integer'},
                'nights': {'type': 'integer'},
                'room_count': {'type': 'integer'},
            },
            'required': ['room_type_id', 'nights'],
        },
    },
    {
        'name': 'check_availability',
        'description': 'Check room availability for a room type in a date range.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'room_type_id': {'type': 'integer'},
                'check_in': {'type': 'string'},
                'check_out': {'type': 'string'},
            },
            'required': ['room_type_id', 'check_in', 'check_out'],
        },
    },
    {
        'name': 'get_wallet_balance',
        'description': 'Get authenticated user wallet balance.',
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'search_flights',
        'description': 'Search flights between origin and destination on a date.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'origin': {'type': 'string'},
                'destination': {'type': 'string'},
                'travel_date': {'type': 'string'},
            },
            'required': ['origin', 'destination', 'travel_date'],
        },
    },
    {
        'name': 'apply_promo',
        'description': 'Validate promo code and compute discount on amount.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'code': {'type': 'string'},
                'amount': {'type': 'number'},
            },
            'required': ['code', 'amount'],
        },
    },
]


def search_hotels(user, **kwargs):
    from apps.hotels.models import Property

    city = (kwargs.get('city') or '').strip()
    min_price = kwargs.get('min_price')
    max_price = kwargs.get('max_price')
    qs = Property.objects.filter(city__name__iexact=city, is_active=True).prefetch_related('room_types')
    results = []
    for prop in qs[:20]:
        room = prop.room_types.order_by('base_price').first()
        if not room:
            continue
        price_from = Decimal(str(room.base_price or 0))
        if min_price is not None and price_from < Decimal(str(min_price)):
            continue
        if max_price is not None and price_from > Decimal(str(max_price)):
            continue
        results.append(
            {
                'id': prop.id,
                'name': prop.name,
                'slug': prop.slug,
                'rating': float(prop.rating or 0),
                'price_from': float(price_from),
            }
        )
    return {'city': city, 'results': results}


def get_price_quote(user, **kwargs):
    from apps.booking.pricing_engine import PricingEngine
    from apps.rooms.models import RoomType

    room_type = RoomType.objects.get(id=kwargs['room_type_id'])
    nights = int(kwargs['nights'])
    room_count = int(kwargs.get('room_count', 1))
    engine = PricingEngine(base_price_per_night=room_type.base_price, nights=nights, room_count=room_count)
    breakdown = engine.apply_property_discount(percent=0).apply_platform_discount(percent=0).apply_gst(percent=5).finalize()
    return {'room_type_id': room_type.id, 'quote': breakdown}


def check_availability(user, **kwargs):
    from apps.rooms.models import RoomInventory

    room_type_id = kwargs['room_type_id']
    check_in = date.fromisoformat(kwargs['check_in'])
    check_out = date.fromisoformat(kwargs['check_out'])
    nights = (check_out - check_in).days
    rows = RoomInventory.objects.filter(
        room_type_id=room_type_id,
        date__gte=check_in,
        date__lt=check_out,
        available_rooms__gt=0,
    ).count()
    return {'room_type_id': room_type_id, 'available': rows == nights, 'matched_nights': rows, 'nights': nights}


def get_wallet_balance(user, **kwargs):
    from apps.wallet.services import get_wallet_balance

    if not user or not user.is_authenticated:
        return {'error': 'Authentication required'}
    balance = get_wallet_balance(user)
    return {'balance': float(balance), 'currency': 'INR'}


def search_flights(user, **kwargs):
    from apps.flights.models import Flight

    origin = (kwargs.get('origin') or '').strip()
    destination = (kwargs.get('destination') or '').strip()
    travel_date = date.fromisoformat(kwargs.get('travel_date'))

    flights = Flight.objects.filter(
        origin__city__icontains=origin,
        destination__city__icontains=destination,
        departure_datetime__date=travel_date,
        is_active=True,
    )[:10]
    return {
        'results': [
            {
                'id': row.id,
                'flight_number': row.flight_number,
                'departure': row.departure_datetime.isoformat(),
                'arrival': row.arrival_datetime.isoformat(),
            }
            for row in flights
        ]
    }


def apply_promo(user, **kwargs):
    from apps.promos.selectors import get_active_promo
    from apps.promos.services import calculate_promo_discount

    code = (kwargs.get('code') or '').strip().upper()
    amount = Decimal(str(kwargs.get('amount', 0)))
    promo = get_active_promo(code)
    if not promo:
        return {'valid': False, 'reason': 'invalid_or_expired'}
    discount = calculate_promo_discount(promo, amount)
    return {
        'valid': True,
        'promo': code,
        'discount': float(discount),
        'final_amount': float(amount - discount),
    }


TOOL_HANDLERS = {
    'search_hotels': search_hotels,
    'get_price_quote': get_price_quote,
    'check_availability': check_availability,
    'get_wallet_balance': get_wallet_balance,
    'search_flights': search_flights,
    'apply_promo': apply_promo,
}


def execute_tool(tool_name, user, **kwargs):
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {'error': f'Unknown tool: {tool_name}'}
    try:
        return handler(user, **kwargs)
    except Exception as exc:
        logger.exception('Tool execution failed: %s', exc)
        return {'error': str(exc)}
