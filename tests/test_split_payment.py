from decimal import Decimal

import pytest

from apps.booking.split_payment_service import SplitPaymentService
from apps.payments.models import PaymentTransaction


@pytest.mark.django_db
def test_wallet_gateway_split_succeeds(booking_factory, wallet_factory, monkeypatch):
    booking = booking_factory(total_amount=Decimal('1000'))
    wallet_factory(user=booking.user, balance=Decimal('1000'))

    monkeypatch.setattr(
        'apps.booking.split_payment_service.process_payment',
        lambda **kwargs: {'transaction_id': 'TXN-1', 'order_id': 'ORDER-1'},
    )
    result = SplitPaymentService().initiate_split(
        booking=booking,
        wallet_amount=Decimal('400'),
        gateway_amount=Decimal('600'),
        gateway='cashfree',
        user=booking.user,
    )
    assert result['wallet_txn_id']


@pytest.mark.django_db
def test_gateway_failure_unlocks_wallet(booking_factory, wallet_factory):
    booking = booking_factory(total_amount=Decimal('1000'))
    wallet = wallet_factory(user=booking.user, balance=Decimal('1000'))
    wallet.lock_balance(Decimal('400'), reference=str(booking.uuid))
    wallet_txn = PaymentTransaction.objects.create(
        transaction_id='LOCK-1',
        gateway=PaymentTransaction.GATEWAY_WALLET,
        user=booking.user,
        booking=booking,
        booking_reference=str(booking.uuid),
        amount=Decimal('400'),
        status=PaymentTransaction.STATUS_LOCKED,
    )

    result = SplitPaymentService().complete_split(booking, gateway_txn_id='missing')
    wallet.refresh_from_db()
    wallet_txn.refresh_from_db()
    assert result['success'] is False
    assert wallet.locked_balance == 0


@pytest.mark.django_db
def test_wallet_insufficient_balance_rejected(booking_factory, wallet_factory):
    booking = booking_factory(total_amount=Decimal('1000'))
    wallet_factory(user=booking.user, balance=Decimal('50'))
    with pytest.raises(ValueError):
        SplitPaymentService().initiate_split(
            booking=booking,
            wallet_amount=Decimal('400'),
            gateway_amount=Decimal('600'),
            gateway='cashfree',
            user=booking.user,
        )
