from datetime import timedelta
import time
from decimal import Decimal
from django.conf import settings
from django.db import OperationalError, connection, transaction
from django.utils import timezone
from apps.core.models import OperationLog
from apps.core.observability import PerformanceLog
from apps.pricing.pricing_service import calculate_from_amounts, resolve_meal_plan_price
from apps.promos.models import PromoUsage
from apps.promos.selectors import get_active_promo
from apps.promos.services import calculate_promo_discount
from apps.rooms.models import RoomInventory
from .models import Booking, BookingGuest, BookingPriceBreakdown, BookingRoom, BookingStatusHistory
from .exceptions import InventoryUnavailableException, BookingStateTransitionError
from .financial_services import set_booking_financials
from .distributed_locks import acquire_booking_lock

_IDEMPOTENCY_COLUMN_AVAILABLE = None


def _has_idempotency_column():
    global _IDEMPOTENCY_COLUMN_AVAILABLE
    if _IDEMPOTENCY_COLUMN_AVAILABLE is not None:
        return _IDEMPOTENCY_COLUMN_AVAILABLE
    try:
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    Booking._meta.db_table,
                )
            }
        _IDEMPOTENCY_COLUMN_AVAILABLE = 'idempotency_key' in columns
    except OperationalError:
        _IDEMPOTENCY_COLUMN_AVAILABLE = False
    return _IDEMPOTENCY_COLUMN_AVAILABLE


def _date_range(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current += timedelta(days=1)


def create_booking(
    user,
    property_obj,
    room_type,
    quantity,
    meal_plan,
    check_in,
    check_out,
    guests,
    promo_code='',
    idempotency_key=None,
    locked_price=None,
):
    """
    Create booking with atomic transaction, inventory locking, and HOLD status.
    
    HARDENED RULES:
    1. Entire operation wrapped in transaction.atomic()
    2. Inventory locked via select_for_update() BEFORE any modifications
    3. Inventory validation happens WHILE holding row locks
    4. Inventory decremented ONLY after HOLD created
    5. Raises InventoryUnavailableException if insufficient inventory
    6. Returns Booking in HOLD status with hold_expires_at set
    """
    start_time = time.time()
    try:
        # Idempotency check (outside transaction to avoid early deadlock)
        use_idempotency = idempotency_key and _has_idempotency_column()
        if use_idempotency:
            existing = Booking.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        
        # Validate dates
        nights = (check_out - check_in).days
        if nights <= 0:
            raise ValueError('Invalid date range: check_out must be after check_in')
        
        # Calculate pricing (OUTSIDE transaction to avoid long locks)
        base_amount = Decimal(room_type.base_price) * quantity * nights
        # Resolve meal plan: supports model instance, string code, or empty
        meal_price_per_room_night = Decimal('0.00')
        if meal_plan and hasattr(meal_plan, 'price_modifier'):
            meal_price_per_room_night = Decimal(str(meal_plan.price_modifier))
        elif meal_plan and isinstance(meal_plan, str):
            meal_price_per_room_night = resolve_meal_plan_price(room_type, meal_plan)
        meal_amount = meal_price_per_room_night * quantity * nights
        
        promo = get_active_promo(promo_code) if promo_code else None
        if promo and promo.max_uses:
            usage_count = PromoUsage.objects.filter(promo=promo).count()
            if usage_count >= promo.max_uses:
                promo = None
        promo_discount = calculate_promo_discount(promo, base_amount + meal_amount)
        
        breakdown = calculate_from_amounts(
            base_amount,
            meal_amount,
            promo_discount,
            tariff_per_night=Decimal(room_type.base_price),
        )

        # If a locked price exists from BookingContext, use it as the final total
        # This ensures the guest pays exactly the price they were shown
        if locked_price is not None and Decimal(str(locked_price)) > 0:
            breakdown['total_amount'] = Decimal(str(locked_price))
        
        # DISTRIBUTED LOCK + ATOMIC BLOCK: Redis lock prevents cross-process races,
        # select_for_update prevents intra-DB races. Both layers are needed.
        with acquire_booking_lock(property_obj.id, room_type.id, check_in, check_out):
          with transaction.atomic():
            lock_start = time.time()
            
            # Lock inventory for update BEFORE validation
            inventories_qs = RoomInventory.objects.select_for_update().filter(
                room_type=room_type,
                date__gte=check_in,
                date__lt=check_out,
            ).order_by('date')  # Consistent ordering to prevent deadlock
            
            inventories = list(inventories_qs)
            lock_ms = int((time.time() - lock_start) * 1000)
            
            # Validate all dates have sufficient inventory WHILE locked
            inventory_map = {item.date: item for item in inventories}
            for day in _date_range(check_in, check_out):
                inventory = inventory_map.get(day)
                if not inventory:
                    raise InventoryUnavailableException(
                        f'No inventory record for {day}'
                    )
                if inventory.available_rooms < quantity:
                    raise InventoryUnavailableException(
                        f'Insufficient inventory on {day}: '
                        f'{inventory.available_rooms} < {quantity}'
                    )
            
            # Create HOLD booking FIRST (atomic state)
            booking_fields = {
                'user': user,
                'property': property_obj,
                'check_in': check_in,
                'check_out': check_out,
                'status': Booking.STATUS_HOLD,  # Always create in HOLD
                'total_amount': breakdown['total_amount'],
                'promo_code': promo.code if promo else '',
            }
            if use_idempotency:
                booking_fields['idempotency_key'] = idempotency_key
            
            booking = Booking.objects.create(**booking_fields)
            
            # Set financial fields (calculates all money fields)
            set_booking_financials(booking, base_amount + meal_amount, tariff_per_night=Decimal(room_type.base_price))
            
            # Now decrement inventory AFTER hold created
            for day in _date_range(check_in, check_out):
                inventory = inventory_map[day]
                inventory.available_rooms -= quantity
                inventory.available_count = inventory.available_rooms  # legacy sync
                inventory.booked_count = (inventory.booked_count or 0) + quantity
                # CRITICAL: Use update_fields to ensure no race conditions
                inventory.save(update_fields=['available_rooms', 'available_count', 'booked_count'])
            
            # Create booking details
            BookingRoom.objects.create(booking=booking, room_type=room_type, quantity=quantity)
            
            for guest in guests:
                BookingGuest.objects.create(
                    booking=booking,
                    full_name=guest['full_name'],
                    age=guest['age'],
                    email=guest.get('email', ''),
                )
            
            BookingPriceBreakdown.objects.create(booking=booking, **breakdown)
            
            if promo:
                PromoUsage.objects.create(promo=promo, booking=booking, user=user)
            
            # Record status history
            BookingStatusHistory.objects.create(
                booking=booking,
                status=Booking.STATUS_HOLD,
                note='Reservation hold created - 30 minute window'
            )
        
        # Log success (outside transaction)
        duration_ms = int((time.time() - start_time) * 1000)
        op_end = timezone.now()
        op_start = op_end - timedelta(milliseconds=duration_ms)
        try:
            PerformanceLog.objects.create(
                operation_type='booking_create_atomic',
                duration_ms=duration_ms,
                start_time=op_start,
                end_time=op_end,
                status='success',
                user_id=user.id if user else None,
                resource_id=booking.id if booking else None,
            )
            OperationLog.objects.create(
                operation_type='booking_hold_created',
                status='success',
                details=str({
                    'booking_id': booking.id,
                    'public_booking_id': booking.public_booking_id,
                    'total_amount': str(booking.total_amount),
                    'hold_expires_at': booking.hold_expires_at.isoformat() if booking.hold_expires_at else None,
                }),
                timestamp=timezone.now(),
            )
        except Exception as log_exc:
            import logging
            logging.getLogger('zygotrip').error('Failed to log booking success: %s', log_exc)
        
        return booking
        
    except InventoryUnavailableException as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        OperationLog.objects.create(
            operation_type='booking_failed',
            status='failed',
            details=str({
                'error': 'InventoryUnavailableException',
                'message': str(exc),
                'property_id': getattr(property_obj, 'id', None),
            }),
            timestamp=timezone.now(),
        )
        raise
        
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        PerformanceLog.objects.create(
            operation_type='booking_create_atomic',
            duration_ms=duration_ms,
            start_time=timezone.now(),
            end_time=timezone.now(),
            status='error',
            error_message=str(exc),
            user_id=user.id if user else None,
            resource_id=property_obj.id if property_obj else None,
        )
        OperationLog.objects.create(
            operation_type='booking_failed',
            status='failed',
            details=str({
                'error': type(exc).__name__,
                'message': str(exc),
                'property_id': getattr(property_obj, 'id', None),
            }),
            timestamp=timezone.now(),
        )
        raise


def create_simple_booking(user, property_obj, form):
    """Create a simple booking from the create view form."""
    check_in = form.cleaned_data['check_in']
    check_out = form.cleaned_data['check_out']
    quantity = form.cleaned_data.get('quantity', 1)

    nights = (check_out - check_in).days
    if nights <= 0:
        raise ValueError('Invalid date range')

    base_price = property_obj.base_price * nights * quantity if property_obj.base_price else 0

    guest_name = form.cleaned_data.get('guest_full_name', user.full_name)
    guest_email = form.cleaned_data.get('guest_email', user.email)
    guest_phone = form.cleaned_data.get('guest_phone', '')

    booking = Booking.objects.create(
        user=user,
        property=property_obj,
        check_in=check_in,
        check_out=check_out,
        total_amount=base_price,
        status=Booking.STATUS_REVIEW,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_phone=guest_phone,
    )

    # Use canonical pricing instead of hardcoded 5% GST
    tariff_per_night = property_obj.base_price if property_obj.base_price else Decimal('0')
    breakdown = calculate_from_amounts(
        base_amount=base_price,
        meal_amount=Decimal('0.00'),
        promo_discount=Decimal('0.00'),
        tariff_per_night=tariff_per_night,
    )

    BookingPriceBreakdown.objects.create(
        booking=booking,
        base_amount=base_price,
        meal_amount=0,
        service_fee=breakdown['service_fee'],
        gst=breakdown['gst'],
        promo_discount=0,
        total_amount=breakdown['total_amount'],
    )

    booking.total_amount = breakdown['total_amount']
    booking.save(update_fields=['total_amount'])

    BookingStatusHistory.objects.create(
        booking=booking,
        status=Booking.STATUS_REVIEW,
        note='Booking created',
    )

    return booking


def transition_booking_status(booking, new_status, note=''):
    """
    Transition booking to new status with state machine validation.
    
    HARDENED RULES:
    1. Check if transition is valid based on VALID_TRANSITIONS
    2. Update status via atomic transaction
    3. Record status history
    4. Return updated booking
    5. Raise BookingStateTransitionError for invalid transitions
    """
    if new_status not in dict(Booking.STATUS_CHOICES):
        raise BookingStateTransitionError(f'Invalid status: {new_status}')
    
    valid_next_states = Booking.VALID_TRANSITIONS.get(booking.status, [])
    if new_status not in valid_next_states:
        raise BookingStateTransitionError(
            f'Cannot transition from {booking.status} to {new_status}. '
            f'Valid transitions: {valid_next_states}'
        )
    
    with transaction.atomic():
        booking.status = new_status
        booking.save(update_fields=['status', 'updated_at'])
        BookingStatusHistory.objects.create(
            booking=booking,
            status=new_status,
            note=note,
        )
    
    return booking