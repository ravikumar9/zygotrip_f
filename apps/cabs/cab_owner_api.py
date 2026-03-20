from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.cabs.models import Cab, CabBooking


def _is_cab_owner_or_admin(user):
    return user.is_authenticated and (getattr(user, 'role', '') == 'cab_owner' or user.is_staff or user.is_superuser)


def _forbidden():
    return Response({'success': False, 'error': 'Only cab owners can access this API.'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cab_owner_dashboard(request):
    if not _is_cab_owner_or_admin(request.user):
        return _forbidden()

    cabs = Cab.objects.all() if (request.user.is_staff or request.user.is_superuser) else Cab.objects.filter(owner=request.user)
    bookings = CabBooking.objects.filter(cab__in=cabs)
    total = bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('final_price'))['total'] or 0
    return Response({'success': True, 'data': {'cab_count': cabs.count(), 'booking_count': bookings.count(), 'active_bookings': bookings.filter(status='confirmed').count(), 'gross_revenue': float(total)}})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cabs_list(request):
    if not _is_cab_owner_or_admin(request.user):
        return _forbidden()

    cabs = Cab.objects.all() if (request.user.is_staff or request.user.is_superuser) else Cab.objects.filter(owner=request.user)
    data = []
    for cab in cabs.order_by('-created_at'):
        data.append({'id': cab.id, 'uuid': str(cab.uuid), 'name': cab.name, 'city': cab.city, 'seats': cab.seats, 'fuel_type': cab.fuel_type, 'base_price_per_km': float(cab.base_price_per_km), 'system_price_per_km': float(cab.system_price_per_km), 'is_active': cab.is_active})
    return Response({'success': True, 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cab_create(request):
    if not _is_cab_owner_or_admin(request.user):
        return _forbidden()

    payload = request.data
    required = ['name', 'city', 'seats', 'fuel_type', 'base_price_per_km']
    missing = [key for key in required if payload.get(key) in [None, '']]
    if missing:
        return Response({'success': False, 'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    cab = Cab.objects.create(
        owner=request.user,
        name=payload.get('name'),
        city=payload.get('city'),
        seats=payload.get('seats'),
        fuel_type=payload.get('fuel_type'),
        base_price_per_km=payload.get('base_price_per_km'),
        system_price_per_km=payload.get('system_price_per_km') or payload.get('base_price_per_km'),
        cab_type_id=payload.get('cab_type_id') or None,
    )
    return Response({'success': True, 'data': {'id': cab.id, 'uuid': str(cab.uuid)}}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def cab_update(request, cab_id):
    if not _is_cab_owner_or_admin(request.user):
        return _forbidden()

    try:
        cab = Cab.objects.get(id=cab_id)
    except Cab.DoesNotExist:
        return Response({'success': False, 'error': 'Cab not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and cab.owner_id != request.user.id:
        return _forbidden()

    for field in ['name', 'city', 'seats', 'fuel_type', 'base_price_per_km', 'system_price_per_km', 'is_active']:
        if field in request.data:
            setattr(cab, field, request.data.get(field))
    if 'cab_type_id' in request.data:
        cab.cab_type_id = request.data.get('cab_type_id')
    cab.save()
    return Response({'success': True, 'data': {'id': cab.id}})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cab_delete(request, cab_id):
    if not _is_cab_owner_or_admin(request.user):
        return _forbidden()

    try:
        cab = Cab.objects.get(id=cab_id)
    except Cab.DoesNotExist:
        return Response({'success': False, 'error': 'Cab not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and cab.owner_id != request.user.id:
        return _forbidden()

    cab.delete()
    return Response({'success': True, 'data': {'deleted': True}})
