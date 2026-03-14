from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User

from .models import Cab, CabAvailability, CabBooking, CabTrip, Driver


class CabBookingApiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='traveler@example.com',
			password='testpass123',
			full_name='Cab Traveler',
		)
		self.owner = User.objects.create_user(
			email='owner@example.com',
			password='testpass123',
			full_name='Cab Owner',
		)
		self.driver_user = User.objects.create_user(
			email='driver@example.com',
			password='testpass123',
			full_name='Cab Driver',
		)
		self.cab = Cab.objects.create(
			owner=self.owner,
			name='City Sedan',
			city='delhi',
			seats=4,
			fuel_type='petrol',
			base_price_per_km=Decimal('12.00'),
			system_price_per_km=Decimal('15.00'),
			is_active=True,
		)
		self.driver = Driver.objects.create(
			user=self.driver_user,
			cab=self.cab,
			license_number='DL-1234567890',
			phone='9999999999',
			city='delhi',
			status='available',
			is_verified=True,
		)
		self.booking_date = timezone.now().date() + timedelta(days=3)

	def test_book_cab_creates_booking_and_marks_inventory_unavailable(self):
		self.client.force_login(self.user)

		response = self.client.post(
			'/api/v1/cabs/book/',
			{
				'cab_id': self.cab.id,
				'pickup_address': 'Connaught Place',
				'dropoff_address': 'Airport Terminal 3',
				'pickup_date': self.booking_date.isoformat(),
			},
		)

		self.assertEqual(response.status_code, 201)
		payload = response.json()
		booking = CabBooking.objects.get(uuid=payload['booking_uuid'])
		availability = CabAvailability.objects.get(cab=self.cab, date=self.booking_date)

		self.assertTrue(payload['public_booking_id'].startswith('BK-'))
		self.assertEqual(payload['status'], 'searching')
		self.assertEqual(booking.user, self.user)
		self.assertEqual(booking.status, 'confirmed')
		self.assertFalse(availability.is_available)

	def test_tracking_returns_driver_details_when_trip_exists(self):
		booking = CabBooking.objects.create(
			cab=self.cab,
			user=self.user,
			driver=self.driver,
			booking_date=self.booking_date,
			pickup_address='Connaught Place',
			drop_address='Airport Terminal 3',
			distance_km=Decimal('12.50'),
			base_fare=Decimal('50.00'),
			price_per_km=Decimal('15.00'),
			total_price=Decimal('0.00'),
			final_price=Decimal('0.00'),
			status='confirmed',
		)
		CabTrip.objects.create(
			booking=booking,
			driver=self.driver,
			trip_status='en_route_pickup',
			eta_minutes=8,
			current_latitude='28.6139000',
			current_longitude='77.2090000',
			otp_code='123456',
		)

		response = self.client.get(f'/api/v1/cabs/bookings/{booking.uuid}/tracking/')

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['status'], 'driver_accepted')
		self.assertEqual(payload['driver']['name'], 'Cab Driver')
		self.assertEqual(payload['driver']['otp'], '123456')
		self.assertEqual(payload['eta_minutes'], 8)


# Create your tests here.