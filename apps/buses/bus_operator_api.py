from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.buses.models import Bus, BusBooking


def _is_operator_or_admin(user):
    return user.is_authenticated and (getattr(user, 'role', '') == 'bus_operator' or user.is_staff or user.is_superuser)


def _forbidden():
    return Response({'success': False, 'error': 'Only bus operators can access this API.'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def operator_dashboard(request):
    if not _is_operator_or_admin(request.user):
        return _forbidden()

    buses = Bus.objects.all() if (request.user.is_staff or request.user.is_superuser) else Bus.objects.filter(operator=request.user)
    bookings = BusBooking.objects.filter(bus__in=buses)
    gross = bookings.filter(status='confirmed').aggregate(total=Sum('total_amount'))['total'] or 0

    return Response({'success': True, 'data': {'bus_count': buses.count(), 'booking_count': bookings.count(), 'confirmed_booking_count': bookings.filter(status='confirmed').count(), 'gross_revenue': float(gross)}})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buses_list(request):
    if not _is_operator_or_admin(request.user):
        return _forbidden()
    buses = Bus.objects.all() if (request.user.is_staff or request.user.is_superuser) else Bus.objects.filter(operator=request.user)
    data = []
    for bus in buses.order_by('-created_at'):
        data.append({'id': bus.id, 'uuid': str(bus.uuid), 'registration_number': bus.registration_number, 'operator_name': bus.operator_name, 'from_city': bus.from_city, 'to_city': bus.to_city, 'price_per_seat': float(bus.price_per_seat), 'available_seats': bus.available_seats, 'is_active': bus.is_active})
    return Response({'success': True, 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bus_create(request):
    if not _is_operator_or_admin(request.user):
        return _forbidden()

    payload = request.data
    required = ['registration_number', 'bus_type_id', 'operator_name', 'from_city', 'to_city', 'departure_time', 'arrival_time', 'price_per_seat', 'available_seats']
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return Response({'success': False, 'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    bus = Bus.objects.create(
        operator=request.user,
        registration_number=payload.get('registration_number'),
        bus_type_id=payload.get('bus_type_id'),
        operator_name=payload.get('operator_name'),
        from_city=payload.get('from_city'),
        to_city=payload.get('to_city'),
        departure_time=payload.get('departure_time'),
        arrival_time=payload.get('arrival_time'),
        journey_date=payload.get('journey_date') or None,
        price_per_seat=payload.get('price_per_seat'),
        available_seats=payload.get('available_seats'),
        amenities=payload.get('amenities') or '',
    )
    return Response({'success': True, 'data': {'id': bus.id, 'uuid': str(bus.uuid)}}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def bus_update(request, bus_id):
    if not _is_operator_or_admin(request.user):
        return _forbidden()

    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and bus.operator_id != request.user.id:
        return _forbidden()

    for field in ['operator_name', 'from_city', 'to_city', 'departure_time', 'arrival_time', 'journey_date', 'price_per_seat', 'available_seats', 'amenities', 'is_active']:
        if field in request.data:
            setattr(bus, field, request.data.get(field))
    if 'bus_type_id' in request.data:
        bus.bus_type_id = request.data.get('bus_type_id')
    bus.save()
    return Response({'success': True, 'data': {'id': bus.id}})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def bus_delete(request, bus_id):
    if not _is_operator_or_admin(request.user):
        return _forbidden()

    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        return Response({'success': False, 'error': 'Bus not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and bus.operator_id != request.user.id:
        return _forbidden()

    bus.delete()
    return Response({'success': True, 'data': {'deleted': True}})
