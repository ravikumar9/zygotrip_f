"""
Refund calculation and processing service (PHASE 4, PROMPT 7).

Handles:
1. Refund amount calculation based on cancellation deadline
2. Status transition to REFUND_PENDING
3. Gateway refund API call
4. Marking as REFUNDED on success
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import Booking
from .state_machine import BookingStateMachine
from .exceptions import RefundCalculationError

logger = logging.getLogger('zygotrip.booking.refund')


def calculate_refund_amount(booking, cancel_time=None):
    """
    Calculate refund amount based on cancellation deadline.
    
    Refund Policy (configurable via settings):
    - **Free cancellation**: Up to 72 hours before check-in = 100% refund
    - **Partial refund**: 24-72 hours = 50% refund
    - **No refund**: Less than 24 hours = 0% refund
    
    Args:
        booking: Booking instance
        cancel_time: datetime when cancellation happens (default: now)
    
    Returns:
        dict with:
        - refund_amount: Decimal amount to refund
        - refund_policy: String explaining policy applied
        - full_refund: Boolean if 100% refund
        - partial_refund: Boolean if 50% refund
    """
    if cancel_time is None:
        cancel_time = timezone.now()
    
    check_in = timezone.make_aware(
        timezone.datetime.combine(booking.check_in, timezone.datetime.min.time())
    )
    
    # Hours until check-in
    hours_until_checkin = (check_in - cancel_time).total_seconds() / 3600
    
    # Refund thresholds (configurable)
    free_cancellation_hours = int(
        getattr(settings, 'REFUND_FREE_DEADLINE_HOURS', 72)
    )
    partial_cancellation_hours = int(
        getattr(settings, 'REFUND_PARTIAL_DEADLINE_HOURS', 24)
    )
    partial_refund_percentage = Decimal(
        str(getattr(settings, 'REFUND_PARTIAL_PERCENTAGE', '0.50'))
    )
    
    gross_amount = booking.gross_amount
    
    if hours_until_checkin >= free_cancellation_hours:
        # Free cancellation
        refund_amount = gross_amount
        policy = 'full'
        full_refund = True
        partial_refund = False
    
    elif hours_until_checkin >= partial_cancellation_hours:
        # Partial refund
        refund_amount = gross_amount * partial_refund_percentage
        policy = 'partial'
        full_refund = False
        partial_refund = True
    
    else:
        # No refund
        refund_amount = Decimal('0')
        policy = 'none'
        full_refund = False
        partial_refund = False
    
    return {
        'refund_amount': refund_amount,
        'refund_policy': policy,
        'full_refund': full_refund,
        'partial_refund': partial_refund,
        'hours_until_checkin': round(hours_until_checkin, 1),
    }


@transaction.atomic
def initiate_refund(booking, reason='', cancel_time=None):
    """
    Initiate refund for a booking.
    
    Process:
    1. Calculate refund amount
    2. Verify booking is CONFIRMED (not already refunded)
    3. Transition to REFUND_PENDING
    4. Call payment gateway refund API
    5. On success, transition to REFUNDED
    6. On failure, stay in REFUND_PENDING for retry
    
    Args:
        booking: Booking instance
        reason: Human readable reason for refund  
        cancel_time: When cancellation occurred
    
    Returns:
        dict with refund status and details
    
    Raises:
        RefundCalculationError: If refund cannot be calculated or processed
    """
    if booking.status != Booking.STATUS_CONFIRMED:
        raise RefundCalculationError(
            f'Can only refund CONFIRMED bookings. Current status: {booking.status}'
        )
    
    # Calculate refund
    refund_calc = calculate_refund_amount(booking, cancel_time)
    refund_amount = refund_calc['refund_amount']
    
    # Transition to REFUND_PENDING
    note = f'Refund initiated: {refund_calc["refund_policy"]} refund (₹{refund_amount}). Reason: {reason}'
    
    booking = BookingStateMachine.transition(
        booking,
        Booking.STATUS_REFUND_PENDING,
        note=note,
    )
    
    # Update refund amount on booking
    booking.refund_amount = refund_amount
    booking.save(update_fields=['refund_amount', 'updated_at'])
    
    # Call payment gateway
    if refund_amount > 0:
        try:
            gateway_result = _call_gateway_refund(
                booking=booking,
                amount=refund_amount,
            )
            
            if gateway_result['success']:
                # Mark as REFUNDED
                booking.refund_reference_id = gateway_result.get('refund_reference_id')
                booking.save(update_fields=['refund_reference_id', 'updated_at'])
                
                BookingStateMachine.transition(
                    booking,
                    Booking.STATUS_REFUNDED,
                    note=f'Refund processed: {gateway_result.get("refund_reference_id")}',
                )
                
                return {
                    'success': True,
                    'message': f'Refund of ₹{refund_amount} processed',
                    'refund_amount': refund_amount,
                    'referenceId': gateway_result.get('refund_reference_id'),
                }
            else:
                # Gateway error, stay in REFUND_PENDING
                return {
                    'success': False,
                    'message': f'Gateway refund failed: {gateway_result.get("error")}',
                    'refund_amount': refund_amount,
                    'retry': True,
                }
        
        except Exception as e:
            raise RefundCalculationError(f'Gateway refund error: {str(e)}')
    
    else:
        # No refund due
        BookingStateMachine.transition(
            booking,
            Booking.STATUS_REFUNDED,
            note='No refund applicable per policy',
        )
        
        return {
            'success': True,
            'message': 'No refund applicable',
            'refund_amount': Decimal('0'),
        }


def _call_gateway_refund(booking, amount):
    """
    Call payment gateway refund API.
    Delegates to the appropriate gateway based on the booking's payment transaction.
    
    Args:
        booking: Booking instance
        amount: Decimal refund amount
    
    Returns:
        dict with:
        - success: Boolean
        - refund_reference_id: Gateway's refund ID
        - error: Error message if failed
    """
    from apps.payments.models import PaymentTransaction
    from apps.payments.gateways import PaymentRouter

    # Find the successful payment transaction for this booking
    txn = PaymentTransaction.objects.filter(
        booking=booking,
        status=PaymentTransaction.STATUS_SUCCESS,
    ).order_by('-created_at').first()

    if not txn:
        return {
            'success': False,
            'error': 'No successful payment transaction found for this booking',
        }

    try:
        gateway = PaymentRouter.get_gateway(txn.gateway)
        result = gateway.refund(txn, amount)

        if result.get('success'):
            # Record refund on transaction
            txn.initiate_refund(amount)
            txn.refund_gateway_id = result.get('refund_id', '')
            txn.save(update_fields=['refund_gateway_id', 'updated_at'])

            # Email notification
            try:
                from apps.core.email_service import send_refund_initiated
                _email = (
                    getattr(booking, 'guest_email', None)
                    or (booking.user.email if booking.user else '')
                )
                _name = (
                    getattr(booking, 'guest_name', None)
                    or (booking.user.full_name if booking.user else 'Guest')
                )
                if _email:
                    send_refund_initiated(
                        to_email=_email,
                        booking_ref=str(booking.public_booking_id),
                        guest_name=_name,
                        refund_amount=f'₹{amount:,.0f}',
                        days=5,
                    )
            except Exception as _e:
                logger.warning('Refund email failed (non-fatal): %s', _e)

            # FCM refund notification
            try:
                from apps.notifications.fcm_service import FCMService
                if booking.user:
                    FCMService().send_to_user(
                        user=booking.user,
                        title='Refund Initiated',
                        body=f'Your refund for booking {booking.public_booking_id} has been initiated.',
                        data={
                            'type': 'refund_initiated',
                            'booking_uuid': str(booking.public_booking_id),
                        },
                    )
            except Exception as _e:
                logger.warning('Refund FCM failed (non-fatal): %s', _e)

            return {
                'success': True,
                'refund_reference_id': result.get('refund_id', f'refund_{booking.id}_{timezone.now().timestamp()}'),
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Gateway refund failed'),
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }
