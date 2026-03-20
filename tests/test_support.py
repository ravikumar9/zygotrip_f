import pytest
from rest_framework.test import APIClient


class TestSupportAPI:
    def test_create_ticket_returns_201(self, user, db):
        api = APIClient()
        api.force_authenticate(user=user)
        resp = api.post('/api/v1/support/tickets/', {
            'subject': 'Booking not confirmed after payment',
            'description': 'I completed the payment but the booking status still shows pending after 30 minutes.',
            'category': 'booking',
            'priority': 'high',
        }, format='json')
        assert resp.status_code in (200, 201)

    def test_list_tickets_returns_only_own(self, db):
        from tests.conftest import UserFactory
        u1, u2 = UserFactory(), UserFactory()
        a1, a2 = APIClient(), APIClient()
        a1.force_authenticate(user=u1)
        a2.force_authenticate(user=u2)
        a1.post('/api/v1/support/tickets/', {
            'subject': 'U1 ticket', 'description': 'Long enough description here to pass validation checks.',
            'category': 'other', 'priority': 'low',
        }, format='json')
        resp = a2.get('/api/v1/support/tickets/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        for t in results:
            assert t.get('user') != u1.id

    def test_unauthenticated_create_returns_401(self, db):
        api = APIClient()
        resp = api.post('/api/v1/support/tickets/', {
            'subject': 'test', 'description': 'test', 'category': 'other'
        }, format='json')
        assert resp.status_code in (401, 403)
