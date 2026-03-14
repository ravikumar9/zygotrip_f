"""
Wishlist / Saved Properties API — Goibibo-style property saving.

Endpoints:
  POST   /api/v1/properties/<id>/save/      — save a property
  DELETE /api/v1/properties/<id>/save/      — unsave a property
  GET    /api/v1/properties/saved/          — list saved properties (paginated)
  GET    /api/v1/properties/<id>/save/      — check if saved (returns {saved: true/false})
"""
import logging

from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.wishlist')


# ── Model ─────────────────────────────────────────────────────────────────────

class SavedProperty(models.Model):
    """User's saved / wishlisted properties."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_properties',
        db_index=True,
    )
    property = models.ForeignKey(
        'hotels.Property',
        on_delete=models.CASCADE,
        related_name='saved_by_users',
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')
        ordering = ['-created_at']
        verbose_name = 'Saved Property'
        verbose_name_plural = 'Saved Properties'
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user} ♥ {self.property.name}'


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _saved_cache_key(user_id: int) -> str:
    return f'wishlist:ids:{user_id}'


def _get_saved_ids(user_id: int) -> set:
    """Return set of saved property IDs for a user (cached 10 min)."""
    key = _saved_cache_key(user_id)
    cached = cache.get(key)
    if cached is not None:
        return set(cached)
    ids = set(
        SavedProperty.objects.filter(user_id=user_id).values_list('property_id', flat=True)
    )
    cache.set(key, list(ids), timeout=600)
    return ids


def _invalidate_saved_cache(user_id: int):
    cache.delete(_saved_cache_key(user_id))


# ── API Views ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def property_save_toggle(request, property_id):
    """
    GET    /api/v1/properties/<id>/save/ — check saved status
    POST   /api/v1/properties/<id>/save/ — save property
    DELETE /api/v1/properties/<id>/save/ — unsave property
    """
    from apps.hotels.models import Property

    try:
        prop = Property.objects.get(pk=property_id, status='approved')
    except Property.DoesNotExist:
        # Try by slug
        try:
            prop = Property.objects.get(slug=str(property_id), status='approved')
        except Property.DoesNotExist:
            return Response({'error': 'Property not found'}, status=404)

    user = request.user

    if request.method == 'GET':
        saved = SavedProperty.objects.filter(user=user, property=prop).exists()
        return Response({'saved': saved, 'property_id': prop.id})

    if request.method == 'POST':
        _, created = SavedProperty.objects.get_or_create(user=user, property=prop)
        _invalidate_saved_cache(user.id)
        save_count = SavedProperty.objects.filter(property=prop).count()
        logger.info('WISHLIST_SAVE user=%s property=%s', user.id, prop.id)
        return Response({
            'saved': True,
            'created': created,
            'save_count': save_count,
            'message': 'Property saved to your wishlist',
        }, status=201 if created else 200)

    if request.method == 'DELETE':
        deleted, _ = SavedProperty.objects.filter(user=user, property=prop).delete()
        _invalidate_saved_cache(user.id)
        logger.info('WISHLIST_REMOVE user=%s property=%s', user.id, prop.id)
        return Response({
            'saved': False,
            'removed': bool(deleted),
            'message': 'Property removed from wishlist',
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def saved_properties_list(request):
    """
    GET /api/v1/properties/saved/
    ?page=1&page_size=20

    Returns user's saved properties with full property detail.
    """
    from apps.hotels.models import Property, PropertyImage

    user = request.user
    page = max(1, int(request.GET.get('page', 1)))
    page_size = min(int(request.GET.get('page_size', 20)), 50)
    offset = (page - 1) * page_size

    saved_qs = (
        SavedProperty.objects
        .filter(user=user)
        .select_related('property__city', 'property__locality')
        .prefetch_related(
            Prefetch(
                'property__images',
                queryset=PropertyImage.objects.filter(is_featured=True).order_by('display_order'),
                to_attr='featured_images',
            )
        )
    )

    total = saved_qs.count()
    page_qs = saved_qs[offset: offset + page_size]

    results = []
    for sp in page_qs:
        prop = sp.property
        featured = prop.featured_images[0].image.url if prop.featured_images else None
        results.append({
            'saved_at':      sp.created_at.isoformat(),
            'property': {
                'id':            prop.id,
                'uuid':          str(prop.uuid),
                'name':          prop.name,
                'slug':          prop.slug,
                'property_type': prop.property_type if hasattr(prop, 'property_type') else 'hotel',
                'city':          prop.city.name if prop.city else '',
                'locality':      prop.locality.name if prop.locality else '',
                'star_category': prop.star_category,
                'rating':        float(prop.rating or 0),
                'review_count':  prop.review_count or 0,
                'base_price':    float(prop.base_price or 0),
                'has_free_cancellation': prop.has_free_cancellation,
                'featured_image': featured,
                'tags':          prop.tags or [],
            },
        })

    return Response({
        'count':     total,
        'page':      page,
        'page_size': page_size,
        'pages':     (total + page_size - 1) // page_size,
        'results':   results,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def saved_property_ids(request):
    """
    GET /api/v1/properties/saved/ids/
    Fast endpoint — returns just the list of saved property IDs for client-side rendering.
    Used by HotelCard to show heart state without N+1 calls.
    """
    ids = list(_get_saved_ids(request.user.id))
    return Response({'saved_ids': ids, 'count': len(ids)})
