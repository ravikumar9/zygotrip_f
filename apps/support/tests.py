from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.support.models import SupportTicket


class SupportTicketApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='traveler@example.com',
            password='pass12345',
            full_name='Traveler One',
        )
        self.client.force_authenticate(self.user)

    def test_create_ticket(self):
        url = reverse('support:support_ticket_list_create')
        payload = {
            'subject': 'Need invoice copy',
            'description': 'Please share GST invoice.',
            'priority': 'medium',
            'channel': 'app',
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data.get('success'))
        self.assertEqual(SupportTicket.objects.count(), 1)

    def test_only_owner_can_access_ticket(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            subject='Need help',
            description='Issue with booking',
            priority='high',
            channel='app',
        )

        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='pass12345',
            full_name='Other User',
        )
        self.client.force_authenticate(other_user)

        url = reverse('support:support_ticket_detail', kwargs={'ticket_id': ticket.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
