import pytest
from decimal import Decimal


class TestWalletService:
    def test_credit_increases_balance(self, wallet):
        initial = wallet.balance
        wallet.credit(Decimal('1000'), txn_type='topup', reference='t1')
        wallet.refresh_from_db()
        assert wallet.balance == initial + Decimal('1000')

    def test_debit_decreases_balance(self, wallet):
        wallet.balance = Decimal('2000')
        wallet.save()
        wallet.debit(Decimal('500'), txn_type='booking_payment', reference='t2')
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('1500')

    def test_can_debit_true_when_sufficient(self, wallet):
        wallet.balance = Decimal('1000')
        wallet.save()
        assert wallet.can_debit(Decimal('500')) is True

    def test_can_debit_false_when_insufficient(self, wallet):
        wallet.balance = Decimal('100')
        wallet.save()
        assert wallet.can_debit(Decimal('500')) is False

    def test_lock_balance(self, wallet):
        wallet.balance = Decimal('3000')
        wallet.save()
        wallet.lock_balance(Decimal('1000'), reference='hold-1')
        wallet.refresh_from_db()
        assert wallet.locked_balance == Decimal('1000')
        assert wallet.balance == Decimal('2000')
