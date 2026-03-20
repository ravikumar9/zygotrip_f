from decimal import Decimal
import importlib

from django.db import transaction

from .models import Referral, ReferralProfile


REFEREE_CREDIT = Decimal('200.00')
REFERRER_POINTS = 500


def get_or_create_profile(user):
    return ReferralProfile.objects.get_or_create(user=user)[0]


@transaction.atomic
def process_signup_referral(new_user, referral_code):
    code = (referral_code or '').strip().upper()
    if not code:
        return False

    try:
        referrer_profile = ReferralProfile.objects.select_for_update().get(referral_code=code)
    except ReferralProfile.DoesNotExist:
        return False

    if referrer_profile.user_id == new_user.id:
        return False

    referral, created = Referral.objects.get_or_create(
        referrer=referrer_profile.user,
        referee=new_user,
        defaults={
            'referral_code': code,
            'status': Referral.STATUS_SIGNED_UP,
        },
    )
    if not created:
        return False

    referral.referee_wallet_credit = REFEREE_CREDIT
    referral.save(update_fields=['referee_wallet_credit', 'updated_at'])

    referrer_profile.total_referrals += 1
    referrer_profile.total_wallet_credits += REFEREE_CREDIT
    referrer_profile.save(update_fields=['total_referrals', 'total_wallet_credits', 'updated_at'])

    try:
        wallet_services = importlib.import_module('apps.wallet.services')
        wallet_models = importlib.import_module('apps.wallet.models')

        wallet = wallet_services.get_or_create_wallet(new_user)
        wallet.credit(
            amount=REFEREE_CREDIT,
            txn_type=wallet_models.WalletTransaction.TYPE_CREDIT,
            reference=f'referral_signup_{referral.id}',
            note='Referral signup credit',
        )
    except Exception:
        pass

    return True


@transaction.atomic
def complete_first_booking_reward(referee_user):
    referral = (
        Referral.objects
        .select_for_update()
        .filter(referee=referee_user, status=Referral.STATUS_SIGNED_UP)
        .first()
    )
    if not referral:
        return False

    referral.status = Referral.STATUS_COMPLETED
    referral.save(update_fields=['status', 'updated_at'])

    try:
        core_loyalty = importlib.import_module('apps.core.loyalty')

        core_loyalty.award_bonus(
            referral.referrer,
            points=REFERRER_POINTS,
            description='Referral reward after first booking',
            reference_type='referral',
            reference_id=str(referral.id),
        )
    except Exception:
        return False

    referrer_profile = get_or_create_profile(referral.referrer)
    referrer_profile.successful_referrals += 1
    referrer_profile.total_loyalty_points += REFERRER_POINTS
    referrer_profile.save(update_fields=['successful_referrals', 'total_loyalty_points', 'updated_at'])

    referral.status = Referral.STATUS_REWARDED
    referral.referrer_loyalty_points = REFERRER_POINTS
    referral.save(update_fields=['status', 'referrer_loyalty_points', 'updated_at'])
    return True
