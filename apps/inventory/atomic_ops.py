"""
Atomic Inventory Operations — Concurrency-safe booking transactions.

All inventory mutations MUST go through this module to prevent overbooking.
Uses SELECT FOR UPDATE + atomic transactions for database-level safety.

Operations:
  - acquire_hold: Atomically reserve rooms for a date range
  - convert_hold: Convert hold → confirmed booking
  - release_hold: Release hold back to available pool
  - check_availability: Date-range availability check (read-only)
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.inventory')


class InventoryError(Exception):
    """Base exception for inventory operations."""
    pass


class InsufficientInventoryError(InventoryError):
    """Raised when requested rooms exceed available inventory."""
    pass


class HoldExpiredError(InventoryError):
    """Raised when attempting to convert an expired hold."""
    pass


class RestrictionError(InventoryError):
    """Raised when booking violates CTA/CTD/min_stay/max_stay/closure."""
    pass


def check_availability(room_type_id, check_in, check_out, rooms_needed=1):
    """
    Check if inventory is available for a date range (read-only).

    Returns:
        Dict with available, min_available, dates, restrictions
    """
    from apps.inventory.models import InventoryCalendar

    dates = []
    current = check_in
    min_avail = None
    restrictions = []
    nights = (check_out - check_in).days

    while current < check_out:
        try:
            cal = InventoryCalendar.objects.get(
                room_type_id=room_type_id, date=current,
            )
            avail = cal.available_rooms
            if cal.is_closed:
                restrictions.append({'date': str(current), 'reason': 'closed'})
                avail = 0
            if current == check_in and cal.close_to_arrival:
                restrictions.append({'date': str(current), 'reason': 'CTA'})
                avail = 0
            if current == check_out - timedelta(days=1) and cal.close_to_departure:
                restrictions.append({'date': str(current), 'reason': 'CTD'})
                avail = 0
            if nights < cal.min_stay:
                restrictions.append({'date': str(current), 'reason': f'min_stay={cal.min_stay}'})
                avail = 0
            if nights > cal.max_stay:
                restrictions.append({'date': str(current), 'reason': f'max_stay={cal.max_stay}'})
                avail = 0

            dates.append({
                'date': str(current),
                'available': avail,
                'rate': float(cal.effective_rate),
            })
            if min_avail is None or avail < min_avail:
                min_avail = avail
        except InventoryCalendar.DoesNotExist:
            dates.append({
                'date': str(current),
                'available': 0,
                'rate': 0,
            })
            min_avail = 0

        current += timedelta(days=1)

    return {
        'available': (min_avail or 0) >= rooms_needed and len(restrictions) == 0,
        'min_available': min_avail or 0,
        'rooms_needed': rooms_needed,
        'dates': dates,
        'restrictions': restrictions,
    }


@transaction.atomic
def acquire_hold(room_type_id, check_in, check_out, rooms=1,
                 booking_context=None, hold_minutes=15):
    """
    Atomically acquire an inventory hold for a date range.

    Uses SELECT FOR UPDATE to prevent concurrent overbooking.
    Creates InventoryHold records and decrements available_rooms.

    Args:
        room_type_id: RoomType PK
        check_in: date
        check_out: date
        rooms: number of rooms to hold
        booking_context: BookingContext instance (optional)
        hold_minutes: hold TTL in minutes (default 15)

    Returns:
        List of InventoryHold objects created

    Raises:
        InsufficientInventoryError: not enough rooms
        RestrictionError: CTA/CTD/closure
    """
    from apps.inventory.models import InventoryCalendar, InventoryHold

    holds = []
    hold_expires = timezone.now() + timedelta(minutes=hold_minutes)
    current = check_in
    nights = (check_out - check_in).days

    while current < check_out:
        # Lock row for atomic update
        cal = (
            InventoryCalendar.objects
            .select_for_update()
            .filter(room_type_id=room_type_id, date=current)
            .first()
        )

        if not cal:
            raise InsufficientInventoryError(
                f'No inventory record for room_type={room_type_id} date={current}'
            )

        # Check restrictions
        if cal.is_closed:
            raise RestrictionError(f'Date {current} is closed for bookings')
        if current == check_in and cal.close_to_arrival:
            raise RestrictionError(f'Close to arrival on {current}')
        if nights < cal.min_stay:
            raise RestrictionError(
                f'Minimum stay is {cal.min_stay} nights, requested {nights}'
            )
        if nights > cal.max_stay:
            raise RestrictionError(
                f'Maximum stay is {cal.max_stay} nights, requested {nights}'
            )

        # Check availability
        if cal.available_rooms < rooms:
            raise InsufficientInventoryError(
                f'Only {cal.available_rooms} rooms available on {current}, '
                f'requested {rooms}'
            )

        # Decrement available, increment held
        cal.held_rooms += rooms
        cal.recompute_available()
        cal.save()

        # Create hold record
        hold = InventoryHold.objects.create(
            room_type_id=room_type_id,
            date=current,
            rooms_held=rooms,
            booking_context=booking_context,
            hold_expires_at=hold_expires,
            status=InventoryHold.STATUS_ACTIVE,
        )
        holds.append(hold)

        current += timedelta(days=1)

    logger.info(
        'Hold acquired: room_type=%s dates=%s→%s rooms=%d holds=%d',
        room_type_id, check_in, check_out, rooms, len(holds),
    )
    return holds


@transaction.atomic
def convert_hold_to_booking(hold_ids, booking=None):
    """
    Convert active holds to confirmed booking.

    Atomically: held_rooms -= qty, booked_rooms += qty, hold status → converted.

    Args:
        hold_ids: list of InventoryHold PKs or UUIDs
        booking: Booking instance to link

    Raises:
        HoldExpiredError: if any hold is expired
    """
    from apps.inventory.models import InventoryCalendar, InventoryHold

    holds = list(
        InventoryHold.objects
        .select_for_update()
        .filter(hold_id__in=hold_ids)
    )

    if not holds:
        holds = list(
            InventoryHold.objects
            .select_for_update()
            .filter(pk__in=hold_ids)
        )

    for hold in holds:
        if hold.status not in (InventoryHold.STATUS_ACTIVE, InventoryHold.STATUS_PAYMENT_PENDING):
            raise HoldExpiredError(
                f'Hold {hold.hold_id} is in status {hold.status}, cannot convert'
            )
        if hold.is_expired:
            raise HoldExpiredError(
                f'Hold {hold.hold_id} expired at {hold.hold_expires_at}'
            )

        # Update calendar
        cal = (
            InventoryCalendar.objects
            .select_for_update()
            .get(room_type=hold.room_type, date=hold.date)
        )
        cal.held_rooms = max(0, cal.held_rooms - hold.rooms_held)
        cal.booked_rooms += hold.rooms_held
        cal.recompute_available()
        cal.save()

        # Update hold
        hold.status = InventoryHold.STATUS_CONVERTED
        hold.converted_at = timezone.now()
        if booking:
            hold.booking = booking
        hold.save()

    logger.info(
        'Holds converted to booking: %d holds, booking=%s',
        len(holds), getattr(booking, 'id', 'N/A'),
    )


@transaction.atomic
def release_holds(hold_ids):
    """
    Release expired or cancelled holds back to available pool.

    Atomically: held_rooms -= qty, available_rooms recomputed.
    """
    from apps.inventory.models import InventoryCalendar, InventoryHold

    holds = list(
        InventoryHold.objects
        .select_for_update()
        .filter(hold_id__in=hold_ids, status__in=[
            InventoryHold.STATUS_ACTIVE,
            InventoryHold.STATUS_PAYMENT_PENDING,
        ])
    )

    if not holds:
        holds = list(
            InventoryHold.objects
            .select_for_update()
            .filter(pk__in=hold_ids, status__in=[
                InventoryHold.STATUS_ACTIVE,
                InventoryHold.STATUS_PAYMENT_PENDING,
            ])
        )

    released = 0
    for hold in holds:
        try:
            cal = (
                InventoryCalendar.objects
                .select_for_update()
                .get(room_type=hold.room_type, date=hold.date)
            )
            cal.held_rooms = max(0, cal.held_rooms - hold.rooms_held)
            cal.recompute_available()
            cal.save()

            hold.status = InventoryHold.STATUS_RELEASED
            hold.released_at = timezone.now()
            hold.save()
            released += 1
        except Exception as exc:
            logger.error('Failed to release hold %s: %s', hold.hold_id, exc)

    logger.info('Released %d/%d holds', released, len(holds))
    return released


def get_availability_matrix(property_id, check_in, check_out):
    """
    Get availability matrix for all room types of a property across a date range.

    Returns:
        List of dicts: [{room_type_id, room_type_name, dates: [{date, available, rate}]}]
    """
    from apps.rooms.models import RoomType
    from apps.inventory.models import InventoryCalendar

    room_types = RoomType.objects.filter(property_id=property_id, is_active=True)
    result = []

    for rt in room_types:
        dates = []
        current = check_in
        min_avail = None

        while current < check_out:
            try:
                cal = InventoryCalendar.objects.get(room_type=rt, date=current)
                avail = cal.available_rooms if not cal.is_closed else 0
                rate = float(cal.effective_rate)
            except InventoryCalendar.DoesNotExist:
                avail = rt.available_count or 0
                rate = float(rt.base_price)

            dates.append({
                'date': str(current),
                'available': avail,
                'rate': rate,
            })
            if min_avail is None or avail < min_avail:
                min_avail = avail
            current += timedelta(days=1)

        result.append({
            'room_type_id': rt.pk,
            'room_type_name': rt.name,
            'base_price': float(rt.base_price),
            'min_available': min_avail or 0,
            'is_bookable': (min_avail or 0) >= 1,
            'dates': dates,
        })

    return result
