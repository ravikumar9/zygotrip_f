from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from decimal import Decimal
from apps.cabs.models import Cab, CabType, CITY_CHOICES, FUEL_TYPE_CHOICES, SEAT_CHOICES

User = get_user_model()


class Command(BaseCommand):
	help = 'Seed cabs database with sample data (idempotent)'

	def handle(self, *args, **options):
		# Get or create default owner
		owner, created = User.objects.get_or_create(
			email='cabowner@example.com',
			defaults={'full_name': 'Cab Owner', 'is_active': True}
		)
		if created:
			owner.set_password('password123')
			owner.save()
			self.stdout.write(f'Created owner: {owner.email}')

		cab_data = [
			# Delhi (5 cabs)
			{'name': 'Delhi Eco Premium', 'city': 'delhi', 'seats': 4, 'fuel': 'diesel', 'price': Decimal('12')},
			{'name': 'Delhi Sedan Plus', 'city': 'delhi', 'seats': 5, 'fuel': 'petrol', 'price': Decimal('15')},
			{'name': 'Delhi SUV Comfort', 'city': 'delhi', 'seats': 7, 'fuel': 'hybrid', 'price': Decimal('18')},
			{'name': 'Delhi Van Deluxe', 'city': 'delhi', 'seats': 12, 'fuel': 'diesel', 'price': Decimal('22')},
			{'name': 'Delhi Electric Smart', 'city': 'delhi', 'seats': 5, 'fuel': 'electric', 'price': Decimal('10')},

			# Mumbai (5 cabs)
			{'name': 'Mumbai City Express', 'city': 'mumbai', 'seats': 4, 'fuel': 'petrol', 'price': Decimal('14')},
			{'name': 'Mumbai Premium SUV', 'city': 'mumbai', 'seats': 7, 'fuel': 'diesel', 'price': Decimal('20')},
			{'name': 'Mumbai Eco Sedan', 'city': 'mumbai', 'seats': 5, 'fuel': 'hybrid', 'price': Decimal('13')},
			{'name': 'Mumbai Van Service', 'city': 'mumbai', 'seats': 8, 'fuel': 'diesel', 'price': Decimal('19')},
			{'name': 'Mumbai Electric Ride', 'city': 'mumbai', 'seats': 5, 'fuel': 'electric', 'price': Decimal('11')},

			# Bangalore (5 cabs)
			{'name': 'Bangalore Tech Ride', 'city': 'bangalore', 'seats': 4, 'fuel': 'petrol', 'price': Decimal('13')},
			{'name': 'Bangalore Comfort Plus', 'city': 'bangalore', 'seats': 5, 'fuel': 'hybrid', 'price': Decimal('14')},
			{'name': 'Bangalore SUV Prime', 'city': 'bangalore', 'seats': 7, 'fuel': 'diesel', 'price': Decimal('17')},
			{'name': 'Bangalore Eco Tour', 'city': 'bangalore', 'seats': 6, 'fuel': 'electric', 'price': Decimal('12')},
			{'name': 'Bangalore Business Van', 'city': 'bangalore', 'seats': 8, 'fuel': 'diesel', 'price': Decimal('18')},

			# Chennai (5 cabs)
			{'name': 'Chennai Coast Ride', 'city': 'chennai', 'seats': 4, 'fuel': 'petrol', 'price': Decimal('11')},
			{'name': 'Chennai Premium Sedan', 'city': 'chennai', 'seats': 5, 'fuel': 'diesel', 'price': Decimal('13')},
			{'name': 'Chennai Family SUV', 'city': 'chennai', 'seats': 7, 'fuel': 'hybrid', 'price': Decimal('15')},
			{'name': 'Chennai Green Eco', 'city': 'chennai', 'seats': 5, 'fuel': 'electric', 'price': Decimal('9')},
			{'name': 'Chennai Group Tour', 'city': 'chennai', 'seats': 12, 'fuel': 'diesel', 'price': Decimal('20')},

			# Goa (5 cabs)
			{'name': 'Goa Beach Express', 'city': 'goa', 'seats': 4, 'fuel': 'petrol', 'price': Decimal('16')},
			{'name': 'Goa Luxury Sedan', 'city': 'goa', 'seats': 5, 'fuel': 'diesel', 'price': Decimal('18')},
			{'name': 'Goa Adventure SUV', 'city': 'goa', 'seats': 7, 'fuel': 'hybrid', 'price': Decimal('20')},
			{'name': 'Goa Eco Resort', 'city': 'goa', 'seats': 6, 'fuel': 'electric', 'price': Decimal('14')},
			{'name': 'Goa Party Van', 'city': 'goa', 'seats': 8, 'fuel': 'diesel', 'price': Decimal('22')},
		]

		seeded_count = 0
		for data in cab_data:
			cab, created = Cab.objects.get_or_create(
				name=data['name'],
				defaults={
					'owner': owner,
					'city': data['city'],
					'seats': data['seats'],
					'fuel_type': data['fuel'],
					'base_price_per_km': data['price'],
					'system_price_per_km': data['price'] + Decimal(getattr(settings, 'PLATFORM_CAB_MARGIN', 3)),
					'is_active': True,
				}
			)
			if created:
				seeded_count += 1

		self.stdout.write(
			self.style.SUCCESS(f'Cabs seeded successfully. Created {seeded_count} new cabs.')
		)