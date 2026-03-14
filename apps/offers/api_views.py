"""
Offers REST API.

GET  /api/v1/offers/featured/  — Active offers for homepage / listing display.
"""
import logging
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Offer

logger = logging.getLogger('zygotrip.api.offers')


@api_view(['GET'])
@permission_classes([AllowAny])
def featured_offers(request):
    """
    GET /api/v1/offers/featured/

    Returns currently active offers. No authentication required.
    Ordered by start_datetime descending (newest first).
    """
    now = timezone.now()
    offers_qs = Offer.objects.filter(
        is_active=True,
        is_global=True,
        start_datetime__lte=now,
        end_datetime__gte=now,
    ).order_by('-start_datetime')[:8]

    results = []
    for offer in offers_qs:
        results.append({
            'id': offer.id,
            'title': offer.title,
            'description': offer.description,
            'offer_type': offer.offer_type,
            'coupon_code': offer.coupon_code,
            'discount_percentage': str(offer.discount_percentage),
            'discount_flat': str(offer.discount_flat),
            'start_datetime': offer.start_datetime.isoformat(),
            'end_datetime': offer.end_datetime.isoformat(),
            'is_global': offer.is_global,
        })

    return Response({
        'success': True,
        'data': results,
    })
