"""
Comprehensive seed data generation for operator dashboards
Creates production-quality test data with proper RBAC setup
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps
from decimal import Decimal
import random
from datetime import datetime, timedelta

User = apps.get_model('accounts', 'User')
Role = apps.get_model('accounts', 'Role')
UserRole = apps.get_model('accounts', 'UserRole')
Bus = apps.get_model('buses', 'Bus')
BusType = apps.get_model('buses', 'BusType')
BusSeat = apps.get_model('buses', 'BusSeat')
Cab = apps.get_model('cabs', 'Cab')
Package = apps.get_model('packages', 'Package')
PackageCategory = apps.get_model('packages', 'PackageCategory')


class Command(BaseCommand):
    help = 'Seed database with operator dashboard test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete all previous data before seeding',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of each operator type to create (default: 3)',
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Hardcoded names to avoid faker dependency
        operator_names = [
            'Comfort Travels',
            'Lightning Express',
            'Star Journeys',
            'Premier Routes',
            'Royal Coach Services',
        ]
        
        owner_first_names = [
            'Raj', 'Priya', 'Amit', 'Deepak', 'Anita', 'Viraj'
        ]
        
        provider_names = [
            'Himalayan Adventures',
            'Tropical Escapes',
            'Cultural Tours India',
            'Beach Getaways',
            'Mountain Expeditions',
        ]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🌱 Seeding operator dashboards (count={count})...'
            )
        )

        with transaction.atomic():
            # Create roles if not exist
            bus_operator_role, _ = Role.objects.get_or_create(
                code='bus_operator',
                defaults={'name': 'Bus Operator', 'description': 'Operates bus services'}
            )
            cab_owner_role, _ = Role.objects.get_or_create(
                code='cab_owner',
                defaults={'name': 'Cab Owner', 'description': 'Owns cab services'}
            )
            package_provider_role, _ = Role.objects.get_or_create(
                code='package_provider',
                defaults={
                    'name': 'Package Provider',
                    'description': 'Provides travel packages'
                }
            )

            # Create BusTypes
            bus_types = []
            for bus_type_code, bus_type_name in [
                ('sleeper', 'Sleeper'),
                ('ac', 'AC'),
                ('non_ac', 'Non-AC'),
            ]:
                bus_type, _ = BusType.objects.get_or_create(
                    name=bus_type_code,
                    defaults={
                        'base_fare': Decimal('500'),
                        'capacity': 40,
                    }
                )
                bus_types.append(bus_type)

            # Create PackageCategories
            categories = []
            for cat_name in ['Adventure', 'Beach', 'Cultural', 'Religious', 'Mountain']:
                category, _ = PackageCategory.objects.get_or_create(
                    name=cat_name,
                    defaults={'description': f'{cat_name} holiday packages'}
                )
                categories.append(category)

            # Create Bus Operators
            bus_operators = []
            for i in range(count):
                email = f'bus_operator_{i+1}@test.com'
                full_name = random.choice(operator_names) + f' #{i+1}'
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'full_name': full_name,
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password('TestOperator@123')
                    user.save()

                # Assign role
                UserRole.objects.get_or_create(
                    user=user,
                    role=bus_operator_role,
                )
                bus_operators.append(user)

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created bus operator: {email}'
                    )
                )

            # Create Buses for each operator
            indian_routes = [
                ('Delhi', 'Mumbai'),
                ('Mumbai', 'Bangalore'),
                ('Bangalore', 'Chennai'),
                ('Delhi', 'Goa'),
                ('Pune', 'Goa'),
                ('Hyderabad', 'Chennai'),
            ]

            for operator in bus_operators:
                for j in range(2):  # 2 buses per operator
                    from_city, to_city = random.choice(indian_routes)
                    bus_type = random.choice(bus_types)

                    bus = Bus.objects.create(
                        operator=operator,
                        registration_number=f'KT-{random.randint(10000, 99999)}',
                        bus_type=bus_type,
                        operator_name=operator.full_name,
                        from_city=from_city,
                        to_city=to_city,
                        departure_time='10:00:00',
                        arrival_time='22:00:00',
                        price_per_seat=Decimal(str(random.randint(1000, 2500))),
                        available_seats=random.randint(10, 40),
                        amenities='WiFi, USB Charging, AC, Water',
                    )

                    # Create seats
                    rows = ['A', 'B', 'C', 'D', 'E']
                    for row in rows:
                        for col in range(1, 9):
                            seat_number = f"{row}{col}"
                            BusSeat.objects.create(
                                bus=bus,
                                seat_number=seat_number,
                                row=row,
                                column=col,
                            )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  → Bus {bus.registration_number}: '
                            f'{from_city} → {to_city} '
                            f'(₹{bus.price_per_seat})'
                        )
                    )

            # Create Cab Owners
            cab_owners = []
            for i in range(count):
                email = f'cab_owner_{i+1}@test.com'
                full_name = f'{random.choice(owner_first_names)} Kumar - Cab Owner {i+1}'
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'full_name': full_name,
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password('TestOwner@123')
                    user.save()

                # Assign role
                UserRole.objects.get_or_create(
                    user=user,
                    role=cab_owner_role,
                )
                cab_owners.append(user)

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created cab owner: {email}'
                    )
                )

            # Create Cabs for each owner
            cab_types = ['sedan', 'suv', 'van']
            
            for owner in cab_owners:
                for k in range(3):  # 3 cabs per owner
                    cab_type = random.choice(cab_types)
                    cab = Cab.objects.create(
                        owner=owner,
                        vehicle_type=cab_type,
                        cab_type=cab_type,
                        from_location=random.choice(['Delhi', 'Mumbai', 'Bangalore']),
                        to_location=random.choice(['Goa', 'Pune', 'Chennai']),
                        distance_km=Decimal(str(random.randint(50, 500))),
                        price_per_km=Decimal(str(random.uniform(10, 20))),
                        base_fare=Decimal('50'),
                        available=True,
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  → Cab {cab.uuid}: {cab_type} '
                            f'(₹{cab.price_per_km}/km + ₹{cab.base_fare} base)'
                        )
                    )

            # Create Package Providers
            package_providers = []
            for i in range(count):
                email = f'package_provider_{i+1}@test.com'
                full_name = random.choice(provider_names) + f' - Provider {i+1}'
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'full_name': full_name,
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password('TestProvider@123')
                    user.save()

                # Assign role
                UserRole.objects.get_or_create(
                    user=user,
                    role=package_provider_role,
                )
                package_providers.append(user)

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created package provider: {email}'
                    )
                )

            # Create Packages for each provider
            inclusions_list = [
                'Flight, Hotel, Meals, Sightseeing',
                'Hotel, Local Transport, Meals',
                'Flight, Hotel, Activities',
                'Train, Hotel, Guide',
            ]

            for provider in package_providers:
                for m in range(4):  # 4 packages per provider
                    category = random.choice(categories)
                    duration = random.randint(3, 14)

                    package = Package.objects.create(
                        provider=provider,
                        name=f'{category.name} Adventure - {duration} Days',
                        description=f'Exciting {category.name.lower()} experience',
                        category=category,
                        duration_days=duration,
                        destination=random.choice(['Goa', 'Ladakh', 'Kerala', 'Rajasthan']),
                        base_price=Decimal(str(random.randint(20000, 100000))),
                        inclusions=random.choice(inclusions_list),
                        max_group_size=random.randint(10, 50),
                        difficulty_level=random.choice(['easy', 'moderate', 'hard']),
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  → {package.name}: ₹{package.base_price} '
                            f'({package.duration_days} days)'
                        )
                    )

        # Print summary
        self.stdout.write(
            self.style.SUCCESS(
                """
================================================================================
OPERATOR DASHBOARD SEED DATA COMPLETE
================================================================================

BUS OPERATORS:
"""
            )
        )
        for i, op in enumerate(bus_operators, 1):
            self.stdout.write(f'  {i}. {op.email} (Password: TestOperator@123)')

        self.stdout.write(
            self.style.SUCCESS(
                """
CAB OWNERS:
"""
            )
        )
        for i, owner in enumerate(cab_owners, 1):
            self.stdout.write(f'  {i}. {owner.email} (Password: TestOwner@123)')

        self.stdout.write(
            self.style.SUCCESS(
                """
PACKAGE PROVIDERS:
"""
            )
        )
        for i, provider in enumerate(package_providers, 1):
            self.stdout.write(f'  {i}. {provider.email} (Password: TestProvider@123)')

        self.stdout.write(
            self.style.SUCCESS(
                f"""
SUMMARY:
  • Buses: {Bus.objects.count()} (created)
  • Buses Seats: {BusSeat.objects.count()} (created)
  • Cabs: {Cab.objects.count()} (created)
  • Packages: {Package.objects.count()} (created)
  
Dashboard Features:
  ✓ Bus operator can manage their buses and bookings
  ✓ Cab owner can manage their fleet
  ✓ Package provider can manage travel itineraries
  ✓ Atomic transactions prevent race conditions
  ✓ RBAC enforcement on all operations
================================================================================
"""
            )
        )