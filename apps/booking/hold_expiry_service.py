"""
Hold expiry management service.

Background job runs every 2 minutes to:
1. Find expired HOLD bookings
2. Release inventory
3. Mark booking as FAILED
4. Keep operation idempotent
"""
from django.db import transaction
from django.utils import timezone
from apps.rooms.models import RoomInventory
from .models import Booking
from .state_machine import BookingStateMachine
from datetime import timedelta


def release_expired_holds():
    """
    Idempotent job to release inventory from expired HOLD bookings.
    
    IDEMPOTENT: Safe to run multiple times without side effects.
    Only transitions HOLD bookings that have expired.
    """
    expired_holds = Booking.objects.filter(
        status=Booking.STATUS_HOLD,
        hold_expires_at__lt=timezone.now(),
    ).select_for_update()  # Lock rows
    
    released_count = 0
    
    for booking in expired_holds:
        # Double check hold is still expired (another process might have changed it)
        if not booking.is_hold_expired():
            continue
        
        released_count += _release_hold_transaction(booking)
    
    return {
        'released_count': released_count,
        'timestamp': timezone.now().isoformat(),
    }


@transaction.atomic
def _release_hold_transaction(booking):
    """
    Atomically release hold: release inventory and mark booking FAILED.
    
    Returns 1 if released, 0 if already released.
    """
    # Re-fetch to check current status within transaction
    booking.refresh_from_db()
    if booking.status != Booking.STATUS_HOLD:
        # Already transitioned, skip
        return 0
    
    if not booking.is_hold_expired():
        # No longer expired, skip
        return 0
    
    # Release inventory
    booking_rooms = booking.rooms.all()
    for booking_room in booking_rooms:
        room_type = booking_room.room_type
        quantity = booking_room.quantity
        check_in = booking.check_in
        check_out = booking.check_out
        
        # Increment available_count for all dates
        from datetime import timedelta as td
        current_date = check_in
        while current_date < check_out:
            inventories = RoomInventory.objects.select_for_update().filter(
                room_type=room_type,
                date=current_date,
            )
            for inventory in inventories:
                inventory.available_rooms += quantity
                inventory.available_count += quantity
                current_booked = inventory.booked_count or 0
                inventory.booked_count = max(0, current_booked - quantity)
                inventory.save(update_fields=['available_rooms', 'available_count', 'booked_count', 'updated_at'])
            
            current_date += td(days=1)
    
    # Mark booking as FAILED
    BookingStateMachine.transition(
        booking=booking,
        new_status=Booking.STATUS_FAILED,
        note='Hold expired - inventory released',
    )

    return 1
