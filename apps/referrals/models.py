import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models


def _generate_code():
    chars = string.ascii_uppercase + string.digits
    return "ZY" + "".join(secrets.choice(chars) for _ in range(6))


class ReferralProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_profile')
    referral_code = models.CharField(max_length=12, unique=True, db_index=True, default=_generate_code)
    total_referrals = models.PositiveIntegerField(default=0)
    successful_referrals = models.PositiveIntegerField(default=0)
    total_wallet_credits = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_loyalty_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return f"{self.user_id}:{self.referral_code}"


class Referral(models.Model):
    STATUS_SIGNED_UP = 'signed_up'
    STATUS_COMPLETED = 'completed'
    STATUS_REWARDED = 'rewarded'

    STATUS_CHOICES = (
        (STATUS_SIGNED_UP, 'Signed Up'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REWARDED, 'Rewarded'),
    )

    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_sent')
    referee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_received')
    referral_code = models.CharField(max_length=12, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SIGNED_UP)
    referee_wallet_credit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    referrer_loyalty_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('referrer', 'referee'), name='unique_referrer_referee_pair'),
        ]

    def __str__(self):
        return f"{self.referrer_id}->{self.referee_id} ({self.status})"
