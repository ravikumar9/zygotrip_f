"""
Referral System — Invite-a-friend rewards.

- Each user gets a unique referral code
- Referrer earns 500 loyalty points when referee completes first booking
- Referee gets ₹200 wallet credit on signup via referral
- Max 50 successful referrals per user
"""
import logging
import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.referral')


def _generate_referral_code():
    """Generate a unique 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return 'ZT' + ''.join(secrets.choice(chars) for _ in range(6))


class ReferralProfile(TimeStampedModel):
    """Per-user referral tracking."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_profile',
    )
    referral_code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        default=_generate_referral_code,
    )
    total_referrals = models.IntegerField(default=0)
    successful_referrals = models.IntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_referrals = models.IntegerField(default=50)

    class Meta:
        app_label = 'core'
        db_table = 'core_referral_profile'

    def __str__(self):
        return f'{self.user.email} — {self.referral_code} ({self.successful_referrals} referrals)'


class Referral(TimeStampedModel):
    """Tracks each referral relationship."""
    STATUS_PENDING = 'pending'
    STATUS_SIGNED_UP = 'signed_up'
    STATUS_COMPLETED = 'completed'   # first booking made
    STATUS_REWARDED = 'rewarded'     # rewards distributed

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SIGNED_UP, 'Signed Up'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REWARDED, 'Rewarded'),
    ]

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made',
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_by',
        null=True,
        blank=True,
    )
    referral_code = models.CharField(max_length=10, db_index=True)
    referee_email = models.EmailField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    referrer_reward = models.IntegerField(default=0, help_text='Loyalty points awarded to referrer')
    referee_reward = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Wallet credit given to referee',
    )

    class Meta:
        app_label = 'core'
        db_table = 'core_referral'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['referrer', 'referee_email'],
                name='unique_referral_per_email',
            ),
        ]


# ── Service functions ──────────────────────────────────────────────────────────


def get_or_create_referral_profile(user):
    """Get or create referral profile for user."""
    profile, created = ReferralProfile.objects.get_or_create(user=user)
    if created:
        logger.info('Created referral profile for user=%s code=%s', user.id, profile.referral_code)
    return profile


@transaction.atomic
def process_referral_signup(new_user, referral_code: str) -> bool:
    """
    Process referee signup with a referral code.
    Awards ₹200 wallet credit to the new user.
    """
    try:
        profile = ReferralProfile.objects.select_for_update().get(referral_code=referral_code)
    except ReferralProfile.DoesNotExist:
        logger.warning('Invalid referral code: %s', referral_code)
        return False

    if profile.user == new_user:
        logger.warning('Self-referral attempted: user=%s', new_user.id)
        return False

    if profile.successful_referrals >= profile.max_referrals:
        logger.warning('Referral limit reached for user=%s', profile.user_id)
        return False

    # Check if already referred
    if Referral.objects.filter(referrer=profile.user, referee=new_user).exists():
        return False

    referral = Referral.objects.create(
        referrer=profile.user,
        referee=new_user,
        referral_code=referral_code,
        referee_email=new_user.email,
        status=Referral.STATUS_SIGNED_UP,
    )

    # Award ₹200 wallet credit to referee
    try:
        from apps.wallet.services import get_or_create_wallet
        from apps.wallet.models import WalletTransaction
        wallet = get_or_create_wallet(new_user)
        wallet.credit(
            amount=Decimal('200.00'),
            txn_type=WalletTransaction.TYPE_CREDIT,
            reference=f'referral_signup_{referral.id}',
            note='Welcome bonus — referred by a friend!',
        )
        referral.referee_reward = Decimal('200.00')
        referral.save(update_fields=['referee_reward', 'updated_at'])
    except Exception as e:
        logger.error('Failed to credit referee wallet: %s', e)

    profile.total_referrals += 1
    profile.save(update_fields=['total_referrals', 'updated_at'])

    logger.info('Referral signup processed: referrer=%s referee=%s', profile.user_id, new_user.id)
    return True


@transaction.atomic
def complete_referral(referee_user) -> bool:
    """
    Called when referee completes their first booking.
    Awards 500 loyalty points to the referrer.
    """
    referral = Referral.objects.filter(
        referee=referee_user,
        status=Referral.STATUS_SIGNED_UP,
    ).first()

    if not referral:
        return False

    referral.status = Referral.STATUS_COMPLETED
    referral.save(update_fields=['status', 'updated_at'])

    # Award referrer 500 loyalty points
    try:
        from apps.core.loyalty import award_bonus
        award_bonus(
            referral.referrer,
            points=500,
            description=f'Referral reward — {referee_user.email} completed first booking',
            reference_type='referral',
            reference_id=str(referral.id),
        )
        referral.referrer_reward = 500
        referral.status = Referral.STATUS_REWARDED
        referral.save(update_fields=['referrer_reward', 'status', 'updated_at'])

        profile = referral.referrer.referral_profile
        profile.successful_referrals += 1
        profile.total_earnings += Decimal('50.00')  # 500 points ≈ ₹50
        profile.save(update_fields=['successful_referrals', 'total_earnings', 'updated_at'])
    except Exception as e:
        logger.error('Failed to award referral bonus: %s', e)

    logger.info('Referral completed: referrer=%s referee=%s', referral.referrer_id, referee_user.id)
    return True
