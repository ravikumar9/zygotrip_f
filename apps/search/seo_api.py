"""
SEO Page Data API — Backend-driven generation of city & segment landing pages.

Endpoints:
  GET  /api/v1/seo/city/<slug>/               → City landing page data
  GET  /api/v1/seo/city/<slug>/<segment>/      → Segment landing page data
  GET  /api/v1/seo/cities/                     → All active city slugs (sitemap)
  GET  /api/v1/seo/city/<slug>/meta/           → City meta tags + structured data

Replaces hardcoded frontend data with live DB-driven aggregates from
PropertySearchIndex, enabling automatic city/segment page creation as
inventory grows.
"""
import logging
from decimal import Decimal
from django.db.models import (
    Avg, Count, Min, Max, Q, F, Sum, Case, When, IntegerField, Value,
)
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from .models import PropertySearchIndex

logger = logging.getLogger('zygotrip.seo')

# ── Segment Definitions ──────────────────────────────────────────────────────

SEGMENT_CONFIG = {
    'budget': {
        'label': 'Budget Hotels',
        'description': 'Affordable stays under ₹3,000 per night',
        'filter': Q(price_min__lte=3000),
        'sort': 'price_min',
    },
    'luxury': {
        'label': 'Luxury Hotels',
        'description': 'Premium 5-star hotels starting from ₹8,000',
        'filter': Q(price_min__gte=8000) | Q(star_category__gte=5),
        'sort': '-rating',
    },
    'family': {
        'label': 'Family Hotels',
        'description': 'Family-friendly stays with spacious rooms and amenities',
        'filter': Q(tags__contains=['Family Friendly']) | Q(amenities__contains=['Kids Area']),
        'sort': '-review_count',
    },
    'couple': {
        'label': 'Couple Hotels',
        'description': 'Romantic stays for couples',
        'filter': Q(tags__contains=['Couple Friendly']),
        'sort': '-rating',
    },
    'free-cancellation': {
        'label': 'Free Cancellation Hotels',
        'description': 'Book freely with no cancellation charges',
        'filter': Q(has_free_cancellation=True),
        'sort': '-popularity_score',
    },
    'near-railway-station': {
        'label': 'Hotels Near Railway Station',
        'description': 'Convenient stays close to the railway station',
        'filter': Q(tags__contains=['Near Railway Station']) | Q(locality_name__icontains='station'),
        'sort': '-popularity_score',
    },
    'near-airport': {
        'label': 'Hotels Near Airport',
        'description': 'Quick access hotels near the airport',
        'filter': Q(tags__contains=['Near Airport']) | Q(locality_name__icontains='airport'),
        'sort': '-popularity_score',
    },
}

# Minimum properties needed to generate a segment page
MIN_PROPERTIES_FOR_SEGMENT = 3


def _city_base_qs(city_slug):
    """Return base queryset for a city by slug (case-insensitive)."""
    return PropertySearchIndex.objects.filter(
        city_name__iexact=city_slug.replace('-', ' '),
        has_availability=True,
    )


def _aggregate_city_stats(qs):
    """Compute aggregate stats for a property queryset."""
    stats = qs.aggregate(
        total=Count('id'),
        avg_price=Avg('price_min'),
        min_price=Min('price_min'),
        max_price=Max('price_max'),
        avg_rating=Avg('rating'),
        total_reviews=Sum('review_count'),
        hotels_3star=Count('id', filter=Q(star_category=3)),
        hotels_4star=Count('id', filter=Q(star_category=4)),
        hotels_5star=Count('id', filter=Q(star_category=5)),
        free_cancellation_count=Count('id', filter=Q(has_free_cancellation=True)),
        pay_at_hotel_count=Count('id', filter=Q(pay_at_hotel=True)),
        trending_count=Count('id', filter=Q(is_trending=True)),
    )
    return {
        'total_properties': stats['total'] or 0,
        'avg_price': round(float(stats['avg_price'] or 0)),
        'min_price': round(float(stats['min_price'] or 0)),
        'max_price': round(float(stats['max_price'] or 0)),
        'avg_rating': round(float(stats['avg_rating'] or 0), 1),
        'total_reviews': stats['total_reviews'] or 0,
        'star_distribution': {
            '3_star': stats['hotels_3star'] or 0,
            '4_star': stats['hotels_4star'] or 0,
            '5_star': stats['hotels_5star'] or 0,
        },
        'free_cancellation_count': stats['free_cancellation_count'] or 0,
        'pay_at_hotel_count': stats['pay_at_hotel_count'] or 0,
        'trending_count': stats['trending_count'] or 0,
    }


def _top_properties(qs, limit=6):
    """Return serialized top properties from a queryset."""
    props = qs.order_by('-ranking_score')[:limit]
    return [
        {
            'id': p.property_id,
            'name': p.property_name,
            'slug': p.slug,
            'locality': p.locality_name,
            'star_category': p.star_category,
            'price_min': float(p.price_min),
            'rating': float(p.rating),
            'review_count': p.review_count,
            'featured_image': p.featured_image_url,
            'has_free_cancellation': p.has_free_cancellation,
            'is_trending': p.is_trending,
        }
        for p in props
    ]


def _popular_localities(qs, limit=8):
    """Return top localities in this city."""
    localities = (
        qs.exclude(locality_name='')
        .values('locality_name')
        .annotate(count=Count('id'), avg_price=Avg('price_min'))
        .order_by('-count')[:limit]
    )
    return [
        {
            'name': loc['locality_name'],
            'property_count': loc['count'],
            'avg_price': round(float(loc['avg_price'] or 0)),
        }
        for loc in localities
    ]


def _price_buckets(qs):
    """Return price distribution buckets."""
    buckets = [
        ('under_1500', 0, 1500),
        ('1500_3000', 1500, 3000),
        ('3000_5000', 3000, 5000),
        ('5000_8000', 5000, 8000),
        ('above_8000', 8000, 999999),
    ]
    result = []
    for label, low, high in buckets:
        count = qs.filter(price_min__gte=low, price_min__lt=high).count()
        result.append({'range': label, 'min': low, 'max': high, 'count': count})
    return result


def _generate_faqs(city_name, stats, segment=None):
    """Generate contextual FAQ schema from live data."""
    faqs = []
    segment_label = SEGMENT_CONFIG[segment]['label'] if segment else 'Hotels'

    if stats['total_properties'] > 0:
        faqs.append({
            'question': f'How many {segment_label.lower()} are available in {city_name}?',
            'answer': f'There are {stats["total_properties"]} {segment_label.lower()} available in {city_name} with prices starting from ₹{stats["min_price"]:,}.',
        })

    if stats['avg_price'] > 0:
        faqs.append({
            'question': f'What is the average price of {segment_label.lower()} in {city_name}?',
            'answer': f'The average price is ₹{stats["avg_price"]:,} per night. Prices range from ₹{stats["min_price"]:,} to ₹{stats["max_price"]:,}.',
        })

    if stats['free_cancellation_count'] > 0:
        faqs.append({
            'question': f'Are there hotels with free cancellation in {city_name}?',
            'answer': f'Yes, {stats["free_cancellation_count"]} hotels in {city_name} offer free cancellation.',
        })

    if stats['avg_rating'] >= 3.5:
        faqs.append({
            'question': f'What is the average rating of hotels in {city_name}?',
            'answer': f'Hotels in {city_name} have an average rating of {stats["avg_rating"]}/5 based on {stats["total_reviews"]:,} reviews.',
        })

    faqs.append({
        'question': f'Which are the best {segment_label.lower()} in {city_name}?',
        'answer': f'Zygo Trip lists {stats["total_properties"]} verified {segment_label.lower()} in {city_name}, ranked by guest ratings, value for money, and real-time availability.',
    })

    return faqs


# ── API Views ─────────────────────────────────────────────────────────────────


@api_view(['GET'])
@permission_classes([AllowAny])
def city_seo_data(request, city_slug):
    """GET /api/v1/seo/city/<slug>/

    Returns complete SEO page data for a city landing page:
    - Aggregate stats (price range, star distribution, etc.)
    - Top-ranked properties
    - Popular localities
    - Price buckets for faceted filtering
    - Available segments (only those with enough inventory)
    - FAQs for rich snippets
    - Meta tags (title, description, canonical)
    """
    qs = _city_base_qs(city_slug)
    total = qs.count()

    if total == 0:
        return Response(
            {'success': False, 'error': f'No properties found in {city_slug}'},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    city_name = qs.first().city_name
    stats = _aggregate_city_stats(qs)

    # Determine which segments have enough inventory
    available_segments = []
    for seg_slug, seg_conf in SEGMENT_CONFIG.items():
        seg_count = qs.filter(seg_conf['filter']).count()
        if seg_count >= MIN_PROPERTIES_FOR_SEGMENT:
            available_segments.append({
                'slug': seg_slug,
                'label': seg_conf['label'],
                'description': seg_conf['description'],
                'property_count': seg_count,
            })

    return Response({
        'success': True,
        'data': {
            'city_name': city_name,
            'city_slug': city_slug,
            'meta': {
                'title': f'Best Hotels in {city_name} — Prices from ₹{stats["min_price"]:,} | Zygo Trip',
                'description': (
                    f'Compare {stats["total_properties"]} hotels in {city_name}. '
                    f'Book from ₹{stats["min_price"]:,}/night. '
                    f'Average rating {stats["avg_rating"]}/5. '
                    f'Free cancellation on {stats["free_cancellation_count"]} properties.'
                ),
                'canonical': f'/hotels/in/{city_slug}',
                'og_image': qs.order_by('-ranking_score').first().featured_image_url if total else '',
            },
            'stats': stats,
            'top_properties': _top_properties(qs),
            'popular_localities': _popular_localities(qs),
            'price_buckets': _price_buckets(qs),
            'segments': available_segments,
            'faqs': _generate_faqs(city_name, stats),
            'last_updated': timezone.now().isoformat(),
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def segment_seo_data(request, city_slug, segment):
    """GET /api/v1/seo/city/<slug>/<segment>/

    Returns SEO page data for a city+segment landing page.
    """
    if segment not in SEGMENT_CONFIG:
        return Response(
            {'success': False, 'error': f'Unknown segment: {segment}'},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    seg_conf = SEGMENT_CONFIG[segment]
    qs = _city_base_qs(city_slug).filter(seg_conf['filter'])
    total = qs.count()

    if total < MIN_PROPERTIES_FOR_SEGMENT:
        return Response(
            {'success': False, 'error': f'Not enough {seg_conf["label"]} in {city_slug}'},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    city_name = qs.first().city_name
    stats = _aggregate_city_stats(qs)

    sort_field = seg_conf.get('sort', '-ranking_score')
    top_props = _top_properties(qs.order_by(sort_field), limit=8)

    return Response({
        'success': True,
        'data': {
            'city_name': city_name,
            'city_slug': city_slug,
            'segment': segment,
            'segment_label': seg_conf['label'],
            'segment_description': seg_conf['description'],
            'meta': {
                'title': f'{seg_conf["label"]} in {city_name} — From ₹{stats["min_price"]:,} | Zygo Trip',
                'description': (
                    f'{total} {seg_conf["label"].lower()} in {city_name}. '
                    f'{seg_conf["description"]}. '
                    f'Prices from ₹{stats["min_price"]:,}/night. Rated {stats["avg_rating"]}/5 avg.'
                ),
                'canonical': f'/hotels/in/{city_slug}/{segment}',
            },
            'stats': stats,
            'top_properties': top_props,
            'popular_localities': _popular_localities(qs),
            'faqs': _generate_faqs(city_name, stats, segment),
            'last_updated': timezone.now().isoformat(),
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def city_list_for_sitemap(request):
    """GET /api/v1/seo/cities/

    Returns all cities with active inventory, plus available segments per city.
    Used by the frontend sitemap generator and ISR page generation.
    """
    cities = (
        PropertySearchIndex.objects
        .filter(has_availability=True)
        .values('city_name')
        .annotate(
            property_count=Count('id'),
            min_price=Min('price_min'),
            avg_rating=Avg('rating'),
        )
        .filter(property_count__gte=3)
        .order_by('-property_count')
    )

    result = []
    for city in cities:
        city_slug = city['city_name'].lower().replace(' ', '-')
        city_qs = _city_base_qs(city_slug)

        segments = []
        for seg_slug, seg_conf in SEGMENT_CONFIG.items():
            seg_count = city_qs.filter(seg_conf['filter']).count()
            if seg_count >= MIN_PROPERTIES_FOR_SEGMENT:
                segments.append(seg_slug)

        result.append({
            'city_name': city['city_name'],
            'city_slug': city_slug,
            'property_count': city['property_count'],
            'min_price': round(float(city['min_price'] or 0)),
            'avg_rating': round(float(city['avg_rating'] or 0), 1),
            'segments': segments,
        })

    return Response({
        'success': True,
        'data': {
            'cities': result,
            'total_cities': len(result),
            'total_pages': sum(1 + len(c['segments']) for c in result),
            'segments_available': list(SEGMENT_CONFIG.keys()),
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def city_meta_data(request, city_slug):
    """GET /api/v1/seo/city/<slug>/meta/

    Lightweight endpoint returning only meta tags + structured data hints.
    Used by Next.js generateMetadata() for server-side rendering.
    """
    qs = _city_base_qs(city_slug)
    total = qs.count()

    if total == 0:
        return Response(
            {'success': False, 'error': f'No properties found in {city_slug}'},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    city_name = qs.first().city_name
    stats = qs.aggregate(
        min_price=Min('price_min'),
        max_price=Max('price_max'),
        avg_rating=Avg('rating'),
        total_reviews=Sum('review_count'),
    )

    return Response({
        'success': True,
        'data': {
            'city_name': city_name,
            'title': f'Best Hotels in {city_name} — Prices from ₹{round(float(stats["min_price"] or 0)):,} | Zygo Trip',
            'description': (
                f'{total} hotels in {city_name} with prices from '
                f'₹{round(float(stats["min_price"] or 0)):,} to ₹{round(float(stats["max_price"] or 0)):,}. '
                f'Average rating {round(float(stats["avg_rating"] or 0), 1)}/5.'
            ),
            'property_count': total,
            'min_price': round(float(stats['min_price'] or 0)),
            'max_price': round(float(stats['max_price'] or 0)),
            'avg_rating': round(float(stats['avg_rating'] or 0), 1),
            'total_reviews': stats['total_reviews'] or 0,
        },
    })
