"""Payment processing and webhook handling services (PHASE 3, PROMPT 6)."""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.booking.models import Booking
from apps.booking.state_machine import BookingStateMachine
from .models import Payment


def process_payment(booking=None, amount=None, payment_method=None, user=None):
    """
    Process a payment for a booking via designated gateway.
    Called by API views — delegates to PaymentRouter.
    """
    from apps.payments.gateways import PaymentRouter
    from apps.payments.models import PaymentTransaction
    import uuid as _uuid

    if not booking or not amount or not payment_method:
        raise ValidationError('booking, amount, and payment_method are required')

    gateway = PaymentRouter.get_gateway(payment_method)
    txn_id = f'{payment_method[:3].upper()}-{_uuid.uuid4().hex[:12].upper()}'

    txn = PaymentTransaction.objects.create(
        transaction_id=txn_id,
        gateway=payment_method,
        user=user or booking.user,
        booking=booking,
        booking_reference=str(booking.uuid),
        amount=amount,
        status=PaymentTransaction.STATUS_INITIATED,
    )

    result = gateway.initiate_payment(booking, amount, user or booking.user, txn)
    if result.get('success'):
        return {
            'status': 'initiated',
            'transaction_id': txn_id,
            'amount': amount,
            'method': payment_method,
            **result,
        }
    else:
        return {
            'status': 'failed',
            'transaction_id': txn_id,
            'amount': amount,
            'method': payment_method,
            'error': result.get('error', 'Payment initiation failed'),
        }


@transaction.atomic
def handle_payment_webhook(payment_reference_id, status, amount, **extra_data):
    """
    Idempotent payment webhook handler.
    
    HARDENED RULES:
    1. Use payment_reference_id as idempotency key
    2. Check if booking already CONFIRMED (idempotent)
    3. Ignore duplicate callbacks
    4. Log duplicate attempts for audit
    5. Only transition from PAYMENT_PENDING → CONFIRMED
    
    Args:
        payment_reference_id: Unique payment gateway transaction ID
        status: 'success', 'failed', 'pending'
        amount: Decimal payment amount
        extra_data: Additional webhook data
    
    Returns:
        dict with operation result
        
    Raises:
        ValidationError: If payment data is invalid
    """
    # Find booking by payment_reference_id
    try:
        booking = Booking.objects.select_for_update().get(
            payment_reference_id=payment_reference_id
        )
    except Booking.DoesNotExist:
        raise ValidationError(f"No booking found for payment {payment_reference_id}")
    
    # Check if already processed (idempotency check)
    if booking.status == Booking.STATUS_CONFIRMED:
        # Already confirmed, log and return (duplicate webhook)
        from django.core.exceptions import SuspiciousOperation
        from apps.core.models import OperationLog
        OperationLog.objects.create(
            operation_type='payment_webhook_duplicate',
            status='ignored',
            details=str({
                'booking_id': booking.id,
                'payment_reference_id': payment_reference_id,
                'status': status,
            }),
            timestamp=timezone.now(),
        )
        return {
            'success': True,
            'message': 'Booking already confirmed',
            'booking_id': booking.id,
            'idempotent': True,
        }
    
    # Only process if in PAYMENT_PENDING state
    if booking.status != Booking.STATUS_PAYMENT_PENDING:
        raise ValidationError(
            f"Booking {booking.id} not in PAYMENT_PENDING state. "
            f"Current: {booking.status}"
        )
    
    # Validate amount
    if Decimal(str(amount)) != booking.total_amount:
        raise ValidationError(
            f"Amount mismatch: {amount} != {booking.total_amount}"
        )
    
    # Process based on payment status
    if status == 'success':
        # Create payment record
        Payment.objects.create(
            booking=booking,
            user=booking.user,
            amount=amount,
            payment_method='gateway',
            transaction_id=payment_reference_id,
            status='success',
        )
        
        # Transition to CONFIRMED
        BookingStateMachine.transition(
            booking,
            Booking.STATUS_CONFIRMED,
            note=f'Payment confirmed via webhook: {payment_reference_id}',
        )
        
        return {
            'success': True,
            'message': 'Payment confirmed, booking confirmed',
            'booking_id': booking.id,
        }
    
    elif status == 'failed':
        # Create failed payment record
        Payment.objects.create(
            booking=booking,
            user=booking.user,
            amount=amount,
            payment_method='gateway',
            transaction_id=payment_reference_id,
            status='failed',
        )
        
        # Transition to FAILED (will trigger inventory release)
        BookingStateMachine.transition(
            booking,
            Booking.STATUS_FAILED,
            note=f'Payment failed via webhook: {payment_reference_id}',
        )
        
        # Release inventory — wrapped in try/except so failure status is always recorded
        try:
            from apps.booking.hold_expiry_service import _release_hold_transaction
            _release_hold_transaction(booking)
        except Exception as inv_exc:
            import logging
            logging.getLogger('zygotrip').error(
                'CRITICAL: Failed to release inventory for booking %s after payment failure: %s',
                booking.id, inv_exc,
            )
        
        return {
            'success': False,
            'message': 'Payment failed, booking cancelled',
            'booking_id': booking.id,
        }
    
    else:
        # Still pending, do nothing
        return {
            'success': True,
            'message': 'Payment still pending',
            'booking_id': booking.id,
        }
