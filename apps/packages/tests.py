from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User

from .models import Package, PackageBooking, PackageCategory, PackageDeparture


class PackageApiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='package-traveler@example.com',
			password='testpass123',
			full_name='Package Traveler',
		)
		self.provider = User.objects.create_user(
			email='provider@example.com',
			password='testpass123',
			full_name='Package Provider',
		)
		self.category = PackageCategory.objects.create(name='Beach Escape')
		self.package = Package.objects.create(
			provider=self.provider,
			category=self.category,
			name='Goa Weekend Escape',
			description='Three-day beach holiday package',
			destination='Goa',
			duration_days=3,
			base_price='12000.00',
			inclusions='Hotel,Breakfast,Airport transfer',
			exclusions='Flights',
			is_active=True,
		)
		self.departure = PackageDeparture.objects.create(
			package=self.package,
			departure_date=timezone.now().date() + timedelta(days=20),
			return_date=timezone.now().date() + timedelta(days=23),
			total_slots=12,
			booked_slots=2,
			is_guaranteed=True,
			is_active=True,
		)

	def test_package_availability_lists_departure_calendar(self):
		response = self.client.get(
			f'/api/v1/packages/{self.package.id}/availability/',
			{'start_date': (timezone.now().date() + timedelta(days=1)).isoformat()},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(len(payload['calendar']), 1)
		self.assertEqual(payload['calendar'][0]['date'], self.departure.departure_date.isoformat())
		self.assertEqual(payload['calendar'][0]['available_slots'], 10)
		self.assertFalse(payload['calendar'][0]['is_sold_out'])

	def test_package_booking_creates_booking_and_decrements_slots(self):
		self.client.force_login(self.user)

		response = self.client.post(
			'/api/v1/packages/book/',
			{
				'package_id': self.package.id,
				'departure_date': self.departure.departure_date.isoformat(),
				'adults': 2,
				'children': 1,
			},
		)

		self.assertEqual(response.status_code, 201)
		payload = response.json()
		booking = PackageBooking.objects.get(id=payload['booking_id'])
		self.departure.refresh_from_db()

		self.assertEqual(booking.user, self.user)
		self.assertEqual(booking.package, self.package)
		self.assertEqual(booking.status, 'confirmed')
		self.assertTrue(payload['public_booking_id'].startswith('BK-'))
		self.assertEqual(self.departure.booked_slots, 5)
