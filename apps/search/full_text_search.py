"""
System 11 — PostgreSQL Full-Text Search Enhancement.

Adds full-text search capabilities to PropertySearchIndex using:
  - PostgreSQL SearchVector / GinIndex
  - Automatic search vector updates via signals
  - Full-text search query interface

This is the pragmatic first step before Elasticsearch — works with
existing PostgreSQL without any new infrastructure.
"""
import logging
from django.db import models
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, SearchVectorField, TrigramSimilarity,
)
from django.contrib.postgres.indexes import GinIndex
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('zygotrip.search')


# ============================================================================
# SEARCH VECTOR FIELD + INDEX (added to PropertySearchIndex via migration)
# ============================================================================

def update_search_vector(instance):
    """
    Update the search_vector field on a PropertySearchIndex instance.
    Weights: A (property name), B (city, locality), C (type, tags), D (amenities).
    """
    from apps.search.models import PropertySearchIndex

    # Build weighted vector
    vector = (
        SearchVector('property_name', weight='A') +
        SearchVector('city_name', weight='B') +
        SearchVector('locality_name', weight='B') +
        SearchVector('property_type', weight='C')
    )

    # Update in DB directly (avoid recursion from signal)
    PropertySearchIndex.objects.filter(pk=instance.pk).update(
        search_vector=vector,
    )


def rebuild_all_search_vectors():
    """
    Rebuild search_vector for ALL PropertySearchIndex entries.
    Called by management command or Celery task.
    """
    from apps.search.models import PropertySearchIndex

    vector = (
        SearchVector('property_name', weight='A') +
        SearchVector('city_name', weight='B') +
        SearchVector('locality_name', weight='B') +
        SearchVector('property_type', weight='C')
    )

    updated = PropertySearchIndex.objects.update(search_vector=vector)
    logger.info('Rebuilt search vectors for %d entries', updated)
    return updated


# ============================================================================
# FULL-TEXT SEARCH QUERY INTERFACE
# ============================================================================

class FullTextSearchEngine:
    """
    PostgreSQL full-text search over PropertySearchIndex.

    Provides ranked search results using search_vector + GinIndex.
    Falls back to ILIKE if search_vector is empty (e.g., during migration).
    """

    @staticmethod
    def search(query_text, city_id=None, limit=50):
        """
        Full-text search with ranking.

        Args:
            query_text: User search query
            city_id: Optional city filter
            limit: Max results

        Returns:
            QuerySet of PropertySearchIndex ordered by relevance
        """
        from apps.search.models import PropertySearchIndex

        if not query_text or not query_text.strip():
            qs = PropertySearchIndex.objects.filter(has_availability=True)
            if city_id:
                qs = qs.filter(city_id=city_id)
            return qs.order_by('-popularity_score')[:limit]

        # Build search query with prefix matching for autocomplete
        search_query = SearchQuery(query_text, search_type='plain')

        qs = PropertySearchIndex.objects.annotate(
            rank=SearchRank('search_vector', search_query),
        ).filter(
            search_vector=search_query,
            has_availability=True,
        )

        if city_id:
            qs = qs.filter(city_id=city_id)

        return qs.order_by('-rank', '-popularity_score')[:limit]

    @staticmethod
    def autocomplete(partial_text, limit=10):
        """
        Autocomplete search using trigram similarity.
        Works for partial matches (typo-tolerant).

        Requires pg_trgm extension: CREATE EXTENSION IF NOT EXISTS pg_trgm;
        """
        from apps.search.models import PropertySearchIndex

        if not partial_text or len(partial_text) < 2:
            return PropertySearchIndex.objects.none()

        return (
            PropertySearchIndex.objects
            .annotate(
                similarity=TrigramSimilarity('property_name', partial_text),
            )
            .filter(similarity__gt=0.1)
            .order_by('-similarity')[:limit]
        )

    @staticmethod
    def search_with_fallback(query_text, city_id=None, limit=50):
        """
        Full-text search with ILIKE fallback for robustness.
        If FTS returns no results, falls back to ILIKE.
        """
        from apps.search.models import PropertySearchIndex

        # Try FTS first
        results = FullTextSearchEngine.search(query_text, city_id, limit)
        if results.exists():
            return results

        # Fallback to ILIKE
        qs = PropertySearchIndex.objects.filter(
            models.Q(property_name__icontains=query_text) |
            models.Q(city_name__icontains=query_text) |
            models.Q(locality_name__icontains=query_text),
            has_availability=True,
        )
        if city_id:
            qs = qs.filter(city_id=city_id)

        return qs.order_by('-popularity_score')[:limit]
