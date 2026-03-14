from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.buses.models import Bus, BusBooking, BusType
from apps.cabs.models import Cab, CabBooking, Driver
from apps.core.location_models import City, Country, Locality, State
from apps.hotels.models import Property
from apps.packages.models import Package, PackageBooking, PackageCategory, PackageDeparture
from apps.rooms.models import RoomInventory, RoomType


class Command(BaseCommand):
    help = 'Seed deterministic live data for Playwright owner/admin E2E flows.'

    def handle(self, *args, **options):
        admin, _ = User.objects.update_or_create(
            email='admin-live@example.com',
            defaults={
                'full_name': 'Admin Live',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        admin.set_password('AdminPass123')
        admin.save()

        owner, _ = User.objects.update_or_create(
            email='owner-live@example.com',
            defaults={
                'full_name': 'Owner Live',
                'role': 'property_owner',
                'is_active': True,
            },
        )
        owner.set_password('OwnerPass123')
        owner.save()

        bus_operator, _ = User.objects.update_or_create(
            email='bus-live@example.com',
            defaults={
                'full_name': 'Bus Live',
                'role': 'bus_operator',
                'is_active': True,
            },
        )
        bus_operator.set_password('BusPass123')
        bus_operator.save()

        cab_owner, _ = User.objects.update_or_create(
            email='cab-live@example.com',
            defaults={
                'full_name': 'Cab Live',
                'role': 'cab_owner',
                'is_active': True,
            },
        )
        cab_owner.set_password('CabPass123')
        cab_owner.save()

        package_provider, _ = User.objects.update_or_create(
            email='package-live@example.com',
            defaults={
                'full_name': 'Package Live',
                'role': 'package_provider',
                'is_active': True,
            },
        )
        package_provider.set_password('PackagePass123')
        package_provider.save()

        traveler, _ = User.objects.update_or_create(
            email='traveler-live@example.com',
            defaults={
                'full_name': 'Traveler Live',
                'role': 'traveler',
                'is_active': True,
            },
        )
        traveler.set_password('TravelerPass123')
        traveler.save()

        country, _ = Country.objects.get_or_create(code='IN', defaults={'name': 'India', 'display_name': 'India'})
        state, _ = State.objects.get_or_create(
            country=country,
            code='KA',
            defaults={'name': 'Karnataka', 'display_name': 'Karnataka'},
        )
        city, _ = City.objects.update_or_create(
            code='BLR-LIVE',
            defaults={
                'state': state,
                'name': 'Bengaluru',
                'display_name': 'Bengaluru',
                'slug': 'bengaluru-live',
                'latitude': Decimal('12.971600'),
                'longitude': Decimal('77.594600'),
            },
        )
        locality, _ = Locality.objects.update_or_create(
            city=city,
            name='Indiranagar Live',
            defaults={
                'display_name': 'Indiranagar Live',
                'slug': 'indiranagar-live',
                'latitude': Decimal('12.978400'),
                'longitude': Decimal('77.640800'),
            },
        )

        property_obj, _ = Property.objects.update_or_create(
            owner=owner,
            name='Skyline Suites Live',
            defaults={
                'property_type': 'Hotel',
                'city': city,
                'locality': locality,
                'address': '100 Residency Road',
                'description': 'Live E2E hotel property',
                'latitude': Decimal('12.971600'),
                'longitude': Decimal('77.594600'),
                'status': 'approved',
                'agreement_signed': True,
                'is_active': True,
            },
        )
        room_type, _ = RoomType.objects.update_or_create(
            property=property_obj,
            name='Deluxe Room',
            defaults={
                'capacity': 2,
                'max_occupancy': 2,
                'available_count': 5,
                'price_per_night': Decimal('4500.00'),
                'base_price': Decimal('4500.00'),
                'max_guests': 2,
            },
        )

        for day_offset, price in enumerate([4750, 4800, 4900], start=2):
            RoomInventory.objects.update_or_create(
                room_type=room_type,
                date=timezone.now().date() + timedelta(days=day_offset),
                defaults={
                    'available_rooms': 6,
                    'available_count': 6,
                    'booked_count': 4,
                    'price': Decimal(str(price)),
                    'is_closed': False,
                },
            )

        bus_type, _ = BusType.objects.get_or_create(name=BusType.AC, defaults={'base_fare': Decimal('700.00'), 'capacity': 40})
        bus, _ = Bus.objects.update_or_create(
            registration_number='KA-01-LIVE-AC01',
            defaults={
                'operator': bus_operator,
                'bus_type': bus_type,
                'operator_name': 'Bus Live Fleet',
                'from_city': 'Bangalore',
                'to_city': 'Chennai',
                'departure_time': timezone.now().time().replace(second=0, microsecond=0),
                'arrival_time': (timezone.now() + timedelta(hours=6)).time().replace(second=0, microsecond=0),
                'journey_date': timezone.now().date() + timedelta(days=3),
                'price_per_seat': Decimal('999.00'),
                'available_seats': 30,
                'is_active': True,
                'amenities': 'WiFi, AC, Water',
            },
        )
        BusBooking.objects.update_or_create(
            bus=bus,
            user=traveler,
            journey_date=bus.journey_date,
            defaults={
                'contact_email': traveler.email,
                'contact_phone': '9999999996',
                'status': 'confirmed',
                'total_amount': Decimal('1998.00'),
            },
        )

        cab, _ = Cab.objects.update_or_create(
            owner=cab_owner,
            name='Airport Sedan Live',
            defaults={
                'city': 'bangalore',
                'seats': 4,
                'fuel_type': 'petrol',
                'base_price_per_km': Decimal('12.00'),
                'system_price_per_km': Decimal('15.00'),
                'is_active': True,
            },
        )
        driver_user, _ = User.objects.update_or_create(
            email='driver-live@example.com',
            defaults={
                'full_name': 'Driver Live',
                'role': 'traveler',
                'is_active': True,
            },
        )
        driver_user.set_password('DriverPass123')
        driver_user.save()
        driver, _ = Driver.objects.update_or_create(
            user=driver_user,
            defaults={
                'cab': cab,
                'license_number': 'KA-LIVE-DRV-01',
                'phone': '9999999995',
                'city': 'bangalore',
                'status': 'available',
                'rating': Decimal('4.8'),
                'total_trips': 12,
                'is_verified': True,
            },
        )
        CabBooking.objects.update_or_create(
            cab=cab,
            user=traveler,
            booking_date=timezone.now().date() + timedelta(days=1),
            defaults={
                'driver': driver,
                'pickup_address': 'MG Road',
                'drop_address': 'Airport',
                'distance_km': Decimal('10.00'),
                'base_fare': Decimal('50.00'),
                'price_per_km': Decimal('15.00'),
                'total_price': Decimal('200.00'),
                'final_price': Decimal('210.00'),
                'status': 'completed',
            },
        )

        package_category, _ = PackageCategory.objects.get_or_create(name='Weekend Trips')
        package, _ = Package.objects.update_or_create(
            provider=package_provider,
            name='Coorg Escape Live',
            defaults={
                'category': package_category,
                'description': 'Live E2E package',
                'destination': 'Coorg',
                'duration_days': 3,
                'base_price': Decimal('12000.00'),
                'is_active': True,
            },
        )
        departure, _ = PackageDeparture.objects.update_or_create(
            package=package,
            departure_date=timezone.now().date() + timedelta(days=15),
            defaults={
                'return_date': timezone.now().date() + timedelta(days=18),
                'total_slots': 20,
                'booked_slots': 6,
                'is_active': True,
            },
        )
        PackageBooking.objects.update_or_create(
            package=package,
            user=traveler,
            departure=departure,
            defaults={
                'adults': 2,
                'children': 0,
                'adult_price': Decimal('12000.00'),
                'child_price': Decimal('0.00'),
                'subtotal': Decimal('24000.00'),
                'group_discount': Decimal('0.00'),
                'promo_discount': Decimal('0.00'),
                'gst': Decimal('1200.00'),
                'total_amount': Decimal('25200.00'),
                'status': 'confirmed',
            },
        )

        self.stdout.write(self.style.SUCCESS('Seeded live Playwright owner/admin data.'))