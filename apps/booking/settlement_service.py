"""
Phase 3: Owner settlement service.
Payouts are ONLY triggered after Booking.status transitions to STATUS_CHECKED_OUT.
This is the single source of truth for all owner disbursements.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone


class SettlementService:
    """
    Handles the full settlement lifecycle:
    1. mark_pending — called when booking is CONFIRMED (locks expected payout)
    2. settle — called when booking reaches CHECKED_OUT (releases funds to owner)
    3. reverse — called on cancellation (reverses pending settlement)
    """

    @transaction.atomic
    def mark_pending(self, booking):
        """
        Called when booking is CONFIRMED.
        Creates a pending entry in OwnerWallet so owner can see expected earnings.
        Does NOT release actual funds.
        """
        from apps.wallet.models import OwnerWallet
        owner = booking.property.owner
        owner_wallet, _ = OwnerWallet.objects.get_or_create(owner=owner)
        payout_amount = self._compute_payout(booking)

        if payout_amount > 0:
            owner_wallet.mark_pending(
                amount=payout_amount,
                booking_reference=booking.public_booking_id or str(booking.uuid),
            )
        return payout_amount

    @transaction.atomic
    def settle(self, booking):
        """
        Called ONLY when booking.status == STATUS_CHECKED_OUT.
        Releases payout to owner wallet — this is the gated disbursement.

        Raises ValueError if booking is not in CHECKED_OUT status.
        """
        from apps.wallet.models import OwnerWallet
        from apps.booking.models import Booking

        if booking.status != Booking.STATUS_CHECKED_OUT:
            raise ValueError(
                f"Settlement blocked: booking {booking.public_booking_id} "
                f"is in status '{booking.status}', not 'checked_out'. "
                "Settlement only allowed after guest checks out."
            )

        owner = booking.property.owner
        owner_wallet, _ = OwnerWallet.objects.get_or_create(owner=owner)
        payout_amount = self._compute_payout(booking)

        # Credit owner wallet
        txn = owner_wallet.credit_settlement(
            amount=payout_amount,
            booking_reference=booking.public_booking_id or str(booking.uuid),
            note=f"Payout for stay {booking.check_in} to {booking.check_out} at {booking.property.name}",
        )

        # Update booking settlement status
        booking.settlement_status = 'settled'
        booking.status = 'settled'
        booking.save(update_fields=['settlement_status', 'status', 'updated_at'])

        # Record in settlement history
        self._record_settlement_history(booking, payout_amount)

        return {
            'payout_amount': payout_amount,
            'owner_wallet_txn': str(txn.uid),
            'settled_at': timezone.now().isoformat(),
        }

    @transaction.atomic
    def reverse(self, booking, reason='Booking cancelled'):
        """
        Called when a confirmed/checked-in booking is cancelled.
        Reverses any pending settlement entries.
        """
        from apps.wallet.models import OwnerWallet, OwnerWalletTransaction
        owner = booking.property.owner
        try:
            owner_wallet = OwnerWallet.objects.get(owner=owner)
        except OwnerWallet.DoesNotExist:
            return None

        payout_amount = self._compute_payout(booking)
        booking_ref = booking.public_booking_id or str(booking.uuid)

        # If pending balance was tracked, reverse it
        if owner_wallet.pending_balance >= payout_amount:
            owner_wallet.pending_balance -= payout_amount
            owner_wallet.save(update_fields=['pending_balance', 'updated_at'])

        OwnerWalletTransaction.objects.create(
            owner_wallet=owner_wallet,
            txn_type=OwnerWalletTransaction.TYPE_REVERSAL,
            amount=-payout_amount,
            balance_after=owner_wallet.balance,
            booking_reference=booking_ref,
            note=reason,
        )
        return payout_amount

    def _compute_payout(self, booking):
        """
        Compute net amount payable to owner after platform commission and gateway fee.
        Uses booking.net_payable_to_hotel if set, else computes from gross.
        """
        if booking.net_payable_to_hotel and booking.net_payable_to_hotel > 0:
            return Decimal(str(booking.net_payable_to_hotel))

        gross = Decimal(str(booking.gross_amount or booking.total_amount or 0))
        commission = Decimal(str(booking.commission_amount or 0))
        gateway = Decimal(str(booking.gateway_fee or 0))
        net = gross - commission - gateway
        return max(Decimal('0.00'), net.quantize(Decimal('0.01')))

    def _record_settlement_history(self, booking, amount):
        """Update the settlement_models.Settlement record if it exists."""
        try:
            from apps.booking.settlement_models import Settlement
            settlement = Settlement.objects.filter(
                hotel=booking.property,
                status__in=['draft', 'pending']
            ).order_by('-period_end').first()
            if settlement:
                settlement.status = Settlement.STATUS_PAID
                settlement.save(update_fields=['status', 'updated_at'])
        except Exception:
            pass  # Non-critical — don't fail the settlement if history fails


class CashbackService:
    """
    Phase 5: Awards cashback after a booking reaches CHECKED_OUT.
    Queries active campaigns and credits user wallet.
    """

    @transaction.atomic
    def award_cashback(self, booking):
        """
        Called when booking.status transitions to STATUS_CHECKED_OUT.
        Finds applicable cashback campaigns and credits wallet.
        """
        from apps.promos.models import CashbackCampaign, CashbackCredit
        from apps.wallet.models import Wallet, WalletTransaction
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        # Find active campaigns applicable to this booking
        active_campaigns = []
        for campaign in CashbackCampaign.objects.filter(status=CashbackCampaign.STATUS_ACTIVE):
            if campaign.start_date and campaign.start_date > today:
                continue
            if campaign.end_date and campaign.end_date < today:
                continue
            # Check property restriction
            props = campaign.applicable_properties.all()
            if props.exists() and not props.filter(pk=booking.property_id).exists():
                continue
            active_campaigns.append(campaign)

        if not active_campaigns:
            return []

        user = booking.user
        user_wallet, _ = Wallet.objects.get_or_create(user=user)
        awarded = []

        for campaign in active_campaigns:
            # Prevent duplicate awards
            if CashbackCredit.objects.filter(campaign=campaign, booking=booking).exists():
                continue

            amount = campaign.compute_cashback(booking.total_amount)
            if amount <= 0:
                continue

            # Credit wallet
            txn = user_wallet.credit(
                amount=amount,
                txn_type=WalletTransaction.TYPE_CASHBACK,
                reference=booking.public_booking_id or str(booking.uuid),
                note=f"Cashback: {campaign.name}",
            )

            expires_at = timezone.now() + timedelta(days=campaign.cashback_expiry_days)
            CashbackCredit.objects.create(
                campaign=campaign,
                booking=booking,
                user=user,
                amount=amount,
                wallet_txn_reference=str(txn.uid),
                expires_at=expires_at,
            )
            awarded.append({'campaign': campaign.name, 'amount': str(amount)})

        return awarded
