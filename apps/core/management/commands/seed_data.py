from datetime import timedelta, time
from decimal import Decimal
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils import timezone

User = apps.get_model('accounts', 'User')
Bus = apps.get_model('buses', 'Bus')
BusType = apps.get_model('buses', 'BusType')
PropertyApproval = apps.get_model('dashboard_admin', 'PropertyApproval')
Property = apps.get_model('hotels', 'Property')
PropertyAmenity = apps.get_model('hotels', 'PropertyAmenity')
PropertyImage = apps.get_model('hotels', 'PropertyImage')
MealPlan = apps.get_model('meals', 'MealPlan')
Package = apps.get_model('packages', 'Package')
PackageCategory = apps.get_model('packages', 'PackageCategory')
PackageItinerary = apps.get_model('packages', 'PackageItinerary')
RoomInventory = apps.get_model('rooms', 'RoomInventory')
RoomType = apps.get_model('rooms', 'RoomType')


class Command(BaseCommand):
    help = 'Seed MVP data for hotels, buses, and packages.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding MVP data...')
        owner = self._get_or_create_user('owner@zygotrip.com', 'Property Owner')
        provider = self._get_or_create_user('provider@zygotrip.com', 'Package Provider')

        self._seed_hotels(owner)
        self._seed_buses()
        self._seed_packages(provider)

        self.stdout.write('Seed data complete.')

    def _get_or_create_user(self, email, full_name):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'full_name': full_name, 'is_active': True},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password', 'updated_at'])
        return user

    def _seed_hotels(self, owner):
        cities = ['Delhi', 'Mumbai', 'Bangalore', 'Chennai', 'Goa', 'Jaipur']
        amenity_labels = ['Free WiFi', 'Breakfast Included', 'Pool', 'Parking']
        room_types = [
            ('Standard Room', Decimal('2500.00')),
            ('Deluxe Room', Decimal('4200.00')),
            ('Suite', Decimal('6800.00')),
        ]
        today = timezone.now().date()

        for index in range(20):
            city = cities[index % len(cities)]
            name = f'Hotel {index + 1} {city}'
            property_obj, created = Property.objects.get_or_create(
                name=name,
                defaults={
                    'owner': owner,
                    'city': city,
                    'country': 'India',
                    'address': f'{100 + index} Main Street, {city}',
                    'description': 'Comfortable stay with modern amenities.',
                    'rating': Decimal('4.2'),
                    'base_price': room_types[0][1],
                    'is_active': True,
                },
            )
            if not created and property_obj.base_price == 0:
                property_obj.base_price = room_types[0][1]
                property_obj.save(update_fields=['base_price', 'updated_at'])

            PropertyApproval.objects.get_or_create(
                property=property_obj,
                defaults={'status': PropertyApproval.STATUS_APPROVED, 'is_active': True},
            )

            for label in amenity_labels:
                PropertyAmenity.objects.get_or_create(property=property_obj, name=label)

            PropertyImage.objects.get_or_create(
                property=property_obj,
                image_url='https://images.unsplash.com/photo-1501117716987-c8e1ecb210d6',
                defaults={'is_featured': True},
            )

            for room_name, price in room_types:
                room_type, _ = RoomType.objects.get_or_create(
                    property=property_obj,
                    name=room_name,
                    defaults={
                        'description': f'{room_name} with premium comfort.',
                        'base_price': price,
                        'max_guests': 2,
                        'bed_type': 'queen',
                    },
                )
                for offset in range(30):
                    inventory_date = today + timedelta(days=offset)
                    RoomInventory.objects.get_or_create(
                        room_type=room_type,
                        date=inventory_date,
                        defaults={'available_count': 10},
                    )

            meal_plans = [
                ('breakfast', 'Breakfast', Decimal('350.00')),
                ('half_board', 'Half Board', Decimal('900.00')),
                ('full_board', 'Full Board', Decimal('1400.00')),
            ]
            for meal_type, name_label, price in meal_plans:
                MealPlan.objects.get_or_create(
                    property=property_obj,
                    meal_type=meal_type,
                    defaults={
                        'name': name_label,
                        'description': f'{name_label} plan',
                        'price': price,
                    },
                )

        self.stdout.write('Hotels seeded.')

    def _seed_buses(self):
        bus_types = [
            ('sleeper', Decimal('600.00'), 30),
            ('semi_sleeper', Decimal('500.00'), 36),
            ('ac', Decimal('700.00'), 40),
            ('seater', Decimal('450.00'), 45),
        ]
        for type_code, base_fare, capacity in bus_types:
            BusType.objects.get_or_create(
                name=type_code,
                defaults={'base_fare': base_fare, 'capacity': capacity},
            )

        routes = [
            ('Delhi', 'Jaipur'),
            ('Mumbai', 'Pune'),
            ('Bangalore', 'Chennai'),
            ('Goa', 'Mumbai'),
            ('Hyderabad', 'Bangalore'),
            ('Delhi', 'Lucknow'),
        ]
        departure_times = [time(6, 30), time(9, 0), time(14, 15), time(18, 45)]
        today = timezone.now().date()

        for index in range(30):
            from_city, to_city = routes[index % len(routes)]
            bus_type = BusType.objects.order_by('id').first()
            if not bus_type:
                continue

            Bus.objects.get_or_create(
                registration_number=f'ZY-BUS-{index + 1:03d}',
                defaults={
                    'operator_name': f'Zygotrip Operator {index + 1}',
                    'bus_type': bus_type,
                    'from_city': from_city,
                    'to_city': to_city,
                    'departure_time': departure_times[index % len(departure_times)],
                    'arrival_time': time(22, 0),
                    'journey_date': today + timedelta(days=(index % 30)),
                    'price_per_seat': Decimal('650.00'),
                    'available_seats': 35,
                    'amenities': 'WiFi, Water, Charging',
                    'is_active': True,
                },
            )

        self.stdout.write('Buses seeded.')

    def _seed_packages(self, provider):
        categories = [
            ('Adventure', 'Adventure experiences'),
            ('Beach', 'Beach getaways'),
            ('Cultural', 'Cultural tours'),
        ]
        for name, description in categories:
            PackageCategory.objects.get_or_create(name=name, defaults={'description': description})

        destinations = ['Goa', 'Jaipur', 'Kerala', 'Manali', 'Udaipur']
        category = PackageCategory.objects.order_by('id').first()

        for index in range(10):
            destination = destinations[index % len(destinations)]
            name = f'{destination} Escape {index + 1}'
            package, created = Package.objects.get_or_create(
                name=name,
                defaults={
                    'provider': provider,
                    'description': 'Curated package with stays and activities.',
                    'category': category,
                    'duration_days': 3 + (index % 3),
                    'destination': destination,
                    'base_price': Decimal('15000.00') + Decimal(index * 500),
                    'rating': Decimal('4.3'),
                    'review_count': 12 + index,
                    'image_url': 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee',
                    'inclusions': 'Hotel, Breakfast, Transfers',
                    'exclusions': 'Flights, Personal expenses',
                    'max_group_size': 25,
                    'is_active': True,
                },
            )
            if created:
                for day in range(1, package.duration_days + 1):
                    PackageItinerary.objects.get_or_create(
                        package=package,
                        day_number=day,
                        defaults={
                            'title': f'Day {day} Activities',
                            'description': 'Guided experiences and leisure time.',
                            'meals_included': 'B',
                            'accommodation': '3-star hotel',
                        },
                    )

        self.stdout.write('Packages seeded.')