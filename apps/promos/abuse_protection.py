"""
Coupon Abuse Protection System
Real multi-layer validation: per-user, per-device, per-IP with pattern detection.
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel

User = get_user_model()
logger = logging.getLogger('zygotrip')


class CouponAbuseLog(TimeStampedModel):
    """Detailed audit log of coupon usage and abuse attempts"""
    
    ATTEMPT_TYPES = [
        ('valid_use', 'Valid Usage'),
        ('duplicate_attempt', 'Duplicate Attempt'),
        ('limit_exceeded', 'Limit Exceeded'),
        ('device_limit', 'Device Limit Exceeded'),
        ('ip_limit', 'IP Limit Exceeded'),
        ('pattern_detected', 'Suspicious Pattern Detected'),
        ('stacking_attempt', 'Coupon Stacking Attempt'),
        ('expired_coupon', 'Expired Coupon'),
        ('invalid_coupon', 'Invalid Coupon Code'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    coupon_code = models.CharField(max_length=100, db_index=True)
    
    # Context
    attempt_type = models.CharField(max_length=50, choices=ATTEMPT_TYPES)
    service_type = models.CharField(max_length=20)  # hotel, bus, cab, package
    booking_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    
    # Device & IP
    device_fingerprint = models.CharField(max_length=256, db_index=True)
    client_ip = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    
    # Additional context
    is_suspicious = models.BooleanField(default=False, db_index=True)
    risk_score = models.PositiveIntegerField(default=0)  # 0-100
    details = models.JSONField(default=dict)
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['client_ip', 'timestamp']),
            models.Index(fields=['device_fingerprint', 'timestamp']),
            models.Index(fields=['is_suspicious', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_attempt_type_display()} - {self.coupon_code} - {self.client_ip}"


class CouponUsageLimit(TimeStampedModel):
    """Track coupon usage and enforce limits"""
    
    coupon_code = models.CharField(max_length=100, unique=True)
    
    # Per-user limits
    max_uses_per_user = models.PositiveIntegerField(default=1)
    max_uses_per_device = models.PositiveIntegerField(default=1)
    max_uses_per_ip = models.PositiveIntegerField(default=5)
    
    # Temporal limits
    min_days_between_uses = models.PositiveIntegerField(default=0)
    
    # Module restriction (prevent stacking)
    allowed_modules = models.JSONField(
        default=list,
        help_text="List of modules: ['hotel', 'bus', 'cab', 'package']"
    )
    prevent_stacking = models.BooleanField(default=True)
    
    # Abuse detection
    anomaly_detection_enabled = models.BooleanField(default=True)
    auto_suspend_on_abuse = models.BooleanField(default=True)
    
    current_uses_counted = models.PositiveIntegerField(default=0)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Coupon Usage Limits"
    
    def __str__(self):
        return f"{self.coupon_code} (Uses: {self.current_uses_counted})"


class AbusePatternDetector:
    """Detect suspicious coupon usage patterns"""
    
    # Pattern thresholds
    RAPID_ATTEMPTS_WINDOW = 300  # seconds (5 min)
    RAPID_ATTEMPTS_THRESHOLD = 5  # attempts in window
    
    IP_GEOGRAPHIC_CHANGE_THRESHOLD = 5  # km per minute (impossible to reach)
    
    def __init__(self, user_id: Optional[int] = None, client_ip: str = '', device_fingerprint: str = ''):
        self.user_id = user_id
        self.client_ip = client_ip
        self.device_fingerprint = device_fingerprint
        self.risk_score = 0
        self.detected_patterns = []
    
    def check_rapid_attempts(self, coupon_code: str) -> bool:
        """Detect rapid coupon attempts from same user/IP/device"""
        five_min_ago = timezone.now() - timedelta(seconds=self.RAPID_ATTEMPTS_WINDOW)
        
        recent_attempts = CouponAbuseLog.objects.filter(
            coupon_code=coupon_code,
            timestamp__gte=five_min_ago
        )
        
        # By user
        if self.user_id:
            user_attempts = recent_attempts.filter(user_id=self.user_id).count()
            if user_attempts >= self.RAPID_ATTEMPTS_THRESHOLD:
                self.detected_patterns.append('rapid_user_attempts')
                self.risk_score += 30
                return True
        
        # By IP
        ip_attempts = recent_attempts.filter(client_ip=self.client_ip).count()
        if ip_attempts >= self.RAPID_ATTEMPTS_THRESHOLD:
            self.detected_patterns.append('rapid_ip_attempts')
            self.risk_score += 25
            return True
        
        # By device
        device_attempts = recent_attempts.filter(device_fingerprint=self.device_fingerprint).count()
        if device_attempts >= self.RAPID_ATTEMPTS_THRESHOLD:
            self.detected_patterns.append('rapid_device_attempts')
            self.risk_score += 25
            return True
        
        return False
    
    def check_ip_velocity(self) -> bool:
        """Detect impossible geographic changes (same user, different IPs"""
        if not self.user_id:
            return False
        
        one_min_ago = timezone.now() - timedelta(minutes=1)
        
        recent_ips = CouponAbuseLog.objects.filter(
            user_id=self.user_id,
            timestamp__gte=one_min_ago
        ).values_list('client_ip', flat=True).distinct()
        
        if len(recent_ips) > 2:
            self.detected_patterns.append('impossible_ip_velocity')
            self.risk_score += 40
            return True
        
        return False
    
    def check_device_switching(self) -> bool:
        """Detect rapid device switching (same user, multiple devices in short time)"""
        if not self.user_id:
            return False
        
        five_min_ago = timezone.now() - timedelta(minutes=5)
        
        devices = CouponAbuseLog.objects.filter(
            user_id=self.user_id,
            timestamp__gte=five_min_ago
        ).values_list('device_fingerprint', flat=True).distinct()
        
        if len(devices) >= 3:
            self.detected_patterns.append('rapid_device_switching')
            self.risk_score += 35
            return True
        
        return False
    
    def check_coupon_stacking_attempt(self, booking_id: int, service_type: str) -> bool:
        """Check if user trying to stack multiple coupons on same booking"""
        from apps.promos.models import BookingCoupon  # Assuming this model exists
        
        try:
            active_coupons = BookingCoupon.objects.filter(
                booking_id=booking_id,
                is_active=True
            ).count()
            
            if active_coupons > 0:
                self.detected_patterns.append('coupon_stacking_attempt')
                self.risk_score += 20
                return True
        except:
            pass
        
        return False
    
    def check_testing_pattern(self, coupon_code: str) -> bool:
        """Detect coupon code testing (trying multiple codes in rapid succession)"""
        one_min_ago = timezone.now() - timedelta(minutes=1)
        
        attempts = CouponAbuseLog.objects.filter(
            client_ip=self.client_ip,
            timestamp__gte=one_min_ago
        ).values_list('coupon_code', flat=True).distinct()
        
        if len(attempts) >= 3:
            self.detected_patterns.append('coupon_code_testing')
            self.risk_score += 25
            return True
        
        return False
    
    def run_all_checks(self, coupon_code: str, booking_id: Optional[int] = None, service_type: str = '') -> Dict:
        """Run all pattern detection checks"""
        self.check_rapid_attempts(coupon_code)
        self.check_ip_velocity()
        self.check_device_switching()
        if booking_id:
            self.check_coupon_stacking_attempt(booking_id, service_type)
        self.check_testing_pattern(coupon_code)
        
        return {
            'is_suspicious': len(self.detected_patterns) > 0,
            'risk_score': min(100, self.risk_score),
            'patterns': self.detected_patterns,
        }


class CouponAbuseProtector:
    """Main abuse protection and validation engine"""
    
    def __init__(self, user: Optional[User] = None, client_ip: str = '', user_agent: str = ''):
        self.user = user
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.device_fingerprint = self._compute_device_fingerprint()
    
    def _compute_device_fingerprint(self) -> str:
        """Compute device fingerprint from user agent and other signals"""
        fingerprint_data = f"{self.user_agent}:{self.client_ip}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]
    
    def validate_and_apply(
        self,
        coupon_code: str,
        booking_amount: Decimal,
        service_type: str,
        booking_id: Optional[int] = None,
    ) -> Tuple[bool, str, Dict]:
        """
        Complete validation and apply coupon.
        Returns (valid, error_message, details)
        """
        details = {
            'coupon_code': coupon_code,
            'user_id': self.user.id if self.user else None,
            'client_ip': self.client_ip,
            'device_fingerprint': self.device_fingerprint,
            'timestamp': timezone.now().isoformat(),
        }
        
        # Load coupon config
        try:
            limit_config = CouponUsageLimit.objects.get(coupon_code=coupon_code)
        except CouponUsageLimit.DoesNotExist:
            self._log_attempt(coupon_code, 'invalid_coupon', service_type, booking_amount, details)
            return False, f"Coupon code '{coupon_code}' not found", details
        
        # Check if suspended
        if limit_config.is_suspended:
            self._log_attempt(coupon_code, 'limit_exceeded', service_type, booking_amount, details)
            return False, f"Coupon '{coupon_code}' is currently suspended", details
        
        # Check module restriction
        if limit_config.allowed_modules and service_type not in limit_config.allowed_modules:
            self._log_attempt(coupon_code, 'limit_exceeded', service_type, booking_amount, details)
            return False, f"Coupon '{coupon_code}' cannot be used for {service_type}", details
        
        # Check per-user limit
        if self.user:
            user_uses = self._get_user_uses(coupon_code, self.user.id)
            if user_uses >= limit_config.max_uses_per_user:
                self._log_attempt(coupon_code, 'limit_exceeded', service_type, booking_amount, details)
                return False, f"You've already used this coupon {limit_config.max_uses_per_user} times", details
        
        # Check per-device limit
        device_uses = self._get_device_uses(coupon_code, self.device_fingerprint)
        if device_uses >= limit_config.max_uses_per_device:
            self._log_attempt(coupon_code, 'device_limit', service_type, booking_amount, details)
            return False, "Device limit reached for this coupon", details
        
        # Check per-IP limit
        ip_uses = self._get_ip_uses(coupon_code, self.client_ip)
        if ip_uses >= limit_config.max_uses_per_ip:
            self._log_attempt(coupon_code, 'ip_limit', service_type, booking_amount, details)
            return False, "IP address limit reached for this coupon", details
        
        # Check for abuse patterns
        if limit_config.anomaly_detection_enabled:
            detector = AbusePatternDetector(
                user_id=self.user.id if self.user else None,
                client_ip=self.client_ip,
                device_fingerprint=self.device_fingerprint
            )
            pattern_check = detector.run_all_checks(coupon_code, booking_id, service_type)
            
            if pattern_check['is_suspicious']:
                if limit_config.auto_suspend_on_abuse and pattern_check['risk_score'] > 70:
                    limit_config.is_suspended = True
                    limit_config.suspension_reason = f"Auto-suspended due to: {', '.join(pattern_check['patterns'])}"
                    limit_config.save()
                    logger.warning(f"Coupon {coupon_code} auto-suspended. Patterns: {pattern_check['patterns']}")
                
                self._log_attempt(
                    coupon_code, 'pattern_detected', service_type, booking_amount,
                    details, is_suspicious=True, risk_score=pattern_check['risk_score']
                )
                
                if pattern_check['risk_score'] > 80:
                    return False, "This request appears suspicious and has been blocked", details
        
        # All checks passed
        self._log_attempt(coupon_code, 'valid_use', service_type, booking_amount, details)
        self._increment_usage(coupon_code, self.user.id if self.user else None)
        
        return True, "", details
    
    def _get_user_uses(self, coupon_code: str, user_id: int, days: int = 30) -> int:
        """Count user's uses in last N days"""
        cutoff = timezone.now() - timedelta(days=days)
        return CouponAbuseLog.objects.filter(
            coupon_code=coupon_code,
            user_id=user_id,
            attempt_type='valid_use',
            timestamp__gte=cutoff
        ).count()
    
    def _get_device_uses(self, coupon_code: str, device_fingerprint: str, days: int = 30) -> int:
        """Count device's uses in last N days"""
        cutoff = timezone.now() - timedelta(days=days)
        return CouponAbuseLog.objects.filter(
            coupon_code=coupon_code,
            device_fingerprint=device_fingerprint,
            attempt_type='valid_use',
            timestamp__gte=cutoff
        ).count()
    
    def _get_ip_uses(self, coupon_code: str, client_ip: str, days: int = 30) -> int:
        """Count IP's uses in last N days"""
        cutoff = timezone.now() - timedelta(days=days)
        return CouponAbuseLog.objects.filter(
            coupon_code=coupon_code,
            client_ip=client_ip,
            attempt_type='valid_use',
            timestamp__gte=cutoff
        ).count()
    
    def _log_attempt(
        self,
        coupon_code: str,
        attempt_type: str,
        service_type: str,
        booking_amount: Optional[Decimal],
        details: Dict,
        is_suspicious: bool = False,
        risk_score: int = 0,
    ) -> CouponAbuseLog:
        """Log coupon attempt to audit trail"""
        log = CouponAbuseLog.objects.create(
            user=self.user,
            coupon_code=coupon_code,
            attempt_type=attempt_type,
            service_type=service_type,
            booking_amount=booking_amount,
            device_fingerprint=self.device_fingerprint,
            client_ip=self.client_ip,
            user_agent=self.user_agent[:500],
            is_suspicious=is_suspicious,
            risk_score=risk_score,
            details=details,
        )
        
        logger.info(f"Coupon attempt logged: {attempt_type} - {coupon_code} - Risk: {risk_score}")
        return log
    
    def _increment_usage(self, coupon_code: str, user_id: Optional[int]):
        """Increment usage counter"""
        try:
            limit_config = CouponUsageLimit.objects.get(coupon_code=coupon_code)
            limit_config.current_uses_counted += 1
            limit_config.save(update_fields=['current_uses_counted'])
        except:
            pass


def get_device_fingerprint(request) -> str:
    """Extract device fingerprint from request"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    
    fingerprint_data = f"{user_agent}:{client_ip}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]


def get_client_ip(request) -> str:
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip