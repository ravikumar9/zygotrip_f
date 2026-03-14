"""
Search app Celery tasks: CTR aggregation, ranking score refresh,
cancellation/reliability sync, geospatial queries.

Tasks:
- aggregate_ctr_scores: Recomputes click_through_rate from impressions/clicks
- refresh_search_engagement: Syncs booking counts from Booking model
- sync_reliability_signals: Cancellation rate + availability reliability
"""
import logging
from celery import shared_task
from django.db.models import F, Value, DecimalField, ExpressionWrapper
from django.utils import timezone

logger = logging.getLogger('zygotrip.search.tasks')


@shared_task
def aggregate_ctr_scores():
    """Recompute click_through_rate for all PropertySearchIndex rows.

    CTR = total_clicks / total_impressions (clamped 0-1).
    Also refreshes total_bookings from Booking model for conversion scoring.
    Run every 30 minutes in production.
    """
    from apps.search.models import PropertySearchIndex

    try:
        # Update CTR for rows with impressions
        updated = PropertySearchIndex.objects.filter(
            total_impressions__gt=0,
        ).update(
            click_through_rate=ExpressionWrapper(
                F('total_clicks') * Value(1.0) / F('total_impressions'),
                output_field=DecimalField(max_digits=5, decimal_places=4),
            ),
        )

        # Sync total_bookings from Booking model
        try:
            from apps.booking.models import Booking
            from django.db.models import Count

            booking_counts = (
                Booking.objects.filter(
                    status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
                )
                .values('property_id')
                .annotate(cnt=Count('id'))
            )

            for row in booking_counts:
                if row['property_id']:
                    PropertySearchIndex.objects.filter(
                        property_id=row['property_id'],
                    ).update(total_bookings=row['cnt'])
        except Exception as e:
            logger.warning('Booking count sync failed: %s', e)

        logger.info('CTR aggregation complete: %d rows updated', updated)

        # Flush learning loop signals (impressions/clicks from Redis → DB)
        try:
            from apps.search.learning_loop import flush_learning_signals_to_db
            flushed = flush_learning_signals_to_db()
            logger.info('Learning loop flush: %d properties updated', flushed)
        except Exception as e:
            logger.warning('Learning loop flush failed: %s', e)

        return {'updated': updated}

    except Exception as exc:
        logger.error('aggregate_ctr_scores failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def refresh_search_engagement():
    """Refresh engagement signals (recent_bookings, rooms_left) on PropertySearchIndex.

    Updates:
    - recent_bookings: count of bookings in last 24h (social proof signal)
    - rooms_left: available rooms for nearest check-in date (urgency signal)
    Run every 15 minutes.
    """
    from apps.search.models import PropertySearchIndex

    try:
        from apps.booking.models import Booking
        from django.db.models import Count
        from datetime import timedelta

        yesterday = timezone.now() - timedelta(hours=24)

        # Recent bookings in last 24h
        recent = (
            Booking.objects.filter(
                status__in=['confirmed', 'checked_in'],
                created_at__gte=yesterday,
            )
            .values('property_id')
            .annotate(cnt=Count('id'))
        )

        for row in recent:
            if row['property_id']:
                PropertySearchIndex.objects.filter(
                    property_id=row['property_id'],
                ).update(recent_bookings=row['cnt'])

        logger.info('Search engagement refreshed')
        return {'status': 'ok'}

    except Exception as exc:
        logger.error('refresh_search_engagement failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def sync_reliability_signals():
    """Sync cancellation_rate + availability_reliability into PropertySearchIndex.

    cancellation_rate = cancelled bookings / total bookings (per property)
    availability_reliability = 1 - (overbooking_incidents / total_holds)

    Run every hour.
    """
    from apps.search.models import PropertySearchIndex

    try:
        from apps.booking.models import Booking
        from django.db.models import Count, Q
        from decimal import Decimal

        # ── Cancellation rate per property ──────────────────────────
        stats = (
            Booking.objects.values('property_id')
            .annotate(
                total=Count('id'),
                cancelled=Count('id', filter=Q(
                    status__in=['cancelled', 'cancelled_by_hotel', 'refunded'],
                )),
            )
            .filter(total__gt=0)
        )

        cancel_updated = 0
        for row in stats:
            if row['property_id']:
                rate = Decimal(str(row['cancelled'])) / Decimal(str(row['total']))
                PropertySearchIndex.objects.filter(
                    property_id=row['property_id'],
                ).update(cancellation_rate=min(rate, Decimal('1.0')))
                cancel_updated += 1

        # ── Availability reliability ────────────────────────────────
        # Measure: what fraction of holds successfully converted vs expired
        try:
            from apps.inventory.models import InventoryHold

            hold_stats = (
                InventoryHold.objects.values('room_type__property_id')
                .annotate(
                    total_holds=Count('id'),
                    failed_holds=Count('id', filter=Q(
                        status__in=['expired', 'cancelled'],
                    )),
                )
                .filter(total_holds__gt=0)
            )

            for row in hold_stats:
                prop_id = row.get('room_type__property_id')
                if prop_id:
                    reliability = Decimal('1.0') - (
                        Decimal(str(row['failed_holds'])) / Decimal(str(row['total_holds']))
                    )
                    PropertySearchIndex.objects.filter(
                        property_id=prop_id,
                    ).update(availability_reliability=max(reliability, Decimal('0.0')))
        except Exception as e:
            logger.warning('Availability reliability sync failed: %s', e)

        # ── Commission percentage sync ──────────────────────────────
        try:
            from apps.hotels.models import Property
            for prop in Property.objects.filter(status='approved').only('id', 'commission_percentage'):
                PropertySearchIndex.objects.filter(
                    property_id=prop.id,
                ).update(commission_percentage=prop.commission_percentage or 15)
        except Exception as e:
            logger.warning('Commission sync failed: %s', e)

        logger.info('Reliability signals synced: %d properties', cancel_updated)
        return {'cancel_updated': cancel_updated}

    except Exception as exc:
        logger.error('sync_reliability_signals failed: %s', exc)
        return {'error': str(exc)}


@shared_task(name='apps.search.tasks.warm_search_cache_task')
def warm_search_cache_task(cities=None):
    """Periodic Redis warm-up for the highest-volume city searches."""
    from apps.search.engine.cache_manager import warm_search_cache

    warmed = warm_search_cache(cities=cities)
    return {'warmed': warmed}


@shared_task(name='apps.search.tasks.warm_popular_search_patterns_task')
def warm_popular_search_patterns_task(cities=None, patterns=None):
    """Pre-compute city/date OTA search combinations into cache."""
    from apps.search.engine.cache_manager import warm_popular_search_patterns

    warmed = warm_popular_search_patterns(cities=cities, patterns=patterns)
    return {'warmed': warmed}


@shared_task(name='apps.search.tasks.warm_rate_cache_task')
def warm_rate_cache_task(property_id=None, days_ahead=30):
    """Warm per-room rate cache for the most in-demand hotels."""
    from apps.search.engine.cache_manager import warm_rate_cache_bulk

    warmed = warm_rate_cache_bulk(property_id=property_id, days_ahead=days_ahead)
    return {'warmed': warmed}


# ── Geospatial Search Utility ──────────────────────────────────────────────

def geospatial_search(lat: float, lng: float, radius_km: float = 5.0, limit: int = 50):
    """
    Find hotels within `radius_km` of a given lat/lng coordinate.

    Uses the Haversine approximation via raw SQL for PostgreSQL:
      d = 6371 * acos(cos(radians(lat1)) * cos(radians(lat2))
          * cos(radians(lng2) - radians(lng1))
          + sin(radians(lat1)) * sin(radians(lat2)))

    Returns PropertySearchIndex queryset annotated with `distance_km`,
    ordered by distance ascending.

    Example: Hotels within 2 km of airport
        results = geospatial_search(12.9716, 77.5946, radius_km=2.0)
    """
    from apps.search.models import PropertySearchIndex
    from django.db.models.expressions import RawSQL

    # Bounding-box pre-filter (rough estimate: 1° lat ≈ 111 km)
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.01, abs(__import__('math').cos(__import__('math').radians(lat)))))

    qs = PropertySearchIndex.objects.filter(
        has_availability=True,
        latitude__range=(lat - lat_delta, lat + lat_delta),
        longitude__range=(lng - lng_delta, lng + lng_delta),
    )

    # Annotate with Haversine distance
    haversine_sql = """
        6371 * acos(
            LEAST(1.0, GREATEST(-1.0,
                cos(radians(%s)) * cos(radians(latitude))
                * cos(radians(longitude) - radians(%s))
                + sin(radians(%s)) * sin(radians(latitude))
            ))
        )
    """

    qs = qs.extra(
        select={'distance_km': haversine_sql},
        select_params=[lat, lng, lat],
    ).order_by('distance_km')

    # Post-filter exact radius
    qs = qs.extra(
        where=[f'{haversine_sql} <= %s'],
        params=[lat, lng, lat, radius_km],
    )

    return qs[:limit]


# ── User Search Profile Refresh ───────────────────────────────────────────


@shared_task
def refresh_user_search_profiles():
    """Recompute UserSearchProfile for active users.

    Targets users who have booked or searched in the last 90 days.
    Run every 2 hours via Celery Beat.
    """
    from apps.search.personalization import aggregate_user_profile

    try:
        from apps.booking.models import Booking
        from django.db.models import Max
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=90)

        # Users with recent bookings
        active_users = (
            Booking.objects.filter(created_at__gte=cutoff)
            .values_list('user_id', flat=True)
            .distinct()
        )

        refreshed = 0
        for uid in active_users[:5000]:  # cap at 5000 per run
            try:
                aggregate_user_profile(uid)
                refreshed += 1
            except Exception as exc:
                logger.debug('Profile refresh failed for user %s: %s', uid, exc)

        logger.info('Refreshed %d user search profiles', refreshed)
        return refreshed

    except Exception as exc:
        logger.error('refresh_user_search_profiles failed: %s', exc)
        return 0


@shared_task
def reindex_elasticsearch():
    """Full ElasticSearch re-index for all hotels."""
    try:
        from apps.search.es_engine import reindex_all_hotels, ensure_indices
        ensure_indices()
        count = reindex_all_hotels()
        logger.info('ElasticSearch re-index completed: %d hotels indexed', count)
        return count
    except Exception as exc:
        logger.error('reindex_elasticsearch failed: %s', exc)
        return 0
