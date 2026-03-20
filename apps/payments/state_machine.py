"""Payment transaction state machine.

This module is the only allowed path for payment status transitions.
"""

import logging

logger = logging.getLogger('zygotrip.payments')


class PaymentStateMachine:
    """Validated transitions for PaymentTransaction status updates."""

    # Required production lifecycle states.
    VALID_STATES = {
        'initiated',
        'pending',
        'success',
        'failed',
        'cancelled',
    }

    # Backward-compatible support for existing refund path.
    OPTIONAL_STATES = {'refunded'}

    ALLOWED_TRANSITIONS = {
        'initiated': {'pending', 'failed', 'cancelled'},
        'pending': {'success', 'failed', 'cancelled'},
        'success': {'refunded'},
        'failed': set(),
        'cancelled': set(),
        'refunded': set(),
    }

    @classmethod
    def transition(cls, txn, to_status, *, reason='', gateway_response=None, gateway_txn_id=''):
        """Validate and apply a payment status transition."""
        from_status = txn.status

        if to_status not in cls.VALID_STATES and to_status not in cls.OPTIONAL_STATES:
            logger.error(
                'payment_transition_invalid_target txn=%s from=%s to=%s',
                txn.transaction_id,
                from_status,
                to_status,
            )
            raise ValueError(f'Invalid target payment status: {to_status}')

        if from_status not in cls.ALLOWED_TRANSITIONS:
            logger.error(
                'payment_transition_invalid_source txn=%s from=%s to=%s',
                txn.transaction_id,
                from_status,
                to_status,
            )
            raise ValueError(f'Invalid source payment status: {from_status}')

        if from_status == to_status:
            logger.info(
                'payment_transition_noop txn=%s status=%s',
                txn.transaction_id,
                to_status,
            )
            return False

        if to_status not in cls.ALLOWED_TRANSITIONS[from_status]:
            logger.warning(
                'payment_transition_rejected txn=%s from=%s to=%s reason=%s',
                txn.transaction_id,
                from_status,
                to_status,
                reason,
            )
            raise ValueError(
                f'Invalid payment transition {from_status} -> {to_status} for {txn.transaction_id}'
            )

        txn.status = to_status
        if gateway_txn_id:
            txn.gateway_transaction_id = gateway_txn_id
        if gateway_response is not None:
            txn.gateway_response = gateway_response
        if reason is not None and to_status == txn.STATUS_FAILED:
            txn.failure_reason = reason

        update_fields = ['status', 'updated_at']
        if gateway_txn_id:
            update_fields.append('gateway_transaction_id')
        if gateway_response is not None:
            update_fields.append('gateway_response')
        if to_status == txn.STATUS_FAILED:
            update_fields.append('failure_reason')

        txn.save(update_fields=update_fields)

        logger.info(
            'payment_transition_applied txn=%s from=%s to=%s gateway_txn_id=%s reason=%s',
            txn.transaction_id,
            from_status,
            to_status,
            gateway_txn_id or '',
            reason or '',
        )
        return True
