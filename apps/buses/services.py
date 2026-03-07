from decimal import Decimal
from django.db import transaction

from .models import BusSeat, BusBooking, BusBookingPassenger, BusPriceBreakdown, BusType


def ensure_bus_seats(bus):
    if bus.seats.exists():
        return
    total_seats = bus.available_seats or (bus.bus_type.capacity if bus.bus_type_id else 40)
    seats_to_create = []
    seat_index = 0
    for _ in range(total_seats):
        row = chr(ord('A') + (seat_index // 4))
        column = (seat_index % 4) + 1
        seat_number = f"{row}{column}"
        seats_to_create.append(
            BusSeat(
                bus=bus,
                seat_number=seat_number,
                row=row,
                column=column,
                is_ladies_seat=False,
                state=BusSeat.AVAILABLE,
            )
        )
        seat_index += 1
    BusSeat.objects.bulk_create(seats_to_create)


def create_bus_booking(user, bus, form, seat_id, journey_date, promo_code):
    with transaction.atomic():
        seat = BusSeat.objects.select_for_update().get(id=seat_id, bus=bus)
        if seat.state != BusSeat.AVAILABLE:
            return None

        base_amount = Decimal(bus.price_per_seat)
        service_fee = Decimal('50')
        gst = (base_amount * Decimal('0.05')).quantize(Decimal('1.00'))
        total_amount = base_amount + service_fee + gst

        booking = BusBooking.objects.create(
            user=user,
            bus=bus,
            journey_date=journey_date,
            status=BusBooking.STATUS_CONFIRMED,
            total_amount=total_amount,
            promo_code=promo_code,
        )
        BusBookingPassenger.objects.create(
            booking=booking,
            seat=seat,
            full_name=form.cleaned_data['passenger_full_name'],
            age=form.cleaned_data['passenger_age'],
            gender=form.cleaned_data['passenger_gender'],
            phone=form.cleaned_data['passenger_phone'],
        )
        BusPriceBreakdown.objects.create(
            booking=booking,
            base_amount=base_amount,
            service_fee=service_fee,
            gst=gst,
            promo_discount=Decimal('0'),
            total_amount=total_amount,
        )

        seat.state = BusSeat.BOOKED
        seat.save(update_fields=['state', 'updated_at'])
        if bus.available_seats > 0:
            bus.available_seats -= 1
            bus.save(update_fields=['available_seats', 'updated_at'])

        return booking


def ensure_default_bus_type(bus):
    if bus.bus_type_id:
        return
    default_type, _ = BusType.objects.get_or_create(
        name=BusType.SEATER,
        defaults={'base_fare': 500, 'capacity': 40},
    )
    bus.bus_type = default_type
