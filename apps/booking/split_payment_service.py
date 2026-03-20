"""Split payment orchestration between wallet and external gateway."""
import logging
from decimal import Decimal

from django.db import transaction

from apps.booking.models import Booking
from apps.payments.models import PaymentTransaction
from apps.payments.services import process_payment
from apps.wallet.services import get_or_create_wallet

logger = logging.getLogger(__name__)


class SplitPaymentService:
    def initiate_split(self, booking, wallet_amount, gateway_amount, gateway, user):
        wallet_amount = Decimal(str(wallet_amount))
        gateway_amount = Decimal(str(gateway_amount))
        total = wallet_amount + gateway_amount
        if total != Decimal(str(booking.total_amount)):
            raise ValueError('wallet_amount + gateway_amount must equal booking.total_amount')

        wallet = get_or_create_wallet(user)
        if wallet is None:
            raise ValueError('Wallet not found')

        wallet_txn = wallet.lock_balance(wallet_amount, reference=str(booking.uuid))

        wallet_payment_txn = PaymentTransaction.objects.create(
            transaction_id=f'WLT-{booking.uuid.hex[:12].upper()}',
            gateway=PaymentTransaction.GATEWAY_WALLET,
            user=user,
            booking=booking,
            booking_reference=str(booking.uuid),
            amount=wallet_amount,
            status=PaymentTransaction.STATUS_LOCKED,
            gateway_transaction_id=str(wallet_txn.uid),
        )

        gateway_result = process_payment(
            booking=booking,
            amount=gateway_amount,
            payment_method=gateway,
            user=user,
        )
        return {
            'order_id': gateway_result.get('order_id') or gateway_result.get('transaction_id'),
            'wallet_txn_id': wallet_payment_txn.id,
        }

    def complete_split(self, booking, gateway_txn_id):
        gateway_txn = PaymentTransaction.objects.filter(
            transaction_id=gateway_txn_id,
            booking=booking,
        ).first()
        wallet_txn = PaymentTransaction.objects.filter(
            booking=booking,
            gateway=PaymentTransaction.GATEWAY_WALLET,
            status=PaymentTransaction.STATUS_LOCKED,
        ).first()

        if wallet_txn is None:
            raise ValueError('Locked wallet transaction not found')

        wallet = get_or_create_wallet(booking.user)
        with transaction.atomic():
            if gateway_txn and gateway_txn.status == PaymentTransaction.STATUS_SUCCESS:
                wallet.capture_locked(wallet_txn.amount, reference=str(booking.uuid))
                wallet_txn.status = PaymentTransaction.STATUS_SUCCESS
                wallet_txn.save(update_fields=['status', 'updated_at'])
                booking.status = Booking.STATUS_CONFIRMED
                booking.save(update_fields=['status', 'updated_at'])
                return {'success': True, 'booking_status': booking.status}

            wallet.unlock(wallet_txn.amount, reference=str(booking.uuid))
            wallet_txn.status = PaymentTransaction.STATUS_FAILED
            wallet_txn.failure_reason = 'Gateway payment failed'
            wallet_txn.save(update_fields=['status', 'failure_reason', 'updated_at'])
            booking.status = Booking.STATUS_FAILED
            booking.save(update_fields=['status', 'updated_at'])
        return {'success': False, 'booking_status': booking.status}
