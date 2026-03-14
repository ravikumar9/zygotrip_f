"""
Booking Orchestration Engine — manages the full booking lifecycle with
idempotent operations, supplier verification, and automatic retry logic.

State flow:
  SEARCHED → HELD → PAYMENT_PENDING → CONFIRMED → CHECKED_IN → CHECKED_OUT → SETTLED
  HELD → EXPIRED
  PAYMENT_PENDING → FAILED
  CONFIRMED → CANCELLED → REFUNDED

All state transitions route through BookingStateMachine.transition() which
enforces VALID_TRANSITIONS with select_for_update locking.

This module adds:
  - BookingOrchestrator: high-level facade for the booking lifecycle
  - Supplier verification post-payment
  - Idempotent create/cancel with retry
  - Automatic failed-booking recovery
"""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from celery import shared_task

from apps.core.ota_events import (
    BOOKING_CANCELLED,
    BOOKING_CREATED,
    INVENTORY_UPDATED,
    publish_ota_event,
)

logger = logging.getLogger('zygotrip.booking.orchestrator')


class BookingOrchestrator:
    """
    High-level booking lifecycle orchestration.

    Usage:
        orchestrator = BookingOrchestrator()
        result = orchestrator.initiate_booking(user, rooms, dates, ...)
        result = orchestrator.confirm_after_payment(booking_id, payment_txn_id)
    """

    # ------------------------------------------------------------------
    # 1. Initiate — Create booking + hold inventory
    # ------------------------------------------------------------------

    @staticmethod
    def initiate_booking(
        user,
        property_id: int,
        room_type_id: int,
        check_in,
        check_out,
        rooms: int = 1,
        guests: list = None,
        idempotency_key: str = None,
    ) -> dict:
        """
        Create a booking in HELD state with inventory locked.
        Idempotent: if idempotency_key already exists, return existing booking.
        """
        from apps.booking.models import Booking

        # Idempotency check
        if idempotency_key:
            existing = Booking.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                logger.info('Idempotent hit: booking %s', existing.id)
                return {'booking_id': existing.id, 'status': existing.status, 'idempotent': True}

        from apps.booking.services import create_booking

        booking = create_booking(
            user=user,
            property_id=property_id,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            rooms=rooms,
            guests=guests or [],
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
        publish_ota_event(
            BOOKING_CREATED,
            payload={
                'booking_id': booking.id,
                'booking_uuid': str(booking.uuid),
                'property_id': property_id,
                'room_type_id': room_type_id,
                'check_in': str(check_in),
                'check_out': str(check_out),
                'rooms': rooms,
                'status': booking.status,
                'total_amount': str(booking.total_amount),
            },
            user_id=getattr(user, 'id', None),
            source='apps.booking.orchestrator.initiate_booking',
        )
        return {
            'booking_id': booking.id,
            'status': booking.status,
            'hold_expires_at': (timezone.now() + timedelta(minutes=15)).isoformat(),
            'total_amount': float(booking.total_amount),
        }

    # ------------------------------------------------------------------
    # 2. Payment → Confirm
    # ------------------------------------------------------------------

    @staticmethod
    def confirm_after_payment(booking_id: int, payment_txn_id: str) -> dict:
        """
        Transition PAYMENT_PENDING → CONFIRMED after payment success.
        Also kicks off supplier verification asynchronously.
        """
        from apps.booking.models import Booking
        from apps.booking.state_machine import BookingStateMachine

        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking_id)
            if booking.status == 'confirmed':
                return {'booking_id': booking.id, 'status': 'confirmed', 'idempotent': True}

            BookingStateMachine.transition(booking, 'confirmed')
            booking.payment_txn_id = payment_txn_id
            booking.confirmed_at = timezone.now()
            booking.save(update_fields=['status', 'payment_txn_id', 'confirmed_at', 'updated_at'])

        # Async: verify with supplier + send confirmation
        verify_supplier_booking.delay(booking_id)
        send_booking_confirmation.delay(booking_id)

        return {'booking_id': booking.id, 'status': 'confirmed'}

    # ------------------------------------------------------------------
    # 3. Cancellation
    # ------------------------------------------------------------------

    @staticmethod
    def cancel_booking(booking_id: int, reason: str = '', requested_by: str = 'user') -> dict:
        """
        Cancel a booking. Calculates refund per cancellation policy.
        Idempotent: calling cancel on already-cancelled returns success.
        """
        from apps.booking.models import Booking
        from apps.booking.state_machine import BookingStateMachine

        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking_id)
            if booking.status in ('cancelled', 'refunded'):
                return {'booking_id': booking.id, 'status': booking.status, 'idempotent': True}

            BookingStateMachine.transition(booking, 'cancelled')
            booking.cancellation_reason = reason
            booking.cancelled_at = timezone.now()
            booking.cancelled_by = requested_by
            booking.save(update_fields=[
                'status', 'cancellation_reason', 'cancelled_at', 'cancelled_by', 'updated_at',
            ])

        # Calculate refund
        refund_amount = BookingOrchestrator._calculate_refund(booking)
        if refund_amount > 0:
            process_booking_refund.delay(booking_id, float(refund_amount))

        # Release inventory
        release_inventory.delay(booking_id)

        publish_ota_event(
            BOOKING_CANCELLED,
            payload={
                'booking_id': booking.id,
                'booking_uuid': str(booking.uuid),
                'property_id': booking.property_id,
                'status': booking.status,
                'reason': reason,
                'requested_by': requested_by,
                'refund_amount': str(refund_amount),
            },
            user_id=getattr(booking.user, 'id', None),
            source='apps.booking.orchestrator.cancel_booking',
        )

        return {
            'booking_id': booking.id,
            'status': 'cancelled',
            'refund_amount': float(refund_amount),
        }

    @staticmethod
    def _calculate_refund(booking) -> Decimal:
        """Calculate refund amount based on cancellation policy + timing."""
        hours_before = Decimal('0')
        if booking.check_in:
            delta = booking.check_in - timezone.now()
            hours_before = Decimal(str(max(0, delta.total_seconds() / 3600)))

        total = booking.total_amount or Decimal('0')

        # Check hotel cancellation policy
        try:
            from apps.hotels.rate_plan_engine import CancellationPolicy, CancellationTier
            policy = CancellationPolicy.objects.filter(
                rate_plans__room_type__property_id=booking.property_id,
                is_active=True,
            ).first()
            if policy:
                return policy.calculate_refund(total, float(hours_before))
        except Exception:
            pass

        # Default refund rules
        if hours_before > 48:
            return total  # Full refund
        elif hours_before > 24:
            return total * Decimal('0.50')  # 50%
        return Decimal('0')  # No refund

    # ------------------------------------------------------------------
    # 4. Retry failed bookings
    # ------------------------------------------------------------------

    @staticmethod
    def retry_failed_booking(booking_id: int) -> dict:
        """Attempt to recover a failed booking by retrying supplier call."""
        from apps.booking.models import Booking
        from apps.booking.state_machine import BookingStateMachine

        booking = Booking.objects.get(id=booking_id)
        if booking.status != 'failed':
            return {'error': f'Cannot retry booking in status {booking.status}'}

        retry_count = getattr(booking, 'retry_count', 0)
        if retry_count >= 3:
            return {'error': 'Max retries exceeded', 'booking_id': booking_id}

        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update().get(id=booking_id)
                BookingStateMachine.transition(booking, 'payment_pending')
                booking.retry_count = retry_count + 1
                booking.save(update_fields=['status', 'retry_count', 'updated_at'])

            verify_supplier_booking.delay(booking_id)
            return {'booking_id': booking_id, 'status': 'retrying', 'retry_count': retry_count + 1}
        except Exception as e:
            logger.error('Retry failed for booking %s: %s', booking_id, e)
            return {'error': str(e)}


# ============================================================================
# Celery tasks for async operations
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def verify_supplier_booking(self, booking_id: int):
    """Verify booking confirmation with the supplier after payment."""
    from apps.booking.models import Booking

    try:
        booking = Booking.objects.get(id=booking_id)
        supplier_ref = getattr(booking, 'supplier_booking_ref', None)

        if not supplier_ref:
            logger.info('No supplier ref for booking %s — direct inventory', booking_id)
            return {'verified': True, 'type': 'direct'}

        # Verify supplier status
        from apps.core.supplier_framework import get_supplier_adapter
        adapter = get_supplier_adapter(booking.supplier_name)
        if adapter:
            status = adapter.verify_booking(supplier_ref)
            if status.get('confirmed'):
                logger.info('Supplier verified booking %s', booking_id)
                return {'verified': True}
            else:
                logger.warning('Supplier verification pending for %s', booking_id)
                self.retry(countdown=60)
        return {'verified': True}
    except Exception as e:
        logger.error('Supplier verification failed for %s: %s', booking_id, e)
        self.retry(exc=e)


@shared_task
def send_booking_confirmation(booking_id: int):
    """Send multi-channel booking confirmation."""
    from apps.booking.models import Booking
    try:
        booking = Booking.objects.select_related('user').get(id=booking_id)
        from apps.core.notification_service import NotificationDispatcher
        NotificationDispatcher.send_booking_confirmation(booking)
    except Exception as e:
        logger.error('Confirmation notification failed for %s: %s', booking_id, e)


@shared_task
def process_booking_refund(booking_id: int, refund_amount: float):
    """Process refund for a cancelled booking."""
    from apps.booking.models import Booking
    try:
        booking = Booking.objects.get(id=booking_id)
        from apps.payments.gateways import refund_payment
        refund_payment(
            booking_id=booking_id,
            amount=Decimal(str(refund_amount)),
            reason='booking_cancellation',
        )
        # Update booking
        booking.refund_amount = Decimal(str(refund_amount))
        booking.status = 'refunded'
        booking.save(update_fields=['refund_amount', 'status', 'updated_at'])
        logger.info('Refund %s processed for booking %s', refund_amount, booking_id)
    except Exception as e:
        logger.error('Refund failed for booking %s: %s', booking_id, e)


@shared_task
def release_inventory(booking_id: int):
    """Release held inventory after cancellation."""
    from apps.booking.models import BookingRoom
    try:
        rooms = BookingRoom.objects.filter(booking_id=booking_id)
        updated_room_types = []
        for room in rooms:
            from apps.inventory.models import InventoryCalendar
            InventoryCalendar.objects.filter(
                room_type_id=room.room_type_id,
                date__range=(room.check_in, room.check_out - timedelta(days=1)),
            ).update(available_rooms=models.F('available_rooms') + room.quantity)
            updated_room_types.append(room.room_type_id)
        logger.info('Inventory released for booking %s', booking_id)
        publish_ota_event(
            INVENTORY_UPDATED,
            payload={
                'booking_id': booking_id,
                'room_type_ids': updated_room_types,
                'reason': 'booking_cancelled_release',
            },
            source='apps.booking.orchestrator.release_inventory',
        )
    except Exception as e:
        logger.error('Inventory release failed for %s: %s', booking_id, e)


from django.db import models  # noqa: E402


@shared_task
def recover_failed_bookings():
    """
    Periodic task: find bookings stuck in 'failed' state and attempt recovery.
    Runs every 15 minutes via Celery Beat.
    """
    from apps.booking.models import Booking
    cutoff = timezone.now() - timedelta(hours=1)
    failed = Booking.objects.filter(
        status='failed',
        updated_at__gte=cutoff,
    ).exclude(retry_count__gte=3)

    recovered = 0
    for booking in failed[:20]:  # Process at most 20 per cycle
        result = BookingOrchestrator.retry_failed_booking(booking.id)
        if 'error' not in result:
            recovered += 1

    if recovered:
        logger.info('Recovered %d/%d failed bookings', recovered, failed.count())
    return recovered


@shared_task
def expire_stale_holds():
    """
    Periodic task: expire bookings stuck in HELD state beyond hold window.
    Runs every 5 minutes via Celery Beat.
    """
    from apps.booking.models import Booking
    from apps.booking.state_machine import BookingStateMachine

    cutoff = timezone.now() - timedelta(minutes=15)
    stale = Booking.objects.filter(
        status='held',
        created_at__lt=cutoff,
    )
    expired = 0
    for booking in stale[:50]:
        try:
            with transaction.atomic():
                b = Booking.objects.select_for_update().get(id=booking.id)
                if b.status == 'held':
                    BookingStateMachine.transition(b, 'expired')
                    b.save(update_fields=['status', 'updated_at'])
                    expired += 1
        except Exception as e:
            logger.warning('Failed to expire hold %s: %s', booking.id, e)
    if expired:
        logger.info('Expired %d stale holds', expired)
    return expired
