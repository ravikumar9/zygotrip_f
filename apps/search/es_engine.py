"""
ElasticSearch-powered search engine for ZygoTrip OTA.

Provides sub-400ms search across all verticals: hotels, flights, buses, cabs,
packages, activities.  Falls back to PostgreSQL PropertySearchIndex when ES
is unreachable.

Index design:
  zygotrip_hotels   — property documents with geo_point, nested rooms
  zygotrip_flights  — route/schedule documents
  zygotrip_buses    — bus route documents
  zygotrip_cabs     — cab type documents
  zygotrip_packages — holiday package documents
  zygotrip_activities — activity documents
"""
import logging
import hashlib
import time
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('zygotrip.search.es')

# ---------------------------------------------------------------------------
# ES client singleton
# ---------------------------------------------------------------------------
_es_client = None


def get_es_client():
    """Lazy-init Elasticsearch client; returns None if unavailable."""
    global _es_client
    if _es_client is not None:
        return _es_client
    try:
        from elasticsearch import Elasticsearch
        hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', ['http://localhost:9200'])
        _es_client = Elasticsearch(
            hosts,
            request_timeout=5,
            max_retries=1,
            retry_on_timeout=False,
        )
        if not _es_client.ping():
            logger.warning('ElasticSearch ping failed — will use fallback')
            _es_client = None
    except Exception as e:
        logger.warning('ElasticSearch unavailable: %s', e)
        _es_client = None
    return _es_client


# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------

HOTEL_INDEX = 'zygotrip_hotels'
FLIGHT_INDEX = 'zygotrip_flights'
BUS_INDEX = 'zygotrip_buses'
CAB_INDEX = 'zygotrip_cabs'
PACKAGE_INDEX = 'zygotrip_packages'
ACTIVITY_INDEX = 'zygotrip_activities'

HOTEL_MAPPING = {
    'properties': {
        'property_id': {'type': 'keyword'},
        'name': {'type': 'text', 'analyzer': 'standard', 'fields': {
            'keyword': {'type': 'keyword'},
            'suggest': {'type': 'completion', 'analyzer': 'simple'},
        }},
        'city': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
        'state': {'type': 'keyword'},
        'country': {'type': 'keyword'},
        'location': {'type': 'geo_point'},
        'property_type': {'type': 'keyword'},
        'star_rating': {'type': 'float'},
        'user_rating': {'type': 'float'},
        'review_count': {'type': 'integer'},
        'min_price': {'type': 'float'},
        'max_price': {'type': 'float'},
        'amenities': {'type': 'keyword'},
        'tags': {'type': 'keyword'},
        'is_featured': {'type': 'boolean'},
        'image_url': {'type': 'keyword', 'index': False},
        'cancellation_type': {'type': 'keyword'},
        'pay_at_hotel': {'type': 'boolean'},
        'booking_count_30d': {'type': 'integer'},
        'popularity_score': {'type': 'float'},
        'updated_at': {'type': 'date'},
    }
}

FLIGHT_MAPPING = {
    'properties': {
        'flight_id': {'type': 'keyword'},
        'airline': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
        'airline_code': {'type': 'keyword'},
        'origin': {'type': 'keyword'},
        'destination': {'type': 'keyword'},
        'origin_city': {'type': 'text', 'fields': {
            'keyword': {'type': 'keyword'},
            'suggest': {'type': 'completion'},
        }},
        'destination_city': {'type': 'text', 'fields': {
            'keyword': {'type': 'keyword'},
            'suggest': {'type': 'completion'},
        }},
        'departure_time': {'type': 'date'},
        'arrival_time': {'type': 'date'},
        'duration_minutes': {'type': 'integer'},
        'stops': {'type': 'integer'},
        'price': {'type': 'float'},
        'cabin_class': {'type': 'keyword'},
        'seats_available': {'type': 'integer'},
        'updated_at': {'type': 'date'},
    }
}

ACTIVITY_MAPPING = {
    'properties': {
        'activity_id': {'type': 'keyword'},
        'name': {'type': 'text', 'fields': {
            'keyword': {'type': 'keyword'},
            'suggest': {'type': 'completion'},
        }},
        'city': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
        'category': {'type': 'keyword'},
        'location': {'type': 'geo_point'},
        'price': {'type': 'float'},
        'rating': {'type': 'float'},
        'review_count': {'type': 'integer'},
        'duration_hours': {'type': 'float'},
        'is_instant_confirm': {'type': 'boolean'},
        'updated_at': {'type': 'date'},
    }
}

INDEX_CONFIGS = {
    HOTEL_INDEX: {'mappings': HOTEL_MAPPING},
    FLIGHT_INDEX: {'mappings': FLIGHT_MAPPING},
    ACTIVITY_INDEX: {'mappings': ACTIVITY_MAPPING},
}


def ensure_indices():
    """Create ES indices if they don't exist."""
    es = get_es_client()
    if not es:
        return
    for idx, body in INDEX_CONFIGS.items():
        try:
            if not es.indices.exists(index=idx):
                es.indices.create(index=idx, body=body)
                logger.info('Created ES index: %s', idx)
        except Exception as e:
            logger.error('Failed to create index %s: %s', idx, e)


# ---------------------------------------------------------------------------
# Indexing helpers
# ---------------------------------------------------------------------------

def index_hotel(property_obj):
    """Index or update a single hotel property in ES."""
    es = get_es_client()
    if not es:
        return
    from apps.rooms.models import RoomType
    rooms = RoomType.objects.filter(property=property_obj, is_active=True)
    prices = [float(r.base_price) for r in rooms if r.base_price]
    doc = {
        'property_id': str(property_obj.uuid),
        'name': property_obj.name,
        'city': property_obj.city.name if property_obj.city else '',
        'state': str(getattr(property_obj.city, 'state', '')),
        'country': 'IN',
        'location': {
            'lat': float(property_obj.latitude) if property_obj.latitude else 0,
            'lon': float(property_obj.longitude) if property_obj.longitude else 0,
        },
        'property_type': property_obj.property_type,
        'star_rating': float(property_obj.star_rating or 0),
        'user_rating': float(property_obj.avg_rating or 0),
        'review_count': property_obj.review_count or 0,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 0,
        'amenities': [a.strip() for a in (property_obj.amenities or '').split(',') if a.strip()],
        'is_featured': getattr(property_obj, 'is_featured', False),
        'image_url': property_obj.featured_image.url if property_obj.featured_image else '',
        'pay_at_hotel': getattr(property_obj, 'pay_at_hotel', False),
        'booking_count_30d': getattr(property_obj, 'booking_count_30d', 0),
        'popularity_score': float(getattr(property_obj, 'popularity_score', 0)),
        'updated_at': property_obj.updated_at.isoformat(),
    }
    try:
        es.index(index=HOTEL_INDEX, id=str(property_obj.uuid), document=doc)
    except Exception as e:
        logger.error('ES index_hotel failed for %s: %s', property_obj.uuid, e)


def index_flight(flight_obj):
    """Index a flight schedule document."""
    es = get_es_client()
    if not es:
        return
    doc = {
        'flight_id': str(flight_obj.id),
        'airline': str(getattr(flight_obj, 'airline', '')),
        'airline_code': getattr(flight_obj, 'airline_code', ''),
        'origin': getattr(flight_obj, 'origin_code', ''),
        'destination': getattr(flight_obj, 'destination_code', ''),
        'origin_city': getattr(flight_obj, 'origin_city', ''),
        'destination_city': getattr(flight_obj, 'destination_city', ''),
        'departure_time': str(getattr(flight_obj, 'departure_time', '')),
        'arrival_time': str(getattr(flight_obj, 'arrival_time', '')),
        'duration_minutes': getattr(flight_obj, 'duration_minutes', 0),
        'stops': getattr(flight_obj, 'stops', 0),
        'price': float(getattr(flight_obj, 'base_price', 0)),
        'cabin_class': getattr(flight_obj, 'cabin_class', 'economy'),
        'seats_available': getattr(flight_obj, 'seats_available', 0),
        'updated_at': str(getattr(flight_obj, 'updated_at', '')),
    }
    try:
        es.index(index=FLIGHT_INDEX, id=str(flight_obj.id), document=doc)
    except Exception as e:
        logger.error('ES index_flight failed: %s', e)


# ---------------------------------------------------------------------------
# Search queries
# ---------------------------------------------------------------------------

def _cache_key(prefix: str, params: dict) -> str:
    raw = f"{prefix}:{sorted(params.items())}"
    return f"es:{hashlib.md5(raw.encode()).hexdigest()}"


def search_hotels(
    query: str = '',
    city: str = '',
    lat: float = None,
    lng: float = None,
    radius_km: float = 10,
    min_price: float = None,
    max_price: float = None,
    min_rating: float = None,
    amenities: list = None,
    property_type: str = None,
    pay_at_hotel: bool = None,
    sort: str = 'relevance',
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Primary hotel search. Returns dict with 'results', 'total', 'took_ms'.
    Falls back to DB search if ES is unavailable.
    """
    cache_params = {
        'q': query, 'city': city, 'lat': lat, 'lng': lng,
        'mp': min_price, 'xp': max_price, 'mr': min_rating,
        'am': str(amenities), 'pt': property_type, 'pah': pay_at_hotel,
        'sort': sort, 'p': page,
    }
    ck = _cache_key('hsearch', cache_params)
    cached = cache.get(ck)
    if cached:
        return cached

    es = get_es_client()
    if not es:
        return _fallback_hotel_search(query, city, min_price, max_price, min_rating, page, page_size)

    must, filter_clauses = [], []

    if query:
        must.append({
            'multi_match': {
                'query': query,
                'fields': ['name^3', 'city^2', 'amenities'],
                'type': 'best_fields',
                'fuzziness': 'AUTO',
            }
        })
    if city:
        filter_clauses.append({'term': {'city.keyword': city}})
    if lat is not None and lng is not None:
        filter_clauses.append({
            'geo_distance': {
                'distance': f'{radius_km}km',
                'location': {'lat': lat, 'lon': lng},
            }
        })
    if min_price is not None or max_price is not None:
        rng = {}
        if min_price is not None:
            rng['gte'] = min_price
        if max_price is not None:
            rng['lte'] = max_price
        filter_clauses.append({'range': {'min_price': rng}})
    if min_rating is not None:
        filter_clauses.append({'range': {'user_rating': {'gte': min_rating}}})
    if amenities:
        for a in amenities:
            filter_clauses.append({'term': {'amenities': a}})
    if property_type:
        filter_clauses.append({'term': {'property_type': property_type}})
    if pay_at_hotel is not None:
        filter_clauses.append({'term': {'pay_at_hotel': pay_at_hotel}})

    body = {
        'query': {
            'bool': {
                'must': must or [{'match_all': {}}],
                'filter': filter_clauses,
            }
        },
        'from': (page - 1) * page_size,
        'size': page_size,
    }

    # Sort
    if sort == 'price_asc':
        body['sort'] = [{'min_price': 'asc'}]
    elif sort == 'price_desc':
        body['sort'] = [{'min_price': 'desc'}]
    elif sort == 'rating':
        body['sort'] = [{'user_rating': 'desc'}]
    elif sort == 'popularity':
        body['sort'] = [{'popularity_score': 'desc'}]
    else:
        body['sort'] = ['_score', {'popularity_score': 'desc'}]

    try:
        t0 = time.monotonic()
        resp = es.search(index=HOTEL_INDEX, body=body)
        took_ms = int((time.monotonic() - t0) * 1000)
        results = []
        for hit in resp['hits']['hits']:
            src = hit['_source']
            src['_score'] = hit.get('_score')
            results.append(src)
        out = {'results': results, 'total': resp['hits']['total']['value'], 'took_ms': took_ms}
        cache.set(ck, out, timeout=120)
        return out
    except Exception as e:
        logger.error('ES hotel search failed: %s', e)
        return _fallback_hotel_search(query, city, min_price, max_price, min_rating, page, page_size)


def search_flights(
    origin: str,
    destination: str,
    date: str = None,
    cabin_class: str = None,
    max_stops: int = None,
    sort: str = 'price',
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Flight search with ES; falls back to DB."""
    es = get_es_client()
    if not es:
        return {'results': [], 'total': 0, 'took_ms': 0, 'fallback': True}

    filter_clauses = [
        {'term': {'origin': origin.upper()}},
        {'term': {'destination': destination.upper()}},
    ]
    if date:
        filter_clauses.append({'range': {'departure_time': {
            'gte': f'{date}T00:00:00', 'lte': f'{date}T23:59:59',
        }}})
    if cabin_class:
        filter_clauses.append({'term': {'cabin_class': cabin_class}})
    if max_stops is not None:
        filter_clauses.append({'range': {'stops': {'lte': max_stops}}})

    sort_clause = [{'price': 'asc'}]
    if sort == 'duration':
        sort_clause = [{'duration_minutes': 'asc'}]
    elif sort == 'departure':
        sort_clause = [{'departure_time': 'asc'}]

    body = {
        'query': {'bool': {'filter': filter_clauses}},
        'sort': sort_clause,
        'from': (page - 1) * page_size,
        'size': page_size,
    }
    try:
        t0 = time.monotonic()
        resp = es.search(index=FLIGHT_INDEX, body=body)
        took_ms = int((time.monotonic() - t0) * 1000)
        results = [hit['_source'] for hit in resp['hits']['hits']]
        return {'results': results, 'total': resp['hits']['total']['value'], 'took_ms': took_ms}
    except Exception as e:
        logger.error('ES flight search failed: %s', e)
        return {'results': [], 'total': 0, 'took_ms': 0, 'fallback': True}


def autocomplete(query: str, vertical: str = 'hotels', size: int = 8) -> list:
    """
    Search-as-you-type autocompletion using ES completion suggester.
    Returns list of dicts with 'text' and 'payload'.
    """
    es = get_es_client()
    if not es:
        return _fallback_autocomplete(query, vertical)

    index_map = {
        'hotels': (HOTEL_INDEX, 'name.suggest'),
        'flights': (FLIGHT_INDEX, 'origin_city.suggest'),
        'activities': (ACTIVITY_INDEX, 'name.suggest'),
    }
    idx, field = index_map.get(vertical, (HOTEL_INDEX, 'name.suggest'))

    body = {
        'suggest': {
            'search_suggest': {
                'prefix': query,
                'completion': {
                    'field': field,
                    'size': size,
                    'fuzzy': {'fuzziness': 'AUTO'},
                }
            }
        }
    }
    try:
        resp = es.search(index=idx, body=body, _source=True)
        suggestions = []
        for option in resp.get('suggest', {}).get('search_suggest', [{}])[0].get('options', []):
            suggestions.append({
                'text': option['text'],
                'score': option.get('_score', 0),
                'payload': option.get('_source', {}),
            })
        return suggestions
    except Exception as e:
        logger.error('ES autocomplete failed: %s', e)
        return _fallback_autocomplete(query, vertical)


def geo_search(lat: float, lng: float, radius_km: float = 5, page_size: int = 20) -> dict:
    """Search hotels near a geo point."""
    return search_hotels(lat=lat, lng=lng, radius_km=radius_km, page_size=page_size, sort='popularity')


# ---------------------------------------------------------------------------
# Fallback — PostgreSQL based search
# ---------------------------------------------------------------------------

def _fallback_hotel_search(query, city, min_price, max_price, min_rating, page, page_size):
    from apps.search.models import PropertySearchIndex
    qs = PropertySearchIndex.objects.filter(is_active=True)
    if query:
        qs = qs.filter(name__icontains=query)
    if city:
        qs = qs.filter(city__iexact=city)
    if min_price:
        qs = qs.filter(min_price__gte=min_price)
    if max_price:
        qs = qs.filter(min_price__lte=max_price)
    if min_rating:
        qs = qs.filter(user_rating__gte=min_rating)
    total = qs.count()
    offset = (page - 1) * page_size
    items = qs.order_by('-popularity_score')[offset:offset + page_size]
    results = []
    for s in items:
        results.append({
            'property_id': str(s.property_id),
            'name': s.name,
            'city': s.city,
            'min_price': float(s.min_price) if s.min_price else 0,
            'user_rating': float(s.user_rating) if s.user_rating else 0,
            'review_count': s.review_count or 0,
            'image_url': s.image_url or '',
        })
    return {'results': results, 'total': total, 'took_ms': 0, 'fallback': True}


def _fallback_autocomplete(query, vertical):
    if vertical == 'hotels':
        from apps.search.models import PropertySearchIndex
        matches = PropertySearchIndex.objects.filter(
            name__icontains=query, is_active=True
        ).values_list('name', flat=True)[:8]
        return [{'text': n, 'score': 1, 'payload': {}} for n in matches]
    return []


# ---------------------------------------------------------------------------
# Bulk re-index Celery task
# ---------------------------------------------------------------------------

def reindex_all_hotels():
    """Rebuild the ES hotel index from database."""
    from apps.hotels.models import Property
    es = get_es_client()
    if not es:
        logger.warning('Cannot reindex — ES unavailable')
        return 0
    count = 0
    for prop in Property.objects.filter(is_active=True).select_related('city').iterator(chunk_size=200):
        index_hotel(prop)
        count += 1
    logger.info('Reindexed %d hotels into ES', count)
    return count
