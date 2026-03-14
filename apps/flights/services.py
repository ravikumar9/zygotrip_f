"""
Flight search & booking services.

Functions:
  search_flights      — route + date search with fare class filtering
  search_roundtrip    — outbound + return pairing
  create_flight_booking — atomic booking with seat decrement + PNR
  cancel_flight_booking — cancellation with refund calculation
  get_fare_calendar   — 30-day price grid for flexible dates
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Min, Q
from django.utils import timezone

from .models import (
    Flight, FlightFareClass, FlightBooking, FlightPassenger,
    FlightPriceBreakdown, FlightBookingHistory, FlightCancellationPolicy,
)

logger = logging.getLogger('zygotrip.flights')


def search_flights(origin_code, destination_code, departure_date,
                   cabin_type='economy', adults=1, children=0, infants=0,
                   sort_by='price', max_results=50):
    """
    Search available flights for a route and date.

    Returns list of dicts with flight + fare details.
    """
    pax_count = adults + children

    flights = (
        Flight.objects
        .filter(
            origin__iata_code=origin_code.upper(),
            destination__iata_code=destination_code.upper(),
            departure_datetime__date=departure_date,
            is_active=True,
        )
        .select_related('airline', 'origin', 'destination', 'operating_airline')
        .prefetch_related('fare_classes', 'legs')
    )

    results = []
    for flight in flights:
        fares = flight.fare_classes.filter(
            cabin_type=cabin_type, is_active=True,
            available_seats__gte=pax_count,
        )
        for fare in fares:
            total_per_adult = fare.total_fare
            total_per_child = fare.total_fare * Decimal('0.75')
            total = (total_per_adult * adults) + (total_per_child * children)

            results.append({
                'flight_id': flight.id,
                'flight_uuid': str(flight.uuid),
                'flight_number': flight.flight_number,
                'airline': {
                    'code': flight.airline.code,
                    'name': flight.airline.name,
                    'logo_url': flight.airline.logo_url,
                    'is_lcc': flight.airline.is_lcc,
                },
                'origin': {
                    'code': flight.origin.iata_code,
                    'name': flight.origin.name,
                    'city': flight.origin.city,
                },
                'destination': {
                    'code': flight.destination.iata_code,
                    'name': flight.destination.name,
                    'city': flight.destination.city,
                },
                'departure': flight.departure_datetime.isoformat(),
                'arrival': flight.arrival_datetime.isoformat(),
                'duration': flight.duration_display,
                'duration_minutes': flight.duration_minutes,
                'stops': flight.stops,
                'aircraft': flight.aircraft_type,
                'is_codeshare': flight.is_codeshare,
                'fare_class': {
                    'id': fare.id,
                    'code': fare.fare_class_code,
                    'cabin': fare.cabin_type,
                    'base_fare': float(fare.base_fare),
                    'taxes': float(fare.taxes),
                    'total_fare': float(fare.total_fare),
                    'available_seats': fare.available_seats,
                    'is_refundable': fare.is_refundable,
                    'baggage_kg': fare.baggage_allowance_kg,
                    'cabin_baggage_kg': fare.cabin_baggage_kg,
                    'meal_included': fare.meal_included,
                },
                'total_price': float(total),
                'price_per_adult': float(total_per_adult),
                'price_per_child': float(total_per_child),
                'legs': [
                    {
                        'leg': leg.leg_number,
                        'origin': leg.origin.iata_code,
                        'destination': leg.destination.iata_code,
                        'departure': leg.departure_datetime.isoformat(),
                        'arrival': leg.arrival_datetime.isoformat(),
                        'duration': leg.duration_minutes,
                        'flight_number': leg.flight_number,
                        'layover': leg.layover_minutes,
                    }
                    for leg in flight.legs.all()
                ] if flight.stops > 0 else [],
            })

    # Sort
    if sort_by == 'price':
        results.sort(key=lambda x: x['total_price'])
    elif sort_by == 'duration':
        results.sort(key=lambda x: x['duration_minutes'])
    elif sort_by == 'departure':
        results.sort(key=lambda x: x['departure'])
    elif sort_by == 'arrival':
        results.sort(key=lambda x: x['arrival'])

    return results[:max_results]


def search_roundtrip(origin_code, destination_code, departure_date,
                     return_date, cabin_type='economy', adults=1,
                     children=0, infants=0):
    """Search outbound + return flights and pair them."""
    outbound = search_flights(
        origin_code, destination_code, departure_date,
        cabin_type, adults, children, infants)
    ret = search_flights(
        destination_code, origin_code, return_date,
        cabin_type, adults, children, infants)

    return {
        'outbound': outbound,
        'return': ret,
        'trip_type': 'roundtrip',
    }


def get_fare_calendar(origin_code, destination_code, start_date, days=30,
                      cabin_type='economy'):
    """Get lowest fare per day for flexible date selection."""
    from .models import Airport

    try:
        origin = Airport.objects.get(iata_code=origin_code.upper())
        dest = Airport.objects.get(iata_code=destination_code.upper())
    except Airport.DoesNotExist:
        return []

    end_date = start_date + timedelta(days=days)

    # Get min fare per day
    daily_fares = (
        FlightFareClass.objects
        .filter(
            flight__origin=origin,
            flight__destination=dest,
            flight__departure_datetime__date__gte=start_date,
            flight__departure_datetime__date__lt=end_date,
            cabin_type=cabin_type,
            is_active=True,
            available_seats__gt=0,
        )
        .values('flight__departure_datetime__date')
        .annotate(min_fare=Min('total_fare'))
        .order_by('flight__departure_datetime__date')
    )

    return [
        {
            'date': str(entry['flight__departure_datetime__date']),
            'min_fare': float(entry['min_fare']),
        }
        for entry in daily_fares
    ]


@transaction.atomic
def create_flight_booking(user, flight_id, fare_class_id, passengers_data,
                          contact_email, contact_phone, promo_code='',
                          return_flight_id=None, return_fare_class_id=None,
                          idempotency_key=None):
    """
    Create a flight booking with PNR, passenger records, and price breakdown.

    Args:
        passengers_data: list of dicts with passenger info
        [{title, first_name, last_name, pax_type, date_of_birth, ...}]
    """
    # Lock fare class row to prevent overselling
    fare_class = (
        FlightFareClass.objects
        .select_for_update()
        .get(pk=fare_class_id)
    )
    flight = fare_class.flight

    pax_count = len([p for p in passengers_data
                     if p.get('pax_type', 'adult') != 'infant'])
    if fare_class.available_seats < pax_count:
        raise ValueError(
            f"Only {fare_class.available_seats} seats available, "
            f"requested {pax_count}")

    # Calculate pricing
    adult_fare = fare_class.total_fare
    child_fare = fare_class.total_fare * Decimal('0.75')
    infant_fare = fare_class.total_fare * Decimal('0.10')

    total = Decimal('0.00')
    for p in passengers_data:
        ptype = p.get('pax_type', 'adult')
        if ptype == 'adult':
            total += adult_fare
        elif ptype == 'child':
            total += child_fare
        else:
            total += infant_fare

    # Handle return flight
    return_fc = None
    if return_flight_id and return_fare_class_id:
        return_fc = (
            FlightFareClass.objects
            .select_for_update()
            .get(pk=return_fare_class_id)
        )
        if return_fc.available_seats < pax_count:
            raise ValueError("Insufficient seats on return flight")
        # Add return fares
        for p in passengers_data:
            ptype = p.get('pax_type', 'adult')
            if ptype == 'adult':
                total += return_fc.total_fare
            elif ptype == 'child':
                total += return_fc.total_fare * Decimal('0.75')
            else:
                total += return_fc.total_fare * Decimal('0.10')

    trip_type = Flight.TRIP_ROUNDTRIP if return_flight_id else Flight.TRIP_ONEWAY

    # Create booking
    booking = FlightBooking.objects.create(
        user=user,
        flight=flight,
        fare_class=fare_class,
        return_flight_id=return_flight_id,
        return_fare_class=return_fc,
        trip_type=trip_type,
        total_amount=total,
        final_amount=total,
        contact_email=contact_email,
        contact_phone=contact_phone,
        promo_code=promo_code,
        idempotency_key=idempotency_key,
        status=FlightBooking.STATUS_HOLD,
        hold_expires_at=timezone.now() + timedelta(minutes=20),
    )

    # Record initial status
    FlightBookingHistory.objects.create(
        booking=booking, status=FlightBooking.STATUS_HOLD,
        note='Booking created with seat hold')

    # Create passenger records
    for p_data in passengers_data:
        ptype = p_data.get('pax_type', 'adult')
        if ptype == 'adult':
            p_fare = adult_fare
        elif ptype == 'child':
            p_fare = child_fare
        else:
            p_fare = infant_fare

        FlightPassenger.objects.create(
            booking=booking,
            title=p_data.get('title', 'mr'),
            first_name=p_data['first_name'],
            last_name=p_data['last_name'],
            pax_type=ptype,
            date_of_birth=p_data.get('date_of_birth'),
            passport_number=p_data.get('passport_number', ''),
            nationality=p_data.get('nationality', 'India'),
            meal_preference=p_data.get('meal_preference', ''),
            fare_amount=p_fare,
        )

    # Decrement available seats
    fare_class.available_seats -= pax_count
    fare_class.save(update_fields=['available_seats', 'updated_at'])
    if return_fc:
        return_fc.available_seats -= pax_count
        return_fc.save(update_fields=['available_seats', 'updated_at'])

    # Create price breakdown
    base_fare = sum(
        p.fare_amount for p in booking.passengers.all()
    )
    FlightPriceBreakdown.objects.create(
        booking=booking,
        base_fare=base_fare,
        convenience_fee=Decimal('199.00'),
        total_amount=total,
    )

    logger.info('Flight booking created: PNR=%s flight=%s pax=%d total=%.2f',
                booking.pnr, flight.flight_number, len(passengers_data),
                float(total))
    return booking


@transaction.atomic
def cancel_flight_booking(booking_id):
    """Cancel a flight booking with refund calculation."""
    booking = (
        FlightBooking.objects
        .select_for_update()
        .get(pk=booking_id)
    )

    if booking.status in (FlightBooking.STATUS_CANCELLED,
                          FlightBooking.STATUS_REFUNDED):
        raise ValueError(f"Booking {booking.pnr} already cancelled/refunded")

    # Calculate refund based on cancellation policy
    hours_before = max(
        0,
        (booking.flight.departure_datetime - timezone.now()).total_seconds() / 3600
    )

    policy = (
        FlightCancellationPolicy.objects
        .filter(
            fare_class=booking.fare_class,
            hours_before_departure__lte=hours_before)
        .order_by('-hours_before_departure')
        .first()
    )

    refund_amount = Decimal('0.00')
    cancel_fee = Decimal('0.00')
    if policy:
        refund_amount = (
            booking.final_amount * policy.refund_percentage / 100
        )
        cancel_fee = policy.cancellation_fee
        refund_amount = max(Decimal('0.00'), refund_amount - cancel_fee)

    # Release seats
    pax_count = booking.passengers.exclude(
        pax_type=FlightPassenger.TYPE_INFANT).count()
    fare_class = (
        FlightFareClass.objects
        .select_for_update()
        .get(pk=booking.fare_class_id)
    )
    fare_class.available_seats += pax_count
    fare_class.save(update_fields=['available_seats', 'updated_at'])

    if booking.return_fare_class:
        return_fc = (
            FlightFareClass.objects
            .select_for_update()
            .get(pk=booking.return_fare_class_id)
        )
        return_fc.available_seats += pax_count
        return_fc.save(update_fields=['available_seats', 'updated_at'])

    booking.transition_to(FlightBooking.STATUS_CANCELLED)

    logger.info('Flight booking cancelled: PNR=%s refund=%.2f fee=%.2f',
                booking.pnr, float(refund_amount), float(cancel_fee))

    return {
        'pnr': booking.pnr,
        'refund_amount': float(refund_amount),
        'cancellation_fee': float(cancel_fee),
        'status': booking.status,
    }
