"""
Bus Operator Dashboard Views
Production-grade views with atomic transactions and RBAC enforcement
"""
import json
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from apps.accounts.permissions import role_required
from apps.accounts.selectors import user_has_role
from .models import Bus, BusBooking, BusBookingPassenger, BusSeat, BusType


@login_required
@role_required('bus_operator')
def bus_dashboard(request):
    """
    Bus operator dashboard showing all their buses and bookings.
    RBAC: bus_operator role required
    """
    operator = request.user
    buses = Bus.objects.filter(operator=operator, is_active=True).prefetch_related('bookings')
    
    stats = {
        'total_buses': buses.count(),
        'total_bookings': BusBooking.objects.filter(bus__operator=operator).count(),
        'confirmed_bookings': BusBooking.objects.filter(
            bus__operator=operator,
            status=BusBooking.STATUS_CONFIRMED
        ).count(),
        'total_revenue': float(
            sum(
                booking.total_amount or 0 
                for booking in BusBooking.objects.filter(bus__operator=operator)
            )
        ),
    }
    
    context = {
        'buses': buses,
        'stats': stats,
    }
    return render(request, 'bus_dashboard/dashboard.html', context)


@login_required
@role_required('bus_operator')
@require_http_methods(["GET", "POST"])
def bus_create(request):
    """
    Create new bus for operator.
    POST creates bus with atomic transaction.
    RBAC: bus_operator role required
    """
    if request.method == 'POST':
        try:
            registration_number = request.POST.get('registration_number') or request.POST.get('bus_number')
            operator_name = request.POST.get('operator_name') or request.user.full_name or request.user.email
            from_city = request.POST.get('from_city')
            to_city = request.POST.get('to_city')
            route = request.POST.get('route')
            if route and (not from_city or not to_city):
                parts = [part.strip() for part in route.split('to', 1)]
                if len(parts) == 2:
                    from_city, to_city = parts
            departure_time = request.POST.get('departure_time') or '09:00'
            arrival_time = request.POST.get('arrival_time') or '18:00'
            price_per_seat = Decimal(request.POST.get('price_per_seat') or '499')
            available_seats = int(request.POST.get('available_seats') or request.POST.get('total_seats') or 40)

            bus_type_id = request.POST.get('bus_type_id')
            if not bus_type_id:
                bus_type_name = request.POST.get('bus_type')
                bus_type = BusType.objects.filter(name=bus_type_name).first() if bus_type_name else BusType.objects.first()
                bus_type_id = bus_type.id if bus_type else None

            if not all([registration_number, operator_name, from_city, to_city]):
                raise ValueError('All required fields must be provided.')
            if price_per_seat <= 0 or available_seats <= 0:
                raise ValueError('Price and available seats must be greater than zero.')
            with transaction.atomic():
                bus = Bus.objects.create(
                    operator=request.user,
                    registration_number=registration_number,
                    bus_type_id=bus_type_id,
                    operator_name=operator_name,
                    from_city=from_city,
                    to_city=to_city,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    price_per_seat=price_per_seat,
                    available_seats=available_seats,
                    amenities=request.POST.get('amenities', ''),
                )
                
                # Create seats
                seats_per_row = 4
                rows = ['A', 'B', 'C', 'D', 'E']
                for row in rows:
                    for col in range(1, seats_per_row + 1):
                        seat_number = f"{row}{col}"
                        BusSeat.objects.create(
                            bus=bus,
                            seat_number=seat_number,
                            row=row,
                            column=col,
                        )
                
                messages.success(request, f'Bus {bus.registration_number} created successfully!')
                return redirect('buses:dashboard')
        except (InvalidOperation, ValueError, TypeError) as e:
            messages.error(request, f'Invalid input: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating bus: {str(e)}')
    
    return render(request, 'bus_dashboard/bus_form.html')


@login_required
@role_required('bus_operator')
def bus_detail(request, bus_id):
    """
    View bus details and bookings.
    RBAC: Operator can only view their own buses
    """
    bus = get_object_or_404(Bus, id=bus_id, operator=request.user)
    bookings = bus.bookings.all().prefetch_related('passengers')
    seats = bus.seats.all()
    
    context = {
        'bus': bus,
        'bookings': bookings,
        'seats': seats,
    }
    return render(request, 'bus_dashboard/bus_detail.html', context)


@login_required
@role_required('bus_operator')
@require_http_methods(["POST"])
def bus_update_availability(request):
    """
    Update bus seat availability via AJAX with atomic lock.
    RBAC: bus_operator role required
    Returns JSON response
    """
    try:
        bus_id = request.POST.get('bus_id')
        available_seats = int(request.POST.get('available_seats'))
        
        # Atomic update with lock
        with transaction.atomic():
            bus = Bus.objects.select_for_update().get(
                id=bus_id,
                operator=request.user
            )
            bus.available_seats = available_seats
            bus.save(update_fields=['available_seats', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Availability updated',
            'available_seats': bus.available_seats,
        })
    except Bus.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bus not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@role_required('bus_operator')
@require_http_methods(["POST"])
def bus_deactivate(request):
    """
    Deactivate bus (soft delete).
    RBAC: bus_operator role required
    """
    try:
        bus_id = request.POST.get('bus_id')
        
        with transaction.atomic():
            bus = Bus.objects.select_for_update().get(
                id=bus_id,
                operator=request.user
            )
            bus.is_active = False
            bus.save(update_fields=['is_active', 'updated_at'])
        
        messages.success(request, 'Bus deactivated successfully')
        return redirect('buses:dashboard')
    except Bus.DoesNotExist:
        messages.error(request, 'Bus not found')
        return redirect('buses:dashboard')


@login_required
@role_required('bus_operator')
def bus_bookings_list(request):
    """
    List all bookings for operator's buses.
    Supports filtering by status.
    """
    operator = request.user
    bookings = BusBooking.objects.filter(
        bus__operator=operator
    ).select_related('bus', 'user').prefetch_related('passengers')
    
    # Filter by status
    status = request.GET.get('status') or ''
    if status:
        bookings = bookings.filter(status=status)
    
    context = {
        'bookings': bookings,
        'status_filter': status,
    }
    return render(request, 'bus_dashboard/bookings_list.html', context)