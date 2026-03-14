from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.buses.models import Bus, BusBooking, BusType
from apps.cabs.models import Cab, CabBooking, Driver
from apps.core.location_models import City, Country, Locality, State
from apps.core.analytics import AnalyticsEvent
from apps.hotels.models import Property, PropertyAmenity, PropertyImage
from apps.packages.models import Package, PackageCategory, PackageDeparture
from apps.rooms.models import RoomInventory, RoomType
from apps.search.models import PropertySearchIndex
from apps.booking.models import Booking


class OwnerDashboardApiTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser(
			email='admin-dashboard@example.com',
			password='testpass123',
			full_name='Dashboard Admin',
		)
		self.owner = User.objects.create_user(
			email='owner-dashboard@example.com',
			password='testpass123',
			full_name='Property Owner',
			role='property_owner',
		)
		self.cab_owner = User.objects.create_user(
			email='cab-owner@example.com',
			password='testpass123',
			full_name='Cab Owner',
			role='cab_owner',
		)
		self.package_provider = User.objects.create_user(
			email='package-provider@example.com',
			password='testpass123',
			full_name='Package Provider',
			role='package_provider',
		)
		self.bus_operator = User.objects.create_user(
			email='bus-operator@example.com',
			password='testpass123',
			full_name='Bus Operator',
			role='bus_operator',
		)

		self.country = Country.objects.create(code='IN', name='India', display_name='India')
		self.state = State.objects.create(country=self.country, code='KA', name='Karnataka', display_name='Karnataka')
		self.city = City.objects.create(
			state=self.state,
			code='BLR',
			name='Bengaluru',
			display_name='Bengaluru',
			slug='bengaluru',
			latitude=Decimal('12.971600'),
			longitude=Decimal('77.594600'),
		)
		self.locality = Locality.objects.create(
			city=self.city,
			name='Indiranagar',
			display_name='Indiranagar',
			slug='indiranagar',
			latitude=Decimal('12.978400'),
			longitude=Decimal('77.640800'),
		)

		self.property = Property.objects.create(
			owner=self.owner,
			name='Skyline Suites',
			property_type='Hotel',
			city=self.city,
			locality=self.locality,
			address='100 Residency Road',
			description='Central business hotel',
			latitude=Decimal('12.971600'),
			longitude=Decimal('77.594600'),
			status='approved',
			agreement_signed=True,
		)
		self.room_type = RoomType.objects.create(
			property=self.property,
			name='Deluxe Room',
			capacity=2,
			max_occupancy=2,
			available_count=5,
			base_price=Decimal('4500.00'),
			price_per_night=Decimal('4500.00'),
			max_guests=2,
		)
		self.inventory_date = timezone.now().date() + timedelta(days=2)
		RoomInventory.objects.create(
			room_type=self.room_type,
			date=self.inventory_date,
			available_rooms=4,
			booked_count=1,
			price=Decimal('4750.00'),
		)

		self.cab = Cab.objects.create(
			owner=self.cab_owner,
			name='Airport Sedan',
			city='bangalore',
			seats=4,
			fuel_type='petrol',
			base_price_per_km=Decimal('12.00'),
			system_price_per_km=Decimal('15.00'),
			is_active=True,
		)
		self.driver_user = User.objects.create_user(
			email='driver-dashboard@example.com',
			password='testpass123',
			full_name='Fleet Driver',
		)
		self.driver = Driver.objects.create(
			user=self.driver_user,
			cab=self.cab,
			license_number='KA-DRV-001',
			phone='9999999998',
			city='bangalore',
			status='available',
			is_verified=True,
		)
		CabBooking.objects.create(
			cab=self.cab,
			user=self.owner,
			driver=self.driver,
			booking_date=timezone.now().date() + timedelta(days=1),
			pickup_address='MG Road',
			drop_address='Airport',
			distance_km=Decimal('10.00'),
			base_fare=Decimal('50.00'),
			price_per_km=Decimal('15.00'),
			total_price=Decimal('200.00'),
			final_price=Decimal('210.00'),
			status='completed',
		)

		self.package_category = PackageCategory.objects.create(name='Weekend Trips')
		self.package = Package.objects.create(
			provider=self.package_provider,
			category=self.package_category,
			name='Coorg Escape',
			description='Two night package in Coorg',
			destination='Coorg',
			duration_days=3,
			base_price=Decimal('12000.00'),
			is_active=True,
		)
		self.departure = PackageDeparture.objects.create(
			package=self.package,
			departure_date=timezone.now().date() + timedelta(days=15),
			return_date=timezone.now().date() + timedelta(days=18),
			total_slots=20,
			booked_slots=6,
			is_active=True,
		)

		self.bus_type = BusType.objects.create(name=BusType.AC, base_fare=Decimal('700.00'), capacity=40)
		self.bus = Bus.objects.create(
			operator=self.bus_operator,
			registration_number='KA-01-BUS-9999',
			bus_type=self.bus_type,
			operator_name='Operator Express',
			from_city='Bangalore',
			to_city='Chennai',
			departure_time=timezone.now().time(),
			arrival_time=(timezone.now() + timedelta(hours=6)).time(),
			journey_date=timezone.now().date() + timedelta(days=3),
			price_per_seat=Decimal('999.00'),
			available_seats=24,
			is_active=True,
		)
		BusBooking.objects.create(
			user=self.owner,
			bus=self.bus,
			journey_date=self.bus.journey_date,
			contact_email='traveler@example.com',
			contact_phone='9999999997',
			status='confirmed',
			total_amount=Decimal('1998.00'),
		)

	def test_admin_can_view_owner_inventory_calendar_with_flat_inventory_rows(self):
		self.client.force_login(self.admin)

		response = self.client.get(
			'/api/v1/dashboard/owner/inventory/',
			{'property_id': self.property.id, 'month': self.inventory_date.strftime('%Y-%m')},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('inventory', payload)
		self.assertEqual(len(payload['inventory']), 1)
		self.assertEqual(payload['inventory'][0]['date'], self.inventory_date.isoformat())
		self.assertEqual(payload['inventory'][0]['total'], 5)
		self.assertEqual(payload['inventory'][0]['booked'], 1)
		self.assertEqual(payload['returned_rows'], 1)
		self.assertEqual(payload['total_rows'], 1)
		self.assertFalse(payload['has_more'])

	def test_admin_inventory_calendar_respects_limit(self):
		RoomInventory.objects.create(
			room_type=self.room_type,
			date=self.inventory_date + timedelta(days=1),
			available_rooms=3,
			booked_count=2,
			price=Decimal('4900.00'),
		)
		self.client.force_login(self.admin)

		response = self.client.get(
			'/api/v1/dashboard/owner/inventory/',
			{'month': self.inventory_date.strftime('%Y-%m'), 'limit': 1},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload['inventory']), 1)
		self.assertEqual(payload['returned_rows'], 1)
		self.assertEqual(payload['total_rows'], 2)
		self.assertTrue(payload['has_more'])

	def test_admin_cab_dashboard_aggregates_other_owners_fleet(self):
		self.client.force_login(self.admin)

		response = self.client.get('/api/v1/dashboard/owner/cab/dashboard/')

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['total_vehicles'], 1)
		self.assertEqual(payload['active_drivers'], 1)
		self.assertEqual(payload['total_revenue'], '210.00')
		self.assertEqual(payload['drivers'][0]['name'], 'Fleet Driver')

	def test_admin_package_dashboard_uses_departure_slot_fields(self):
		self.client.force_login(self.admin)

		response = self.client.get('/api/v1/dashboard/owner/package/dashboard/')

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['active_departures'], 1)
		self.assertEqual(payload['upcoming_departures'][0]['total_slots'], 20)
		self.assertEqual(payload['upcoming_departures'][0]['booked_slots'], 6)
		self.assertEqual(payload['upcoming_departures'][0]['available_slots'], 14)

	def test_bus_operator_dashboard_uses_operator_relation(self):
		self.client.force_login(self.bus_operator)

		response = self.client.get('/api/v1/dashboard/owner/bus/dashboard/')

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['total_buses'], 1)
		self.assertEqual(payload['total_bookings'], 1)
		self.assertEqual(payload['routes'][0]['route'], 'Bangalore → Chennai')

	def test_owner_command_center_returns_consolidated_intelligence(self):
		Booking.objects.create(
			user=self.owner,
			property=self.property,
			check_in=timezone.now().date() + timedelta(days=5),
			check_out=timezone.now().date() + timedelta(days=7),
			status=Booking.STATUS_CONFIRMED,
			total_amount=Decimal('9500.00'),
			gross_amount=Decimal('9500.00'),
			commission_amount=Decimal('950.00'),
			net_payable_to_hotel=Decimal('8550.00'),
		)

		AnalyticsEvent.objects.create(
			event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
			user=self.owner,
			property_id=self.property.id,
			session_id='owner-cmd-center-session',
			city=self.city.name,
		)
		AnalyticsEvent.objects.create(
			event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
			user=self.owner,
			property_id=self.property.id,
			session_id='owner-cmd-center-session',
			city=self.city.name,
			amount=Decimal('9500.00'),
		)

		PropertySearchIndex.objects.update_or_create(
			property=self.property,
			defaults={
				'property_name': self.property.name,
				'slug': self.property.slug,
				'property_type': self.property.property_type,
				'city_id': self.property.city_id,
				'city_name': self.property.city.name,
				'locality_name': self.locality.name,
				'latitude': self.property.latitude,
				'longitude': self.property.longitude,
				'star_category': self.property.star_category,
				'price_min': Decimal('4500.00'),
				'price_max': Decimal('6500.00'),
				'rating': Decimal('4.3'),
				'review_count': 12,
				'review_score': Decimal('8.4'),
				'popularity_score': 55,
				'total_impressions': 200,
				'total_clicks': 36,
				'total_bookings': 5,
				'availability_reliability': Decimal('0.94'),
				'cancellation_rate': Decimal('0.08'),
			},
		)

		self.client.force_login(self.owner)
		response = self.client.get(
			'/api/v1/dashboard/owner/command-center/',
			{'property_id': self.property.id},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['property']['id'], self.property.id)
		self.assertIn('market_comparison', payload)
		self.assertIn('conversion_optimization', payload)
		self.assertIn('supply_quality', payload)
		self.assertIn('cancellation_prediction', payload)
		self.assertIn('dynamic_commission', payload)
		self.assertIn('alerts', payload)


class OwnerSetupFlowTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			email='resort-owner@example.com',
			password='testpass123',
			full_name='Resort Owner',
			role='property_owner',
		)

		self.country = Country.objects.create(code='IN', name='India', display_name='India')
		self.state = State.objects.create(country=self.country, code='KA', name='Karnataka', display_name='Karnataka')
		self.city = City.objects.create(
			state=self.state,
			code='COG',
			name='Coorg',
			display_name='Coorg',
			slug='coorg',
			latitude=Decimal('12.424400'),
			longitude=Decimal('75.738200'),
		)
		self.locality = Locality.objects.create(
			city=self.city,
			name='Madikeri',
			display_name='Madikeri',
			slug='madikeri',
			latitude=Decimal('12.424400'),
			longitude=Decimal('75.738200'),
		)

		self.property = Property.objects.create(
			owner=self.owner,
			name='Misty Valley Retreat',
			property_type='Resort',
			city=self.city,
			locality=self.locality,
			area='Old Madikeri Road',
			landmark='Near Abbey Falls Junction',
			address='12 Hillcrest Road, Coorg',
			description='Resort in the hills',
			latitude=Decimal('12.424400'),
			longitude=Decimal('75.738200'),
			status='approved',
			agreement_signed=True,
		)

	def test_owner_can_create_resort_with_location_and_featured_photo(self):
		self.client.force_login(self.owner)

		response = self.client.post(
			'/owner/dashboard/properties/add/',
			{
				'name': 'Coorg Valley Resort',
				'property_type': 'Resort',
				'city': self.city.id,
				'area': 'Madikeri Hills',
				'landmark': 'Near Raja Seat',
				'country': 'India',
				'address': '45 View Point Road, Coorg',
				'description': 'A resort with valley views and spa experiences.',
				'rating': '4.6',
				'latitude': '12.431200',
				'longitude': '75.739900',
				'place_id': 'coorg-valley-place-id',
				'formatted_address': '45 View Point Road, Madikeri, Coorg, Karnataka, India',
				'image_url': 'https://example.com/images/coorg-valley-resort.jpg',
			},
		)

		self.assertEqual(response.status_code, 302)
		property_obj = Property.objects.get(name='Coorg Valley Resort')
		self.assertEqual(property_obj.owner, self.owner)
		self.assertEqual(property_obj.property_type, 'Resort')
		self.assertEqual(property_obj.area, 'Madikeri Hills')
		self.assertEqual(property_obj.landmark, 'Near Raja Seat')
		self.assertEqual(property_obj.place_id, 'coorg-valley-place-id')
		self.assertEqual(property_obj.formatted_address, '45 View Point Road, Madikeri, Coorg, Karnataka, India')
		self.assertEqual(property_obj.images.count(), 1)
		self.assertEqual(property_obj.images.first().image_url, 'https://example.com/images/coorg-valley-resort.jpg')

	def test_owner_can_edit_resort_features_tags_and_amenities(self):
		self.client.force_login(self.owner)

		response = self.client.post(
			f'/owner/dashboard/properties/{self.property.id}/edit/',
			{
				'name': 'Misty Valley Luxury Resort',
				'city': self.city.id,
				'area': 'Upper Madikeri',
				'landmark': 'Opposite Sunset Point',
				'country': 'India',
				'address': '88 Sunset Point Road, Coorg',
				'description': 'Luxury resort with infinity pool and wellness spa.',
				'property_type': 'Luxury Resort',
				'star_category': '5',
				'has_free_cancellation': 'on',
				'cancellation_hours': '48',
				'pay_at_hotel': 'on',
				'tags': 'Pool View, Spa Resort, Couple Friendly',
				'latitude': '12.440000',
				'longitude': '75.740000',
				'place_id': 'misty-luxury-place-id',
				'formatted_address': '88 Sunset Point Road, Coorg, Karnataka, India',
				'amenities_list': 'Infinity Pool\nSpa\nKids Play Area',
			},
		)

		self.assertEqual(response.status_code, 302)
		self.property.refresh_from_db()
		self.assertEqual(self.property.name, 'Misty Valley Luxury Resort')
		self.assertEqual(self.property.area, 'Upper Madikeri')
		self.assertEqual(self.property.landmark, 'Opposite Sunset Point')
		self.assertEqual(self.property.property_type, 'Luxury Resort')
		self.assertEqual(self.property.star_category, 5)
		self.assertTrue(self.property.pay_at_hotel)
		self.assertEqual(self.property.tags, ['Pool View', 'Spa Resort', 'Couple Friendly'])
		self.assertEqual(
			list(PropertyAmenity.objects.filter(property=self.property).values_list('name', flat=True)),
			['Infinity Pool', 'Spa', 'Kids Play Area'],
		)

	def test_owner_can_add_room_and_bulk_inventory_updates(self):
		self.client.force_login(self.owner)

		room_response = self.client.post(
			f'/owner/dashboard/properties/{self.property.id}/rooms/add/',
			{
				'name': 'Forest View Villa',
				'description': 'Private villa with deck and coffee estate view.',
				'base_price': '6250.00',
				'max_guests': '4',
				'available_count': '6',
				'bed_type': 'King Bed',
				'room_size_sqm': '42',
			},
		)

		self.assertEqual(room_response.status_code, 302)
		room = RoomType.objects.get(property=self.property, name='Forest View Villa')

		inventory_response = self.client.post(
			f'/owner/dashboard/properties/{self.property.id}/inventory/',
			{
				'start_date': '2026-04-01',
				'end_date': '2026-04-03',
				'room_type': room.id,
				'available_rooms': '7',
				'price': '6499.00',
			},
		)

		self.assertEqual(inventory_response.status_code, 302)
		inventories = RoomInventory.objects.filter(room_type=room).order_by('date')
		self.assertEqual(inventories.count(), 3)
		self.assertEqual(inventories.first().available_rooms, 7)
		self.assertEqual(inventories.first().price, Decimal('6499.00'))

	def test_owner_inventory_general_route_renders_selected_property(self):
		self.client.force_login(self.owner)
		room = RoomType.objects.create(
			property=self.property,
			name='Garden Suite',
			capacity=2,
			max_occupancy=2,
			available_count=3,
			base_price=Decimal('5500.00'),
			price_per_night=Decimal('5500.00'),
			max_guests=2,
		)
		RoomInventory.objects.create(
			room_type=room,
			date=timezone.now().date() + timedelta(days=1),
			available_rooms=3,
			price=Decimal('5750.00'),
		)

		response = self.client.get('/owner/dashboard/inventory/', {'property': self.property.id})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Inventory Management')
		self.assertContains(response, 'Misty Valley Retreat')
		self.assertContains(response, 'Garden Suite')