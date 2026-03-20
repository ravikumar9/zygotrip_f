from rest_framework import serializers

from apps.referrals.models import Referral


class RedeemReferralSerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=16)


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referral
        fields = (
            'id',
            'referral_code',
            'status',
            'referee_wallet_credit',
            'referrer_loyalty_points',
            'created_at',
        )
