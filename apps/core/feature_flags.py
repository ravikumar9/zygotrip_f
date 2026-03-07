"""
System 14 — Feature Flag System.

Production-grade feature flag system with:
  - Database-backed FeatureFlag model
  - Percentage-based rollout
  - User-group targeting
  - Evaluation service with caching
  - Context processor for templates
  - Middleware for request-scoped flags
"""
import hashlib
import logging
from functools import lru_cache
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.feature_flags')

CACHE_KEY_PREFIX = 'ff:'
CACHE_TTL = 60  # seconds — short TTL for near-real-time flag changes


# ============================================================================
# MODEL
# ============================================================================

class FeatureFlag(TimeStampedModel):
    """
    Database-backed feature flag.
    Supports: on/off, percentage rollout, user-group targeting.
    """
    name = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text='Unique flag name (e.g. "enable_new_checkout")',
    )
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(
        default=False, db_index=True,
        help_text='Master switch — if False, flag is off for everyone',
    )
    rollout_percentage = models.PositiveIntegerField(
        default=100,
        help_text='0-100: percentage of users who see this flag as enabled',
    )
    allowed_groups = models.JSONField(
        default=list, blank=True,
        help_text='List of Django group names that can see this flag (empty = all groups)',
    )
    allowed_users = models.JSONField(
        default=list, blank=True,
        help_text='List of user IDs that always see this flag (override rollout)',
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Arbitrary key-value data (e.g. variant config)',
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Auto-disable after this date (cleanup)',
    )

    class Meta:
        app_label = 'core'
        ordering = ['name']
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'

    def __str__(self):
        state = 'ON' if self.is_enabled else 'OFF'
        return f"FF:{self.name} [{state}] {self.rollout_percentage}%"


# ============================================================================
# EVALUATION SERVICE
# ============================================================================

class FeatureFlagService:
    """
    Evaluate feature flags for a given user.
    Results are cached in Redis/memcache for CACHE_TTL seconds.
    """

    @staticmethod
    def _cache_key(flag_name, user_id=None):
        uid = str(user_id) if user_id else 'anon'
        return f'{CACHE_KEY_PREFIX}{flag_name}:{uid}'

    @classmethod
    def is_enabled(cls, flag_name, user=None, default=False):
        """
        Check if a feature flag is enabled for the given user.

        Logic:
          1. If flag doesn't exist → return default
          2. If flag.is_enabled is False → False
          3. If flag has expired → False
          4. If user in allowed_users → True (override)
          5. If allowed_groups is set and user not in any → False
          6. Percentage rollout: hash(user_id + flag_name) % 100 < rollout_percentage
          7. Anonymous users: hash(session_key + flag_name) if available
        """
        user_id = getattr(user, 'id', None) if user else None
        cache_key = cls._cache_key(flag_name, user_id)

        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            flag = FeatureFlag.objects.get(name=flag_name)
        except FeatureFlag.DoesNotExist:
            cache.set(cache_key, default, CACHE_TTL)
            return default

        result = cls._evaluate(flag, user)
        cache.set(cache_key, result, CACHE_TTL)
        return result

    @classmethod
    def _evaluate(cls, flag, user):
        """Pure evaluation logic (no caching)."""
        if not flag.is_enabled:
            return False

        if flag.expires_at and flag.expires_at < timezone.now():
            return False

        user_id = getattr(user, 'id', None) if user else None

        # Explicit user allowlist
        if user_id and flag.allowed_users:
            if user_id in flag.allowed_users or str(user_id) in [str(u) for u in flag.allowed_users]:
                return True

        # Group restriction
        if flag.allowed_groups and user:
            user_groups = set(user.groups.values_list('name', flat=True)) if hasattr(user, 'groups') else set()
            if not user_groups.intersection(set(flag.allowed_groups)):
                return False

        # Percentage rollout
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        # Deterministic hash for consistent user experience
        hash_input = f'{flag.name}:{user_id or "anon"}'
        bucket = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100
        return bucket < flag.rollout_percentage

    @classmethod
    def get_all_flags(cls, user=None):
        """
        Return dict of all flag names → bool for the given user.
        Useful for passing to frontend or template context.
        """
        flags = FeatureFlag.objects.filter(is_active=True)
        return {
            flag.name: cls._evaluate(flag, user)
            for flag in flags
        }

    @classmethod
    def invalidate_cache(cls, flag_name=None):
        """
        Invalidate cached flag evaluations.
        Call after admin changes a flag.
        """
        if flag_name:
            # Invalidate all user variants of this flag
            # Since we can't enumerate, use a version key pattern
            cache.delete_pattern(f'{CACHE_KEY_PREFIX}{flag_name}:*')
        else:
            cache.delete_pattern(f'{CACHE_KEY_PREFIX}*')

    @classmethod
    def ensure_defaults(cls):
        """
        Create default feature flags from settings.FEATURE_FLAGS dict.
        Called during startup or management command.
        """
        defaults = getattr(settings, 'FEATURE_FLAGS', {})
        created = 0
        for name, enabled in defaults.items():
            _, was_created = FeatureFlag.objects.get_or_create(
                name=name,
                defaults={
                    'is_enabled': bool(enabled),
                    'rollout_percentage': 100,
                    'description': f'Migrated from settings.FEATURE_FLAGS',
                },
            )
            if was_created:
                created += 1
        if created:
            logger.info('Created %d default feature flags from settings', created)
        return created


# Singleton
feature_flags = FeatureFlagService()


# ============================================================================
# DJANGO CONTEXT PROCESSOR
# ============================================================================

def feature_flags_context(request):
    """
    Template context processor.
    Add to settings.TEMPLATES[0]['OPTIONS']['context_processors'].

    Usage in template: {% if feature_flags.enable_new_checkout %}
    """
    user = getattr(request, 'user', None)
    if user and not user.is_authenticated:
        user = None
    return {
        'feature_flags': FeatureFlagService.get_all_flags(user),
    }


# ============================================================================
# MIDDLEWARE
# ============================================================================

class FeatureFlagMiddleware:
    """
    Middleware that attaches feature flags to request object.
    Usage in views: request.feature_flags['enable_new_checkout']
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and not user.is_authenticated:
            user = None
        request.feature_flags = FeatureFlagService.get_all_flags(user)
        response = self.get_response(request)
        return response
