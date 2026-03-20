from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import PlatformSettings

PLATFORM_SETTINGS_CACHE_KEY = 'core:platform_settings:singleton'
PLATFORM_SETTINGS_CACHE_TTL = 300


def get_platform_settings(force_refresh=False):
    """Return singleton PlatformSettings with a short-lived cache."""
    if not force_refresh:
        cached = cache.get(PLATFORM_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached

    settings_obj = PlatformSettings.get_settings()
    cache.set(PLATFORM_SETTINGS_CACHE_KEY, settings_obj, PLATFORM_SETTINGS_CACHE_TTL)
    return settings_obj


def invalidate_platform_settings_cache():
    cache.delete(PLATFORM_SETTINGS_CACHE_KEY)


@receiver(post_save, sender=PlatformSettings)
def _invalidate_platform_settings_cache_on_save(sender, instance, **kwargs):
    invalidate_platform_settings_cache()
