"""
Wallet service layer for ZygoTrip.
Phase 2: Full wallet operations using WalletTransaction model.
"""
from decimal import Decimal
from django.db import transaction


def get_or_create_wallet(user):
    """Get or create a customer wallet for the given user."""
    if not user or not user.pk:
        return None
    from .models import Wallet
    wallet, _ = Wallet.objects.get_or_create(user=user, defaults={'currency': 'INR'})
    return wallet


def get_or_create_owner_wallet(user):
    """Get or create an owner wallet for the given property owner."""
    if not user or not user.pk:
        return None
    from .models import OwnerWallet
    wallet, _ = OwnerWallet.objects.get_or_create(owner=user, defaults={'currency': 'INR'})
    return wallet


def check_wallet_balance(user, amount):
    """Check if user has sufficient wallet balance."""
    wallet = get_or_create_wallet(user)
    if not wallet:
        return False
    return wallet.can_debit(Decimal(str(amount)))


@transaction.atomic
def use_wallet_for_payment(user, amount, booking_reference):
    """
    Debit wallet to pay for a booking.
    Returns (success: bool, error_message: str|None)
    """
    from .models import WalletTransaction
    wallet = get_or_create_wallet(user)
    if not wallet:
        return False, 'Wallet not found.'
    try:
        wallet.debit(
            amount=Decimal(str(amount)),
            txn_type=WalletTransaction.TYPE_PAYMENT,
            reference=booking_reference,
            note=f'Payment for booking {booking_reference}',
        )
        return True, None
    except ValueError as e:
        return False, str(e)


@transaction.atomic
def refund_to_wallet(user, amount, booking_reference, note=''):
    """Credit refund back to customer wallet."""
    from .models import WalletTransaction
    wallet = get_or_create_wallet(user)
    if not wallet:
        return False
    wallet.credit(
        amount=Decimal(str(amount)),
        txn_type=WalletTransaction.TYPE_REFUND,
        reference=booking_reference,
        note=note or f'Refund for booking {booking_reference}',
    )
    return True


def get_wallet_balance(user):
    """Return current available balance for a user."""
    wallet = get_or_create_wallet(user)
    if not wallet:
        return Decimal('0.00')
    return wallet.balance


def get_transaction_history(user, limit=20):
    """Return recent wallet transactions for a user."""
    wallet = get_or_create_wallet(user)
    if not wallet:
        return []
    return list(wallet.transactions.order_by('-created_at')[:limit])