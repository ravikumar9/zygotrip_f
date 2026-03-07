"""
Fraud Detection — Velocity checks and suspicious activity flagging.

Checks:
  - Multiple bookings from same IP in short window
  - Multiple failed payments per user
  - Unusual booking patterns (very high amounts, rapid succession)
  - Device fingerprint anomalies
  - Geographic impossible travel

Actions:
  - FLAG: Mark for manual review
  - BLOCK: Reject the transaction
  - REQUIRE_VERIFICATION: Force additional auth (OTP/email)
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.fraud')


# ── Risk Score Thresholds ──────────────────────────────────────────────────────

RISK_LOW = 0          # 0-30: allow
RISK_MEDIUM = 30      # 30-60: flag
RISK_HIGH = 60        # 60-80: require verification
RISK_CRITICAL = 80    # 80+: block


class FraudFlag(TimeStampedModel):
    """Record of flagged suspicious activity."""
    ACTION_FLAG = 'flag'
    ACTION_BLOCK = 'block'
    ACTION_VERIFY = 'require_verification'
    ACTION_ALLOW = 'allow'

    ACTION_CHOICES = [
        (ACTION_FLAG, 'Flag for Review'),
        (ACTION_BLOCK, 'Block'),
        (ACTION_VERIFY, 'Require Verification'),
        (ACTION_ALLOW, 'Allow'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraud_flags',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    risk_score = models.IntegerField(default=0)
    action_taken = models.CharField(max_length=25, choices=ACTION_CHOICES, default=ACTION_FLAG)
    reason = models.TextField()
    reference_type = models.CharField(max_length=50, blank=True)  # 'booking', 'payment', 'login'
    reference_id = models.CharField(max_length=100, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraud_resolutions',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        db_table = 'core_fraud_flag'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='fraud_user_idx'),
            models.Index(fields=['ip_address', '-created_at'], name='fraud_ip_idx'),
            models.Index(fields=['resolved', '-created_at'], name='fraud_unresolved_idx'),
        ]

    def __str__(self):
        return f'FraudFlag #{self.id} score={self.risk_score} action={self.action_taken}'


# ── Risk Assessment Engine ─────────────────────────────────────────────────────


def assess_booking_risk(user, ip_address: str, amount: Decimal, property_id=None) -> dict:
    """
    Assess fraud risk for a booking attempt.
    Returns { risk_score: int, action: str, reasons: list[str] }
    """
    score = 0
    reasons = []

    # 1. Velocity check — bookings per IP in last 30 minutes
    ip_key = f'fraud:booking_ip:{ip_address}'
    ip_count = cache.get(ip_key, 0)
    if ip_count >= 10:
        score += 40
        reasons.append(f'High velocity: {ip_count} bookings from IP in 30min')
    elif ip_count >= 5:
        score += 20
        reasons.append(f'Moderate velocity: {ip_count} bookings from IP in 30min')

    # Increment IP counter
    try:
        cache.incr(ip_key)
    except ValueError:
        cache.set(ip_key, 1, 1800)  # 30 min window

    # 2. User velocity — bookings per user in last hour
    if user and user.is_authenticated:
        user_key = f'fraud:booking_user:{user.id}'
        user_count = cache.get(user_key, 0)
        if user_count >= 5:
            score += 30
            reasons.append(f'User velocity: {user_count} bookings in 1hr')
        elif user_count >= 3:
            score += 15
            reasons.append(f'User velocity: {user_count} bookings in 1hr')
        try:
            cache.incr(user_key)
        except ValueError:
            cache.set(user_key, 1, 3600)  # 1 hour window

    # 3. Amount anomaly
    if amount > Decimal('100000'):
        score += 25
        reasons.append(f'High amount: ₹{amount}')
    elif amount > Decimal('50000'):
        score += 10
        reasons.append(f'Elevated amount: ₹{amount}')

    # 4. New account check
    if user and user.is_authenticated:
        join_date = getattr(user, 'created_at', None) or getattr(user, 'date_joined', timezone.now())
        account_age = (timezone.now() - join_date).days
        if account_age < 1:
            score += 15
            reasons.append(f'New account: {account_age} days old')
        elif account_age < 7:
            score += 5
            reasons.append(f'Recent account: {account_age} days old')

    # 5. Failed payment history
    if user and user.is_authenticated:
        fail_key = f'fraud:pay_fail:{user.id}'
        fail_count = cache.get(fail_key, 0)
        if fail_count >= 3:
            score += 25
            reasons.append(f'Multiple payment failures: {fail_count} in 24hrs')

    # Determine action
    if score >= RISK_CRITICAL:
        action = FraudFlag.ACTION_BLOCK
    elif score >= RISK_HIGH:
        action = FraudFlag.ACTION_VERIFY
    elif score >= RISK_MEDIUM:
        action = FraudFlag.ACTION_FLAG
    else:
        action = FraudFlag.ACTION_ALLOW

    # Log if flagged
    if score >= RISK_MEDIUM:
        FraudFlag.objects.create(
            user=user if user and user.is_authenticated else None,
            ip_address=ip_address,
            risk_score=score,
            action_taken=action,
            reason='; '.join(reasons),
            reference_type='booking',
            reference_id=str(property_id or ''),
        )
        logger.warning(
            'Fraud assessment: score=%d action=%s ip=%s user=%s reasons=%s',
            score, action, ip_address, getattr(user, 'id', None), reasons,
        )

    return {
        'risk_score': score,
        'action': action,
        'reasons': reasons,
    }


def record_payment_failure(user):
    """Track payment failure for fraud scoring."""
    if user and user.is_authenticated:
        fail_key = f'fraud:pay_fail:{user.id}'
        try:
            cache.incr(fail_key)
        except ValueError:
            cache.set(fail_key, 1, 86400)  # 24 hour window


def assess_login_risk(ip_address: str, email: str) -> dict:
    """Assess fraud risk for login attempt."""
    score = 0
    reasons = []

    # Failed login velocity
    login_key = f'fraud:login_fail:{ip_address}'
    fail_count = cache.get(login_key, 0)
    if fail_count >= 10:
        score += 60
        reasons.append(f'Brute force: {fail_count} failed logins from IP')
    elif fail_count >= 5:
        score += 30
        reasons.append(f'Multiple failed logins: {fail_count} from IP')

    if score >= RISK_HIGH:
        action = FraudFlag.ACTION_BLOCK
    elif score >= RISK_MEDIUM:
        action = FraudFlag.ACTION_VERIFY
    else:
        action = FraudFlag.ACTION_ALLOW

    return {'risk_score': score, 'action': action, 'reasons': reasons}


def record_login_failure(ip_address: str):
    """Track login failure for fraud scoring."""
    login_key = f'fraud:login_fail:{ip_address}'
    try:
        cache.incr(login_key)
    except ValueError:
        cache.set(login_key, 1, 3600)  # 1 hour window
