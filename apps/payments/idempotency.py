"""
Payment Idempotency Guard — Prevents Duplicate Charges.

Provides:
  1. IdempotencyRecord model — stores request hash + cached response
  2. idempotency_guard() decorator — wraps payment views for atomic dedup
  3. Generate/validate idempotency keys

Flow:
  Client sends Idempotency-Key header → Guard checks for existing record →
  If found and status=completed, return cached response →
  If found and status=processing, return 409 Conflict →
  If not found, create record, run view, cache response, return.
"""
import hashlib
import json
import logging
import time
import uuid
from functools import wraps

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.http import JsonResponse
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.idempotency')


# ============================================================================
# Model
# ============================================================================

class IdempotencyRecord(TimeStampedModel):
    """
    Tracks idempotent request processing.
    Unique on idempotency_key, expires after 24 hours.
    """

    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    request_path = models.CharField(max_length=255)
    request_hash = models.CharField(
        max_length=64, blank=True,
        help_text='SHA256 of request body to detect mismatched replays',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'payments'
        indexes = [
            models.Index(fields=['idempotency_key', 'status'], name='idempotency_key_status_idx'),
            models.Index(fields=['expires_at'], name='idempotency_expires_idx'),
        ]

    def __str__(self):
        return f"Idempotency({self.idempotency_key[:12]}..., {self.status})"


# ============================================================================
# Decorator
# ============================================================================

def idempotency_guard(ttl_hours=24):
    """
    Decorator for payment views ensuring at-most-once processing.

    Usage:
        @idempotency_guard()
        def initiate_payment(request, ...):
            ...

    Client must send: Idempotency-Key: <uuid> header.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Extract idempotency key
            key = (
                request.META.get('HTTP_IDEMPOTENCY_KEY')
                or request.META.get('HTTP_X_IDEMPOTENCY_KEY')
                or request.POST.get('idempotency_key')
            )

            if not key:
                # No key = normal (non-idempotent) processing
                return view_func(request, *args, **kwargs)

            # Hash request body for mismatch detection
            body = request.body or b''
            request_hash = hashlib.sha256(body).hexdigest()

            user = request.user if request.user.is_authenticated else None
            now = timezone.now()
            expires = now + timezone.timedelta(hours=ttl_hours)

            # Try to find existing record
            try:
                with transaction.atomic():
                    record = IdempotencyRecord.objects.select_for_update(
                        nowait=True,
                    ).get(idempotency_key=key)

                    # Found existing record
                    if record.status == IdempotencyRecord.STATUS_COMPLETED:
                        # Return cached response
                        logger.info('Idempotency hit (completed): %s', key[:12])
                        return JsonResponse(
                            record.response_body or {'detail': 'Already processed'},
                            status=record.status_code or 200,
                        )

                    if record.status == IdempotencyRecord.STATUS_PROCESSING:
                        # Another request is currently processing
                        age = (now - record.locked_at).total_seconds() if record.locked_at else 999
                        if age < 30:
                            return JsonResponse(
                                {'detail': 'Request is being processed. Please retry.'},
                                status=409,
                            )
                        # Stale lock — reclaim
                        record.locked_at = now
                        record.save(update_fields=['locked_at'])

                    if record.status == IdempotencyRecord.STATUS_FAILED:
                        # Allow retry of failed requests
                        record.status = IdempotencyRecord.STATUS_PROCESSING
                        record.locked_at = now
                        record.save(update_fields=['status', 'locked_at'])

                    # Check body mismatch
                    if record.request_hash and record.request_hash != request_hash:
                        return JsonResponse(
                            {'detail': 'Idempotency key reused with different request body.'},
                            status=422,
                        )

            except IdempotencyRecord.DoesNotExist:
                # Create new record
                try:
                    record = IdempotencyRecord.objects.create(
                        idempotency_key=key,
                        user=user,
                        request_path=request.path[:255],
                        request_hash=request_hash,
                        status=IdempotencyRecord.STATUS_PROCESSING,
                        locked_at=now,
                        expires_at=expires,
                    )
                except IntegrityError:
                    # Race condition — another request created it first
                    return JsonResponse(
                        {'detail': 'Request is being processed. Please retry.'},
                        status=409,
                    )

            except Exception:
                # select_for_update(nowait=True) can raise OperationalError
                return JsonResponse(
                    {'detail': 'Request is being processed. Please retry.'},
                    status=409,
                )

            # Execute the actual view
            try:
                response = view_func(request, *args, **kwargs)

                # Cache the response
                try:
                    if hasattr(response, 'content'):
                        resp_body = json.loads(response.content)
                    else:
                        resp_body = {'detail': 'processed'}
                except (json.JSONDecodeError, AttributeError):
                    resp_body = {'detail': 'processed'}

                record.status = IdempotencyRecord.STATUS_COMPLETED
                record.status_code = getattr(response, 'status_code', 200)
                record.response_body = resp_body
                record.save(update_fields=['status', 'status_code', 'response_body'])

                return response

            except Exception as exc:
                record.status = IdempotencyRecord.STATUS_FAILED
                record.response_body = {'error': str(exc)[:500]}
                record.save(update_fields=['status', 'response_body'])
                raise

        return wrapper
    return decorator


# ============================================================================
# Utilities
# ============================================================================

def generate_idempotency_key():
    """Generate a unique idempotency key for client use."""
    return uuid.uuid4().hex


def cleanup_expired_records():
    """Remove expired idempotency records. Run via Celery beat."""
    cutoff = timezone.now()
    deleted, _ = IdempotencyRecord.objects.filter(expires_at__lt=cutoff).delete()
    logger.info('Cleaned up %d expired idempotency records', deleted)
    return deleted
