"""
Owner Dashboard API Views.

Provides RESTful endpoints for property owners, bus operators, 
cab fleet owners, and package providers.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.dashboard')


def _is_admin_user(user):
    return user.is_authenticated and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False) or user.is_admin())


def _owner_properties(user, property_id=None):
    from apps.hotels.models import Property

    properties = Property.objects.all() if _is_admin_user(user) else Property.objects.filter(owner=user)
    if property_id:
        properties = properties.filter(id=property_id)
    return properties


# ============================================================================
# Hotel Owner Dashboard
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_dashboard_summary(request):
    """Get hotel owner dashboard summary — bookings, revenue, occupancy."""
    property_id = request.query_params.get('property_id')
    properties = _owner_properties(request.user, property_id=property_id)
    if not properties.exists():
        return Response({'error': 'No properties found'}, status=404)

    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    from apps.booking.models import Booking
    bookings = Booking.objects.filter(
        property__in=properties,
        created_at__date__gte=start_date,
    )

    total_bookings = bookings.count()
    confirmed = bookings.filter(status__in=['confirmed', 'checked_in', 'checked_out', 'settled']).count()
    cancelled = bookings.filter(status='cancelled').count()
    revenue = bookings.filter(
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).aggregate(total=Sum('net_payable_to_hotel'))['total'] or Decimal('0')

    # Occupancy rate
    from apps.rooms.models import RoomInventory
    total_room_nights = RoomInventory.objects.filter(
        room_type__property__in=properties,
        date__gte=start_date,
        date__lte=date.today(),
    ).aggregate(
        total=Sum('available_rooms'),
        booked=Sum('booked_count'),
    )
    total_rooms = total_room_nights['total'] or 0
    booked_rooms = total_room_nights['booked'] or 0
    occupancy_rate = (booked_rooms / total_rooms * 100) if total_rooms > 0 else 0

    # Revenue trend (daily)
    revenue_trend = bookings.filter(
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).annotate(
        day=TruncDate('created_at'),
    ).values('day').annotate(
        daily_revenue=Sum('net_payable_to_hotel'),
        daily_bookings=Count('id'),
    ).order_by('day')

    return Response({
        'period_days': days,
        'properties_count': properties.count(),
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed,
        'cancelled_bookings': cancelled,
        'revenue': str(revenue),
        'total_revenue': str(revenue),
        'occupancy_rate': round(occupancy_rate, 1),
        'avg_occupancy': round(occupancy_rate, 1),
        'revenue_trend': [
            {
                'date': str(r['day']),
                'revenue': str(r['daily_revenue'] or 0),
                'bookings': r['daily_bookings'],
            }
            for r in revenue_trend
        ],
        'trend': [
            {
                'date': str(r['day']),
                'revenue': float(r['daily_revenue'] or 0),
                'bookings': r['daily_bookings'],
            }
            for r in revenue_trend
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_inventory_calendar(request):
    """Get inventory calendar for owner's properties."""
    property_id = request.query_params.get('property_id')
    month = request.query_params.get('month')
    try:
        limit = max(int(request.query_params.get('limit', 100)), 1)
    except (TypeError, ValueError):
        limit = 100

    if month:
        try:
            year, month_num = month.split('-')
            month_start = date(int(year), int(month_num), 1)
            if int(month_num) == 12:
                month_end = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(int(year), int(month_num) + 1, 1) - timedelta(days=1)
            start = request.query_params.get('start_date', str(month_start))
            end = request.query_params.get('end_date', str(month_end))
        except ValueError:
            start = request.query_params.get('start_date', str(date.today()))
            end = request.query_params.get('end_date', str(date.today() + timedelta(days=30)))
    else:
        start = request.query_params.get('start_date', str(date.today()))
        end = request.query_params.get('end_date', str(date.today() + timedelta(days=30)))

    properties = _owner_properties(request.user, property_id=property_id)

    if not properties.exists():
        return Response({'error': 'No properties found'}, status=404)

    from apps.rooms.models import RoomInventory
    inventory = RoomInventory.objects.filter(
        room_type__property__in=properties,
        date__gte=start,
        date__lte=end,
    ).annotate(
        room_type_name=F('room_type__name'),
        property_name=F('room_type__property__name'),
        total_rooms=F('available_rooms') + F('booked_count'),
    ).values(
        'date',
        'room_type_id',
        'room_type_name',
        'property_name',
        'total_rooms',
        'available_rooms',
        'booked_count',
        'price',
        'is_closed',
    ).order_by('date', 'room_type_name', 'room_type_id')

    total_rows = inventory.count()
    inventory_rows = list(inventory[:limit])

    calendar = {}
    flat_inventory = []
    for inv in inventory_rows:
        dt = str(inv['date'])
        if dt not in calendar:
            calendar[dt] = []
        row = {
            'room_type': inv['room_type_name'],
            'room_type_id': inv['room_type_id'],
            'property': inv['property_name'] or '',
            'total': inv['total_rooms'],
            'available': inv['available_rooms'],
            'booked': inv['booked_count'],
            'price': str(inv['price']),
            'is_closed': inv['is_closed'],
        }
        calendar[dt].append(row)
        flat_inventory.append({'date': dt, **row})

    return Response({
        'calendar': calendar,
        'inventory': flat_inventory,
        'returned_rows': len(flat_inventory),
        'total_rows': total_rows,
        'has_more': total_rows > len(flat_inventory),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def owner_bulk_price_update(request):
    """Bulk update prices for a room type across date range."""
    from apps.rooms.models import RoomInventory, RoomType

    updates = request.data.get('updates') or []
    if updates:
        total_updated = 0
        touched_room_types = set()
        for update in updates:
            room_type_id = update.get('room_type_id')
            start_date = update.get('date_from') or update.get('start_date')
            end_date = update.get('date_to') or update.get('end_date')
            new_price = update.get('price')

            if not all([room_type_id, start_date, end_date, new_price]):
                continue

            try:
                room_type = RoomType.objects.select_related('property').get(id=room_type_id)
            except RoomType.DoesNotExist:
                continue

            if room_type.property and not _is_admin_user(request.user) and room_type.property.owner != request.user:
                continue

            total_updated += RoomInventory.objects.filter(
                room_type=room_type,
                date__gte=start_date,
                date__lte=end_date,
            ).update(price=Decimal(str(new_price)))
            touched_room_types.add(room_type.name)

        return Response({
            'updated': total_updated,
            'updated_dates': total_updated,
            'room_types': sorted(touched_room_types),
        })

    room_type_id = request.data.get('room_type_id')
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    new_price = request.data.get('price')

    if not all([room_type_id, start_date, end_date, new_price]):
        return Response({'error': 'room_type_id, start_date, end_date, price required'}, status=400)

    # Verify ownership
    try:
        room_type = RoomType.objects.select_related('property').get(id=room_type_id)
    except RoomType.DoesNotExist:
        return Response({'error': 'Room type not found'}, status=404)

    if room_type.property and not _is_admin_user(request.user) and room_type.property.owner != request.user:
        return Response({'error': 'Not your property'}, status=403)

    updated = RoomInventory.objects.filter(
        room_type=room_type,
        date__gte=start_date,
        date__lte=end_date,
    ).update(price=Decimal(str(new_price)))

    return Response({
        'updated_dates': updated,
        'room_type': room_type.name,
        'new_price': str(new_price),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_booking_analytics(request):
    """Detailed booking analytics for owner properties."""
    property_id = request.query_params.get('property_id')
    properties = _owner_properties(request.user, property_id=property_id)
    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    from apps.booking.models import Booking

    bookings = Booking.objects.filter(
        property__in=properties,
        created_at__date__gte=start_date,
    )

    # Status breakdown
    status_breakdown = dict(
        bookings.values_list('status').annotate(count=Count('id')).values_list('status', 'count')
    )

    # Average booking value
    avg_value = bookings.filter(
        status__in=['confirmed', 'checked_in', 'checked_out'],
    ).aggregate(avg=Avg('total_amount'))['avg'] or 0

    # Top room types
    from apps.booking.models import BookingRoom
    top_rooms = BookingRoom.objects.filter(
        booking__property__in=properties,
        booking__created_at__date__gte=start_date,
    ).values('room_type__name').annotate(
        count=Count('id'),
        revenue=Sum('booking__total_amount'),
    ).order_by('-count')[:5]

    top_room_types = [
        {
            'room': room['room_type__name'],
            'bookings': room['count'],
            'revenue': float(room['revenue'] or 0),
        }
        for room in top_rooms
    ]

    # Guest demographics (repeat vs new)
    unique_guests = bookings.filter(user__isnull=False).values('user').distinct().count()
    repeat_guests = bookings.filter(user__isnull=False).values('user').annotate(
        cnt=Count('id'),
    ).filter(cnt__gt=1).count()

    return Response({
        'period_days': days,
        'status_breakdown': [
            {'status': status, 'count': count}
            for status, count in status_breakdown.items()
        ],
        'avg_booking_value': str(round(avg_value, 2)),
        'top_room_types': top_room_types,
        'top_rooms': top_room_types,
        'unique_guests': unique_guests,
        'repeat_guests': repeat_guests,
        'repeat_rate': round(repeat_guests / unique_guests * 100, 1) if unique_guests > 0 else 0,
        'avg_lead_time_days': 0,
        'monthly_trend': [],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_revenue_dashboard(request):
    """Revenue dashboard with settlement tracking."""
    property_id = request.query_params.get('property_id')
    properties = _owner_properties(request.user, property_id=property_id)
    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    from apps.booking.models import Booking

    bookings = Booking.objects.filter(
        property__in=properties,
        created_at__date__gte=start_date,
    )

    financials = bookings.filter(
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    ).aggregate(
        total_gross=Sum('gross_amount'),
        total_commission=Sum('commission_amount'),
        total_gst=Sum('gst_amount'),
        total_gateway_fees=Sum('gateway_fee'),
        total_net_payable=Sum('net_payable_to_hotel'),
        total_refunds=Sum('refund_amount'),
    )

    # Settlement status
    settlement_rows = list(
        bookings.values('settlement_status').annotate(
            count=Count('id'),
            amount=Sum('net_payable_to_hotel'),
        )
    )
    pending_settlement = sum(
        Decimal(str(row['amount'] or 0))
        for row in settlement_rows
        if row['settlement_status'] not in {'settled', 'paid'}
    )
    commission_paid = financials['total_commission'] or Decimal('0')
    commission_rate = round((commission_paid / financials['total_gross'] * 100), 2) if financials['total_gross'] else 0

    return Response({
        'period_days': days,
        'gross_revenue': str(financials['total_gross'] or 0),
        'commission_paid': str(financials['total_commission'] or 0),
        'commission': str(financials['total_commission'] or 0),
        'commission_rate': commission_rate,
        'gst_collected': str(financials['total_gst'] or 0),
        'gst_on_commission': str(financials['total_gst'] or 0),
        'gateway_fees': str(financials['total_gateway_fees'] or 0),
        'net_payable': str(financials['total_net_payable'] or 0),
        'net_payout': str(financials['total_net_payable'] or 0),
        'total_refunds': str(financials['total_refunds'] or 0),
        'pending_settlement': str(pending_settlement),
        'last_settlement_date': None,
        'settlement_breakdown': settlement_rows,
    })


# ============================================================================
# Bus Operator Dashboard
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bus_operator_dashboard(request):
    """Bus operator dashboard — fleet management, bookings, revenue."""
    from apps.buses.models import Bus, BusBooking

    buses = Bus.objects.all() if _is_admin_user(request.user) else Bus.objects.filter(operator=request.user)
    if not buses.exists():
        return Response({'error': 'No buses found'}, status=404)

    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    bookings = BusBooking.objects.filter(
        bus__in=buses,
        created_at__date__gte=start_date,
    )

    total_bookings = bookings.count()
    revenue = bookings.filter(
        status__in=['confirmed', 'completed'],
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

    # Fleet status
    active_buses = buses.filter(is_active=True).count()
    total_seats = buses.aggregate(total=Sum('bus_type__capacity'))['total'] or 0

    # Occupancy by route
    route_stats = bookings.filter(
        status__in=['confirmed', 'completed'],
    ).values(
        'bus__from_city', 'bus__to_city',
    ).annotate(
        bookings=Count('id'),
        revenue=Sum('total_amount'),
    ).order_by('-bookings')[:10]

    return Response({
        'period_days': days,
        'active_buses': active_buses,
        'active_schedules': active_buses,
        'total_buses': buses.count(),
        'total_seats': total_seats,
        'total_bookings': total_bookings,
        'revenue': str(revenue),
        'total_revenue': str(revenue),
        'occupancy_rate': 0,
        'route_stats': list(route_stats),
        'routes': [
            {
                'route': f"{row['bus__from_city']} → {row['bus__to_city']}",
                'bookings': row['bookings'],
                'revenue': float(row['revenue'] or 0),
                'occupancy': 0,
            }
            for row in route_stats
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bus_schedule_management(request):
    """Get bus schedules for operator management."""
    from apps.buses.models import Bus

    buses = Bus.objects.all() if _is_admin_user(request.user) else Bus.objects.filter(operator=request.user, is_active=True)
    bus_id = request.query_params.get('bus_id')
    if bus_id:
        buses = buses.filter(id=bus_id)

    schedules = []
    for bus in buses.select_related()[:50]:
        schedules.append({
            'bus_id': bus.id,
            'operator': bus.operator,
            'from_city': bus.from_city,
            'to_city': bus.to_city,
            'departure_time': str(bus.departure_time),
            'arrival_time': str(bus.arrival_time),
            'bus_type': bus.bus_type,
            'capacity': bus.capacity,
            'available_seats': bus.available_seats,
            'price_per_seat': str(bus.price_per_seat),
            'is_active': bus.is_active,
        })

    return Response({'schedules': schedules})


# ============================================================================
# Cab Fleet Owner Dashboard
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cab_fleet_dashboard(request):
    """Cab fleet owner dashboard — vehicles, drivers, trips."""
    from apps.cabs.models import Cab, CabBooking, Driver

    cabs = Cab.objects.all() if _is_admin_user(request.user) else Cab.objects.filter(owner=request.user)
    if not cabs.exists():
        return Response({'error': 'No cabs found'}, status=404)

    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    bookings = CabBooking.objects.filter(
        cab__in=cabs,
        created_at__date__gte=start_date,
    )

    total_trips = bookings.filter(status='completed').count()
    revenue = bookings.filter(status='completed').aggregate(
        total=Sum('final_price'),
    )['total'] or Decimal('0')

    # Driver stats
    drivers = Driver.objects.filter(cab__in=cabs)
    driver_stats = {
        'total_drivers': drivers.count(),
        'active_drivers': drivers.exclude(status='offline').count(),
        'avg_rating': float(drivers.aggregate(avg=Avg('rating'))['avg'] or 0),
    }

    driver_rows = []
    for driver in drivers.select_related('user')[:20]:
        driver_bookings = bookings.filter(driver=driver, status='completed')
        driver_rows.append({
            'name': driver.user.full_name,
            'trips': driver_bookings.count(),
            'rating': float(driver.rating or 0),
            'earnings': float(driver_bookings.aggregate(total=Sum('final_price'))['total'] or 0),
        })

    # Vehicle utilization
    vehicle_stats = []
    for cab in cabs[:20]:
        cab_bookings = bookings.filter(cab=cab)
        vehicle_stats.append({
            'cab_id': cab.id,
            'name': cab.name,
            'cab_type': cab.cab_type,
            'trips': cab_bookings.filter(status='completed').count(),
            'revenue': str(cab_bookings.filter(status='completed').aggregate(
                total=Sum('final_price'),
            )['total'] or 0),
        })

    return Response({
        'period_days': days,
        'total_vehicles': cabs.count(),
        'total_trips': total_trips,
        'revenue': str(revenue),
        'total_revenue': str(revenue),
        'driver_stats': driver_stats,
        'active_drivers': driver_stats['active_drivers'],
        'avg_rating': driver_stats['avg_rating'],
        'drivers': driver_rows,
        'vehicle_stats': vehicle_stats,
    })


# ============================================================================
# Package Provider Dashboard
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def package_provider_dashboard(request):
    """Package provider dashboard — packages, bookings, availability."""
    from apps.packages.models import Package, PackageBooking, PackageDeparture

    packages = Package.objects.all() if _is_admin_user(request.user) else Package.objects.filter(provider=request.user)
    if not packages.exists():
        return Response({'error': 'No packages found'}, status=404)

    days = int(request.query_params.get('days', 30))
    start_date = date.today() - timedelta(days=days)

    bookings = PackageBooking.objects.filter(
        package__in=packages,
        created_at__date__gte=start_date,
    )

    total_bookings = bookings.count()
    revenue = bookings.filter(
        status__in=['confirmed', 'completed'],
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

    # Upcoming departures
    upcoming = PackageDeparture.objects.filter(
        package__in=packages,
        departure_date__gte=date.today(),
        is_active=True,
    ).order_by('departure_date')[:10]

    upcoming_list = []
    for dep in upcoming:
        upcoming_list.append({
            'departure_id': dep.id,
            'package_name': dep.package.name,
            'departure_date': str(dep.departure_date),
            'total_slots': dep.total_slots,
            'booked_slots': dep.booked_slots,
            'available_slots': dep.available_slots,
        })

    # Popular packages
    popular = bookings.values('package__name').annotate(
        bookings=Count('id'),
        revenue=Sum('total_amount'),
    ).order_by('-bookings')[:5]

    return Response({
        'period_days': days,
        'total_packages': packages.count(),
        'active_packages': packages.filter(is_active=True).count(),
        'active_departures': upcoming.count(),
        'total_bookings': total_bookings,
        'revenue': str(revenue),
        'total_revenue': str(revenue),
        'upcoming_departures': upcoming_list,
        'popular_packages': [
            {
                'name': row['package__name'],
                'bookings': row['bookings'],
                'revenue': float(row['revenue'] or 0),
            }
            for row in popular
        ],
    })
