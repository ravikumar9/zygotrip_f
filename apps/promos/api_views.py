"""
Promo Engine REST API.

POST /api/v1/promo/apply/
  Validates a promo code and returns updated price breakdown.
  Frontend must NEVER calculate discounts — this endpoint is the single
  source of truth for promo validation and breakdown.
"""
import logging
from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from apps.promos.selectors import get_active_promo
from apps.promos.services import calculate_promo_discount
from apps.promos.models import Promo, PromoUsage
from apps.pricing.pricing_service import calculate_from_amounts
from apps.core.service_guard import require_service_enabled

logger = logging.getLogger('zygotrip.api.promos')


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('promos')
def apply_promo(request):
    """
    POST /api/v1/promo/apply/

    Validates a promo code against the supplied booking parameters and returns
    the full updated price breakdown.

    Request body:
      {
        "promo_code": "SAVE10",
        "base_amount": "5000.00",        // total room cost before tax (nights × rooms × tariff)
        "meal_amount": "0.00",           // optional meal add-on total
        "context_uuid": "<uuid>"         // optional — attach context for double-apply guard
      }

    Response:
      {
        "success": true,
        "data": {
          "valid": true,
          "promo_code": "SAVE10",
          "discount_type": "percent",
          "discount_value": "10.00",
          "discount_amount": "500.00",
          "updated_breakdown": {
            "base_amount": "5000.00",
            "meal_amount": "0.00",
            "service_fee": "250.00",
            "gst_percentage": "5",
            "gst_amount": "262.50",
            "promo_discount": "500.00",
            "total_amount": "5012.50"
          },
          "new_total": "5012.50"
        }
      }

    Error responses:
      { "success": false, "error": { "code": "invalid_promo", "message": "..." } }
    """
    promo_code = (request.data.get('promo_code') or '').strip()
    if not promo_code:
        return Response(
            {'success': False, 'error': {'code': 'missing_promo', 'message': 'promo_code is required.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        base_amount = Decimal(str(request.data.get('base_amount', '0')))
        meal_amount = Decimal(str(request.data.get('meal_amount', '0')))
    except Exception:
        return Response(
            {'success': False, 'error': {'code': 'invalid_amount', 'message': 'base_amount and meal_amount must be valid numbers.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if base_amount <= Decimal('0'):
        return Response(
            {'success': False, 'error': {'code': 'invalid_amount', 'message': 'base_amount must be greater than 0.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Lookup promo
    promo = get_active_promo(promo_code)
    if not promo:
        return Response(
            {
                'success': False,
                'error': {'code': 'invalid_promo', 'message': 'Promo code is invalid or has expired.'},
                'data': {'valid': False},
            },
            status=status.HTTP_200_OK,  # Not an error — frontend receives valid=false
        )

    # Check max_uses
    if promo.max_uses and promo.max_uses > 0:
        usage_count = PromoUsage.objects.filter(promo=promo).count()
        if usage_count >= promo.max_uses:
            return Response(
                {
                    'success': False,
                    'error': {'code': 'promo_exhausted', 'message': 'This promo code has reached its usage limit.'},
                    'data': {'valid': False},
                },
                status=status.HTTP_200_OK,
            )

    # Check per-user usage (one use per user) — only for authenticated users.
    # Anonymous users can preview discounts without logging in (OTA standard).
    if request.user.is_authenticated:
        already_used = PromoUsage.objects.filter(promo=promo, user=request.user).exists()
        if already_used:
            return Response(
                {
                    'success': False,
                    'error': {'code': 'already_used', 'message': 'You have already used this promo code.'},
                    'data': {'valid': False},
                },
                status=status.HTTP_200_OK,
            )

    # Calculate discount on base + meal
    subtotal = base_amount + meal_amount
    discount_amount = calculate_promo_discount(promo, subtotal)

    # Apply max_discount cap if set
    if promo.max_discount and discount_amount > promo.max_discount:
        discount_amount = Decimal(str(promo.max_discount))

    # Recalculate full breakdown with promo discount applied
    breakdown = calculate_from_amounts(
        base_amount=base_amount,
        meal_amount=meal_amount,
        promo_discount=discount_amount,
        tariff_per_night=base_amount,  # approximate; use per-night if available
    )

    logger.info(
        'Promo applied: code=%s user=%s discount=%s',
        promo_code, getattr(request.user, 'email', 'anonymous'), discount_amount
    )

    return Response({
        'success': True,
        'data': {
            'valid': True,
            'promo_code': promo.code,
            'discount_type': promo.discount_type,
            'discount_value': str(promo.value),
            'discount_amount': str(discount_amount),
            'updated_breakdown': {
                'base_amount': str(breakdown['base_amount']),
                'meal_amount': str(breakdown['meal_amount']),
                'service_fee': str(breakdown['service_fee']),
                'gst_percentage': breakdown['gst_percentage'],
                'gst_amount': str(breakdown['gst']),
                'promo_discount': str(breakdown['promo_discount']),
                'total_amount': str(breakdown['total_amount']),
            },
            'new_total': str(breakdown['total_amount']),
        },
    })
