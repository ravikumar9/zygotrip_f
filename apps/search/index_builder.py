"""
Search index builder — callable from both management commands and AppConfig.ready().
Keeps the rebuild logic DRY so it can be triggered:
  - At Django startup (HotelsConfig.ready → post_migrate signal)
  - After seeding (seed_ota_data management command)
  - On demand (rebuild_search_index management command)
"""
import logging

logger = logging.getLogger('zygotrip.search')

# Correct filter for OTA-visible properties (mirrors ota_visible_properties())
_OTA_FILTER = dict(status='approved', agreement_signed=True)


def rebuild_search_index():
    """
    Full rebuild of all search index tables:
      1. search_searchindex  (SearchIndex — used by property_search_api)
      2. core_locationsearchindex  (LocationSearchIndex — used by autosuggest)

    Also syncs City.hotel_count to the real approved property count per city.

    Property filter: status='approved' AND agreement_signed=True
      (matches ota_visible_properties() in hotels/ota_selectors.py)

    Returns a dict with counts: {cities, areas, properties, total,
                                  location_entries, hotel_count_updated}
    """
    from django.db.models import Count, Q
    from django.utils.text import slugify

    from apps.core.location_models import City, Locality, LocationSearchIndex
    from apps.hotels.models import Property
    from apps.search.models import SearchIndex

    # ── 1. Sync City.hotel_count ──────────────────────────────────────────────
    hotel_count_updated = 0
    try:
        city_counts = (
            Property.objects
            .filter(**_OTA_FILTER)
            .values('city_id')
            .annotate(cnt=Count('id'))
        )
        count_map = {row['city_id']: row['cnt'] for row in city_counts}

        cities_to_update = []
        for city in City.objects.filter(is_active=True):
            new_count = count_map.get(city.pk, 0)
            if city.hotel_count != new_count:
                city.hotel_count = new_count
                cities_to_update.append(city)

        if cities_to_update:
            City.objects.bulk_update(cities_to_update, ['hotel_count'])
            hotel_count_updated = len(cities_to_update)
            logger.debug("rebuild_search_index: updated hotel_count for %d cities", hotel_count_updated)
    except Exception as exc:
        logger.warning("rebuild_search_index: City.hotel_count sync failed: %s", exc)

    # ── 2. Rebuild search_searchindex (SearchIndex) ───────────────────────────
    try:
        SearchIndex.objects.all().delete()
        logger.debug("rebuild_search_index: search_searchindex cleared")
    except Exception as exc:
        logger.error("rebuild_search_index: failed to clear search_searchindex: %s", exc)
        raise

    city_entries = []
    for city in City.objects.filter(is_active=True).select_related('state'):
        name = city.display_name or city.name
        city_entries.append(
            SearchIndex(
                name=name,
                type=SearchIndex.TYPE_CITY,
                property_count=city.hotel_count,
                slug=slugify(name)[:220],
            )
        )

    area_entries = []
    try:
        for locality in Locality.objects.filter(is_active=True).select_related('city'):
            name = locality.display_name or locality.name
            area_entries.append(
                SearchIndex(
                    name=name,
                    type=SearchIndex.TYPE_AREA,
                    property_count=locality.hotel_count,
                    slug=slugify(name)[:220],
                )
            )
    except Exception as exc:
        logger.warning("rebuild_search_index: locality SearchIndex skipped: %s", exc)

    property_entries = []
    for prop in Property.objects.filter(**_OTA_FILTER):
        slug = prop.slug or slugify(prop.name)
        property_entries.append(
            SearchIndex(
                name=prop.name,
                type=SearchIndex.TYPE_PROPERTY,
                property_count=None,
                slug=slug[:220],
            )
        )

    SearchIndex.objects.bulk_create(city_entries, ignore_conflicts=True)
    SearchIndex.objects.bulk_create(area_entries, ignore_conflicts=True)
    SearchIndex.objects.bulk_create(property_entries, ignore_conflicts=True)

    totals = {
        'cities': len(city_entries),
        'areas': len(area_entries),
        'properties': len(property_entries),
        'total': len(city_entries) + len(area_entries) + len(property_entries),
    }

    # ── 3. Rebuild core_locationsearchindex (LocationSearchIndex) ────────────
    location_entries = 0
    try:
        LocationSearchIndex.objects.all().delete()
        logger.debug("rebuild_search_index: core_locationsearchindex cleared")

        loc_bulk = []

        # Cities
        for city in City.objects.filter(is_active=True).select_related('state__country'):
            name = city.display_name or city.name
            state_name = city.state.name if city.state else ''
            loc_bulk.append(LocationSearchIndex(
                entity_type='city',
                entity_id=city.pk,
                display_name=name,
                search_text=f"{name} {state_name} {city.alternate_names}".strip().lower(),
                alternate_names=city.alternate_names,
                context_city=city,
                context_state=city.state if city.state else None,
                context_country=city.state.country if city.state else None,
                search_score=city.hotel_count * 10 + city.popularity_score,
                latitude=city.latitude,
                longitude=city.longitude,
                is_active=True,
            ))

        # Localities
        for loc in Locality.objects.filter(is_active=True).select_related('city__state__country'):
            name = loc.display_name or loc.name
            city_obj = loc.city
            loc_bulk.append(LocationSearchIndex(
                entity_type='locality',
                entity_id=loc.pk,
                display_name=name,
                search_text=f"{name} {city_obj.name} {loc.landmarks}".strip().lower(),
                alternate_names='',
                context_city=city_obj,
                context_state=city_obj.state if city_obj.state else None,
                context_country=city_obj.state.country if city_obj.state else None,
                search_score=loc.hotel_count * 5 + loc.popularity_score,
                latitude=loc.latitude,
                longitude=loc.longitude,
                is_active=True,
            ))

        # Properties
        for prop in Property.objects.filter(**_OTA_FILTER).select_related('city__state__country'):
            city_obj = prop.city
            loc_bulk.append(LocationSearchIndex(
                entity_type='hotel',
                entity_id=prop.pk,
                display_name=prop.name,
                search_text=f"{prop.name} {city_obj.name if city_obj else ''} {prop.area} {prop.landmark}".strip().lower(),
                alternate_names='',
                context_city=city_obj,
                context_state=city_obj.state if city_obj and city_obj.state else None,
                context_country=city_obj.state.country if city_obj and city_obj.state else None,
                search_score=int(prop.rating * 10) + prop.popularity_score,
                latitude=prop.latitude,
                longitude=prop.longitude,
                is_active=True,
            ))

        LocationSearchIndex.objects.bulk_create(loc_bulk, ignore_conflicts=True)
        location_entries = len(loc_bulk)
        logger.debug("rebuild_search_index: core_locationsearchindex populated: %d entries", location_entries)

    except Exception as exc:
        logger.warning("rebuild_search_index: LocationSearchIndex rebuild failed: %s", exc)

    totals['location_entries'] = location_entries
    totals['hotel_count_updated'] = hotel_count_updated

    logger.info(
        "rebuild_search_index: complete — cities=%d areas=%d properties=%d "
        "location_idx=%d hotel_count_synced=%d",
        totals['cities'], totals['areas'], totals['properties'],
        location_entries, hotel_count_updated,
    )
    return totals
