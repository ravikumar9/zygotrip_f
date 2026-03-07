"""
Write operations for inventory domain — OTA Freeze Grade.

PHASE 2-3: Full inventory lifecycle with InventoryCalendar + InventoryHold.

All inventory operations MUST use select_for_update() to prevent races.
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from apps.rooms.models import RoomInventory
from .models import InventoryCalendar, InventoryHold, InventoryLog

logger = logging.getLogger('zygotrip.inventory')

# ============================================================================
# LEGACY SERVICES (RoomInventory — kept for backwards compat)
# ============================================================================


@transaction.atomic
def initialize_inventory(room_type, start_date, end_date, total_rooms):
    """Initialize inventory for room type across date range."""
    current_date = start_date
    created = []

    while current_date < end_date:
        inventory, _ = RoomInventory.objects.get_or_create(
            room_type=room_type,
            date=current_date,
            defaults={
                'available_rooms': total_rooms,
                'available_count': total_rooms,
                'booked_count': 0,
            }
        )
        created.append(inventory)
        current_date += timedelta(days=1)

    return created


@transaction.atomic
def reserve_inventory(room_type, start_date, end_date, quantity):
    """Reserve inventory for booking (decrease available, increase booked)."""
    current_date = start_date
    updated = []

    while current_date < end_date:
        inventory = RoomInventory.objects.select_for_update().get(
            room_type=room_type,
            date=current_date,
        )

        if inventory.available_rooms < quantity:
            raise ValueError(
                f"Insufficient inventory on {current_date}: "
                f"{inventory.available_rooms} available < {quantity} requested"
            )

        inventory.available_rooms -= quantity
        inventory.available_count = inventory.available_rooms  # keep legacy in sync
        inventory.booked_count += quantity
        inventory.save(update_fields=['available_rooms', 'available_count', 'booked_count'])
        updated.append(inventory)
        current_date += timedelta(days=1)

    return updated


@transaction.atomic
def release_inventory(room_type, start_date, end_date, quantity):
    """Release inventory (increase available, decrease booked). Used on cancellation/expiry."""
    current_date = start_date
    updated = []

    while current_date < end_date:
        inventory = RoomInventory.objects.select_for_update().get(
            room_type=room_type,
            date=current_date,
        )

        inventory.available_rooms += quantity
        inventory.available_count = inventory.available_rooms  # keep legacy in sync
        inventory.booked_count = max(0, inventory.booked_count - quantity)
        inventory.save(update_fields=['available_rooms', 'available_count', 'booked_count'])
        updated.append(inventory)
        current_date += timedelta(days=1)

    return updated


@transaction.atomic
def update_inventory_total(room_type, start_date, end_date, new_total):
    """Update total inventory and adjust available proportionally."""
    current_date = start_date
    updated = []

    while current_date < end_date:
        inventory = RoomInventory.objects.select_for_update().get(
            room_type=room_type,
            date=current_date,
        )

        old_total = inventory.available_rooms + inventory.booked_count
        diff = new_total - old_total
        inventory.available_rooms = max(0, inventory.available_rooms + diff)
        inventory.available_count = inventory.available_rooms  # keep legacy in sync
        inventory.save(update_fields=['available_rooms', 'available_count'])
        updated.append(inventory)
        current_date += timedelta(days=1)

    return updated


# ============================================================================
# PHASE 2: INVENTORY CALENDAR SERVICES
# ============================================================================

@transaction.atomic
def init_calendar(room_type, start_date, end_date, total_rooms):
    """
    Initialize InventoryCalendar rows for a room type across a date range.
    Idempotent: skips dates that already exist.
    """
    current = start_date
    created = []
    while current <= end_date:
        cal, was_created = InventoryCalendar.objects.get_or_create(
            room_type=room_type,
            date=current,
            defaults={
                'total_rooms': total_rooms,
                'available_rooms': total_rooms,
                'booked_rooms': 0,
                'blocked_rooms': 0,
                'held_rooms': 0,
            },
        )
        if was_created:
            created.append(cal)
        current += timedelta(days=1)
    return created


@transaction.atomic
def check_availability(room_type, check_in, check_out, quantity):
    """
    Check if `quantity` rooms are available for every night in the range.
    Returns (is_available: bool, unavailable_dates: list[date]).
    Does NOT lock rows — read-only check.

    Results cached in Redis for 2 min to reduce DB pressure on search pages.
    """
    room_type_id = getattr(room_type, 'id', None)

    # ── Cache lookup ─────────────────────────────────────────────────────
    try:
        from apps.search.engine.cache_manager import availability_cache
        cached = availability_cache.get_availability(
            room_type_id, check_in, check_out, quantity,
        )
        if cached is not None:
            return cached
    except Exception:
        pass

    unavailable = []
    current = check_in
    while current < check_out:
        try:
            cal = InventoryCalendar.objects.get(
                room_type=room_type, date=current,
            )
            if cal.is_closed or cal.available_rooms < quantity:
                unavailable.append(current)
        except InventoryCalendar.DoesNotExist:
            unavailable.append(current)
        current += timedelta(days=1)

    result = (len(unavailable) == 0, unavailable)

    # ── Cache write ──────────────────────────────────────────────────────
    try:
        from apps.search.engine.cache_manager import availability_cache as _ac
        _ac.set_availability(room_type_id, check_in, check_out, quantity, result)
    except Exception:
        pass

    return result


# ============================================================================
# PHASE 3: INVENTORY HOLD SERVICES (TTL 15 min, Celery every 2 min)
# ============================================================================

@transaction.atomic
def create_hold(room_type, check_in, check_out, quantity, booking_context=None):
    """
    Create inventory holds for each date in the range.
    Decrements available_rooms and increments held_rooms on InventoryCalendar.
    Returns list of InventoryHold objects.
    """
    holds = []
    current = check_in
    hold_expires = timezone.now() + timedelta(minutes=InventoryHold.HOLD_TTL_MINUTES)

    while current < check_out:
        cal = InventoryCalendar.objects.select_for_update().get(
            room_type=room_type, date=current,
        )
        if cal.is_closed or cal.available_rooms < quantity:
            raise ValueError(
                f"Cannot hold: {cal.available_rooms} available on {current}, need {quantity}"
            )

        available_before = cal.available_rooms
        cal.held_rooms += quantity
        cal.recompute_available()
        cal.save(update_fields=['held_rooms', 'available_rooms', 'updated_at'])

        hold = InventoryHold.objects.create(
            room_type=room_type,
            date=current,
            rooms_held=quantity,
            booking_context=booking_context,
            hold_expires_at=hold_expires,
            status=InventoryHold.STATUS_ACTIVE,
        )
        holds.append(hold)

        InventoryLog.objects.create(
            room_type=room_type,
            date=current,
            event=InventoryLog.EVENT_HOLD_CREATED,
            quantity=quantity,
            available_before=available_before,
            available_after=cal.available_rooms,
            reference_id=str(hold.hold_id),
        )

        current += timedelta(days=1)

    # Invalidate availability cache after holds change inventory
    try:
        from apps.search.engine.cache_manager import availability_cache as _ac
        _ac.invalidate_availability(getattr(room_type, 'id', None))
    except Exception:
        pass

    return holds


@transaction.atomic
def release_holds(holds):
    """
    Release holds — return rooms to available pool.
    Called by Celery task for expired holds or by user cancellation.
    """
    for hold in holds:
        if hold.status != InventoryHold.STATUS_ACTIVE:
            continue

        cal = InventoryCalendar.objects.select_for_update().get(
            room_type=hold.room_type, date=hold.date,
        )
        available_before = cal.available_rooms
        cal.held_rooms = max(0, cal.held_rooms - hold.rooms_held)
        cal.recompute_available()
        cal.save(update_fields=['held_rooms', 'available_rooms', 'updated_at'])

        hold.status = InventoryHold.STATUS_RELEASED
        hold.released_at = timezone.now()
        hold.save(update_fields=['status', 'released_at', 'updated_at'])

        InventoryLog.objects.create(
            room_type=hold.room_type,
            date=hold.date,
            event=InventoryLog.EVENT_HOLD_RELEASED,
            quantity=-hold.rooms_held,
            available_before=available_before,
            available_after=cal.available_rooms,
            reference_id=str(hold.hold_id),
        )


@transaction.atomic
def convert_hold_to_booking(holds, booking):
    """
    Convert active holds to a confirmed booking.
    held_rooms -= quantity, booked_rooms += quantity.
    """
    for hold in holds:
        if hold.status != InventoryHold.STATUS_ACTIVE:
            continue

        cal = InventoryCalendar.objects.select_for_update().get(
            room_type=hold.room_type, date=hold.date,
        )
        available_before = cal.available_rooms
        cal.held_rooms = max(0, cal.held_rooms - hold.rooms_held)
        cal.booked_rooms += hold.rooms_held
        cal.recompute_available()
        cal.save(update_fields=['held_rooms', 'booked_rooms', 'available_rooms', 'updated_at'])

        hold.status = InventoryHold.STATUS_CONVERTED
        hold.booking = booking
        hold.converted_at = timezone.now()
        hold.save(update_fields=['status', 'booking', 'converted_at', 'updated_at'])

        InventoryLog.objects.create(
            room_type=hold.room_type,
            date=hold.date,
            event=InventoryLog.EVENT_HOLD_CONVERTED,
            quantity=hold.rooms_held,
            available_before=available_before,
            available_after=cal.available_rooms,
            reference_id=str(booking.uuid),
        )


@transaction.atomic
def release_booking_inventory(room_type, check_in, check_out, quantity, booking_uuid=''):
    """
    Release inventory when a booking is cancelled.
    booked_rooms -= quantity, available_rooms recomputed.
    """
    current = check_in
    while current < check_out:
        try:
            cal = InventoryCalendar.objects.select_for_update().get(
                room_type=room_type, date=current,
            )
            available_before = cal.available_rooms
            cal.booked_rooms = max(0, cal.booked_rooms - quantity)
            cal.recompute_available()
            cal.save(update_fields=['booked_rooms', 'available_rooms', 'updated_at'])

            InventoryLog.objects.create(
                room_type=room_type,
                date=current,
                event=InventoryLog.EVENT_BOOKING_CANCELLED,
                quantity=-quantity,
                available_before=available_before,
                available_after=cal.available_rooms,
                reference_id=str(booking_uuid),
            )
        except InventoryCalendar.DoesNotExist:
            logger.warning(f"No InventoryCalendar for {room_type} on {current} during release")
        current += timedelta(days=1)

    # Invalidate availability cache after booking release
    try:
        from apps.search.engine.cache_manager import availability_cache as _ac
        _ac.invalidate_availability(getattr(room_type, 'id', None))
    except Exception:
        pass


def release_expired_holds():
    """
    Release all holds past their TTL. Called by Celery beat every 2 minutes.
    Returns count of released holds.
    """
    expired = InventoryHold.objects.filter(
        status=InventoryHold.STATUS_ACTIVE,
        hold_expires_at__lt=timezone.now(),
    ).select_related('room_type')

    if not expired.exists():
        return 0

    count = 0
    # Process in batches to avoid long transactions
    for hold in expired[:200]:
        try:
            with transaction.atomic():
                cal = InventoryCalendar.objects.select_for_update().get(
                    room_type=hold.room_type, date=hold.date,
                )
                available_before = cal.available_rooms
                cal.held_rooms = max(0, cal.held_rooms - hold.rooms_held)
                cal.recompute_available()
                cal.save(update_fields=['held_rooms', 'available_rooms', 'updated_at'])

                hold.status = InventoryHold.STATUS_EXPIRED
                hold.released_at = timezone.now()
                hold.save(update_fields=['status', 'released_at', 'updated_at'])

                InventoryLog.objects.create(
                    room_type=hold.room_type,
                    date=hold.date,
                    event=InventoryLog.EVENT_HOLD_EXPIRED,
                    quantity=-hold.rooms_held,
                    available_before=available_before,
                    available_after=cal.available_rooms,
                    reference_id=str(hold.hold_id),
                )
                count += 1
        except Exception as e:
            logger.error(f"Failed to release hold {hold.hold_id}: {e}")

    return count