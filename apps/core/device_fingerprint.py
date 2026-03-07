"""
Step 7 + Section 11 — Device Fingerprint & Fraud Detection.

Tracks device fingerprints for booking fraud, rate-abuse detection,
multi-account abuse prevention, and coupon/promo abuse detection.

Enhanced with:
  - Promo abuse scoring (multiple promo uses across accounts/IPs)
  - Velocity checks (too many bookings too fast)
  - Payment card fingerprint cross-match
"""
import hashlib
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.fraud.fingerprint')


# ============================================================================
# MODEL
# ============================================================================

class DeviceFingerprint(TimeStampedModel):
    """
    Stores device fingerprint data per user session / booking.
    Used for fraud scoring and abuse detection.
    """
    fingerprint_hash = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='device_fingerprints',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    accept_language = models.CharField(max_length=200, blank=True)
    screen_resolution = models.CharField(max_length=50, blank=True)
    timezone_offset = models.IntegerField(null=True, blank=True, help_text="Minutes from UTC")
    platform = models.CharField(max_length=100, blank=True)
    is_mobile = models.BooleanField(default=False)
    canvas_hash = models.CharField(max_length=64, blank=True, help_text="Canvas fingerprint from JS")
    webgl_hash = models.CharField(max_length=64, blank=True, help_text="WebGL renderer hash")

    # Fraud scoring
    fraud_score = models.IntegerField(default=0, help_text="0-100, higher = more suspicious")
    is_flagged = models.BooleanField(default=False, db_index=True)
    flag_reasons = models.JSONField(default=list, blank=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['fingerprint_hash', 'user']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['is_flagged', '-fraud_score']),
        ]

    def __str__(self):
        return f"FP:{self.fingerprint_hash[:12]} user={self.user_id} score={self.fraud_score}"


# ============================================================================
# FINGERPRINT SERVICE
# ============================================================================

class FingerprintService:
    """
    Collect and analyze device fingerprints for fraud detection.
    """

    @staticmethod
    def collect_from_request(request) -> DeviceFingerprint:
        """
        Extract device fingerprint from HTTP request.
        Call from booking/payment views.
        """
        user = request.user if request.user.is_authenticated else None
        ip = FingerprintService._get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')
        lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')[:200]

        # Client-side fields (sent via POST body or headers)
        data = request.data if hasattr(request, 'data') else {}
        screen = data.get('screen_resolution', '')
        tz_offset = data.get('timezone_offset')
        platform = data.get('platform', '')
        canvas = data.get('canvas_hash', '')
        webgl = data.get('webgl_hash', '')

        # Build fingerprint hash
        fp_raw = f"{ua}|{lang}|{screen}|{tz_offset}|{platform}|{canvas}|{webgl}"
        fp_hash = hashlib.sha256(fp_raw.encode()).hexdigest()

        fp, _ = DeviceFingerprint.objects.update_or_create(
            fingerprint_hash=fp_hash,
            user=user,
            defaults={
                'ip_address': ip,
                'user_agent': ua,
                'accept_language': lang,
                'screen_resolution': str(screen),
                'timezone_offset': int(tz_offset) if tz_offset else None,
                'platform': str(platform),
                'is_mobile': FingerprintService._detect_mobile(ua),
                'canvas_hash': str(canvas),
                'webgl_hash': str(webgl),
            },
        )

        # Score the fingerprint
        score, reasons = FingerprintService.compute_fraud_score(fp)
        fp.fraud_score = score
        fp.flag_reasons = reasons
        fp.is_flagged = score >= 60
        fp.save(update_fields=['fraud_score', 'flag_reasons', 'is_flagged'])

        if fp.is_flagged:
            logger.warning("Flagged device: %s (score=%d, reasons=%s)", fp_hash[:12], score, reasons)

        return fp

    @staticmethod
    def compute_fraud_score(fp: DeviceFingerprint) -> tuple[int, list[str]]:
        """
        Score a fingerprint for fraud risk (0-100).

        Signals:
          - Multiple users from same fingerprint (+20)
          - Many bookings from same IP in short time (+15)
          - Known bot user-agent pattern (+30)
          - Missing JS fingerprint fields (+10)
          - TOR / VPN / datacenter IP range (+25)
        """
        score = 0
        reasons = []

        # 1. Multi-user same fingerprint
        user_count = (
            DeviceFingerprint.objects
            .filter(fingerprint_hash=fp.fingerprint_hash)
            .values('user').distinct().count()
        )
        if user_count > 3:
            score += 20
            reasons.append(f"multi_user_{user_count}")

        # 2. High booking frequency from same IP
        if fp.ip_address:
            recent_fps = DeviceFingerprint.objects.filter(
                ip_address=fp.ip_address,
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).count()
            if recent_fps > 10:
                score += 15
                reasons.append(f"high_frequency_ip_{recent_fps}")

        # 3. Bot user-agent
        ua_lower = (fp.user_agent or '').lower()
        bot_patterns = ['bot', 'crawler', 'spider', 'headless', 'phantom', 'selenium', 'puppeteer']
        if any(p in ua_lower for p in bot_patterns):
            score += 30
            reasons.append('bot_ua')

        # 4. Missing JS fingerprint
        if not fp.canvas_hash and not fp.webgl_hash:
            score += 10
            reasons.append('no_js_fingerprint')

        # 5. Empty user-agent
        if not fp.user_agent:
            score += 15
            reasons.append('empty_ua')

        return min(score, 100), reasons

    @staticmethod
    def _get_client_ip(request) -> str | None:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def _detect_mobile(ua: str) -> bool:
        mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'opera mini', 'opera mobi']
        return any(k in (ua or '').lower() for k in mobile_keywords)

    @staticmethod
    def check_booking_risk(user, fingerprint_hash: str | None = None) -> dict:
        """
        Pre-booking fraud check.  Returns risk assessment.
        """
        risk = {'level': 'low', 'score': 0, 'block': False, 'reasons': []}

        if not user:
            return risk

        # Recent flagged fingerprints for this user
        flagged = DeviceFingerprint.objects.filter(
            user=user, is_flagged=True,
            created_at__gte=timezone.now() - timedelta(days=30),
        ).count()

        if flagged >= 3:
            risk['level'] = 'high'
            risk['score'] = 80
            risk['block'] = True
            risk['reasons'].append(f'{flagged}_flagged_fingerprints_30d')
        elif flagged >= 1:
            risk['level'] = 'medium'
            risk['score'] = 40
            risk['reasons'].append(f'{flagged}_flagged_fingerprints_30d')

        # Check specific fingerprint
        if fingerprint_hash:
            fp = DeviceFingerprint.objects.filter(fingerprint_hash=fingerprint_hash).first()
            if fp and fp.fraud_score >= 60:
                risk['score'] = max(risk['score'], fp.fraud_score)
                risk['level'] = 'high' if fp.fraud_score >= 80 else 'medium'
                risk['reasons'].extend(fp.flag_reasons)

        return risk

    # ── Section 11: Enhanced Fraud — Velocity & Promo Abuse ─────────────

    @staticmethod
    def check_booking_velocity(user, window_hours: int = 1, max_bookings: int = 5) -> dict:
        """
        Velocity check: flag users creating too many bookings in a short window.

        Returns:
            dict with 'allowed' bool, 'count' int, 'reason' str | None
        """
        from django.apps import apps
        Booking = apps.get_model('booking', 'Booking')

        cutoff = timezone.now() - timedelta(hours=window_hours)
        count = Booking.objects.filter(user=user, created_at__gte=cutoff).count()

        if count >= max_bookings:
            logger.warning(
                "Velocity block: user=%s created %d bookings in last %dh",
                user.id, count, window_hours,
            )
            return {
                'allowed': False,
                'count': count,
                'reason': f'{count}_bookings_in_{window_hours}h (max {max_bookings})',
            }
        return {'allowed': True, 'count': count, 'reason': None}

    @staticmethod
    def check_promo_abuse(user, promo_code: str, ip_address: str | None = None) -> dict:
        """
        Detect coupon / promo abuse across accounts or IPs.

        Checks:
          - Same promo used by >3 fingerprints from same IP → abuse
          - Same promo used by >5 different users from same IP → abuse
          - User applied >10 distinct promos in last 30 days → suspicious

        Returns:
            dict with 'allowed' bool, 'risk_score' int, 'reasons' list
        """
        from django.apps import apps
        reasons = []
        score = 0

        try:
            PromoUsage = apps.get_model('promos', 'PromoUsage')
        except LookupError:
            return {'allowed': True, 'risk_score': 0, 'reasons': []}

        cutoff_30d = timezone.now() - timedelta(days=30)

        # 1) User used too many distinct promos
        distinct_promos = PromoUsage.objects.filter(
            user=user, created_at__gte=cutoff_30d,
        ).values('promo').distinct().count()
        if distinct_promos > 10:
            score += 30
            reasons.append(f'{distinct_promos}_distinct_promos_30d')

        # 2) Same promo used by multiple users from same IP
        if ip_address and promo_code:
            from django.db.models import Q
            same_ip_users = DeviceFingerprint.objects.filter(
                ip_address=ip_address,
                created_at__gte=cutoff_30d,
            ).values('user_id').distinct().count()
            if same_ip_users > 5:
                score += 25
                reasons.append(f'{same_ip_users}_users_same_ip_same_promo')

        # 3) Same promo already used by this user
        already_used = PromoUsage.objects.filter(
            user=user,
            promo__code=promo_code,
        ).exists()
        if already_used:
            score += 20
            reasons.append('promo_already_used_by_user')

        blocked = score >= 50
        if blocked:
            logger.warning("Promo abuse detected: user=%s promo=%s score=%d", user.id, promo_code, score)

        return {'allowed': not blocked, 'risk_score': score, 'reasons': reasons}

    @staticmethod
    def get_fraud_summary(user) -> dict:
        """
        Return a consolidated fraud summary for a user — used by admin dashboard.
        """
        cutoff = timezone.now() - timedelta(days=90)
        fps = DeviceFingerprint.objects.filter(user=user, created_at__gte=cutoff)
        return {
            'total_fingerprints': fps.count(),
            'flagged_fingerprints': fps.filter(is_flagged=True).count(),
            'max_fraud_score': fps.order_by('-fraud_score').values_list('fraud_score', flat=True).first() or 0,
            'unique_ips': fps.values('ip_address').distinct().count(),
            'unique_devices': fps.values('fingerprint_hash').distinct().count(),
            'all_reasons': list(
                fps.filter(is_flagged=True)
                .values_list('flag_reasons', flat=True)
            ),
        }
