import logging
from datetime import date as date_type
from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.pricing')


@api_view(['POST'])
@permission_classes([AllowAny])
def price_quote(request):
	"""
	POST /api/v1/pricing/quote/
	Body: {
	  room_type_id: int,
	  check_in: "YYYY-MM-DD",
	  check_out: "YYYY-MM-DD",
	  room_count: int (default 1),
	  promo_code: str (optional)
	}
	Returns full itemised price breakdown with dynamic pricing applied.
	"""
	data = request.data

	# Validate input
	try:
		room_type_id = int(data['room_type_id'])
		check_in_str = data['check_in']
		check_out_str = data['check_out']
		room_count = int(data.get('room_count', 1))
		promo_code = str(data.get('promo_code', '')).strip()
	except (KeyError, ValueError, TypeError) as exc:
		return Response({'error': f'Invalid input: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

	try:
		check_in = date_type.fromisoformat(check_in_str)
		check_out = date_type.fromisoformat(check_out_str)
		nights = (check_out - check_in).days
		if nights <= 0:
			return Response({'error': 'check_out must be after check_in'}, status=status.HTTP_400_BAD_REQUEST)
	except ValueError:
		return Response({'error': 'Invalid date format - use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

	# Load room type
	from apps.rooms.models import RoomType

	try:
		room_type = RoomType.objects.select_related('property').get(id=room_type_id)
	except RoomType.DoesNotExist:
		return Response({'error': 'Room type not found'}, status=status.HTTP_404_NOT_FOUND)

	# Dynamic pricing
	demand_level = 'medium'
	surge_active = False
	multiplier = Decimal('1.00')
	base_price = room_type.base_price or room_type.price_per_night

	try:
		from apps.pricing.dynamic_pricing import DemandPricingService

		svc = DemandPricingService()
		dynamic_price = svc.get_dynamic_price(
			property_id=room_type.property_id,
			room_type_id=room_type_id,
			target_date=check_in,
		)
		multiplier = svc.calculate_multiplier(room_type.property_id, check_in)
		base_price = dynamic_price

		if multiplier >= Decimal('1.20'):
			demand_level = 'peak'
		elif multiplier >= Decimal('1.10'):
			demand_level = 'high'
		elif multiplier <= Decimal('0.85'):
			demand_level = 'low'
		else:
			demand_level = 'medium'
		surge_active = multiplier > Decimal('1.05')
	except Exception as exc:
		logger.warning('Dynamic pricing unavailable, using base price: %s', exc)

	# Build price using PricingEngine
	from apps.booking.pricing_engine import PricingEngine

	engine = PricingEngine(
		base_price_per_night=base_price,
		nights=nights,
		room_count=room_count,
	)

	# Property-level discount
	prop = room_type.property
	prop_discount = getattr(prop, 'discount_percent', None) or getattr(prop, 'base_discount_percent', None)
	if prop_discount:
		engine.apply_property_discount(percent=float(prop_discount))

	# Promo code
	if promo_code:
		try:
			from apps.promos.selectors import get_active_promo
			from apps.promos.services import calculate_promo_discount

			promo = get_active_promo(promo_code)
			if promo:
				subtotal_so_far = Decimal(str(engine.breakdown.get('after_property_discount', engine.base_total)))
				disc = calculate_promo_discount(promo, subtotal_so_far)
				engine.apply_coupon(promo_code, amount=disc)
		except Exception as exc:
			logger.warning('Promo code apply failed: %s', exc)

	# GST (India slab rates)
	subtotal = Decimal(
		str(
			engine.breakdown.get(
				'after_coupon_discount',
				engine.breakdown.get('after_property_discount', engine.base_total),
			)
		)
	)
	if subtotal > Decimal('7500'):
		gst_pct = 18
	elif subtotal > Decimal('2500'):
		gst_pct = 12
	else:
		gst_pct = 0
	engine.apply_gst(percent=gst_pct)

	breakdown = engine.breakdown
	breakdown.update(
		{
			'demand_level': demand_level,
			'surge_active': surge_active,
			'demand_multiplier': float(multiplier),
			'room_type_id': room_type_id,
			'room_type_name': room_type.name,
			'property_id': room_type.property_id,
			'property_name': prop.name,
			'check_in': check_in_str,
			'check_out': check_out_str,
			'nights': nights,
			'room_count': room_count,
		}
	)
	return Response(breakdown)
