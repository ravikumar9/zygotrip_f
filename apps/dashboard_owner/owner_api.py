from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.hotels.models import Property
from apps.rooms.models import RoomType
from apps.booking.models import Booking


def _is_owner_or_admin(user):
    return user.is_authenticated and (getattr(user, 'role', '') == 'property_owner' or user.is_staff or user.is_superuser)


def _forbidden():
    return Response({'success': False, 'error': 'Only property owners can access this API.'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_properties_list(request):
    if not _is_owner_or_admin(request.user):
        return _forbidden()

    qs = Property.objects.all() if (request.user.is_staff or request.user.is_superuser) else Property.objects.filter(owner=request.user)
    rows = []
    for prop in qs.order_by('-created_at'):
        rows.append(
            {
                'id': prop.id,
                'uuid': str(prop.uuid),
                'name': prop.name,
                'city': getattr(prop.city, 'name', ''),
                'status': prop.status,
                'commission_percentage': float(prop.commission_percentage),
                'agreement_signed': prop.agreement_signed,
                'is_active': prop.is_active,
            }
        )
    return Response({'success': True, 'data': rows})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def owner_property_create(request):
    if not _is_owner_or_admin(request.user):
        return _forbidden()

    payload = request.data
    required = ['name', 'city_id', 'address', 'description', 'latitude', 'longitude']
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return Response({'success': False, 'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    prop = Property.objects.create(
        owner=request.user,
        name=payload.get('name'),
        city_id=payload.get('city_id'),
        address=payload.get('address'),
        description=payload.get('description'),
        latitude=payload.get('latitude'),
        longitude=payload.get('longitude'),
        property_type=payload.get('property_type') or 'Hotel',
        area=payload.get('area') or '',
        landmark=payload.get('landmark') or '',
        status='pending',
    )
    return Response({'success': True, 'data': {'id': prop.id, 'uuid': str(prop.uuid)}}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def owner_property_update(request, property_id):
    if not _is_owner_or_admin(request.user):
        return _forbidden()

    try:
        prop = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        return Response({'success': False, 'error': 'Property not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and prop.owner_id != request.user.id:
        return _forbidden()

    for field in ['name', 'address', 'description', 'area', 'landmark', 'property_type', 'status', 'agreement_signed', 'is_active']:
        if field in request.data:
            setattr(prop, field, request.data.get(field))
    if 'commission_percentage' in request.data:
        prop.commission_percentage = request.data.get('commission_percentage')
    prop.save()

    return Response({'success': True, 'data': {'id': prop.id, 'uuid': str(prop.uuid)}})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def owner_property_delete(request, property_id):
    if not _is_owner_or_admin(request.user):
        return _forbidden()

    try:
        prop = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        return Response({'success': False, 'error': 'Property not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and prop.owner_id != request.user.id:
        return _forbidden()

    prop.delete()
    return Response({'success': True, 'data': {'deleted': True}})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_dashboard_summary(request):
    if not _is_owner_or_admin(request.user):
        return _forbidden()

    properties = Property.objects.all() if (request.user.is_staff or request.user.is_superuser) else Property.objects.filter(owner=request.user)
    bookings = Booking.objects.filter(property__in=properties)
    room_types = RoomType.objects.filter(property__in=properties)

    total_revenue = bookings.filter(status__in=['confirmed', 'checked_in', 'checked_out', 'settled']).aggregate(total=Sum('total_amount'))['total'] or 0
    return Response(
        {
            'success': True,
            'data': {
                'property_count': properties.count(),
                'room_type_count': room_types.count(),
                'booking_count': bookings.count(),
                'confirmed_count': bookings.filter(status='confirmed').count(),
                'total_revenue': float(total_revenue),
                'pending_approvals': properties.filter(status='pending').count(),
            },
        }
    )
