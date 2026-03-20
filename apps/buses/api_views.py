"""
Bus REST API — JSON endpoints for the Next.js frontend.

Endpoints:
  GET  /api/v1/buses/search/          → Search buses by route + date
  GET  /api/v1/buses/<id>/            → Bus detail with seat map
  GET  /api/v1/buses/<id>/seats/      → Available seats for a bus
  GET  /api/v1/buses/<id>/seat-map/   → Visual seat layout grid
  GET  /api/v1/buses/<id>/points/     → Boarding + dropping points
  POST /api/v1/buses/<id>/lock-seats/ → Lock seats during checkout
  POST /api/v1/buses/<id>/release-seats/ → Release locked seats
  GET  /api/v1/buses/routes/          → Popular routes autocomplete
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from django.db.models import Q, Count, Min
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import (
    Bus,
    BusSeat,
    BusType,
    BoardingPoint,
    DroppingPoint,
    BusBooking,
    BusBookingPassenger,
    BusPriceBreakdown,
)
from apps.core.service_guard import require_service_enabled

logger = logging.getLogger('zygotrip.buses')


def _serialize_bus(bus, journey_date=None):
    """Serialize a Bus to JSON for frontend consumption."""
    amenities = bus.get_amenities_list() if bus.amenities else []
    bus_type_name = ''
    if bus.bus_type:
        bus_type_name = bus.bus_type.get_name_display() if hasattr(bus.bus_type, 'get_name_display') else str(bus.bus_type)

    available = bus.available_seats
    if journey_date:
        booked = bus.seats.filter(state='booked').count()
        available = max(0, bus.seats.count() - booked)

    return {
        'id': bus.id,
        'uuid': str(bus.uuid),
        'operator_name': bus.operator_name or 'Bus Service',
        'registration_number': bus.registration_number,
        'from_city': bus.from_city,
        'to_city': bus.to_city,
        'departure_time': bus.departure_time.strftime('%H:%M') if bus.departure_time else '',
        'arrival_time': bus.arrival_time.strftime('%H:%M') if bus.arrival_time else '',
        'journey_date': str(bus.journey_date) if bus.journey_date else str(journey_date) if journey_date else '',
        'bus_type': bus_type_name,
        'bus_type_code': bus.bus_type.name if bus.bus_type else '',
        'amenities': amenities,
        'price_per_seat': float(bus.price_per_seat),
        'available_seats': available,
        'total_seats': bus.seats.count() if bus.seats.exists() else bus.available_seats,
        'is_ac': bus.bus_type.name in ('ac', 'volvo') if bus.bus_type else False,
        'is_sleeper': bus.bus_type.name in ('sleeper', 'semi_sleeper') if bus.bus_type else False,
    }


def _serialize_seat(seat):
    """Serialize a BusSeat to JSON."""
    return {
        'id': seat.id,
        'seat_number': seat.seat_number,
        'row': seat.row,
        'column': seat.column,
        'is_ladies_seat': seat.is_ladies_seat,
        'state': seat.state,
        'is_available': seat.state == 'available',
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def search_buses(request):
    """
    GET /api/v1/buses/search/?from=Delhi&to=Mumbai&date=2026-03-15&bus_type=ac&sort=price
    """
    from_city = request.GET.get('from', '').strip()
    to_city = request.GET.get('to', '').strip()
    date_str = request.GET.get('date', '')
    bus_type = request.GET.get('bus_type', '')
    sort = request.GET.get('sort', 'departure')
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 50)

    qs = Bus.objects.filter(is_active=True).select_related('bus_type').prefetch_related('seats')

    if from_city:
        qs = qs.filter(from_city__icontains=from_city)
    if to_city:
        qs = qs.filter(to_city__icontains=to_city)

    journey_date = None
    if date_str:
        try:
            journey_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            qs = qs.filter(Q(journey_date=journey_date) | Q(journey_date__isnull=True))
        except ValueError:
            pass

    if bus_type:
        qs = qs.filter(bus_type__name=bus_type)

    # Filter out buses with no seats
    qs = qs.filter(available_seats__gt=0)

    # Sorting
    sort_map = {
        'price': 'price_per_seat',
        'price_desc': '-price_per_seat',
        'departure': 'departure_time',
        'arrival': 'arrival_time',
        'seats': '-available_seats',
    }
    qs = qs.order_by(sort_map.get(sort, 'departure_time'))

    total = qs.count()
    offset = (page - 1) * per_page
    buses = qs[offset:offset + per_page]

    # Collect filter options
    all_bus_types = BusType.objects.values_list('name', flat=True)
    routes_from = Bus.objects.filter(is_active=True).values_list('from_city', flat=True).distinct()[:20]
    routes_to = Bus.objects.filter(is_active=True).values_list('to_city', flat=True).distinct()[:20]

    return Response({
        'success': True,
        'data': {
            'buses': [_serialize_bus(b, journey_date) for b in buses],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'filters': {
                'bus_types': list(all_bus_types),
                'from_cities': sorted(set(routes_from)),
                'to_cities': sorted(set(routes_to)),
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def bus_detail(request, bus_id):
    """GET /api/v1/buses/<id>/"""
    try:
        bus = Bus.objects.select_related('bus_type').prefetch_related('seats').get(id=bus_id, is_active=True)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    data = _serialize_bus(bus)

    # Seat map organized by rows
    seats = bus.seats.all().order_by('row', 'column')
    seat_map = {}
    for seat in seats:
        if seat.row not in seat_map:
            seat_map[seat.row] = []
        seat_map[seat.row].append(_serialize_seat(seat))

    data['seat_map'] = seat_map
    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def bus_seats(request, bus_id):
    """GET /api/v1/buses/<id>/seats/"""
    try:
        bus = Bus.objects.prefetch_related('seats').get(id=bus_id, is_active=True)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    seats = bus.seats.all().order_by('row', 'column')
    return Response({
        'success': True,
        'data': {
            'seats': [_serialize_seat(s) for s in seats],
            'available_count': seats.filter(state='available').count(),
            'total_count': seats.count(),
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def popular_routes(request):
    """GET /api/v1/buses/routes/ — Popular bus routes."""
    routes = (
        Bus.objects.filter(is_active=True)
        .values('from_city', 'to_city')
        .annotate(bus_count=Count('id'), min_price=Min('price_per_seat'))
        .order_by('-bus_count')[:15]
    )
    return Response({
        'success': True,
        'data': [
            {
                'from_city': r['from_city'],
                'to_city': r['to_city'],
                'bus_count': r['bus_count'],
                'min_price': float(r['min_price']) if r['min_price'] else 0,
            }
            for r in routes
        ],
    })


# ── Seat Map Layout ──────────────────────────────────────────────────────────


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def seat_map_layout(request, bus_id):
    """GET /api/v1/buses/<id>/seat-map/

    Returns a visual grid layout for the frontend seat selector.

    Response format:
    {
      "bus_type": "sleeper",
      "total_seats": 36,
      "available_seats": 28,
      "layout": {
        "lower_deck": [
          [{"seat_number": "L1", "row": "A", "column": 1, "state": "available", ...}, null, ...],
          ...
        ],
        "upper_deck": [...] // only for sleeper buses
      },
      "legend": {"available": 28, "booked": 6, "ladies": 2, "locked": 0}
    }
    """
    try:
        bus = Bus.objects.select_related('bus_type').prefetch_related('seats').get(
            id=bus_id, is_active=True,
        )
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    seats = bus.seats.all().order_by('row', 'column')

    # Release any expired locks first
    BusSeat.release_expired_locks()

    # Build grid layout
    is_sleeper = bus.bus_type and bus.bus_type.name in ('sleeper', 'semi_sleeper')

    # Organize seats into rows
    rows = {}
    for seat in seats:
        if seat.row not in rows:
            rows[seat.row] = {}
        rows[seat.row][seat.column] = {
            'id': seat.id,
            'seat_number': seat.seat_number,
            'row': seat.row,
            'column': seat.column,
            'state': 'available' if (seat.state == 'available' or
                                     (seat.state == 'locked' and seat.is_lock_expired))
                     else seat.state,
            'is_ladies_seat': seat.is_ladies_seat,
            'price': float(bus.price_per_seat),
        }

    # Determine max columns for null-padding
    max_col = max((s.column for s in seats), default=0)
    sorted_rows = sorted(rows.keys())

    # Split into decks for sleeper buses (rows A-F = lower, G-L = upper)
    if is_sleeper:
        mid = len(sorted_rows) // 2
        lower_rows = sorted_rows[:mid] if mid > 0 else sorted_rows
        upper_rows = sorted_rows[mid:] if mid > 0 else []
    else:
        lower_rows = sorted_rows
        upper_rows = []

    def build_grid(row_keys):
        grid = []
        for row_key in row_keys:
            row_data = []
            for col in range(1, max_col + 1):
                row_data.append(rows.get(row_key, {}).get(col, None))
            grid.append(row_data)
        return grid

    # Legend counts
    legend = {'available': 0, 'booked': 0, 'ladies': 0, 'locked': 0}
    for seat in seats:
        effective_state = seat.state
        if seat.state == 'locked' and seat.is_lock_expired:
            effective_state = 'available'
        if effective_state == 'available':
            legend['available'] += 1
        elif effective_state == 'booked':
            legend['booked'] += 1
        elif effective_state == 'ladies':
            legend['ladies'] += 1
        elif effective_state == 'locked':
            legend['locked'] += 1

    layout = {'lower_deck': build_grid(lower_rows)}
    if upper_rows:
        layout['upper_deck'] = build_grid(upper_rows)

    return Response({
        'success': True,
        'data': {
            'bus_type': bus.bus_type.name if bus.bus_type else 'seater',
            'total_seats': seats.count(),
            'available_seats': legend['available'] + legend['ladies'],
            'layout': layout,
            'legend': legend,
        },
    })


# ── Boarding & Dropping Points ────────────────────────────────────────────────


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('buses')
def boarding_dropping_points(request, bus_id):
    """GET /api/v1/buses/<id>/points/

    Returns boarding and dropping points for a bus route.
    """
    try:
        bus = Bus.objects.get(id=bus_id, is_active=True)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    boarding = BoardingPoint.objects.filter(bus=bus, is_active=True).order_by('time')
    dropping = DroppingPoint.objects.filter(bus=bus, is_active=True).order_by('time')

    return Response({
        'success': True,
        'data': {
            'boarding_points': [
                {
                    'id': bp.id,
                    'name': bp.name,
                    'address': bp.address,
                    'landmark': bp.landmark,
                    'city': bp.city,
                    'time': bp.time.strftime('%H:%M'),
                    'contact_number': bp.contact_number,
                    'latitude': float(bp.latitude) if bp.latitude else None,
                    'longitude': float(bp.longitude) if bp.longitude else None,
                }
                for bp in boarding
            ],
            'dropping_points': [
                {
                    'id': dp.id,
                    'name': dp.name,
                    'address': dp.address,
                    'landmark': dp.landmark,
                    'city': dp.city,
                    'time': dp.time.strftime('%H:%M'),
                    'latitude': float(dp.latitude) if dp.latitude else None,
                    'longitude': float(dp.longitude) if dp.longitude else None,
                }
                for dp in dropping
            ],
        },
    })


# ── Seat Locking ─────────────────────────────────────────────────────────────


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def lock_seats(request, bus_id):
    """POST /api/v1/buses/<id>/lock-seats/

    Body: {"seat_ids": [1, 2, 3]}

    Atomically locks selected seats for the user during checkout.
    Lock expires after 10 minutes (BusSeat.LOCK_TTL_SECONDS).
    """
    seat_ids = request.data.get('seat_ids', [])
    if not seat_ids or not isinstance(seat_ids, list):
        return Response(
            {'success': False, 'error': 'seat_ids required (list of seat IDs)'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(seat_ids) > 6:
        return Response(
            {'success': False, 'error': 'Maximum 6 seats per booking'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        bus = Bus.objects.get(id=bus_id, is_active=True)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    # Release expired locks first
    BusSeat.release_expired_locks()

    locked = []
    failed = []

    with transaction.atomic():
        seats = BusSeat.objects.select_for_update().filter(
            id__in=seat_ids, bus=bus,
        )
        for seat in seats:
            if seat.acquire_lock(request.user, session_ref=f'checkout-{request.user.id}'):
                locked.append(seat.seat_number)
            else:
                failed.append({
                    'seat_number': seat.seat_number,
                    'state': seat.state,
                })

    if failed:
        # Rollback: release any seats we just locked
        BusSeat.objects.filter(
            bus=bus,
            seat_number__in=locked,
            locked_by=request.user,
        ).update(state='available', locked_by=None, locked_at=None, lock_session='')

        return Response({
            'success': False,
            'error': 'Some seats unavailable',
            'locked': [],
            'failed': failed,
        }, status=status.HTTP_409_CONFLICT)

    return Response({
        'success': True,
        'data': {
            'locked_seats': locked,
            'lock_ttl_seconds': BusSeat.LOCK_TTL_SECONDS,
            'message': f'{len(locked)} seats locked for {BusSeat.LOCK_TTL_SECONDS // 60} minutes',
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def release_seats(request, bus_id):
    """POST /api/v1/buses/<id>/release-seats/

    Body: {"seat_ids": [1, 2, 3]}

    Release previously locked seats (e.g., user abandons checkout).
    """
    seat_ids = request.data.get('seat_ids', [])

    released = BusSeat.objects.filter(
        id__in=seat_ids,
        bus_id=bus_id,
        locked_by=request.user,
        state='locked',
    )
    count = 0
    for seat in released:
        seat.release_lock()
        count += 1

    return Response({
        'success': True,
        'data': {'released_count': count},
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def create_booking(request, bus_id):
    seat_ids = request.data.get('seat_ids') or []
    passengers = request.data.get('passengers') or []

    if not seat_ids:
        return Response({'success': False, 'error': 'seat_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
    if passengers and len(passengers) != len(seat_ids):
        return Response({'success': False, 'error': 'passengers count must match seat_ids count'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        bus = Bus.objects.get(id=bus_id, is_active=True)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found'}, status=status.HTTP_404_NOT_FOUND)

    journey_date = request.data.get('journey_date')
    if not journey_date:
        journey_date = bus.journey_date or date.today()

    with transaction.atomic():
        seats = list(BusSeat.objects.select_for_update().filter(bus=bus, id__in=seat_ids))
        if len(seats) != len(seat_ids):
            return Response({'success': False, 'error': 'Invalid seats selected'}, status=status.HTTP_400_BAD_REQUEST)

        for seat in seats:
            if seat.state == BusSeat.BOOKED:
                return Response({'success': False, 'error': f'Seat {seat.seat_number} already booked'}, status=status.HTTP_409_CONFLICT)
            if seat.state == BusSeat.LOCKED and seat.locked_by_id != request.user.id and not seat.is_lock_expired:
                return Response({'success': False, 'error': f'Seat {seat.seat_number} is locked by another user'}, status=status.HTTP_409_CONFLICT)
            if seat.state in (BusSeat.AVAILABLE, BusSeat.LADIES) or seat.is_lock_expired:
                if not seat.acquire_lock(request.user, session_ref=f'bus-booking-{request.user.id}'):
                    return Response({'success': False, 'error': f'Unable to lock seat {seat.seat_number}'}, status=status.HTTP_409_CONFLICT)

        base_amount = Decimal(str(bus.price_per_seat)) * Decimal(len(seats))
        service_fee = (base_amount * Decimal('0.05')).quantize(Decimal('0.01'))
        gst = ((base_amount + service_fee) * Decimal('0.05')).quantize(Decimal('0.01'))
        total = (base_amount + service_fee + gst).quantize(Decimal('0.01'))

        booking = BusBooking.objects.create(
            user=request.user,
            bus=bus,
            journey_date=journey_date,
            contact_email=request.data.get('contact_email') or getattr(request.user, 'email', ''),
            contact_phone=request.data.get('contact_phone') or getattr(request.user, 'phone', ''),
            boarding_point_id=request.data.get('boarding_point_id') or None,
            dropping_point_id=request.data.get('dropping_point_id') or None,
            status=BusBooking.STATUS_CONFIRMED,
            total_amount=total,
            promo_code=request.data.get('promo_code') or '',
        )

        for idx, seat in enumerate(seats):
            passenger = passengers[idx] if idx < len(passengers) else {}
            BusBookingPassenger.objects.create(
                booking=booking,
                seat=seat,
                full_name=passenger.get('full_name') or f'Passenger {idx + 1}',
                age=passenger.get('age') or 30,
                gender=passenger.get('gender') or BusBookingPassenger.MALE,
                phone=passenger.get('phone') or '',
                id_proof_type=passenger.get('id_proof_type') or '',
                id_proof_number=passenger.get('id_proof_number') or '',
            )
            seat.confirm_booking()

        BusPriceBreakdown.objects.create(
            booking=booking,
            base_amount=base_amount,
            service_fee=service_fee,
            gst=gst,
            promo_discount=Decimal('0.00'),
            total_amount=total,
        )

    return Response(
        {
            'success': True,
            'data': {
                'booking_uuid': str(booking.uuid),
                'public_booking_id': booking.public_booking_id,
                'pnr': booking.pnr,
                'status': booking.status,
                'total_amount': str(booking.total_amount),
                'seat_numbers': [seat.seat_number for seat in seats],
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def booking_detail(request, booking_uuid):
    try:
        booking = BusBooking.objects.select_related('bus', 'boarding_point', 'dropping_point').prefetch_related('passengers__seat').get(uuid=booking_uuid)
    except BusBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.user_id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
        return Response({'success': False, 'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    breakdown = getattr(booking, 'price_breakdown', None)
    return Response(
        {
            'success': True,
            'data': {
                'booking_uuid': str(booking.uuid),
                'public_booking_id': booking.public_booking_id,
                'pnr': booking.pnr,
                'status': booking.status,
                'journey_date': str(booking.journey_date),
                'bus': _serialize_bus(booking.bus, booking.journey_date),
                'boarding_point': booking.boarding_point.name if booking.boarding_point else '',
                'dropping_point': booking.dropping_point.name if booking.dropping_point else '',
                'passengers': [
                    {
                        'full_name': p.full_name,
                        'age': p.age,
                        'gender': p.gender,
                        'seat_number': p.seat.seat_number,
                    }
                    for p in booking.passengers.all()
                ],
                'price_breakdown': {
                    'base_amount': str(breakdown.base_amount) if breakdown else str(booking.total_amount),
                    'service_fee': str(breakdown.service_fee) if breakdown else '0.00',
                    'gst': str(breakdown.gst) if breakdown else '0.00',
                    'promo_discount': str(breakdown.promo_discount) if breakdown else '0.00',
                    'total_amount': str(breakdown.total_amount) if breakdown else str(booking.total_amount),
                },
            },
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def booking_tracking(request, booking_uuid):
    try:
        booking = BusBooking.objects.select_related('bus').get(uuid=booking_uuid)
    except BusBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.user_id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
        return Response({'success': False, 'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    timeline = list(
        booking.history.order_by('created_at').values('from_status', 'to_status', 'note', 'created_at')
    )
    return Response(
        {
            'success': True,
            'data': {
                'booking_uuid': str(booking.uuid),
                'status': booking.status,
                'pnr': booking.pnr,
                'from_city': booking.bus.from_city,
                'to_city': booking.bus.to_city,
                'departure_time': booking.bus.departure_time.strftime('%H:%M'),
                'arrival_time': booking.bus.arrival_time.strftime('%H:%M'),
                'timeline': timeline,
            },
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_service_enabled('buses')
def cancel_booking(request, booking_uuid):
    try:
        booking = BusBooking.objects.prefetch_related('passengers__seat').get(uuid=booking_uuid)
    except BusBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.user_id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
        return Response({'success': False, 'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    if booking.status not in [BusBooking.STATUS_PENDING, BusBooking.STATUS_REVIEW, BusBooking.STATUS_PAYMENT, BusBooking.STATUS_CONFIRMED]:
        return Response({'success': False, 'error': 'Booking cannot be cancelled in current status'}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = BusBooking.STATUS_CANCELLED
    booking.save(update_fields=['status', 'updated_at'])
    for passenger in booking.passengers.all():
        seat = passenger.seat
        seat.release_lock()

    return Response({'success': True, 'data': {'booking_uuid': str(booking.uuid), 'status': booking.status}})
