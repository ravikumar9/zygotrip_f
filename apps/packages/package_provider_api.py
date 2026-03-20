from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.packages.models import Package, PackageBooking


def _is_provider_or_admin(user):
    return user.is_authenticated and (getattr(user, 'role', '') == 'package_provider' or user.is_staff or user.is_superuser)


def _forbidden():
    return Response({'success': False, 'error': 'Only package providers can access this API.'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def package_provider_dashboard(request):
    if not _is_provider_or_admin(request.user):
        return _forbidden()

    packages = Package.objects.all() if (request.user.is_staff or request.user.is_superuser) else Package.objects.filter(provider=request.user)
    bookings = PackageBooking.objects.filter(package__in=packages)
    total = bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_amount'))['total'] or 0
    return Response({'success': True, 'data': {'package_count': packages.count(), 'booking_count': bookings.count(), 'confirmed_booking_count': bookings.filter(status='confirmed').count(), 'gross_revenue': float(total)}})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def package_list(request):
    if not _is_provider_or_admin(request.user):
        return _forbidden()

    packages = Package.objects.all() if (request.user.is_staff or request.user.is_superuser) else Package.objects.filter(provider=request.user)
    data = []
    for pkg in packages.order_by('-created_at'):
        data.append({'id': pkg.id, 'slug': pkg.slug, 'name': pkg.name, 'destination': pkg.destination, 'duration_days': pkg.duration_days, 'base_price': float(pkg.base_price), 'rating': float(pkg.rating), 'is_active': pkg.is_active})
    return Response({'success': True, 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def package_create(request):
    if not _is_provider_or_admin(request.user):
        return _forbidden()

    payload = request.data
    required = ['name', 'description', 'destination', 'duration_days', 'base_price']
    missing = [key for key in required if payload.get(key) in [None, '']]
    if missing:
        return Response({'success': False, 'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    pkg = Package.objects.create(
        provider=request.user,
        category_id=payload.get('category_id') or None,
        name=payload.get('name'),
        description=payload.get('description'),
        destination=payload.get('destination'),
        duration_days=payload.get('duration_days'),
        base_price=payload.get('base_price'),
        inclusions=payload.get('inclusions') or '',
        exclusions=payload.get('exclusions') or '',
        image_url=payload.get('image_url') or '',
    )
    return Response({'success': True, 'data': {'id': pkg.id, 'slug': pkg.slug}}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def package_update(request, package_id):
    if not _is_provider_or_admin(request.user):
        return _forbidden()

    try:
        pkg = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        return Response({'success': False, 'error': 'Package not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and pkg.provider_id != request.user.id:
        return _forbidden()

    for field in ['name', 'description', 'destination', 'duration_days', 'base_price', 'inclusions', 'exclusions', 'max_group_size', 'difficulty_level', 'hotel_included', 'meals_included', 'transport_included', 'guide_included', 'is_active']:
        if field in request.data:
            setattr(pkg, field, request.data.get(field))
    if 'category_id' in request.data:
        pkg.category_id = request.data.get('category_id')
    pkg.save()
    return Response({'success': True, 'data': {'id': pkg.id, 'slug': pkg.slug}})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def package_delete(request, package_id):
    if not _is_provider_or_admin(request.user):
        return _forbidden()

    try:
        pkg = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        return Response({'success': False, 'error': 'Package not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (request.user.is_staff or request.user.is_superuser) and pkg.provider_id != request.user.id:
        return _forbidden()

    pkg.delete()
    return Response({'success': True, 'data': {'deleted': True}})
