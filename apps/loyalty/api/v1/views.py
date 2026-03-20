"""Loyalty API views."""
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.loyalty.models import LoyaltyAccount, PointsTransaction
from apps.loyalty.services import redeem_estimate, redeem_points
from apps.core.service_guard import require_service_enabled


class LoyaltyAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @require_service_enabled('loyalty')
    def get(self, request):
        account, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
        return Response(
            {
                'points_balance': float(account.points_balance),
                'lifetime_points': float(account.lifetime_points),
                'tier': account.tier,
                'last_tier_update': account.last_tier_update,
            }
        )


class PointsHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @require_service_enabled('loyalty')
    def get(self, request):
        account, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
        qs = PointsTransaction.objects.filter(account=account).order_by('-created_at')
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        data = [
            {
                'id': row.id,
                'type': row.transaction_type,
                'points': float(row.points),
                'booking_id': row.booking_id,
                'note': row.note,
                'created_at': row.created_at,
            }
            for row in page
        ]
        return paginator.get_paginated_response(data)


class RedeemEstimateView(APIView):
    permission_classes = [IsAuthenticated]

    @require_service_enabled('loyalty')
    def post(self, request):
        booking_amount = request.data.get('booking_amount')
        if booking_amount is None:
            return Response({'error': 'booking_amount is required'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(redeem_estimate(request.user, booking_amount))


class RedeemView(APIView):
    permission_classes = [IsAuthenticated]

    @require_service_enabled('loyalty')
    def post(self, request):
        points = request.data.get('points')
        booking_id = request.data.get('booking_id')
        if points is None:
            return Response({'error': 'points is required'}, status=status.HTTP_400_BAD_REQUEST)

        booking = None
        if booking_id:
            from apps.booking.models import Booking

            booking = Booking.objects.filter(id=booking_id, user=request.user).first()

        try:
            discount_amount = redeem_points(request.user, points, booking)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'discount_amount': float(discount_amount)})
