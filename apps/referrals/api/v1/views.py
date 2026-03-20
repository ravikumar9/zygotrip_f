from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.referrals.models import Referral
from apps.referrals.services import (
    complete_first_booking_reward,
    get_or_create_profile,
    process_signup_referral,
)

from .serializers import RedeemReferralSerializer, ReferralSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_profile(request):
    profile = get_or_create_profile(request.user)
    return Response(
        {
            'success': True,
            'data': {
                'referral_code': profile.referral_code,
                'total_referrals': profile.total_referrals,
                'successful_referrals': profile.successful_referrals,
                'total_wallet_credits': str(profile.total_wallet_credits),
                'total_loyalty_points': profile.total_loyalty_points,
            },
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_history(request):
    sent = Referral.objects.filter(referrer=request.user)
    return Response({'success': True, 'data': ReferralSerializer(sent, many=True).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_referral_code(request):
    serializer = RedeemReferralSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    ok = process_signup_referral(request.user, serializer.validated_data['referral_code'])
    if not ok:
        return Response(
            {'success': False, 'error': {'code': 'invalid_referral', 'message': 'Referral code could not be applied.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({'success': True, 'data': {'message': 'Referral applied successfully.'}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_first_booking(request):
    ok = complete_first_booking_reward(request.user)
    if not ok:
        return Response({'success': True, 'data': {'applied': False}})
    return Response({'success': True, 'data': {'applied': True}})
