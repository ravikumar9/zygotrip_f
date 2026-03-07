"""
Inventory Aggregation Service — Step 7.

Merges inventory from multiple suppliers into canonical InventoryCalendar records.

Pipeline:
  1. Supplier adapters fetch raw inventory → SupplierPropertyMap links to internal Property
  2. Normalization: standardize room type names, capacities, and rates across suppliers
  3. Aggregation: merge duplicate room types (same property, same capacity) → pick best rate
  4. Storage: update_or_create into InventoryCalendar (source of truth)

Prevents duplicate listings by deduplicating on (property, room_name_normalized, capacity).
"""

import logging
from datetime import timedelta
from decimal import Decimal
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.inventory.models import (
    SupplierPropertyMap,
    InventoryCalendar,
    InventoryLog,
)

logger = logging.getLogger('zygotrip.inventory.aggregation')


# ──────────────────────────────────────────────────────────────────────────────
# ROOM TYPE NORMALIZATION
# ──────────────────────────────────────────────────────────────────────────────

# Standard name mappings for cross-supplier deduplication
_ROOM_NAME_MAP = {
    'standard': 'Standard',
    'std': 'Standard',
    'standard room': 'Standard',
    'deluxe': 'Deluxe',
    'dlx': 'Deluxe',
    'deluxe room': 'Deluxe',
    'superior': 'Superior',
    'superior room': 'Superior',
    'super deluxe': 'Super Deluxe',
    'premium': 'Premium',
    'premium room': 'Premium',
    'suite': 'Suite',
    'executive suite': 'Executive Suite',
    'family': 'Family',
    'family room': 'Family',
    'twin': 'Twin',
    'twin room': 'Twin',
    'single': 'Single',
    'single room': 'Single',
    'double': 'Double',
    'double room': 'Double',
}


def normalize_room_name(raw_name: str) -> str:
    """Normalize a supplier room name to a canonical name for dedup."""
    if not raw_name:
        return 'Standard'
    cleaned = raw_name.strip().lower()
    return _ROOM_NAME_MAP.get(cleaned, raw_name.strip().title())


# ──────────────────────────────────────────────────────────────────────────────
# INVENTORY AGGREGATION SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class InventoryAggregationService:
    """
    Merges inventory data from multiple supplier feeds into canonical
    InventoryCalendar records, preventing duplicate listings.
    """

    @staticmethod
    def aggregate_supplier_data(property_obj, supplier_feeds: list[dict]) -> dict:
        """
        Aggregate raw inventory feeds from multiple suppliers.

        Args:
            property_obj: Property model instance
            supplier_feeds: List of dicts, each with structure:
                {
                    'supplier_name': 'hotelbeds',
                    'rooms': [
                        {
                            'room_name': 'Deluxe Room',
                            'capacity': 2,
                            'dates': {
                                '2026-03-10': {'available': 5, 'rate': 3500.00},
                                '2026-03-11': {'available': 3, 'rate': 3800.00},
                            }
                        }
                    ]
                }

        Returns:
            Dict with aggregation stats: {merged, updated, skipped, errors}
        """
        stats = {'merged': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        if not supplier_feeds:
            return stats

        # Step 1: Normalize and group by (normalized_name, capacity)
        grouped = defaultdict(list)
        for feed in supplier_feeds:
            supplier = feed.get('supplier_name', 'unknown')
            for room_data in feed.get('rooms', []):
                norm_name = normalize_room_name(room_data.get('room_name', ''))
                capacity = room_data.get('capacity', 2)
                key = (norm_name, capacity)
                grouped[key].append({
                    'supplier': supplier,
                    'dates': room_data.get('dates', {}),
                    'raw_name': room_data.get('room_name', ''),
                })

        # Step 2: For each normalized room type, merge dates from all suppliers
        from apps.rooms.models import RoomType
        for (norm_name, capacity), supplier_rooms in grouped.items():
            try:
                # Find or skip the matching internal room type
                room_type = RoomType.objects.filter(
                    property=property_obj,
                    capacity=capacity,
                ).first()

                if not room_type:
                    # Try looser match by name similarity
                    room_type = RoomType.objects.filter(
                        property=property_obj,
                        name__icontains=norm_name.split()[0] if norm_name else '',
                    ).first()

                if not room_type:
                    logger.debug(
                        "No matching room type for %s (cap=%s) at %s, skipping",
                        norm_name, capacity, property_obj.name,
                    )
                    stats['skipped'] += 1
                    continue

                # Step 3: Merge dates — pick highest availability and best (lowest) rate
                merged_dates = InventoryAggregationService._merge_date_data(supplier_rooms)

                # Step 4: Write to InventoryCalendar
                for date_str, data in merged_dates.items():
                    try:
                        from datetime import datetime
                        inv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        InventoryAggregationService._upsert_calendar(
                            room_type=room_type,
                            inv_date=inv_date,
                            available=data['available'],
                            rate=data['rate'],
                            supplier=data['best_supplier'],
                        )
                        stats['updated'] += 1
                    except Exception as e:
                        logger.warning("Failed to upsert calendar for %s %s: %s", norm_name, date_str, e)
                        stats['errors'] += 1

                stats['merged'] += 1

            except Exception as e:
                logger.error("Aggregation error for %s at %s: %s", norm_name, property_obj.name, e)
                stats['errors'] += 1

        logger.info(
            "Inventory aggregation for %s: merged=%d updated=%d skipped=%d errors=%d",
            property_obj.name, stats['merged'], stats['updated'], stats['skipped'], stats['errors'],
        )
        return stats

    @staticmethod
    def _merge_date_data(supplier_rooms: list[dict]) -> dict:
        """
        Merge date-level data from multiple suppliers.

        Strategy:
        - availability = max across suppliers (most optimistic)
        - rate = min across suppliers (best price for guest)
        - best_supplier = supplier providing the best rate
        """
        merged = {}
        for sr in supplier_rooms:
            supplier = sr['supplier']
            for date_str, data in sr.get('dates', {}).items():
                avail = data.get('available', 0)
                rate = Decimal(str(data.get('rate', 0)))

                if date_str not in merged:
                    merged[date_str] = {
                        'available': avail,
                        'rate': rate,
                        'best_supplier': supplier,
                    }
                else:
                    existing = merged[date_str]
                    # Take max availability
                    if avail > existing['available']:
                        existing['available'] = avail
                    # Take lowest rate (best price)
                    if rate > 0 and (existing['rate'] <= 0 or rate < existing['rate']):
                        existing['rate'] = rate
                        existing['best_supplier'] = supplier
        return merged

    @staticmethod
    @transaction.atomic
    def _upsert_calendar(room_type, inv_date, available, rate, supplier):
        """
        Create or update InventoryCalendar row with merged data.
        Uses select_for_update for concurrency safety.
        """
        cal, created = InventoryCalendar.objects.select_for_update().get_or_create(
            room_type=room_type,
            date=inv_date,
            defaults={
                'total_rooms': available,
                'available_rooms': available,
                'booked_rooms': 0,
                'blocked_rooms': 0,
                'held_rooms': 0,
                'rate_override': rate if rate > 0 else None,
            },
        )

        if not created:
            old_available = cal.available_rooms
            # Update total and recompute availability
            cal.total_rooms = max(cal.total_rooms, available)
            if rate and rate > 0:
                cal.rate_override = rate
            cal.recompute_available()
            cal.save(update_fields=['total_rooms', 'available_rooms', 'rate_override', 'updated_at'])

            # Log the sync event
            InventoryLog.objects.create(
                room_type=room_type,
                date=inv_date,
                event=InventoryLog.EVENT_SYNC,
                quantity=cal.available_rooms - old_available,
                available_before=old_available,
                available_after=cal.available_rooms,
                reference_id=f'supplier_sync:{supplier}',
                metadata={'supplier': supplier, 'rate': str(rate)},
            )

    @staticmethod
    def deduplicate_supplier_listings(property_obj) -> int:
        """
        Detect and mark duplicate room types from multiple suppliers
        that map to the same internal room type.

        Returns count of duplicate mappings found.
        """
        duplicates = 0
        mappings = SupplierPropertyMap.objects.filter(
            property=property_obj,
            verified=True,
        ).order_by('supplier_name')

        # Group external IDs by supplier
        supplier_ids = defaultdict(list)
        for m in mappings:
            supplier_ids[m.supplier_name].append(m.external_id)

        # Check for cross-supplier duplicate external IDs (shouldn't happen but guard)
        seen_externals = set()
        for supplier, ext_ids in supplier_ids.items():
            for ext_id in ext_ids:
                if ext_id in seen_externals:
                    duplicates += 1
                    logger.warning(
                        "Duplicate external_id %s found across suppliers for %s",
                        ext_id, property_obj.name,
                    )
                seen_externals.add(ext_id)

        return duplicates
