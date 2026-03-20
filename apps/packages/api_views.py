"""
Package REST API — JSON endpoints for the Next.js frontend.

Endpoints:
  GET  /api/v1/packages/search/        → Search packages
  GET  /api/v1/packages/<slug>/        → Package detail
  GET  /api/v1/packages/destinations/  → Popular destinations
  GET  /api/v1/packages/categories/    → Package categories
"""
import logging
from django.db.models import Q, Avg, Min
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from apps.core.service_guard import require_service_enabled
from .models import (
    Package, PackageCategory, PackageImage, PackageItinerary,
    PackageAddon, PackageSeasonalPrice, PackageDeparture, PackageBundleCalculator,
    PackageBooking,
)
from .availability_engine import book_package_slot

logger = logging.getLogger('zygotrip.packages')


def _serialize_package(pkg, detail=False):
    """Serialize a Package to JSON for frontend."""
    featured_img = pkg.images.filter(is_featured=True).first()
    image_url = featured_img.image_url if featured_img else pkg.image_url or ''

    inclusions = [i.strip() for i in (pkg.inclusions or '').split(',') if i.strip()]
    tags = []
    if pkg.hotel_included:
        tags.append('Hotel')
    if pkg.meals_included:
        tags.append('Meals')
    if pkg.transport_included:
        tags.append('Transport')
    if pkg.guide_included:
        tags.append('Guide')

    data = {
        'id': pkg.id,
        'slug': pkg.slug,
        'name': pkg.name,
        'destination': pkg.destination,
        'description': pkg.description[:200] + '...' if len(pkg.description) > 200 and not detail else pkg.description,
        'duration_days': pkg.duration_days,
        'duration_nights': max(pkg.duration_days - 1, 0),
        'base_price': float(pkg.base_price),
        'price_adult': float(pkg.base_price),
        'price_child': round(float(pkg.base_price) * 0.7, 2),
        'rating': float(pkg.rating),
        'review_count': pkg.review_count,
        'image_url': image_url,
        'difficulty_level': pkg.difficulty_level,
        'max_group_size': pkg.max_group_size,
        'category': pkg.category.name if pkg.category else '',
        'category_slug': pkg.category.slug if pkg.category else '',
        'tags': tags,
        'highlights': inclusions[:6],
        'inclusions_summary': inclusions[:4],
    }

    if detail:
        data['inclusions'] = inclusions
        data['exclusions'] = [e.strip() for e in (pkg.exclusions or '').split(',') if e.strip()]
        data['images'] = [
            {'url': img.image_url, 'is_featured': img.is_featured}
            for img in pkg.images.all().order_by('-is_featured', 'display_order')
        ]
        data['itinerary'] = [
            {
                'day': it.day_number,
                'title': it.title,
                'description': it.description,
                'accommodation': it.accommodation or '',
                'meals_included': it.meals_included or '',
                'location': '',
                'activities': [],
                'meals': [it.meals_included] if it.meals_included else [],
                'hotel': it.accommodation or '',
            }
            for it in pkg.itinerary.filter(is_active=True).order_by('day_number')
        ]

    return data


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def search_packages(request):
    """
    GET /api/v1/packages/search/?destination=Goa&duration=3-5&budget=5000-15000&category=adventure&sort=price
    """
    destination = request.GET.get('destination', '').strip()
    category_slug = request.GET.get('category', '')
    duration = request.GET.get('duration', '')
    budget = request.GET.get('budget', '')
    difficulty = request.GET.get('difficulty', '')
    sort = request.GET.get('sort', 'popular')
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 50)

    qs = Package.objects.filter(is_active=True).select_related('category').prefetch_related('images')

    if destination:
        qs = qs.filter(destination__icontains=destination)

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if duration:
        try:
            parts = duration.split('-')
            if len(parts) == 2:
                qs = qs.filter(duration_days__gte=int(parts[0]), duration_days__lte=int(parts[1]))
            else:
                qs = qs.filter(duration_days=int(parts[0]))
        except (ValueError, IndexError):
            pass

    if budget:
        try:
            parts = budget.split('-')
            if len(parts) == 2:
                qs = qs.filter(base_price__gte=int(parts[0]), base_price__lte=int(parts[1]))
        except (ValueError, IndexError):
            pass

    if difficulty:
        qs = qs.filter(difficulty_level=difficulty)

    # Sorting
    sort_map = {
        'price': 'base_price',
        'price_desc': '-base_price',
        'rating': '-rating',
        'duration': 'duration_days',
        'popular': '-review_count',
    }
    qs = qs.order_by(sort_map.get(sort, '-review_count'))

    total = qs.count()
    offset = (page - 1) * per_page
    packages = qs[offset:offset + per_page]

    # Collect filter options
    destinations = Package.objects.filter(is_active=True).values_list('destination', flat=True).distinct()[:20]
    categories = PackageCategory.objects.filter(is_active=True).values('name', 'slug')

    return Response({
        'success': True,
        'data': {
            'packages': [_serialize_package(p) for p in packages],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'filters': {
                'destinations': sorted(set(destinations)),
                'categories': list(categories),
                'durations': ['1-2', '3-5', '6-10', '10+'],
                'difficulties': ['easy', 'moderate', 'challenging'],
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def package_detail(request, slug):
    """GET /api/v1/packages/<slug>/"""
    try:
        pkg = Package.objects.select_related('category').prefetch_related(
            'images', 'itinerary'
        ).get(slug=slug, is_active=True)
    except Package.DoesNotExist:
        return Response({'success': False, 'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

    # Include add-ons and departures in detail response
    data = _serialize_package(pkg, detail=True)

    # Add-ons
    addons = PackageAddon.objects.filter(package=pkg, is_active=True)
    data['addons'] = [
        {
            'id': a.id,
            'addon_type': a.addon_type,
            'name': a.name,
            'description': a.description,
            'price': float(a.price),
            'pricing_type': a.pricing_type,
            'max_quantity': a.max_quantity,
            'is_popular': a.is_popular,
            'bundle_discount_pct': float(a.bundle_discount_pct),
        }
        for a in addons
    ]

    # Upcoming departures
    upcoming = PackageDeparture.objects.filter(
        package=pkg, is_active=True, departure_date__gte=timezone.now().date(),
    ).order_by('departure_date')[:10]
    data['departures'] = [
        {
            'id': dep.id,
            'departure_date': str(dep.departure_date),
            'return_date': str(dep.return_date),
            'available_slots': dep.available_slots,
            'is_guaranteed': dep.is_guaranteed,
            'is_sold_out': dep.is_sold_out,
        }
        for dep in upcoming
    ]

    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def package_availability(request, package_id):
    """GET /api/v1/packages/<id>/availability/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD"""
    from datetime import datetime

    try:
        pkg = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return Response({'success': False, 'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else timezone.now().date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return Response({'success': False, 'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)

    departures = PackageDeparture.objects.filter(
        package=pkg,
        departure_date__gte=start_date,
        is_active=True,
    ).order_by('departure_date')
    if end_date:
        departures = departures.filter(departure_date__lte=end_date)

    calendar = []
    for dep in departures:
        calendar.append({
            'date': str(dep.departure_date),
            'available_slots': dep.available_slots,
            'price_adult': float(pkg.base_price),
            'price_child': round(float(pkg.base_price) * 0.7, 2),
            'season': 'regular',
            'is_sold_out': dep.is_sold_out,
        })

    return Response({'success': True, 'calendar': calendar})


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def package_book(request):
    """POST /api/v1/packages/book/"""
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

    package_id = request.data.get('package_id')
    departure_date = request.data.get('departure_date')
    adults = int(request.data.get('adults', 1) or 1)
    children = int(request.data.get('children', 0) or 0)
    addon_ids = request.data.get('addon_ids', []) or []

    try:
        pkg = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        departure = PackageDeparture.objects.get(
            package=pkg,
            departure_date=departure_date,
            is_active=True,
        )
    except PackageDeparture.DoesNotExist:
        return Response({'error': 'Departure not found'}, status=status.HTTP_404_NOT_FOUND)

    success, result = book_package_slot(pkg.id, departure.id, adults, children, request.user, addons=addon_ids)
    if not success:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    booking = PackageBooking.objects.get(id=result['booking_id'])
    return Response({
        'booking_id': booking.id,
        'uuid': str(booking.uuid),
        'public_booking_id': booking.public_booking_id,
        'total_amount': str(booking.total_amount),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def bundle_pricing(request, slug):
    """POST /api/v1/packages/<slug>/bundle-pricing/

    Body: {
      "travel_date": "2025-03-15",   // optional
      "adults": 2,
      "children": 1,
      "addon_ids": [5, 8]              // optional, returns recommended if empty
    }

    Returns dynamic bundle pricing with breakdown.
    """
    try:
        pkg = Package.objects.get(slug=slug, is_active=True)
    except Package.DoesNotExist:
        return Response({'success': False, 'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

    adults = int(request.data.get('adults', 1))
    children = int(request.data.get('children', 0))
    travel_date_str = request.data.get('travel_date', '')
    addon_ids = request.data.get('addon_ids', [])

    travel_date = None
    if travel_date_str:
        try:
            from datetime import datetime as dt
            travel_date = dt.strptime(travel_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if addon_ids:
        # Calculate specific bundle
        calc = PackageBundleCalculator(pkg, travel_date, adults, children)
        for aid in addon_ids:
            try:
                calc.add_addon(addon_id=aid)
            except PackageAddon.DoesNotExist:
                continue
        result = calc.calculate()
        return Response({'success': True, 'data': result})
    else:
        # Return recommended bundles
        bundles = PackageBundleCalculator.recommended_bundles(
            pkg, travel_date, adults, children, top_n=3,
        )
        return Response({'success': True, 'data': {'recommended_bundles': bundles}})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def popular_destinations(request):
    """GET /api/v1/packages/destinations/"""
    destinations = (
        Package.objects.filter(is_active=True)
        .values('destination')
        .annotate(
            count=Min('id'),  # just for grouping
            avg_price=Avg('base_price'),
            avg_rating=Avg('rating'),
        )
        .order_by('-avg_rating')[:15]
    )
    return Response({
        'success': True,
        'data': [
            {
                'destination': d['destination'],
                'avg_price': float(d['avg_price']) if d['avg_price'] else 0,
                'avg_rating': round(float(d['avg_rating']), 1) if d['avg_rating'] else 0,
            }
            for d in destinations
        ],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def package_categories(request):
    """GET /api/v1/packages/categories/"""
    cats = PackageCategory.objects.filter(is_active=True).order_by('name')
    return Response({
        'success': True,
        'data': [
            {'name': c.name, 'slug': c.slug, 'description': c.description}
            for c in cats
        ],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def booking_list(request):
    if not request.user.is_authenticated:
        return Response({'success': False, 'error': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

    rows = PackageBooking.objects.filter(user=request.user).select_related('package').order_by('-created_at')
    data = [
        {
            'booking_uuid': str(row.uuid),
            'public_booking_id': row.public_booking_id,
            'status': row.status,
            'package_name': row.package.name,
            'destination': row.package.destination,
            'adults': row.adults,
            'children': row.children,
            'total_amount': float(row.total_amount),
            'created_at': row.created_at,
        }
        for row in rows
    ]
    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def booking_detail(request, booking_uuid):
    if not request.user.is_authenticated:
        return Response({'success': False, 'error': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = PackageBooking.objects.select_related('package', 'departure').prefetch_related('travelers', 'booking_addons__addon').get(uuid=booking_uuid, user=request.user)
    except PackageBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {
            'success': True,
            'data': {
                'booking_uuid': str(booking.uuid),
                'public_booking_id': booking.public_booking_id,
                'status': booking.status,
                'package': {
                    'id': booking.package.id,
                    'slug': booking.package.slug,
                    'name': booking.package.name,
                    'destination': booking.package.destination,
                },
                'departure_date': str(booking.departure.departure_date) if booking.departure else None,
                'travellers': {
                    'adults': booking.adults,
                    'children': booking.children,
                    'details': [
                        {
                            'full_name': t.full_name,
                            'age': t.age,
                            'traveler_type': t.traveler_type,
                        }
                        for t in booking.travelers.all()
                    ],
                },
                'addons': [
                    {
                        'name': ba.addon.name,
                        'quantity': ba.quantity,
                        'total_price': float(ba.total_price),
                    }
                    for ba in booking.booking_addons.all()
                ],
                'pricing': {
                    'subtotal': float(booking.subtotal),
                    'group_discount': float(booking.group_discount),
                    'promo_discount': float(booking.promo_discount),
                    'gst': float(booking.gst),
                    'total_amount': float(booking.total_amount),
                },
            },
        }
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('packages')
def booking_cancel(request, booking_uuid):
    if not request.user.is_authenticated:
        return Response({'success': False, 'error': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = PackageBooking.objects.select_related('departure').get(uuid=booking_uuid, user=request.user)
    except PackageBooking.DoesNotExist:
        return Response({'success': False, 'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.status in ['cancelled', 'refunded']:
        return Response({'success': False, 'error': 'Booking already cancelled/refunded'}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = 'cancelled'
    booking.save(update_fields=['status', 'updated_at'])

    if booking.departure:
        booking.departure.booked_slots = max(0, booking.departure.booked_slots - (booking.adults + booking.children))
        booking.departure.save(update_fields=['booked_slots', 'updated_at'])

    return Response({'success': True, 'data': {'booking_uuid': str(booking.uuid), 'status': booking.status}})
