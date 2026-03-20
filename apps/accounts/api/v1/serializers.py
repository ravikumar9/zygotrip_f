"""
Auth and User serializers for API v1.
"""
from django.contrib.auth import authenticate
from rest_framework import serializers
from apps.accounts.models import User, ROLE_CHOICES


class UserSerializer(serializers.ModelSerializer):
    """Public user profile (safe to return in API responses)."""

    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.full_name or ''

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'full_name', 'phone',
            'role', 'is_verified_vendor',
            'created_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified_vendor', 'created_at']


class RegisterSerializer(serializers.Serializer):
    """User registration — returns JWT tokens on success."""

    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20, default='', required=False)
    role = serializers.ChoiceField(
        choices=[r[0] for r in ROLE_CHOICES],
        default='traveler',
        required=False,
    )
    referral_code = serializers.CharField(max_length=16, required=False, allow_blank=True, write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def create(self, validated_data):
        referral_code = (validated_data.pop('referral_code', '') or '').strip()
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            phone=validated_data.get('phone', ''),
            role=validated_data.get('role', 'traveler'),
        )
        user._raw_referral_code = referral_code
        return user


class LoginSerializer(serializers.Serializer):
    """Email + password login."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')
        data['user'] = user
        return data


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Partial profile update — email and role are immutable."""

    class Meta:
        model = User
        fields = ['full_name', 'phone']
