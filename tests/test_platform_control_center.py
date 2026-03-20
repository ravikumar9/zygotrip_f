import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import PlatformSettings


@pytest.mark.django_db
def test_platform_config_endpoint_returns_service_switches():
    settings_obj = PlatformSettings.get_settings()
    settings_obj.hotels_enabled = True
    settings_obj.buses_enabled = False
    settings_obj.ai_assistant_enabled = True
    settings_obj.min_app_version_android = '2.1.0'
    settings_obj.min_app_version_ios = '2.2.0'
    settings_obj.save()

    client = APIClient()
    response = client.get('/api/v1/platform/config/')

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['data']['services']['hotels'] is True
    assert payload['data']['services']['buses'] is False
    assert payload['data']['services']['ai'] is True
    assert payload['data']['app_versions']['min_android'] == '2.1.0'
    assert payload['data']['app_versions']['min_ios'] == '2.2.0'


@pytest.mark.django_db
def test_maintenance_mode_blocks_public_api_calls():
    settings_obj = PlatformSettings.get_settings()
    settings_obj.maintenance_mode = True
    settings_obj.maintenance_message = 'Scheduled maintenance in progress.'
    settings_obj.save()

    client = APIClient()
    response = client.get('/api/v1/cabs/search/?city=delhi')

    assert response.status_code == 503
    payload = response.json()
    assert payload['success'] is False
    assert payload['error']['code'] == 'maintenance_mode'


@pytest.mark.django_db
def test_service_guard_blocks_disabled_cabs_search():
    settings_obj = PlatformSettings.get_settings()
    settings_obj.cabs_enabled = False
    settings_obj.save()

    client = APIClient()
    response = client.get('/api/v1/cabs/search/?city=delhi')

    assert response.status_code == 503
    payload = response.json()
    assert payload['success'] is False
    assert payload['error']['code'] == 'service_disabled'


@pytest.mark.django_db
def test_owner_api_requires_owner_role():
    user = User.objects.create_user(email='traveler@example.com', password='pass1234', full_name='Traveler', role='traveler')
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get('/api/v1/dashboard/owner-api/properties/')
    assert response.status_code == 403
