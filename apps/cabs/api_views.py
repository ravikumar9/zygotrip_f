"""
Cab REST API — JSON endpoints for the Next.js frontend.

Endpoints:
  GET  /api/v1/cabs/search/           → Search cabs by city + date
  GET  /api/v1/cabs/<id>/             → Cab detail
  GET  /api/v1/cabs/cities/           → Available cities
  GET  /api/v1/cabs/<id>/availability/ → Check availability by date
"""
import logging
from datetime import datetime
from decimal import Decimal
from django.db.models import Q, Min, Avg
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from .models import Cab, CabImage, CabAvailability, CabType, CITY_CHOICES, CabBooking, CabTrip
from apps.core.service_guard import require_service_enabled

logger = logging.getLogger('zygotrip.cabs')

VEHICLE_CATEGORIES = {
    'hatchback': {'label': 'Hatchback', 'seats_range': (2, 4), 'icon': '🚗'},
    'sedan':     {'label': 'Sedan',     'seats_range': (4, 5), 'icon': '🚘'},
    'suv':       {'label': 'SUV',       'seats_range': (6, 8), 'icon': '🚙'},
    'luxury':    {'label': 'Luxury',    'seats_range': (4, 8), 'icon': '✨'},
}


def _categorize_cab(cab):
    """Map cab seats to vehicle category."""
    seats = cab.seats or 5
    if seats <= 4:
        return 'hatchback'
    elif seats <= 5:
        return 'sedan'
    elif seats <= 8:
        return 'suv'
    else:
        return 'luxury'


def _serialize_cab(cab):
    """Serialize a Cab to JSON for frontend."""
    primary_image = cab.images.filter(is_primary=True).first()
    image_url = primary_image.image.url if primary_image and primary_image.image else ''
    category = _categorize_cab(cab)
    cat_info = VEHICLE_CATEGORIES.get(category, VEHICLE_CATEGORIES['sedan'])

    return {
        'id': cab.id,
        'uuid': str(cab.uuid),
        'name': cab.name,
        'city': cab.city,
        'city_display': dict(CITY_CHOICES).get(cab.city, cab.city),
        'seats': cab.seats,
        'fuel_type': cab.fuel_type,
        'base_price_per_km': float(cab.base_price_per_km),
        'price_per_km': float(cab.system_price_per_km),
        'image_url': image_url,
        'category': category,
        'category_label': cat_info['label'],
        'category_icon': cat_info['icon'],
        'is_active': cab.is_active,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def search_cabs(request):
    """
    GET /api/v1/cabs/search/?city=bangalore&date=2026-03-15&category=sedan&sort=price
    """
    city = request.GET.get('city', '').strip().lower()
    date_str = request.GET.get('date', '')
    category = request.GET.get('category', '')
    sort = request.GET.get('sort', 'price')
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 50)

    qs = Cab.objects.filter(is_active=True).prefetch_related('images')

    if city:
        qs = qs.filter(city__icontains=city)

    # Filter by availability on date
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            unavailable_ids = CabAvailability.objects.filter(
                date=target_date, is_available=False
            ).values_list('cab_id', flat=True)
            qs = qs.exclude(id__in=unavailable_ids)
        except ValueError:
            pass

    # Filter by vehicle category
    if category:
        cat_info = VEHICLE_CATEGORIES.get(category)
        if cat_info:
            lo, hi = cat_info['seats_range']
            qs = qs.filter(seats__gte=lo, seats__lte=hi)

    # Sorting
    sort_map = {
        'price': 'system_price_per_km',
        'price_desc': '-system_price_per_km',
        'seats': '-seats',
        'name': 'name',
    }
    qs = qs.order_by(sort_map.get(sort, 'system_price_per_km'))

    total = qs.count()
    offset = (page - 1) * per_page
    cabs = qs[offset:offset + per_page]

    return Response({
        'success': True,
        'data': {
            'cabs': [_serialize_cab(c) for c in cabs],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'filters': {
                'cities': [{'value': k, 'label': v} for k, v in CITY_CHOICES],
                'categories': [
                    {'value': k, 'label': v['label'], 'icon': v['icon']}
                    for k, v in VEHICLE_CATEGORIES.items()
                ],
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def cab_detail(request, cab_id):
    """GET /api/v1/cabs/<id>/"""
    try:
        cab = Cab.objects.prefetch_related('images', 'availability').get(id=cab_id, is_active=True)
    except Cab.DoesNotExist:
        return Response({'success': False, 'error': 'Cab not found'}, status=http_status.HTTP_404_NOT_FOUND)

    data = _serialize_cab(cab)

    # All images
    data['images'] = [
        {'id': img.id, 'url': img.image.url if img.image else '', 'is_primary': img.is_primary}
        for img in cab.images.all()
    ]

    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def cab_availability(request, cab_id):
    """GET /api/v1/cabs/<id>/availability/?month=2026-03"""
    try:
        cab = Cab.objects.get(id=cab_id, is_active=True)
    except Cab.DoesNotExist:
        return Response({'success': False, 'error': 'Cab not found'}, status=http_status.HTTP_404_NOT_FOUND)

    month_str = request.GET.get('month', '')
    avail = CabAvailability.objects.filter(cab=cab)
    if month_str:
        try:
            year, month = month_str.split('-')
            avail = avail.filter(date__year=int(year), date__month=int(month))
        except (ValueError, IndexError):
            pass

    return Response({
        'success': True,
        'data': [
            {'date': str(a.date), 'is_available': a.is_available}
            for a in avail.order_by('date')
        ],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def available_cities(request):
    """GET /api/v1/cabs/cities/"""
    cities = (
        Cab.objects.filter(is_active=True)
        .values_list('city', flat=True)
        .distinct()
    )
    city_dict = dict(CITY_CHOICES)
    return Response({
        'success': True,
        'data': [
            {'value': c, 'label': city_dict.get(c, c)}
            for c in sorted(set(cities))
        ],
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def book_cab(request):
    """POST /api/v1/cabs/book/"""
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=http_status.HTTP_403_FORBIDDEN)

    cab_id = request.data.get('cab_id')
    pickup_address = request.data.get('pickup_address', '').strip()
    dropoff_address = request.data.get('dropoff_address', '').strip()
    pickup_date = request.data.get('pickup_date', '')

    if not cab_id or not pickup_address or not dropoff_address or not pickup_date:
        return Response({'error': 'cab_id, pickup_address, dropoff_address and pickup_date are required'}, status=http_status.HTTP_400_BAD_REQUEST)

    try:
        cab = Cab.objects.get(id=cab_id, is_active=True)
    except Cab.DoesNotExist:
        return Response({'error': 'Cab not found'}, status=http_status.HTTP_404_NOT_FOUND)

    try:
        booking_date = datetime.strptime(pickup_date, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid pickup_date format'}, status=http_status.HTTP_400_BAD_REQUEST)

    availability, _ = CabAvailability.objects.get_or_create(
        cab=cab,
        date=booking_date,
        defaults={'is_available': True},
    )
    if not availability.is_available:
        return Response({'error': 'Cab is not available for the selected date'}, status=http_status.HTTP_400_BAD_REQUEST)

    booking = CabBooking.objects.create(
        cab=cab,
        user=request.user,
        booking_date=booking_date,
        pickup_address=pickup_address,
        drop_address=dropoff_address,
        distance_km=Decimal('10.00'),
        base_fare=Decimal('50.00'),
        price_per_km=cab.system_price_per_km,
        total_price=Decimal('0.00'),
        final_price=Decimal('0.00'),
        status='confirmed',
    )
    availability.is_available = False
    availability.save(update_fields=['is_available', 'updated_at'])

    return Response({
        'booking_uuid': str(booking.uuid),
        'public_booking_id': booking.public_booking_id,
        'status': 'searching',
    }, status=http_status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def booking_tracking(request, booking_uuid):
    """GET /api/v1/cabs/bookings/<uuid>/tracking/"""
    try:
        booking = CabBooking.objects.select_related('driver').get(uuid=booking_uuid)
    except CabBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=http_status.HTTP_404_NOT_FOUND)

    trip = getattr(booking, 'trip', None)
    if trip:
        status_map = {
            'driver_assigned': 'driver_found',
            'en_route_pickup': 'driver_accepted',
            'arrived_pickup': 'arrived',
            'trip_started': 'in_trip',
            'trip_completed': 'completed',
            'trip_cancelled': 'completed',
        }
        driver = trip.driver
        driver_name = getattr(driver.user, 'full_name', '')
        if not driver_name and hasattr(driver.user, 'get_full_name'):
            driver_name = driver.user.get_full_name()
        if not driver_name:
            driver_name = str(driver.user)
        return Response({
            'status': status_map.get(trip.trip_status, 'driver_found'),
            'driver': {
                'name': driver_name,
                'phone': driver.phone,
                'rating': float(driver.rating),
                'trips_completed': driver.total_trips,
                'vehicle_number': getattr(driver.cab, 'name', ''),
                'otp': trip.otp_code,
            },
            'eta_minutes': trip.eta_minutes,
            'lat': trip.current_latitude,
            'lng': trip.current_longitude,
        })

    return Response({'status': 'searching'})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def booking_detail(request, booking_uuid):
    try:
        booking = CabBooking.objects.select_related('cab', 'driver').get(uuid=booking_uuid)
    except CabBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=http_status.HTTP_404_NOT_FOUND)

    if booking.user_id != getattr(request.user, 'id', None) and not getattr(request.user, 'is_staff', False):
        return Response({'success': False, 'error': 'Forbidden'}, status=http_status.HTTP_403_FORBIDDEN)

    return Response(
        {
            'success': True,
            'data': {
                'booking_uuid': str(booking.uuid),
                'public_booking_id': booking.public_booking_id,
                'status': booking.status,
                'booking_date': str(booking.booking_date),
                'pickup_address': booking.pickup_address,
                'drop_address': booking.drop_address,
                'distance_km': float(booking.distance_km),
                'final_price': float(booking.final_price),
                'cab': _serialize_cab(booking.cab),
                'driver_id': booking.driver_id,
            },
        }
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('cabs')
def cancel_booking(request, booking_uuid):
    try:
        booking = CabBooking.objects.get(uuid=booking_uuid)
    except CabBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=http_status.HTTP_404_NOT_FOUND)

    if booking.user_id != getattr(request.user, 'id', None) and not getattr(request.user, 'is_staff', False):
        return Response({'success': False, 'error': 'Forbidden'}, status=http_status.HTTP_403_FORBIDDEN)

    if booking.status in ['completed', 'cancelled']:
        return Response({'success': False, 'error': 'Booking cannot be cancelled'}, status=http_status.HTTP_400_BAD_REQUEST)

    booking.status = 'cancelled'
    booking.save(update_fields=['status', 'updated_at'])

    avail, _ = CabAvailability.objects.get_or_create(cab=booking.cab, date=booking.booking_date)
    avail.is_available = True
    avail.save(update_fields=['is_available', 'updated_at'])

    return Response({'success': True, 'data': {'booking_uuid': str(booking.uuid), 'status': booking.status}})
