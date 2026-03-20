from datetime import timedelta
from decimal import Decimal
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from datetime import time

Permission = apps.get_model('accounts', 'Permission')
Role = apps.get_model('accounts', 'Role')
RolePermission = apps.get_model('accounts', 'RolePermission')
User = apps.get_model('accounts', 'User')
UserRole = apps.get_model('accounts', 'UserRole')
PropertyApproval = apps.get_model('dashboard_admin', 'PropertyApproval')
Property = apps.get_model('hotels', 'Property')
City = apps.get_model('core', 'City')
MealPlan = apps.get_model('meals', 'MealPlan')
Promo = apps.get_model('promos', 'Promo')
RoomInventory = apps.get_model('rooms', 'RoomInventory')
RoomType = apps.get_model('rooms', 'RoomType')
RoomAmenity = apps.get_model('rooms', 'RoomAmenity')
Wallet = apps.get_model('wallet', 'Wallet')
Bus = apps.get_model('buses', 'Bus')
BusType = apps.get_model('buses', 'BusType')
BusSeat = apps.get_model('buses', 'BusSeat')
Package = apps.get_model('packages', 'Package')
PackageCategory = apps.get_model('packages', 'PackageCategory')
PackageItinerary = apps.get_model('packages', 'PackageItinerary')


class Command(BaseCommand):
    help = 'Seed data for e2e tests'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('SET statement_timeout TO 0')

        with transaction.atomic():
            roles = {
                'product_owner': 'Product Owner',
                'property_owner': 'Property Owner',
                'staff_admin': 'Staff Admin',
                'finance_admin': 'Finance Admin',
                'customer': 'Customer',
            }
            for code, name in roles.items():
                Role.objects.get_or_create(code=code, defaults={'name': name})

            permissions = {
                'manage_properties': 'Manage Properties',
                'approve_properties': 'Approve Properties',
                'manage_finance': 'Manage Finance',
                'book_hotels': 'Book Hotels',
            }
            for code, name in permissions.items():
                Permission.objects.get_or_create(code=code, defaults={'name': name})

            role_permissions = {
                'product_owner': ['manage_properties', 'approve_properties'],
                'property_owner': ['manage_properties'],
                'staff_admin': ['approve_properties'],
                'finance_admin': ['manage_finance'],
                'customer': ['book_hotels'],
            }
            for role_code, perm_codes in role_permissions.items():
                role = Role.objects.get(code=role_code)
                for perm_code in perm_codes:
                    permission = Permission.objects.get(code=perm_code)
                    RolePermission.objects.get_or_create(role=role, permission=permission)

            users = {
                'product_owner@test.com': 'product_owner',
                'property_owner@test.com': 'property_owner',
                'staff_admin@test.com': 'staff_admin',
                'finance_admin@test.com': 'finance_admin',
                'customer@test.com': 'customer',
            }
            for email, role_code in users.items():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={'full_name': email.split('@')[0].replace('_', ' ').title()},
                )
                user.set_password('Test@123')
                user.save()
                role = Role.objects.get(code=role_code)
                UserRole.objects.get_or_create(user=user, role=role)

            owner = User.objects.get(email='property_owner@test.com')
            
            # Create Indian Hotels with Google Maps coordinates
            hotel_data = [
                {
                    'name': 'Taj Gardens Delhi',
                    'city': 'Delhi',
                    'country': 'India',
                    'address': 'New Delhi, India',
                    'description': 'Luxury hotel with world-class amenities in the heart of Delhi.',
                    'rating': Decimal('4.8'),
                    'latitude': Decimal('28.6139'),
                    'longitude': Decimal('77.2090'),
                    'base_price': Decimal('4500.00'),
                    'room_name': 'Deluxe Room',
                    'room_price': Decimal('4500.00'),
                    'bed_type': 'double',
                    'room_size': 35,
                },
                {
                    'name': 'Marine Bay Mumbai',
                    'city': 'Mumbai',
                    'country': 'India',
                    'address': 'Bandra, Mumbai, India',
                    'description': 'Beachfront luxury property with stunning sea views.',
                    'rating': Decimal('4.7'),
                    'latitude': Decimal('19.0596'),
                    'longitude': Decimal('72.8295'),
                    'base_price': Decimal('5500.00'),
                    'room_name': 'Ocean View Suite',
                    'room_price': Decimal('5500.00'),
                    'bed_type': 'king',
                    'room_size': 45,
                },
                {
                    'name': 'Goa Paradise Beach Resort',
                    'city': 'Goa',
                    'country': 'India',
                    'address': 'Candolim, Goa, India',
                    'description': 'Tropical beach resort with water sports and spa.',
                    'rating': Decimal('4.6'),
                    'latitude': Decimal('15.4909'),
                    'longitude': Decimal('73.8305'),
                    'base_price': Decimal('3500.00'),
                    'room_name': 'Beach Hut',
                    'room_price': Decimal('3500.00'),
                    'bed_type': 'twin',
                    'room_size': 30,
                },
                {
                    'name': 'Bangalore Tech Park Hotel',
                    'city': 'Bangalore',
                    'country': 'India',
                    'address': 'Whitefield, Bangalore, India',
                    'description': 'Modern business hotel in tech hub.',
                    'rating': Decimal('4.5'),
                    'latitude': Decimal('13.0827'),
                    'longitude': Decimal('77.6055'),
                    'base_price': Decimal('3000.00'),
                    'room_name': 'Executive Room',
                    'room_price': Decimal('3000.00'),
                    'bed_type': 'queen',
                    'room_size': 32,
                },
                {
                    'name': 'Chennai Pearl Hotel',
                    'city': 'Chennai',
                    'country': 'India',
                    'address': 'Marina Beach, Chennai, India',
                    'description': 'Beachfront hotel with traditional South Indian cuisine.',
                    'rating': Decimal('4.4'),
                    'latitude': Decimal('13.0499'),
                    'longitude': Decimal('80.2824'),
                    'base_price': Decimal('2800.00'),
                    'room_name': 'Sea Facing Room',
                    'room_price': Decimal('2800.00'),
                    'bed_type': 'double',
                    'room_size': 28,
                },
            ]
            
            # Meal plan templates (4 types for each property)
            meal_templates = [
                ('breakfast', 'Breakfast Only', Decimal('500.00'), '🍳'),
                ('half_board', 'Half Board (Breakfast + Lunch)', Decimal('1200.00'), '🍽️'),
                ('full_board', 'Full Board (All Meals)', Decimal('1800.00'), '🥘'),
                ('all_inclusive', 'All Inclusive (Meals + Drinks)', Decimal('2300.00'), '🍷'),
            ]
            meal_code_map = {
                'breakfast': 'R+B',
                'half_board': 'R+B+L/D',
                'full_board': 'R+A',
                'all_inclusive': 'R+A',
            }
            
            for hotel in hotel_data:
                room_name = hotel.pop('room_name')
                room_price = hotel.pop('room_price')
                bed_type = hotel.pop('bed_type')
                room_size = hotel.pop('room_size')
                hotel.pop('base_price', None)
                city_name = hotel.pop('city')
                city_obj = City.objects.filter(name=city_name).first()
                if city_obj is None:
                    city_obj = City.objects.create(name=city_name, is_active=True)
                
                property_obj, _ = Property.objects.get_or_create(
                    name=hotel['name'],
                    owner=owner,
                    defaults={**hotel, 'city': city_obj},
                )
                approval, _ = PropertyApproval.objects.get_or_create(property=property_obj)
                approval.status = PropertyApproval.STATUS_APPROVED
                approval.save(update_fields=['status', 'updated_at'])

                room, _ = RoomType.objects.get_or_create(
                    property=property_obj,
                    name=room_name,
                    defaults={
                        'description': f'{room_name} with modern amenities.',
                        'base_price': room_price,
                        'max_guests': 2,
                        'bed_type': bed_type,
                        'room_size_sqm': room_size,
                    },
                )
                
                # Add room amenities
                amenities_list = [
                    ('WiFi', '📶'),
                    ('Air Conditioning', '❄️'),
                    ('Hot Water', '🚿'),
                    ('Television', '📺'),
                    ('Mini Bar', '🍹'),
                    ('Safe Box', '🔒'),
                    ('Work Desk', '💼'),
                ]
                for amenity_name, icon in amenities_list:
                    RoomAmenity.objects.get_or_create(
                        room_type=room,
                        name=amenity_name,
                        defaults={'icon': icon},
                    )
                
                # Create 4 meal plans per property
                for meal_type, meal_name, meal_price, icon in meal_templates:
                    meal_code = meal_code_map.get(meal_type, 'R')
                    MealPlan.objects.get_or_create(
                        code=meal_code,
                        defaults={
                            'name': meal_name,
                            'display_name': meal_name,
                            'icon': icon,
                            'description': f'{meal_name} included in your stay',
                            'is_active': True,
                        },
                    )

                today = timezone.now().date()
                for offset in range(0, 10):
                    inventory, _ = RoomInventory.objects.get_or_create(
                        room_type=room,
                        date=today + timedelta(days=offset),
                        defaults={'available_count': 50},
                    )
                    if inventory.available_count != 50:
                        inventory.available_count = 50
                        inventory.save(update_fields=['available_count'])

            # Normalize inventory for all room types (legacy and new)
            today = timezone.now().date()
            for room in RoomType.objects.all():
                for offset in range(0, 10):
                    inventory, _ = RoomInventory.objects.get_or_create(
                        room_type=room,
                        date=today + timedelta(days=offset),
                        defaults={'available_count': 50},
                    )
                    if inventory.available_count != 50:
                        inventory.available_count = 50
                        inventory.save(update_fields=['available_count'])

            Promo.objects.get_or_create(
                code='WELCOME10',
                defaults={
                    'discount_type': Promo.TYPE_PERCENT,
                    'value': Decimal('10.00'),
                    'max_uses': 100,
                },
            )

            customer = User.objects.get(email='customer@test.com')
            wallet, _ = Wallet.objects.get_or_create(user=customer)
            if wallet.balance < Decimal('15000.00'):
                wallet.balance = Decimal('15000.00')
                wallet.save(update_fields=['balance', 'updated_at'])

            # Create Bus Types
            bus_types_data = [
                {'name': BusType.SLEEPER, 'base_fare': Decimal('800.00'), 'capacity': 30},
                {'name': BusType.SEMI_SLEEPER, 'base_fare': Decimal('600.00'), 'capacity': 40},
                {'name': BusType.AC, 'base_fare': Decimal('700.00'), 'capacity': 45},
                {'name': BusType.NON_AC, 'base_fare': Decimal('400.00'), 'capacity': 50},
                {'name': BusType.VOLVO, 'base_fare': Decimal('1000.00'), 'capacity': 35},
                {'name': BusType.SEATER, 'base_fare': Decimal('500.00'), 'capacity': 50},
            ]
            
            for bus_type_data in bus_types_data:
                BusType.objects.get_or_create(name=bus_type_data['name'], defaults=bus_type_data)

            # Create Sample Buses (Indian Routes)
            buses_data = [
                {
                    'registration_number': 'DL-01-AB-1234',
                    'bus_type_name': BusType.VOLVO,
                    'operator_name': 'RedBus Express',
                    'from_city': 'Delhi',
                    'to_city': 'Jaipur',
                    'departure_time': time(22, 0),
                    'arrival_time': time(6, 0),
                    'price_per_seat': Decimal('1200.00'),
                    'available_seats': 25,
                    'amenities': 'WiFi, USB Charging, Pillow, Blanket, Refreshments',
                },
                {
                    'registration_number': 'MH-02-CD-5678',
                    'bus_type_name': BusType.AC,
                    'operator_name': 'Greyhound Travels',
                    'from_city': 'Mumbai',
                    'to_city': 'Goa',
                    'departure_time': time(20, 0),
                    'arrival_time': time(8, 0),
                    'price_per_seat': Decimal('1500.00'),
                    'available_seats': 35,
                    'amenities': 'AC, WiFi, Meal Service, Entertainment System',
                },
                {
                    'registration_number': 'KA-03-EF-9012',
                    'bus_type_name': BusType.SEATER,
                    'operator_name': 'Shrinath Travels',
                    'from_city': 'Bangalore',
                    'to_city': 'Hyderabad',
                    'departure_time': time(14, 30),
                    'arrival_time': time(20, 30),
                    'price_per_seat': Decimal('600.00'),
                    'available_seats': 40,
                    'amenities': 'Fan, Basic Amenities',
                },
            ]
            
            for bus_data in buses_data:
                bus_type_name = bus_data.pop('bus_type_name')
                bus_type = BusType.objects.get(name=bus_type_name)
                
                bus, _ = Bus.objects.get_or_create(
                    registration_number=bus_data['registration_number'],
                    defaults={**bus_data, 'bus_type': bus_type},
                )
                
                # Create seats for the bus
                if bus.seats.count() == 0:
                    rows = ['A', 'B', 'C', 'D', 'E']
                    cols = range(1, 11)
                    ladies_seats = ['A1', 'A2', 'B1', 'B2']
                    
                    for row in rows:
                        for col in cols:
                            seat_number = f'{row}{col}'
                            BusSeat.objects.get_or_create(
                                bus=bus,
                                seat_number=seat_number,
                                defaults={
                                    'row': row,
                                    'column': col,
                                    'is_ladies_seat': seat_number in ladies_seats,
                                },
                            )

            # Create Package Categories
            category_names = ['Adventure', 'Beach', 'Cultural', 'Mountain', 'Shopping']
            for cat_name in category_names:
                PackageCategory.objects.get_or_create(name=cat_name, defaults={'description': f'{cat_name} holiday packages'})

            # Create Holiday Packages (India)
            packages_data = [
                {
                    'name': 'Goa Beach Escape',
                    'category_name': 'Beach',
                    'description': 'Experience paradise with this 3-day Goa beach package including water sports and nightlife.',
                    'duration_days': 3,
                    'destination': 'Goa',
                    'base_price': Decimal('12000.00'),
                    'rating': Decimal('4.6'),
                    'review_count': 234,
                    'inclusions': 'Hotel Stay, Airport Transfer, Beach Activities, Meals',
                    'exclusions': 'Personal Expenses, Tips',
                    'difficulty_level': 'easy',
                    'max_group_size': 25,
                },
                {
                    'name': 'Jaipur Palace Tour',
                    'category_name': 'Cultural',
                    'description': 'Explore the Pink City with visits to Hawa Mahal, City Palace, and Jantar Mantar.',
                    'duration_days': 2,
                    'destination': 'Jaipur',
                    'base_price': Decimal('8500.00'),
                    'rating': Decimal('4.7'),
                    'review_count': 456,
                    'inclusions': 'Hotel, Guide, Entrance Fees, Meals',
                    'exclusions': 'Travel to Jaipur',
                    'difficulty_level': 'easy',
                    'max_group_size': 30,
                },
                {
                    'name': 'Himalayan Trek',
                    'category_name': 'Adventure',
                    'description': 'Challenging 5-day trek in the Himalayas with experienced guides and camping.',
                    'duration_days': 5,
                    'destination': 'Manali',
                    'base_price': Decimal('18000.00'),
                    'rating': Decimal('4.8'),
                    'review_count': 345,
                    'inclusions': 'Accommodation, Meals, Guide, Equipment',
                    'exclusions': 'Personal Gear, Permits',
                    'difficulty_level': 'hard',
                    'max_group_size': 15,
                },
            ]
            
            for pkg_data in packages_data:
                category_name = pkg_data.pop('category_name')
                category = PackageCategory.objects.get(name=category_name)
                
                package, _ = Package.objects.get_or_create(
                    name=pkg_data['name'],
                    defaults={**pkg_data, 'category': category},
                )
                
                # Create itinerary if doesn't exist
                if package.itinerary.count() == 0:
                    for day in range(1, package.duration_days + 1):
                        PackageItinerary.objects.create(
                            package=package,
                            day_number=day,
                            title=f'Day {day} Activities',
                            description=f'Explore attractions on day {day} with our expert guides.',
                            meals_included='BLD',
                            accommodation='Hotel' if day < package.duration_days else 'Check-out',
                        )

            # Initialize InventoryCalendar for checkout flow reliability
            from apps.inventory.services import init_calendar
            start_cal = timezone.now().date()
            end_cal = start_cal + timedelta(days=30)
            all_room_types = RoomType.objects.order_by('id')[:20]
            for rt in all_room_types:
                total_rooms_count = getattr(rt, 'available_count', 10) or 10
                init_calendar(rt, start_cal, end_cal, total_rooms=total_rooms_count)
                self.stdout.write(f'  InventoryCalendar initialized: {rt.name}')

        # Print seeded credentials
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('ZYGOTRIP TEST CREDENTIALS'))
        self.stdout.write(self.style.SUCCESS('='*80))
        test_users = [
            ('product_owner@test.com', 'Product Owner'),
            ('property_owner@test.com', 'Property Owner'),
            ('finance_admin@test.com', 'Finance Admin'),
            ('staff_admin@test.com', 'Staff Admin'),
            ('customer@test.com', 'Customer'),
        ]
        for email, role_name in test_users:
            self.stdout.write(f'\n{role_name}:')
            self.stdout.write(f'  Email: {email}')
            self.stdout.write(f'  Password: Test@123')
        self.stdout.write(self.style.SUCCESS('\n' + '='*80 + '\n'))