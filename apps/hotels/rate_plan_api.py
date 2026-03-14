"""
Rate Plan API — System 3: Hotel Rate Plan System.

GET /api/v1/rate-plans/?room_type_id=&check_in=YYYY-MM-DD&check_out=YYYY-MM-DD
Returns available rate plans for a room type with computed prices.
"""
import logging
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.hotels.rateplans')


@api_view(['GET'])
@permission_classes([AllowAny])
def rate_plans_api(request):
    """
    GET /api/v1/rate-plans/
    Params: room_type_id (required), check_in, check_out (optional)
    """
    rt_id      = request.GET.get('room_type_id')
    ci_str     = request.GET.get('check_in')
    co_str     = request.GET.get('check_out')

    if not rt_id:
        return Response({'error': 'room_type_id is required'}, status=400)

    check_in = check_out = None
    if ci_str and co_str:
        try:
            check_in  = date.fromisoformat(ci_str)
            check_out = date.fromisoformat(co_str)
        except ValueError:
            return Response({'error': 'Dates must be YYYY-MM-DD'}, status=400)

    try:
        from apps.rooms.models import RoomType
        room_type = RoomType.objects.select_related('property').get(id=rt_id)
    except Exception:
        return Response({'error': 'Room type not found'}, status=404)

    try:
        from apps.hotels.rate_plan_engine import get_rate_plans_for_room
        plans = get_rate_plans_for_room(room_type, check_in, check_out)

        if check_in and check_out:
            # Plans returned as list of dicts with pricing
            data = [
                {
                    'id':               p['plan'].id,
                    'plan_type':        p['plan'].plan_type,
                    'name':             p['plan'].name,
                    'description':      p['plan'].description,
                    'nightly_price':    str(p['nightly_price']),
                    'total_price':      str(p['total_price']),
                    'nights':           p['nights'],
                    'is_refundable':    p['is_refundable'],
                    'includes_breakfast': p['includes_breakfast'],
                    'includes_lunch':   p['plan'].includes_lunch,
                    'includes_dinner':  p['plan'].includes_dinner,
                    'pay_at_hotel':     p['plan'].pay_at_hotel,
                    'min_nights':       p['plan'].min_nights,
                    'cancellation_policy': (
                        {
                            'name':        p['cancellation_policy'].name,
                            'policy_type': p['cancellation_policy'].policy_type,
                        }
                        if p.get('cancellation_policy') else None
                    ),
                }
                for p in plans
            ]
        else:
            data = [
                {
                    'id':                    p.id,
                    'plan_type':             p.plan_type,
                    'name':                  p.name,
                    'description':           p.description,
                    'price_modifier_percent': str(p.price_modifier_percent),
                    'is_refundable':         p.is_refundable,
                    'includes_breakfast':    p.includes_breakfast,
                    'includes_lunch':        p.includes_lunch,
                    'includes_dinner':       p.includes_dinner,
                    'pay_at_hotel':          p.pay_at_hotel,
                    'min_nights':            p.min_nights,
                    'max_nights':            p.max_nights,
                }
                for p in plans
            ]

        return Response({'rate_plans': data, 'room_type_id': rt_id})

    except Exception as exc:
        logger.error('rate_plans_api error: %s', exc, exc_info=True)
        return Response({'error': 'Failed to fetch rate plans'}, status=500)
