import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.referrals.models import Referral
from apps.referrals.services import get_or_create_profile


@pytest.mark.django_db
def test_referral_code_redeem_creates_referral_record():
    referrer = User.objects.create_user(
        email='referrer@example.com',
        password='pass1234',
        full_name='Referrer User',
    )
    referee = User.objects.create_user(
        email='referee@example.com',
        password='pass1234',
        full_name='Referee User',
    )

    profile = get_or_create_profile(referrer)

    client = APIClient()
    client.force_authenticate(user=referee)
    response = client.post('/api/v1/referrals/redeem/', {'referral_code': profile.referral_code}, format='json')

    assert response.status_code == 200
    assert Referral.objects.filter(referrer=referrer, referee=referee).exists()


@pytest.mark.django_db
def test_register_with_referral_code_applies_referral():
    referrer = User.objects.create_user(
        email='register-referrer@example.com',
        password='pass1234',
        full_name='Register Referrer',
    )
    profile = get_or_create_profile(referrer)

    client = APIClient()
    response = client.post(
        '/api/v1/auth/register/',
        {
            'email': 'new-user@example.com',
            'password': 'pass12345',
            'full_name': 'New User',
            'referral_code': profile.referral_code,
        },
        format='json',
    )

    assert response.status_code == 201
    created_user = User.objects.get(email='new-user@example.com')
    assert Referral.objects.filter(referrer=referrer, referee=created_user).exists()
