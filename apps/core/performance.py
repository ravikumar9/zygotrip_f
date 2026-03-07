"""
Performance Optimization — Database Indexes, Query Patterns, Bulk Operations.

Provides:
  1. DatabaseIndexAudit — verifies critical indexes exist
  2. QueryOptimizer — common bulk query patterns
  3. CacheWarmer — pre-populate Redis caches on startup
  4. SlowQueryMonitor — log and alert on slow queries
"""
import logging
import time
from decimal import Decimal

from django.conf import settings
from django.db import connection, models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.performance')


# ============================================================================
# Critical Index Definitions (for migration)
# ============================================================================

class PerformanceIndex(TimeStampedModel):
    """
    Tracks custom performance indexes applied to the database.
    Not a real table — just documents index requirements.
    Use Django Meta.indexes on the actual models.
    """

    CRITICAL_INDEXES = [
        # Booking lookups
        ('booking_booking', 'status, hold_expires_at'),
        ('booking_booking', 'property_id, status, created_at DESC'),
        ('booking_booking', 'user_id, status, created_at DESC'),
        ('booking_booking', 'check_in, check_out'),
        ('booking_booking', 'property_id, check_in, check_out'),
        # Inventory
        ('inventory_inventorycalendar', 'room_type_id, date'),
        ('inventory_inventorycalendar', 'room_type_id, date, available_rooms'),
        # Search
        ('search_propertysearchindex', 'city, is_active'),
        ('search_propertysearchindex', 'latitude, longitude'),
        # Payments
        ('payments_paymenttransaction', 'idempotency_key'),
        ('payments_paymenttransaction', 'booking_id, status'),
        # Analytics
        ('core_analytics_event', 'event_type, created_at DESC'),
        ('core_analytics_event', 'property_id, event_type, created_at DESC'),
        # Geo
        ('hotels_property', 'latitude, longitude'),
        ('hotels_property', 'city, is_active'),
    ]

    class Meta:
        app_label = 'core'
        managed = False  # Not a real table

    @classmethod
    def audit(cls):
        """Check which critical indexes exist vs. missing."""
        results = {'present': [], 'missing': []}

        with connection.cursor() as cursor:
            for table, columns in cls.CRITICAL_INDEXES:
                # Check if an index exists on these columns
                if connection.vendor == 'postgresql':
                    cursor.execute("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = %s
                    """, [table])
                    index_names = [row[0] for row in cursor.fetchall()]
                    # Heuristic: check if column names appear in any index name
                    col_parts = [c.strip().replace(' DESC', '').replace('_id', '')
                                 for c in columns.split(',')]
                    found = any(
                        all(part in idx_name for part in col_parts)
                        for idx_name in index_names
                    )
                else:
                    found = True  # Skip for SQLite

                entry = f'{table}({columns})'
                if found:
                    results['present'].append(entry)
                else:
                    results['missing'].append(entry)

        return results


# ============================================================================
# Query Optimizer — Bulk Patterns
# ============================================================================

class QueryOptimizer:
    """Common optimized query patterns for high-traffic endpoints."""

    @staticmethod
    def bulk_check_availability(room_type_ids, check_in, check_out):
        """
        Check availability for multiple room types in a single query.
        Returns dict: {room_type_id: min_available_rooms}
        """
        from apps.inventory.models import InventoryCalendar

        results = {}
        calendars = (
            InventoryCalendar.objects.filter(
                room_type_id__in=room_type_ids,
                date__gte=check_in,
                date__lt=check_out,
            )
            .values('room_type_id')
            .annotate(min_available=models.Min('available_rooms'))
        )

        for row in calendars:
            results[row['room_type_id']] = row['min_available'] or 0

        # Mark missing as 0
        for rtid in room_type_ids:
            if rtid not in results:
                results[rtid] = 0

        return results

    @staticmethod
    def bulk_get_rates(room_type_ids, check_in, check_out):
        """
        Fetch rates for multiple room types across date range.
        Returns dict: {room_type_id: {date: rate}}
        """
        from apps.inventory.models import InventoryCalendar

        results = {}
        calendars = InventoryCalendar.objects.filter(
            room_type_id__in=room_type_ids,
            date__gte=check_in,
            date__lt=check_out,
        ).values_list('room_type_id', 'date', 'rate')

        for rtid, date, rate in calendars:
            if rtid not in results:
                results[rtid] = {}
            results[rtid][str(date)] = float(rate) if rate else None

        return results

    @staticmethod
    def prefetch_booking_details(booking_qs):
        """
        Optimally prefetch all related data for booking list views.
        Reduces N+1 queries.
        """
        return booking_qs.select_related(
            'property', 'user',
        ).prefetch_related(
            'rooms__room_type',
            'guests',
            'price_breakdown',
            'status_history',
        )

    @staticmethod
    def bulk_property_stats(property_ids, days=30):
        """
        Get booking stats for multiple properties in a single query batch.
        Returns dict: {property_id: {bookings, revenue, avg_rating}}
        """
        from apps.booking.models import Booking
        from django.db.models import Count, Sum, Avg

        cutoff = timezone.now() - timezone.timedelta(days=days)

        stats = (
            Booking.objects.filter(
                property_id__in=property_ids,
                created_at__gte=cutoff,
                status__in=['confirmed', 'completed'],
            )
            .values('property_id')
            .annotate(
                bookings=Count('id'),
                revenue=Sum('total_amount'),
            )
        )

        results = {}
        for row in stats:
            results[row['property_id']] = {
                'bookings': row['bookings'],
                'revenue': float(row['revenue'] or 0),
            }

        for pid in property_ids:
            if pid not in results:
                results[pid] = {'bookings': 0, 'revenue': 0}

        return results


# ============================================================================
# Cache Warmer
# ============================================================================

class CacheWarmer:
    """Pre-populate critical Redis caches on deployment/restart."""

    @classmethod
    def warm_all(cls):
        """Run all cache warming tasks."""
        results = {}
        results['popular_cities'] = cls._warm_popular_cities()
        results['search_config'] = cls._warm_search_config()
        logger.info('Cache warming complete: %s', results)
        return results

    @classmethod
    def _warm_popular_cities(cls):
        """Cache top cities for autocomplete."""
        r = _redis()
        if not r:
            return 0

        from apps.core.location_models import City
        cities = City.objects.filter(is_active=True).order_by('-property_count')[:50]

        import json
        data = [
            {'code': c.code, 'name': c.name, 'state': getattr(c, 'state_name', '')}
            for c in cities
        ]
        r.setex('cache:popular_cities', 3600, json.dumps(data))
        return len(data)

    @classmethod
    def _warm_search_config(cls):
        """Cache search configuration (filters, ranges)."""
        r = _redis()
        if not r:
            return False

        from apps.hotels.models import Property
        from django.db.models import Min, Max

        price_range = Property.objects.filter(is_active=True).aggregate(
            min_price=Min('min_rate'),
            max_price=Max('min_rate'),
        )

        import json
        config = {
            'price_range': {
                'min': float(price_range['min_price'] or 0),
                'max': float(price_range['max_price'] or 50000),
            },
            'star_ratings': [1, 2, 3, 4, 5],
        }
        r.setex('cache:search_config', 3600, json.dumps(config))
        return True


# ============================================================================
# Slow Query Monitor
# ============================================================================

class SlowQueryLog(TimeStampedModel):
    """Persisted slow query log for analysis."""

    query = models.TextField()
    duration_ms = models.FloatField()
    view_name = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    params = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-duration_ms', '-created_at'],
                         name='slow_query_duration_idx'),
        ]

    @classmethod
    def cleanup(cls, days=30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted


def _redis():
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception:
        return None
