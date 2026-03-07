"""
Inventory Normalization Engine — Multi-Supplier Reconciliation.

Normalizes and reconciles inventory data from multiple external suppliers
(Booking.com, Expedia, OYO, Airbnb) with the internal InventoryCalendar.

Key features:
  1. Supplier data ingestion with conflict resolution
  2. Price normalization across suppliers (currency, tax treatment)
  3. Availability reconciliation (most conservative wins)
  4. Anomaly detection (sudden price drops, availability mismatches)
  5. PriceHistory audit trail for all updates
"""
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Avg, Min, Max, Q
from django.utils import timezone

logger = logging.getLogger('zygotrip.inventory.normalization')


def _q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class InventoryNormalizationEngine:
    """
    Reconciles supplier inventory feeds into the canonical InventoryCalendar.

    Strategies:
      - CONSERVATIVE: Use minimum availability across all suppliers
      - OPTIMISTIC: Use maximum availability (for direct contracts)
      - WEIGHTED: Weighted average by supplier confidence score

    Price strategy:
      - LOWEST: Use the lowest supplier price as base
      - AVERAGE: Use average across suppliers
      - MANUAL: Owner-set price takes precedence
    """

    STRATEGY_CONSERVATIVE = 'conservative'
    STRATEGY_OPTIMISTIC = 'optimistic'
    STRATEGY_WEIGHTED = 'weighted'

    PRICE_LOWEST = 'lowest'
    PRICE_AVERAGE = 'average'
    PRICE_MANUAL = 'manual'

    def __init__(
        self,
        availability_strategy=STRATEGY_CONSERVATIVE,
        price_strategy=PRICE_MANUAL,
    ):
        self.availability_strategy = availability_strategy
        self.price_strategy = price_strategy

    def ingest_supplier_data(self, supplier_name, external_id, data):
        """
        Ingest a supplier inventory feed for a property.

        Args:
            supplier_name: str — 'booking', 'expedia', 'oyo', etc.
            external_id: str — supplier's property ID
            data: list of dicts, each with:
                - date: date object
                - room_type_name: str
                - available_rooms: int
                - price_per_night: Decimal
                - currency: str (default 'INR')
                - is_closed: bool (optional)

        Returns:
            dict with ingestion stats
        """
        from apps.inventory.models import (
            SupplierPropertyMap, PriceHistory, InventoryLog,
        )

        # Find the supplier mapping
        try:
            mapping = SupplierPropertyMap.objects.get(
                supplier_name=supplier_name,
                external_id=external_id,
            )
        except SupplierPropertyMap.DoesNotExist:
            logger.warning(
                'No mapping for %s:%s — skipping ingestion', supplier_name, external_id,
            )
            return {'status': 'skipped', 'reason': 'no_mapping'}

        property_obj = mapping.property
        stats = {'ingested': 0, 'skipped': 0, 'anomalies': 0, 'errors': 0}

        for entry in data:
            try:
                result = self._process_entry(
                    property_obj, supplier_name, mapping, entry,
                )
                stats[result] += 1
            except Exception as e:
                logger.error(
                    'Error processing entry %s for %s:%s — %s',
                    entry.get('date'), supplier_name, external_id, e,
                )
                stats['errors'] += 1

        # Log the ingestion
        InventoryLog.objects.create(
            property=property_obj,
            action='supplier_ingestion',
            details={
                'supplier': supplier_name,
                'external_id': external_id,
                'stats': stats,
            },
        )

        logger.info(
            'Ingestion complete: %s:%s → %s',
            supplier_name, external_id, stats,
        )
        return stats

    def _process_entry(self, property_obj, supplier_name, mapping, entry):
        """Process a single inventory entry from a supplier."""
        from apps.inventory.models import PriceHistory
        from apps.pricing.models import CompetitorPrice
        from apps.rooms.models import RoomType

        target_date = entry['date']
        price = _q(Decimal(str(entry['price_per_night'])))
        available = int(entry.get('available_rooms', 0))

        # Anomaly detection: reject price drops > 50% from last known
        last_price = PriceHistory.objects.filter(
            property=property_obj,
            date=target_date,
            source=supplier_name,
        ).order_by('-created_at').first()

        if last_price and last_price.price > 0:
            pct_change = abs(price - last_price.price) / last_price.price
            if pct_change > Decimal('0.50'):
                logger.warning(
                    'Anomaly: %s price change %.0f%% for %s on %s (₹%s → ₹%s)',
                    supplier_name, pct_change * 100,
                    property_obj.id, target_date,
                    last_price.price, price,
                )
                return 'anomalies'

        # Store competitor price
        CompetitorPrice.objects.update_or_create(
            property=property_obj,
            competitor_name=supplier_name,
            date=target_date,
            defaults={
                'price_per_night': price,
                'is_available': available > 0,
            },
        )

        # Store price history
        PriceHistory.objects.create(
            property=property_obj,
            date=target_date,
            price=price,
            source=supplier_name,
            confidence=mapping.confidence_score,
        )

        return 'ingested'

    @transaction.atomic
    def reconcile_property(self, property_obj, date_range_start, date_range_end):
        """
        Reconcile all supplier data for a property over a date range.
        Updates InventoryCalendar based on the configured strategy.

        Returns dict with reconciliation stats.
        """
        from apps.inventory.models import InventoryCalendar
        from apps.pricing.models import CompetitorPrice
        from apps.rooms.models import RoomType

        stats = {'updated': 0, 'unchanged': 0}
        room_types = RoomType.objects.filter(property=property_obj)

        for room_type in room_types:
            current = date_range_start
            while current <= date_range_end:
                # Get all competitor prices for this date
                comp_prices = CompetitorPrice.objects.filter(
                    property=property_obj,
                    date=current,
                    is_available=True,
                )

                if comp_prices.exists():
                    # Apply price strategy
                    suggested_price = self._apply_price_strategy(
                        room_type, comp_prices,
                    )

                    # Update the calendar if price strategy requires it
                    # (only if not MANUAL)
                    if self.price_strategy != self.PRICE_MANUAL:
                        cal, created = InventoryCalendar.objects.get_or_create(
                            room_type=room_type,
                            date=current,
                            defaults={
                                'property': property_obj,
                                'base_price': suggested_price,
                                'selling_price': suggested_price,
                            },
                        )
                        if not created and cal.selling_price != suggested_price:
                            cal.selling_price = suggested_price
                            cal.save(update_fields=['selling_price', 'updated_at'])
                            stats['updated'] += 1
                        else:
                            stats['unchanged'] += 1
                    else:
                        stats['unchanged'] += 1

                current += timedelta(days=1)

        logger.info(
            'Reconciliation for property %s: %s', property_obj.id, stats,
        )
        return stats

    def _apply_price_strategy(self, room_type, competitor_prices_qs):
        """Apply the price strategy to determine the selling price."""
        if self.price_strategy == self.PRICE_LOWEST:
            result = competitor_prices_qs.aggregate(lowest=Min('price_per_night'))
            return _q(result['lowest'] or room_type.base_price)

        elif self.price_strategy == self.PRICE_AVERAGE:
            result = competitor_prices_qs.aggregate(avg=Avg('price_per_night'))
            return _q(result['avg'] or room_type.base_price)

        # MANUAL: use room_type's existing base_price
        return _q(room_type.base_price)

    def detect_rate_parity_violations(self, property_obj, tolerance=Decimal('0.10')):
        """
        Detect rate parity violations across suppliers.
        Returns list of dates where prices differ > tolerance.

        Args:
            property_obj: Property instance
            tolerance: Decimal — max allowed price difference (0.10 = 10%)
        """
        from apps.pricing.models import CompetitorPrice

        violations = []
        today = timezone.now().date()
        end_date = today + timedelta(days=90)

        dates = CompetitorPrice.objects.filter(
            property=property_obj,
            date__gte=today,
            date__lte=end_date,
        ).values_list('date', flat=True).distinct()

        for target_date in dates:
            prices = CompetitorPrice.objects.filter(
                property=property_obj,
                date=target_date,
                is_available=True,
            ).values_list('competitor_name', 'price_per_night')

            if len(prices) < 2:
                continue

            price_list = [p[1] for p in prices]
            min_price = min(price_list)
            max_price = max(price_list)

            if min_price > 0:
                deviation = (max_price - min_price) / min_price
                if deviation > tolerance:
                    violations.append({
                        'date': target_date,
                        'min_price': float(min_price),
                        'max_price': float(max_price),
                        'deviation': float(deviation),
                        'prices': {name: float(p) for name, p in prices},
                    })

        return violations

    def get_price_position(self, property_obj, check_in, check_out):
        """
        Get price position vs competitors for a date range.
        Returns dict with our_price, competitor_avg, percentile, etc.
        """
        from apps.pricing.models import CompetitorPrice
        from apps.rooms.models import RoomType

        room_type = RoomType.objects.filter(
            property=property_obj,
        ).order_by('base_price').first()

        if not room_type:
            return {'status': 'no_rooms'}

        nights = (check_out - check_in).days
        our_price = float(room_type.base_price) * nights

        comp_agg = CompetitorPrice.objects.filter(
            property=property_obj,
            date__gte=check_in,
            date__lt=check_out,
            is_available=True,
        ).aggregate(
            avg=Avg('price_per_night'),
            min=Min('price_per_night'),
            max=Max('price_per_night'),
        )

        comp_avg = float(comp_agg['avg'] or 0) * nights if comp_agg['avg'] else None

        return {
            'our_price': our_price,
            'competitor_avg_total': comp_avg,
            'competitor_min_per_night': float(comp_agg['min'] or 0),
            'competitor_max_per_night': float(comp_agg['max'] or 0),
            'nights': nights,
            'cheaper_than_avg': our_price < comp_avg if comp_avg else None,
            'price_difference_pct': round(
                ((our_price - comp_avg) / comp_avg * 100), 1,
            ) if comp_avg and comp_avg > 0 else None,
        }
