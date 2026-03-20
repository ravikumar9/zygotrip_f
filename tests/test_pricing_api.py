import pytest
from rest_framework.test import APIClient


class TestPricingQuoteAPI:
    def test_quote_returns_breakdown(self, room_type, db):
        api = APIClient()
        resp = api.post('/api/v1/pricing/quote/', {
            'room_type_id': room_type.id,
            'check_in': '2026-12-01',
            'check_out': '2026-12-03',
            'room_count': 1,
        }, format='json')
        assert resp.status_code == 200
        assert 'base_total' in resp.data
        assert 'nights' in resp.data
        assert resp.data['nights'] == 2

    def test_invalid_dates_returns_400(self, room_type, db):
        api = APIClient()
        resp = api.post('/api/v1/pricing/quote/', {
            'room_type_id': room_type.id,
            'check_in': '2026-12-05',
            'check_out': '2026-12-03',
        }, format='json')
        assert resp.status_code == 400

    def test_missing_room_type_returns_404(self, db):
        api = APIClient()
        resp = api.post('/api/v1/pricing/quote/', {
            'room_type_id': 99999,
            'check_in': '2026-12-01',
            'check_out': '2026-12-03',
        }, format='json')
        assert resp.status_code == 404
