from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone


def _create_property_fixture(suffix='pricing'):
	from apps.accounts.models import User
	from apps.core.location_models import City, Country, Locality, State
	from apps.hotels.models import Property
	from apps.rooms.models import RoomType

	owner = User.objects.create_user(
		email=f'owner-{suffix}@example.com',
		password='testpass123',
		full_name=f'Owner {suffix}',
		phone=f'99999{suffix[-5:].zfill(5) if suffix[-5:].isdigit() else "10001"}',
		role='property_owner',
	)
	country, _ = Country.objects.get_or_create(
		code='IN', defaults={'name': 'India', 'display_name': 'India'}
	)
	state, _ = State.objects.get_or_create(
		country=country,
		code=f'KA{suffix[:2].upper()}',
		defaults={'name': 'Karnataka', 'display_name': 'Karnataka'},
	)
	city, _ = City.objects.get_or_create(
		state=state,
		code=f'BLR-{suffix[:6]}',
		defaults={
			'name': f'Bengaluru {suffix}',
			'display_name': f'Bengaluru {suffix}',
			'slug': f'bengaluru-{suffix}',
			'latitude': Decimal('12.971600'),
			'longitude': Decimal('77.594600'),
		},
	)
	locality, _ = Locality.objects.get_or_create(
		city=city,
		name=f'Indiranagar {suffix}',
		defaults={
			'display_name': f'Indiranagar {suffix}',
			'slug': f'indiranagar-{suffix}',
			'latitude': Decimal('12.978400'),
			'longitude': Decimal('77.640800'),
		},
	)
	prop = Property.objects.create(
		owner=owner,
		name=f'Skyline Suites {suffix}',
		slug=f'skyline-suites-{suffix}',
		property_type='Hotel',
		city=city,
		locality=locality,
		address='100 Residency Road',
		description='Central business hotel',
		latitude=Decimal('12.971600'),
		longitude=Decimal('77.594600'),
		status='approved',
		agreement_signed=True,
	)
	room_type = RoomType.objects.create(
		property=prop,
		name='Deluxe Room',
		capacity=2,
		max_occupancy=2,
		available_count=5,
		base_price=Decimal('5000.00'),
		price_per_night=Decimal('5000.00'),
		max_guests=2,
	)
	return owner, city, locality, prop, room_type


class PriceCalendarApiTests(TestCase):
	def setUp(self):
		from apps.core.intelligence import DemandForecast
		from apps.core.models import HolidayCalendar
		from apps.inventory.models import InventoryCalendar
		from apps.pricing.models import EventPricing, WeekendPricing

		self.client = Client()
		_, self.city, _, self.property, self.room_type = _create_property_fixture('calendar')
		self.start_date = timezone.now().date() + timedelta(days=2)

		WeekendPricing.objects.create(
			property=self.property,
			weekend_multiplier=Decimal('1.20'),
			weekend_days=[self.start_date.isoweekday()],
			is_active=True,
		)
		EventPricing.objects.create(
			property=self.property,
			event_name='Festival Rush',
			date=self.start_date,
			multiplier=Decimal('1.40'),
			is_active=True,
		)
		HolidayCalendar.objects.create(
			holiday_name='City Festival',
			country='IN',
			state='',
			city=self.city,
			date=self.start_date,
			holiday_type='festival',
			demand_multiplier=Decimal('1.35'),
			is_active=True,
		)
		DemandForecast.objects.create(
			property=self.property,
			date=self.start_date,
			predicted_occupancy=Decimal('0.88'),
			predicted_demand_score=88,
			confidence=Decimal('0.80'),
			factors={'velocity': 1.7},
		)
		InventoryCalendar.objects.create(
			room_type=self.room_type,
			date=self.start_date,
			total_rooms=10,
			available_rooms=2,
			booked_rooms=8,
			blocked_rooms=0,
			held_rooms=0,
			rate_override=Decimal('5200.00'),
		)

	def test_global_price_calendar_supports_365_days_and_cache(self):
		response = self.client.get('/api/v1/properties/price-calendar/', {
			'property_id': self.property.id,
			'start': self.start_date.isoformat(),
			'days': 365,
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['property_id'], self.property.id)
		self.assertEqual(payload['days'], 365)
		self.assertEqual(len(payload['dates']), 365)
		self.assertFalse(payload['cached'])

		second = self.client.get('/api/v1/properties/price-calendar/', {
			'property_id': self.property.id,
			'start': self.start_date.isoformat(),
			'days': 365,
		})
		self.assertEqual(second.status_code, 200)
		self.assertTrue(second.json()['cached'])

	def test_property_price_calendar_route_uses_unified_calendar_payload(self):
		response = self.client.get(
			f'/api/v1/properties/{self.property.slug}/price-calendar/',
			{'start': self.start_date.isoformat(), 'days': 3},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(payload['data']['property_id'], self.property.id)
		self.assertEqual(payload['data']['days'], 3)
		self.assertEqual(len(payload['data']['calendar']), 3)
		first_day = payload['data']['calendar'][0]
		self.assertEqual(first_day['availability'], 2)
		self.assertIn(first_day['pricing_source'], {'dynamic_engine', 'calendar_fallback', 'bulk_calendar_engine'})
		self.assertGreater(first_day['final_price'], first_day['base_price'])

	def test_global_price_calendar_validates_property_id(self):
		response = self.client.get('/api/v1/properties/price-calendar/', {
			'start': self.start_date.isoformat(),
			'days': 30,
		})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'property_id is required')


class DynamicPricingRuleTests(TestCase):
	def setUp(self):
		from apps.core.intelligence import DemandForecast
		from apps.inventory.models import InventoryCalendar

		_, _, _, self.property, self.room_type = _create_property_fixture('dynamic')
		self.check_date = timezone.now().date() + timedelta(days=3)
		InventoryCalendar.objects.create(
			room_type=self.room_type,
			date=self.check_date,
			total_rooms=10,
			available_rooms=2,
			booked_rooms=8,
			blocked_rooms=0,
			held_rooms=0,
		)
		DemandForecast.objects.create(
			property=self.property,
			date=self.check_date,
			predicted_occupancy=Decimal('0.85'),
			predicted_demand_score=85,
			confidence=Decimal('0.75'),
			factors={'velocity': 1.5},
		)

	def test_dynamic_price_applies_occupancy_and_last_room_surge(self):
		from apps.pricing.dynamic_engine import calculate_dynamic_price

		result = calculate_dynamic_price(self.room_type, self.check_date, property_obj=self.property)

		self.assertGreater(result.occupancy_adjustment, Decimal('0'))
		self.assertGreater(result.scarcity_adjustment, Decimal('0'))
		self.assertGreater(result.demand_adjustment, Decimal('0'))
		self.assertGreater(result.final_price, self.room_type.base_price)
		self.assertEqual(result.breakdown['available_rooms'], 2)
