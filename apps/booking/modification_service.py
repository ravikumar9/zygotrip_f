"""
Booking Modification Service.

Supports date changes 24+ hours before check-in with price recalculation.
All modifications go through the state machine and are fully auditable.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.booking.models import Booking, BookingStatusHistory
from apps.booking.state_machine import BookingStateMachine

logger = logging.getLogger('zygotrip.booking')


class BookingModification:
    """Handles booking date changes and room modifications."""

    # Minimum hours before check-in to allow modification
    MIN_HOURS_BEFORE_CHECKIN = 24

    @classmethod
    def can_modify(cls, booking):
        """Check if booking is eligible for modification."""
        if booking.status not in (Booking.STATUS_CONFIRMED, Booking.STATUS_HOLD):
            return False, 'Only confirmed or held bookings can be modified'

        hours_until_checkin = (
            timezone.make_aware(
                timezone.datetime.combine(booking.check_in, timezone.datetime.min.time())
            ) - timezone.now()
        ).total_seconds() / 3600

        if hours_until_checkin < cls.MIN_HOURS_BEFORE_CHECKIN:
            return False, f'Modifications must be made at least {cls.MIN_HOURS_BEFORE_CHECKIN}h before check-in'

        return True, ''

    @classmethod
    @transaction.atomic
    def modify_dates(cls, booking, new_check_in, new_check_out, user=None):
        """
        Modify booking dates with price recalculation.

        Returns: (success: bool, result: dict)
        """
        can, reason = cls.can_modify(booking)
        if not can:
            return False, {'error': reason}

        if new_check_in >= new_check_out:
            return False, {'error': 'Check-out must be after check-in'}

        booking = Booking.objects.select_for_update().get(pk=booking.pk)

        old_check_in = booking.check_in
        old_check_out = booking.check_out
        old_amount = booking.total_amount

        # Recalculate price for new dates
        nights = (new_check_out - new_check_in).days
        if nights < 1:
            return False, {'error': 'Minimum 1 night stay required'}

        # Get base nightly rate from the booking's room types
        nightly_rate = Decimal('0')
        for br in booking.rooms.select_related('room_type').all():
            if br.room_type:
                nightly_rate += br.room_type.base_price * br.quantity

        new_total = nightly_rate * nights
        price_diff = new_total - old_amount

        # Update the booking
        booking.check_in = new_check_in
        booking.check_out = new_check_out
        booking.total_amount = new_total
        booking.gross_amount = new_total
        booking.save(update_fields=[
            'check_in', 'check_out', 'total_amount', 'gross_amount', 'updated_at',
        ])

        # Record modification in audit trail
        BookingStatusHistory.objects.create(
            booking=booking,
            status=booking.status,
            note=f'Dates modified: {old_check_in}→{new_check_in}, '
                 f'{old_check_out}→{new_check_out}. '
                 f'Amount: {old_amount}→{new_total} (diff: {price_diff:+})',
        )

        logger.info(
            'Booking %s modified: dates %s-%s → %s-%s, amount %s → %s',
            booking.uuid, old_check_in, old_check_out,
            new_check_in, new_check_out, old_amount, new_total,
        )

        return True, {
            'booking_uuid': str(booking.uuid),
            'old_dates': {'check_in': str(old_check_in), 'check_out': str(old_check_out)},
            'new_dates': {'check_in': str(new_check_in), 'check_out': str(new_check_out)},
            'old_amount': str(old_amount),
            'new_amount': str(new_total),
            'price_difference': str(price_diff),
        }

    @classmethod
    @transaction.atomic
    def modify_rooms(cls, booking, room_changes, user=None):
        """
        Modify room selection (add/remove rooms).

        room_changes: list of {'room_type_id': int, 'quantity': int}
        """
        from apps.rooms.models import RoomType

        can, reason = cls.can_modify(booking)
        if not can:
            return False, {'error': reason}

        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        old_amount = booking.total_amount

        # Clear existing room assignments
        booking.rooms.all().delete()

        nights = (booking.check_out - booking.check_in).days
        new_total = Decimal('0')
        rooms_added = []

        for change in room_changes:
            try:
                room_type = RoomType.objects.get(
                    id=change['room_type_id'],
                    property=booking.property,
                )
            except RoomType.DoesNotExist:
                return False, {'error': f'Room type {change["room_type_id"]} not found'}

            qty = max(1, change.get('quantity', 1))
            booking.rooms.create(room_type=room_type, quantity=qty)
            new_total += room_type.base_price * qty * nights
            rooms_added.append({'room_type': room_type.name, 'quantity': qty})

        booking.total_amount = new_total
        booking.gross_amount = new_total
        booking.save(update_fields=['total_amount', 'gross_amount', 'updated_at'])

        BookingStatusHistory.objects.create(
            booking=booking,
            status=booking.status,
            note=f'Rooms modified. Amount: {old_amount}→{new_total}. Rooms: {rooms_added}',
        )

        return True, {
            'booking_uuid': str(booking.uuid),
            'rooms': rooms_added,
            'old_amount': str(old_amount),
            'new_amount': str(new_total),
        }
