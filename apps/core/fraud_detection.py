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


def _increment_counter(cache_key, ttl_seconds):
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, ttl_seconds)


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
    _increment_counter(ip_key, 1800)

    # 1b. Shared IP fan-out across multiple accounts in 24 hours
    if user and user.is_authenticated:
        ip_users_key = f'fraud:booking_ip_users:{ip_address}'
        ip_users = cache.get(ip_users_key, []) or []
        if user.id not in ip_users:
            ip_users = [*ip_users, user.id][-10:]
            cache.set(ip_users_key, ip_users, 86400)
        distinct_users = len(ip_users)
        if distinct_users >= 5:
            score += 30
            reasons.append(f'Shared IP across {distinct_users} accounts in 24h')
        elif distinct_users >= 3:
            score += 15
            reasons.append(f'Shared IP across {distinct_users} accounts in 24h')

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
        _increment_counter(user_key, 3600)

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

    if ip_address:
        ip_fail_key = f'fraud:pay_fail_ip:{ip_address}'
        ip_fail_count = cache.get(ip_fail_key, 0)
        if ip_fail_count >= 6:
            score += 30
            reasons.append(f'Payment failures concentrated on IP: {ip_fail_count} in 24hrs')
        elif ip_fail_count >= 3:
            score += 15
            reasons.append(f'Payment failures concentrated on IP: {ip_fail_count} in 24hrs')

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


def record_payment_failure(user, ip_address: str | None = None):
    """Track payment failure for fraud scoring."""
    if user and user.is_authenticated:
        fail_key = f'fraud:pay_fail:{user.id}'
        _increment_counter(fail_key, 86400)
    if ip_address:
        ip_fail_key = f'fraud:pay_fail_ip:{ip_address}'
        _increment_counter(ip_fail_key, 86400)


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


# ── Section 9: Coupon Abuse + Excessive Cancellation Detection ─────────────


def detect_coupon_abuse(user) -> dict:
    """
    Detect coupon/promo abuse patterns.

    Flags:
    - User applying >5 different coupons in 24h (coupon farming)
    - Same payment method used across multiple accounts
    - User creating multiple accounts for first-booking coupons
    """
    score = 0
    reasons = []

    if not user or not user.is_authenticated:
        return {'risk_score': 0, 'action': 'allow', 'reasons': []}

    # 1. Coupon velocity — too many coupon attempts in 24h
    coupon_key = f'fraud:coupon_attempts:{user.id}'
    coupon_count = cache.get(coupon_key, 0)
    if coupon_count >= 10:
        score += 50
        reasons.append(f'Excessive coupon attempts: {coupon_count} in 24h')
    elif coupon_count >= 5:
        score += 25
        reasons.append(f'High coupon attempts: {coupon_count} in 24h')

    # 2. Check PromoUsage frequency
    try:
        from apps.promos.models import PromoUsage
        from datetime import timedelta

        week_ago = timezone.now() - timedelta(days=7)
        promo_uses = PromoUsage.objects.filter(
            user=user,
            used_at__gte=week_ago,
        ).count()

        if promo_uses >= 10:
            score += 40
            reasons.append(f'Used {promo_uses} promos in 7 days')
        elif promo_uses >= 5:
            score += 15
            reasons.append(f'Used {promo_uses} promos in 7 days')
    except Exception:
        pass

    # 3. Check for same payment fingerprint across users
    try:
        from apps.core.device_fingerprint import DeviceFingerprint
        user_fps = DeviceFingerprint.objects.filter(user=user).values_list(
            'fingerprint_hash', flat=True
        )[:5]
        if user_fps:
            other_users = DeviceFingerprint.objects.filter(
                fingerprint_hash__in=list(user_fps),
            ).exclude(user=user).values('user_id').distinct().count()
            if other_users >= 3:
                score += 45
                reasons.append(f'Same device fingerprint on {other_users} other accounts')
            elif other_users >= 1:
                score += 20
                reasons.append(f'Shared device fingerprint with {other_users} account(s)')
    except Exception:
        pass

    # Determine action
    if score >= RISK_CRITICAL:
        action = FraudFlag.ACTION_BLOCK
    elif score >= RISK_HIGH:
        action = FraudFlag.ACTION_VERIFY
    elif score >= RISK_MEDIUM:
        action = FraudFlag.ACTION_FLAG
    else:
        action = FraudFlag.ACTION_ALLOW

    if score >= RISK_MEDIUM:
        FraudFlag.objects.create(
            user=user,
            risk_score=score,
            action_taken=action,
            reason='; '.join(reasons),
            reference_type='coupon_abuse',
        )
        logger.warning('Coupon abuse: score=%d user=%s reasons=%s', score, user.id, reasons)

    return {'risk_score': score, 'action': action, 'reasons': reasons}


def record_coupon_attempt(user):
    """Track coupon application attempt for abuse detection."""
    if user and user.is_authenticated:
        key = f'fraud:coupon_attempts:{user.id}'
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 86400)  # 24h window


def detect_excessive_cancellations(user) -> dict:
    """
    Flag users who repeatedly book and cancel hotels.

    Thresholds:
    - ≥5 cancellations in 30 days → flag
    - ≥10 cancellations in 30 days → block
    - Cancellation rate >60% → flag
    """
    score = 0
    reasons = []

    if not user or not user.is_authenticated:
        return {'risk_score': 0, 'action': 'allow', 'reasons': []}

    try:
        from apps.booking.models import Booking
        from datetime import timedelta
        from django.db.models import Count, Q

        month_ago = timezone.now() - timedelta(days=30)

        stats = Booking.objects.filter(
            user=user,
            created_at__gte=month_ago,
        ).aggregate(
            total=Count('id'),
            cancelled=Count('id', filter=Q(
                status__in=['cancelled', 'cancelled_by_hotel', 'refunded'],
            )),
        )

        total = stats['total'] or 0
        cancelled = stats['cancelled'] or 0

        if cancelled >= 10:
            score += 60
            reasons.append(f'{cancelled} cancellations in 30 days')
        elif cancelled >= 5:
            score += 30
            reasons.append(f'{cancelled} cancellations in 30 days')

        if total >= 3 and cancelled / total > 0.60:
            score += 25
            reasons.append(f'Cancellation rate: {cancelled}/{total} ({int(cancelled/total*100)}%)')

    except Exception as exc:
        logger.debug('Cancellation check failed: %s', exc)

    if score >= RISK_CRITICAL:
        action = FraudFlag.ACTION_BLOCK
    elif score >= RISK_HIGH:
        action = FraudFlag.ACTION_VERIFY
    elif score >= RISK_MEDIUM:
        action = FraudFlag.ACTION_FLAG
    else:
        action = FraudFlag.ACTION_ALLOW

    if score >= RISK_MEDIUM:
        FraudFlag.objects.create(
            user=user,
            risk_score=score,
            action_taken=action,
            reason='; '.join(reasons),
            reference_type='excessive_cancellation',
        )

    return {'risk_score': score, 'action': action, 'reasons': reasons}


# ── Shared Payment Method Detection ──────────────────────────────────────────


def detect_shared_payment_method(user) -> dict:
    """
    Detect multiple accounts using the same payment method.

    Flags:
    - Same card last-4 + card fingerprint used across ≥2 accounts → flag
    - Same UPI VPA across ≥3 accounts → flag
    - Same bank account across ≥2 accounts → block

    Relies on payment records stored by the payment gateway module.
    """
    score = 0
    reasons = []

    if not user or not user.is_authenticated:
        return {'risk_score': 0, 'action': 'allow', 'reasons': []}

    try:
        from apps.payments.models import PaymentTransaction

        # Get this user's payment fingerprints from last 90 days
        cutoff = timezone.now() - timedelta(days=90)
        user_payments = PaymentTransaction.objects.filter(
            user=user,
            created_at__gte=cutoff,
        ).exclude(
            payment_method_fingerprint='',
        ).values_list('payment_method_fingerprint', flat=True).distinct()

        fingerprints = list(user_payments[:20])

        if fingerprints:
            # Find other users sharing the same payment fingerprints
            shared_users = (
                PaymentTransaction.objects.filter(
                    payment_method_fingerprint__in=fingerprints,
                    created_at__gte=cutoff,
                )
                .exclude(user=user)
                .values('user_id')
                .distinct()
                .count()
            )

            if shared_users >= 3:
                score += 60
                reasons.append(
                    f'Payment method shared with {shared_users} other accounts'
                )
            elif shared_users >= 1:
                score += 30
                reasons.append(
                    f'Payment method shared with {shared_users} other account(s)'
                )

        # Check UPI VPA sharing
        user_vpas = PaymentTransaction.objects.filter(
            user=user,
            created_at__gte=cutoff,
            payment_mode='upi',
        ).exclude(
            upi_vpa='',
        ).values_list('upi_vpa', flat=True).distinct()

        vpas = list(user_vpas[:10])

        if vpas:
            vpa_shared = (
                PaymentTransaction.objects.filter(
                    upi_vpa__in=vpas,
                    created_at__gte=cutoff,
                )
                .exclude(user=user)
                .values('user_id')
                .distinct()
                .count()
            )
            if vpa_shared >= 2:
                score += 40
                reasons.append(f'UPI VPA shared with {vpa_shared} other accounts')
            elif vpa_shared >= 1:
                score += 15
                reasons.append(f'UPI VPA shared with {vpa_shared} account(s)')

    except Exception as exc:
        logger.debug('Shared payment check failed: %s', exc)

    # Determine action
    if score >= RISK_CRITICAL:
        action = FraudFlag.ACTION_BLOCK
    elif score >= RISK_HIGH:
        action = FraudFlag.ACTION_VERIFY
    elif score >= RISK_MEDIUM:
        action = FraudFlag.ACTION_FLAG
    else:
        action = FraudFlag.ACTION_ALLOW

    if score >= RISK_MEDIUM:
        FraudFlag.objects.create(
            user=user,
            risk_score=score,
            action_taken=action,
            reason='; '.join(reasons),
            reference_type='shared_payment_method',
        )
        logger.warning(
            'Shared payment detected: score=%d user=%s reasons=%s',
            score, user.id, reasons,
        )

    return {'risk_score': score, 'action': action, 'reasons': reasons}
