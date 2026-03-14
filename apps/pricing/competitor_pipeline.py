"""
Competitor Price Ingestion Pipeline.

Sources:
  1. Supplier API feeds (Hotelbeds, STAAH, SiteMinder)
  2. Scraped OTA rates (Booking.com, Agoda, MakeMyTrip)
  3. Manual rate uploads (admin dashboard)

Stores snapshots in CompetitorPrice and generates CompetitorRateAlerts.
"""
import logging
import re
import hashlib
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.pricing.competitor')


# ============================================================================
# OTA WEB SCRAPER (Production-grade with retry + rate limiting)
# ============================================================================

class OTARateScraper:
    """HTTP-based rate scraper for competitor OTAs.

    Scrapes publicly available rate data from Booking.com, MakeMyTrip,
    and Agoda search APIs. Uses structured API endpoints where available,
    falling back to HTML parsing.

    Features:
    - Per-OTA adapter methods with custom headers/parsing
    - Rate limiting (1 req/sec default, configurable)
    - Retry with exponential backoff
    - User-Agent rotation
    - Result normalization to CompetitorPrice schema
    """

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36',
    ]

    # OTA search API endpoints (public guest-facing APIs)
    OTA_CONFIGS = {
        'booking.com': {
            'base_url': 'https://www.booking.com/searchresults.json',
            'params_fn': '_booking_params',
            'parser_fn': '_parse_booking_response',
        },
        'makemytrip': {
            'base_url': 'https://www.makemytrip.com/hotels/search',
            'params_fn': '_mmt_params',
            'parser_fn': '_parse_mmt_response',
        },
        'agoda': {
            'base_url': 'https://www.agoda.com/api/cronos/search',
            'params_fn': '_agoda_params',
            'parser_fn': '_parse_agoda_response',
        },
    }

    def __init__(self, rate_limit_delay: float = 1.5, max_retries: int = 3):
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self._session = None

    def _get_session(self):
        """Lazy-init a requests session with retry adapter."""
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retries = Retry(
                total=self.max_retries,
                backoff_factor=1.0,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=['GET'],
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            # Rotate User-Agent
            import random
            session.headers.update({
                'User-Agent': random.choice(self.USER_AGENTS),
                'Accept': 'application/json, text/html',
                'Accept-Language': 'en-IN,en;q=0.9',
            })
            self._session = session
        return self._session

    def scrape_rates_for_property(self, property_name: str, city_name: str,
                                   checkin: date = None, checkout: date = None) -> list[dict]:
        """Scrape rates from all configured OTAs for a given property.

        Args:
            property_name: Hotel name for search matching
            city_name: City for geographic scoping
            checkin: Check-in date (default: tomorrow)
            checkout: Check-out date (default: day after tomorrow)

        Returns:
            List of rate dicts: [{competitor_name, price_per_night, is_available, source, notes}]
        """
        import time

        if checkin is None:
            checkin = date.today() + timedelta(days=1)
        if checkout is None:
            checkout = checkin + timedelta(days=1)

        all_rates = []

        for ota_name, config in self.OTA_CONFIGS.items():
            try:
                params_fn = getattr(self, config['params_fn'])
                parser_fn = getattr(self, config['parser_fn'])

                url = config['base_url']
                params = params_fn(property_name, city_name, checkin, checkout)

                session = self._get_session()
                response = session.get(url, params=params, timeout=15)

                if response.status_code == 200:
                    rates = parser_fn(response, property_name)
                    for rate in rates:
                        rate['competitor_name'] = ota_name
                        rate['source'] = 'scrape'
                    all_rates.extend(rates)
                    logger.info(
                        'Scraped %d rates from %s for "%s" in %s',
                        len(rates), ota_name, property_name, city_name,
                    )
                else:
                    logger.warning(
                        'OTA scrape HTTP %d from %s for "%s"',
                        response.status_code, ota_name, property_name,
                    )

                # Rate limiting between OTA requests
                time.sleep(self.rate_limit_delay)

            except Exception as exc:
                logger.warning('OTA scrape failed for %s: %s', ota_name, exc)

        return all_rates

    # ── Per-OTA parameter builders ────────────────────────────────

    @staticmethod
    def _booking_params(property_name, city_name, checkin, checkout):
        return {
            'ss': f'{property_name} {city_name}',
            'checkin_year': checkin.year,
            'checkin_month': checkin.month,
            'checkin_monthday': checkin.day,
            'checkout_year': checkout.year,
            'checkout_month': checkout.month,
            'checkout_monthday': checkout.day,
            'group_adults': 2,
            'no_rooms': 1,
            'selected_currency': 'INR',
        }

    @staticmethod
    def _mmt_params(property_name, city_name, checkin, checkout):
        return {
            'checkin': checkin.strftime('%m%d%Y'),
            'checkout': checkout.strftime('%m%d%Y'),
            'city': city_name,
            'searchText': property_name,
            'roomStayQualifier': '2e0e',
            'Currency': 'INR',
        }

    @staticmethod
    def _agoda_params(property_name, city_name, checkin, checkout):
        return {
            'searchText': f'{property_name}, {city_name}',
            'checkIn': checkin.isoformat(),
            'checkOut': checkout.isoformat(),
            'rooms': 1,
            'adults': 2,
            'children': 0,
            'currency': 'INR',
        }

    # ── Per-OTA response parsers ──────────────────────────────────

    @staticmethod
    def _parse_booking_response(response, property_name) -> list[dict]:
        """Parse Booking.com search response. Returns matched rates."""
        rates = []
        try:
            data = response.json()
            results = data.get('result', data.get('results', []))
            name_lower = property_name.lower()

            for hotel in results[:20]:
                hotel_name = str(hotel.get('hotel_name', hotel.get('name', ''))).lower()
                # Fuzzy match: property name must overlap significantly
                if name_lower[:8] in hotel_name or hotel_name[:8] in name_lower:
                    price = hotel.get('min_total_price') or hotel.get('price_breakdown', {}).get('gross_price')
                    if price:
                        rates.append({
                            'price_per_night': Decimal(str(price)),
                            'is_available': True,
                            'notes': f"Booking.com: {hotel.get('hotel_name', '')}",
                        })
        except Exception:
            # Fallback: try to extract prices from HTML
            try:
                text = response.text
                prices = re.findall(r'₹\s*([\d,]+)', text)
                if prices:
                    rates.append({
                        'price_per_night': Decimal(prices[0].replace(',', '')),
                        'is_available': True,
                        'notes': 'Booking.com HTML fallback',
                    })
            except Exception:
                pass
        return rates

    @staticmethod
    def _parse_mmt_response(response, property_name) -> list[dict]:
        """Parse MakeMyTrip response."""
        rates = []
        try:
            data = response.json()
            hotels = data.get('searchResult', {}).get('hotelResults', [])
            name_lower = property_name.lower()

            for hotel in hotels[:20]:
                hotel_name = str(hotel.get('name', '')).lower()
                if name_lower[:8] in hotel_name or hotel_name[:8] in name_lower:
                    price_data = hotel.get('price', {})
                    price = price_data.get('mrp') or price_data.get('displayedPrice')
                    if price:
                        rates.append({
                            'price_per_night': Decimal(str(price)),
                            'is_available': True,
                            'notes': f"MMT: {hotel.get('name', '')}",
                        })
        except Exception:
            pass
        return rates

    @staticmethod
    def _parse_agoda_response(response, property_name) -> list[dict]:
        """Parse Agoda search response."""
        rates = []
        try:
            data = response.json()
            results = data.get('data', {}).get('searchResults', data.get('results', []))
            name_lower = property_name.lower()

            for hotel in results[:20]:
                hotel_name = str(hotel.get('propertyName', hotel.get('name', ''))).lower()
                if name_lower[:8] in hotel_name or hotel_name[:8] in name_lower:
                    price = (
                        hotel.get('pricing', {}).get('price')
                        or hotel.get('dailyRate')
                        or hotel.get('price')
                    )
                    if price:
                        rates.append({
                            'price_per_night': Decimal(str(price)),
                            'is_available': True,
                            'notes': f"Agoda: {hotel.get('propertyName', '')}",
                        })
        except Exception:
            pass
        return rates


# Singleton scraper instance
_ota_scraper = OTARateScraper()


# ============================================================================
# INGESTION FUNCTIONS
# ============================================================================

def ingest_competitor_rate(
    property_id: int,
    competitor_name: str,
    source: str,
    price_per_night: Decimal,
    rate_date: date = None,
    is_available: bool = True,
    notes: str = '',
) -> 'CompetitorPrice':
    """
    Ingest a single competitor rate snapshot.

    Args:
        property_id: Property PK
        competitor_name: e.g. 'Booking.com', 'Agoda', 'MakeMyTrip'
        source: 'api', 'scrape', 'manual'
        price_per_night: Competitor price
        rate_date: Date the rate applies to (default: today)
        is_available: Whether competitor has availability
        notes: Optional notes

    Returns:
        CompetitorPrice instance
    """
    from apps.pricing.models import CompetitorPrice
    from apps.hotels.models import Property

    if rate_date is None:
        rate_date = timezone.now().date()

    prop = Property.objects.get(pk=property_id)
    price = Decimal(str(price_per_night))

    cp, created = CompetitorPrice.objects.update_or_create(
        property=prop,
        competitor_name=competitor_name,
        date=rate_date,
        defaults={
            'source': source,
            'price_per_night': price,
            'is_available': is_available,
            'notes': notes,
            'fetched_at': timezone.now(),
        },
    )

    if created:
        logger.info(
            "New competitor rate: %s @ ₹%s for property %d on %s",
            competitor_name, price, property_id, rate_date,
        )
    return cp


def bulk_ingest_competitor_rates(rates: list[dict]) -> dict:
    """
    Bulk ingest competitor rates.

    Args:
        rates: list of dicts with keys:
            property_id, competitor_name, source, price_per_night,
            date (optional), is_available (optional), notes (optional)

    Returns:
        dict with ingested/errors counts
    """
    stats = {'ingested': 0, 'errors': 0}

    for entry in rates:
        try:
            ingest_competitor_rate(
                property_id=entry['property_id'],
                competitor_name=entry['competitor_name'],
                source=entry.get('source', 'api'),
                price_per_night=Decimal(str(entry['price_per_night'])),
                rate_date=entry.get('date'),
                is_available=entry.get('is_available', True),
                notes=entry.get('notes', ''),
            )
            stats['ingested'] += 1
        except Exception as exc:
            logger.warning("Competitor rate ingestion error: %s", exc)
            stats['errors'] += 1

    return stats


def detect_rate_parity_violations(tolerance_pct: float = 10.0) -> list[dict]:
    """
    Compare our prices with competitor prices and flag violations.

    A violation occurs when our price differs from a competitor by more
    than `tolerance_pct` percent.

    Returns:
        list of violation dicts: {property_id, competitor, our_price, their_price, delta_pct}
    """
    from apps.pricing.models import CompetitorPrice
    from apps.hotels.models import Property
    from django.db.models import Min

    violations = []
    today = timezone.now().date()

    # Get latest competitor prices per property
    properties_with_comps = (
        CompetitorPrice.objects
        .filter(date__gte=today - timedelta(days=7), is_available=True)
        .values_list('property_id', flat=True)
        .distinct()
    )

    for prop_id in properties_with_comps:
        try:
            prop = Property.objects.prefetch_related('room_types').get(pk=prop_id)
            our_min = prop.room_types.aggregate(min_p=Min('base_price'))['min_p']
            if not our_min:
                continue

            latest_comps = (
                CompetitorPrice.objects
                .filter(property_id=prop_id, is_available=True, date__gte=today - timedelta(days=7))
                .order_by('competitor_name', '-date')
            )

            seen = set()
            for cp in latest_comps:
                if cp.competitor_name in seen:
                    continue
                seen.add(cp.competitor_name)

                delta_pct = float((our_min - cp.price_per_night) / cp.price_per_night * 100)
                if abs(delta_pct) > tolerance_pct:
                    violations.append({
                        'property_id': prop_id,
                        'property_name': prop.name,
                        'competitor': cp.competitor_name,
                        'our_price': float(our_min),
                        'their_price': float(cp.price_per_night),
                        'delta_pct': round(delta_pct, 2),
                        'direction': 'cheaper' if delta_pct < 0 else 'more_expensive',
                    })
        except Exception as exc:
            logger.warning("Rate parity check failed for property %d: %s", prop_id, exc)

    if violations:
        logger.warning("Found %d rate parity violations (>%s%% diff)", len(violations), tolerance_pct)

    return violations


# ============================================================================
# ALERT GENERATION
# ============================================================================

def generate_competitor_alerts():
    """
    Generate CompetitorRateAlerts based on current market data.
    Called by daily Celery task.
    """
    from apps.core.intelligence import CompetitorIntelligence
    from apps.hotels.models import Property

    properties = Property.objects.filter(
        status='approved', agreement_signed=True, is_active=True,
    )

    alerts_created = 0
    for prop in properties:
        try:
            alerts = CompetitorIntelligence.scan_and_alert(prop)
            alerts_created += len(alerts)
        except Exception as exc:
            logger.warning("Alert generation failed for property %d: %s", prop.id, exc)

    logger.info("Generated %d competitor alerts", alerts_created)
    return alerts_created


# ============================================================================
# CELERY TASKS
# ============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def task_competitor_price_scan(self):
    """
    Competitor price scan: scrape OTA rates + detect parity violations + generate alerts.
    Schedule: every 3 hours (upgraded from daily for price freshness).
    """
    try:
        from apps.hotels.models import Property

        # Phase 1: Scrape OTA rates for all active properties
        properties = Property.objects.filter(
            status='approved', agreement_signed=True, is_active=True,
        ).select_related('city')

        scrape_stats = {'scraped': 0, 'ingested': 0, 'errors': 0}
        tomorrow = date.today() + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)

        for prop in properties.iterator(chunk_size=20):
            try:
                city_name = prop.city.name if prop.city else ''
                rates = _ota_scraper.scrape_rates_for_property(
                    property_name=prop.name,
                    city_name=city_name,
                    checkin=tomorrow,
                    checkout=day_after,
                )
                scrape_stats['scraped'] += 1

                for rate in rates:
                    try:
                        ingest_competitor_rate(
                            property_id=prop.id,
                            competitor_name=rate['competitor_name'],
                            source=rate.get('source', 'scrape'),
                            price_per_night=rate['price_per_night'],
                            rate_date=tomorrow,
                            is_available=rate.get('is_available', True),
                            notes=rate.get('notes', ''),
                        )
                        scrape_stats['ingested'] += 1
                    except Exception as e:
                        scrape_stats['errors'] += 1
                        logger.debug('Rate ingest failed: %s', e)

            except Exception as e:
                scrape_stats['errors'] += 1
                logger.warning('Scrape failed for property %d: %s', prop.id, e)

        # Phase 2: Detect rate parity violations
        violations = detect_rate_parity_violations()

        # Phase 3: Generate competitor alerts
        alerts = generate_competitor_alerts()

        logger.info(
            'Competitor scan complete: scraped=%d ingested=%d violations=%d alerts=%d',
            scrape_stats['scraped'], scrape_stats['ingested'],
            len(violations), alerts,
        )

        return {
            'scrape_stats': scrape_stats,
            'violations': len(violations),
            'alerts_created': alerts,
        }
    except Exception as exc:
        logger.error("Competitor price scan failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def task_bulk_ingest_rates(self, rates: list):
    """Async bulk ingestion of competitor rates."""
    try:
        return bulk_ingest_competitor_rates(rates)
    except Exception as exc:
        logger.error("Bulk rate ingestion failed: %s", exc)
        raise self.retry(exc=exc)
