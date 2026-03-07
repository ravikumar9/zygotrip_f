from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.permissions import provider_required
from .serializers import BusRenderReadySerializer
from .forms import BusRegistrationForm, BusSeatBookingForm
from .selectors import (
    get_bus_queryset,
    paginate_buses,
    get_bus_or_404,
    get_booking_or_404,
    get_available_seats,
)
from .services import ensure_bus_seats, create_bus_booking, ensure_default_bus_type
from .ota_selectors import get_ota_context

def list_buses(request):
    """LIST BUSES: Backend-driven OTA listing
    
    Uses get_ota_context() from ota_selectors.py
    Enforces all 8 OTA rules for consistent filtering
    """
    context = get_ota_context(request)
    
    # Ensure all required context fields are present
    context.setdefault('empty_state', True)
    context.setdefault('total_count', 0)
    context.setdefault('filter_options', {})
    context.setdefault('selected_filters', {})
    context.setdefault('current_sort', 'popular')
    context.setdefault('page_title', 'Bus Tickets - Zygotrip')
    
    return render(request, 'buses/list.html', context)

def bus_detail(request, bus_id):
    bus = get_bus_or_404(bus_id)
    # Group seats by row for display
    seats_by_row = {}
    for seat in bus.seats.all():
        if seat.row not in seats_by_row:
            seats_by_row[seat.row] = []
        seats_by_row[seat.row].append(seat)
    
    context = {
        'bus': bus,
        'seats_by_row': dict(sorted(seats_by_row.items())),
        'amenities': bus.get_amenities_list()
    }
    return render(request, 'buses/detail.html', context)


@login_required
def bus_booking(request, bus_id):
    bus = get_bus_or_404(bus_id)
    ensure_bus_seats(bus)
    available_seats = get_available_seats(bus)
    seat_choices = [(str(seat.id), seat.seat_number) for seat in available_seats]

    if request.method == 'POST':
        form = BusSeatBookingForm(request.POST, seat_choices=seat_choices)
        if form.is_valid():
            seat_id = int(form.cleaned_data['seat_id'])
            journey_date = form.cleaned_data['journey_date']
            promo_code = form.cleaned_data['promo_code'].strip()

            booking = create_bus_booking(
                request.user,
                bus,
                form,
                seat_id,
                journey_date,
                promo_code,
            )
            if booking is None:
                messages.error(request, 'Selected seat is no longer available.')
                return redirect('buses:booking', bus_id=bus.id)

            messages.success(request, 'Bus booking confirmed!')
            return redirect('buses:booking-success', booking_uuid=booking.uuid)
    else:
        form = BusSeatBookingForm(seat_choices=seat_choices, initial={
            'journey_date': bus.journey_date,
        })

    context = {
        'bus': bus,
        'form': form,
        'available_seats': available_seats,
    }
    return render(request, 'buses/booking.html', context)


@login_required
def booking_success(request, booking_uuid):
    booking = get_booking_or_404(booking_uuid, request.user)
    context = {'booking': booking}
    return render(request, 'buses/booking_success.html', context)

@login_required
def booking_review(request, booking_uuid):
    booking = get_booking_or_404(booking_uuid, request.user)
    context = {'booking': booking}
    return render(request, 'buses/review.html', context)


@provider_required
def owner_bus_add(request):
    """
    Bus operator registration form for adding new buses
    """
    if request.method == 'POST':
        form = BusRegistrationForm(request.POST)
        if form.is_valid():
            bus = form.save(commit=False)
            bus.operator = request.user
            ensure_default_bus_type(bus)
            
            bus.save()
            messages.success(request, 'Bus registered successfully!')
            return redirect('buses:list')
    else:
        form = BusRegistrationForm()
    
    context = {'form': form}
    return render(request, 'buses/owner_registration.html', context)