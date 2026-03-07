import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.text import slugify

from apps.core.location_models import City, Locality
from apps.hotels.models import Property

from .models import SearchIndex

logger = logging.getLogger('zygotrip.search.signals')


def _upsert_index(entry_type, name, slug, property_count=None):
    if not name:
        return
    SearchIndex.objects.update_or_create(
        type=entry_type,
        slug=slug,
        defaults={
            "name": name,
            "property_count": property_count,
            "is_active": True,
        },
    )


@receiver(post_save, sender=City)
def index_city(sender, instance, **kwargs):
    if not instance.is_active:
        return
    _upsert_index(
        SearchIndex.TYPE_CITY,
        instance.display_name or instance.name,
        slugify(instance.display_name or instance.name),
        property_count=instance.hotel_count,
    )


@receiver(post_save, sender=Locality)
def index_area(sender, instance, **kwargs):
    if not instance.is_active:
        return
    _upsert_index(
        SearchIndex.TYPE_AREA,
        instance.display_name or instance.name,
        slugify(instance.display_name or instance.name),
        property_count=instance.hotel_count,
    )


@receiver(post_save, sender=Property)
def index_property(sender, instance, **kwargs):
    if not instance.is_active:
        return
    slug = instance.slug or slugify(instance.name)
    _upsert_index(
        SearchIndex.TYPE_PROPERTY,
        instance.name,
        slug,
        property_count=None,
    )


# ──────────────────────────────────────────────────────────────────────────────
# SEARCH INDEX REFRESH SIGNALS (Step 6 — inventory, price, review changes)
# ──────────────────────────────────────────────────────────────────────────────

def _schedule_property_index_rebuild(property_obj):
    """Enqueue a targeted PropertySearchIndex rebuild for one property."""
    try:
        from apps.core.tasks import rebuild_property_search_index
        rebuild_property_search_index.delay(property_id=property_obj.id)
    except Exception:
        logger.warning("Failed to enqueue search index rebuild for property %s", property_obj.id)


@receiver(post_save, sender='rooms.RoomInventory')
def refresh_index_on_inventory_change(sender, instance, **kwargs):
    """Trigger search index rebuild + cache invalidation when room inventory changes."""
    try:
        _schedule_property_index_rebuild(instance.room_type.property)
    except Exception:
        logger.debug("Could not schedule index rebuild on inventory change")
    # Invalidate rate + availability caches for this room type
    try:
        from apps.search.engine.cache_manager import price_cache, availability_cache
        price_cache.invalidate_price(instance.room_type_id)
        availability_cache.invalidate_availability(instance.room_type_id)
    except Exception:
        pass


@receiver(post_save, sender='inventory.InventoryCalendar')
def refresh_index_on_calendar_change(sender, instance, **kwargs):
    """Trigger search index rebuild + cache invalidation when InventoryCalendar changes."""
    try:
        _schedule_property_index_rebuild(instance.room_type.property)
    except Exception:
        logger.debug("Could not schedule index rebuild on calendar change")
    # Invalidate availability cache for this room type
    try:
        from apps.search.engine.cache_manager import availability_cache
        availability_cache.invalidate_availability(instance.room_type_id)
    except Exception:
        pass


@receiver(post_save, sender='pricing.CompetitorPrice')
def refresh_index_on_price_change(sender, instance, **kwargs):
    """Trigger search index rebuild when competitor prices update."""
    try:
        _schedule_property_index_rebuild(instance.property)
    except Exception:
        logger.debug("Could not schedule index rebuild on price change")


@receiver(post_save, sender='hotels.Review')
@receiver(post_delete, sender='hotels.Review')
def refresh_index_on_review_change(sender, instance, **kwargs):
    """Trigger search index rebuild when reviews are added or deleted."""
    try:
        _schedule_property_index_rebuild(instance.property)
    except Exception:
        logger.debug("Could not schedule index rebuild on review change")
