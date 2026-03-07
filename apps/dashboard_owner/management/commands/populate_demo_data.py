"""
Management command to populate demo data for the owner dashboard.
Creates sample properties, bookings, check-ins, etc. for testing.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta, datetime
import random

from apps.accounts.models import User
from apps.hotels.models import Property, PropertyAmenity
from apps.rooms.models import RoomType, RoomInventory
from apps.booking.models import Booking
from apps.core.models import City, Locality


class Command(BaseCommand):
    help = 'Populate demo data for testing owner dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--owner_email',
            type=str,
            default='owner@example.com',
            help='Email of the property owner to create properties for'
        )
        parser.add_argument(
            '--properties',
            type=int,
            default=3,
            help='Number of properties to create'
        )
        parser.add_argument(
            '--bookings',
            type=int,
            default=15,
            help='Number of bookings to create'
        )

    def handle(self, *args, **options):
        owner_email = options['owner_email']
        num_properties = options['properties']
        num_bookings = options['bookings']

        # Get or create owner
        owner, created = User.objects.get_or_create(
            email=owner_email,
            defaults={
                'full_name': owner_email.split('@')[0].title(),
                'role': 'property_owner',
            }
        )
        if created:
            owner.set_password('testpass123')
            owner.save()
            self.stdout.write(f'Created owner: {owner.email}')
        else:
            self.stdout.write(f'Using existing owner: {owner.email}')

        # Amenities list
        amenities_list = [
            'Free WiFi', 'AC', 'TV', 'Hot Water', 'Parking',
            'Swimming Pool', 'Gym', 'Restaurant', 'Spa', 'Laundry'
        ]


        # Try to get a city; if none exist, skip demo data creation
        city = City.objects.first()
        if not city:
            self.stdout.write(self.style.WARNING(
                'No cities found. Please add cities via admin panel first. Skipping demo data creation.'
            ))
            return
        # Create properties
        property_names = [
            'Sunset Beach Resort',
            'Mountain Bliss Hotel',
            'Urban Star Apartments'
        ]

        properties = []
        for i in range(min(num_properties, len(property_names))):
            
            # Generate coordinates slightly offset from center (max 6 decimal places)
            from decimal import Decimal
            base_lat = Decimal('28.613900') + Decimal(str(i * 0.01))
            base_lng = Decimal('77.209000') + Decimal(str(i * 0.01))
            prop, created = Property.objects.get_or_create(
                name=property_names[i],
                owner=owner,
                defaults={
                    'slug': slugify(property_names[i]),
                    'property_type': 'Hotel',
                    'city': city,
                    'address': f'Address {i+1}, Demo City',
                    'description': f'Beautifully designed {property_names[i]} with premium amenities.',
                    'latitude': base_lat,
                    'longitude': base_lng,
                        'rating': 4.0 if i == 0 else 4 if i == 1 else 3,
                    'review_count': 50 + (i * 20),
                    'star_category': 3 + i,
                    'commission_percentage': 5.0,
                    'status': 'approved',
                    'has_free_cancellation': True,
                    'cancellation_hours': 48,
                }
            )
            properties.append(prop)
            
            if created:
                # Add amenities
                for amenity_name in ['Free WiFi', 'AC', 'TV', 'Hot Water']:
                    PropertyAmenity.objects.get_or_create(
                        property=prop,
                        name=amenity_name
                    )
                self.stdout.write(f'Created property: {prop.name}')
            else:
                self.stdout.write(f'Using existing property: {prop.name}')

            # Create room types
            room_types = []
            base_room_price = 2000 + (i * 1000)
            room_type_data = [
                {'type': 'Single', 'capacity': 1, 'price': base_room_price},
                {'type': 'Double', 'capacity': 2, 'price': base_room_price + 500},
                {'type': 'Suite', 'capacity': 4, 'price': base_room_price + 1500},
            ]


            for rt_data in room_type_data:
                room_type, created = RoomType.objects.get_or_create(
                    property=prop,
                    name=rt_data['type'],
                    defaults={
                        'capacity': rt_data['capacity'],
                        'base_price': rt_data['price'],
                    }
                )
                room_types.append(room_type)
                if created:
                    self.stdout.write(f'  Created room type: {rt_data["type"]}')
            # Create room inventory for next 90 days
            today = timezone.now().date()
            for days_ahead in range(90):
                current_date = today + timedelta(days=days_ahead)
                # Vary prices - higher on weekends
                is_weekend = current_date.weekday() >= 5
                price_multiplier = 1.2 if is_weekend else 1.0


                for room_type in room_types:
                    price = float(room_type.base_price) * price_multiplier
                    RoomInventory.objects.get_or_create(
                        room_type=room_type,
                        date=current_date,
                        defaults={
                            'available_rooms': 3,
                            'price': round(price, 2),
                            'is_closed': False,
                        }
                    )
        # Create bookings
        customers = []
        for i in range(5):  # Create 5 test customers
            customer, _ = User.objects.get_or_create(
                email=f'customer{i}@example.com',
                defaults={
                    'full_name': f'Customer {i}',
                    'role': 'traveler',
                }
            )
            customers.append(customer)

        booking_statuses = ['confirmed', 'pending', 'cancelled']
        created_bookings = 0


        for i in range(num_bookings):
            prop = random.choice(properties)
            room_type = prop.room_types.all().first()
            customer = random.choice(customers)
            # Generate date range
            start_offset = random.randint(-30, 60)
            check_in = timezone.now().date() + timedelta(days=start_offset)
            nights = random.randint(1, 7)
            check_out = check_in + timedelta(days=nights)


            # Calculate price
            inventory = RoomInventory.objects.filter(
                room_type=room_type,
                date=check_in
            ).first()
            price = float(inventory.price) if inventory else float(room_type.base_price)
            gross_amount = int(price * nights)
            status = random.choice(booking_statuses)
            refund_amount = 0
            cancelled_at = None

            if status == 'cancelled':
                cancelled_at = timezone.now() - timedelta(days=random.randint(1, 15))
                # Calculate refund
                days_before_checkin = (check_in - timezone.now().date()).days
                if days_before_checkin >= 2:
                    refund_amount = int(gross_amount * 0.9)  # 90% refund
                else:
                    refund_amount = int(gross_amount * 0.5)  # 50% refund


            booking, created = Booking.objects.get_or_create(
                public_booking_id=f'DEMO{i:05d}',
                defaults={
                    'user': customer,
                    'property': prop,
                    'check_in': check_in,
                    'check_out': check_out,
                    'guest_name': customer.full_name,
                    'guest_email': customer.email,
                    'guest_phone': f'98{random.randint(10000000, 99999999)}',
                    'gross_amount': gross_amount,
                    'commission_amount': int(gross_amount * 0.05),
                    'gst_amount': int(gross_amount * 0.18),
                    'net_payable_to_hotel': int(gross_amount * 0.77),
                    'refund_amount': refund_amount,
                    'status': status if status in ['confirmed', 'pending', 'cancelled'] else 'confirmed',
                }
            )
            if created:
                created_bookings += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully created demo data:\n'
                f'  - Properties: {len(properties)}\n'
                f'  - Room Types per property: 3\n'
                f'  - Booking Inventories: 90 days × room types\n'
                f'  - Customers: 5\n'
                f'  - New Bookings: {created_bookings}\n'
                f'\n  Owner Email: {owner.email}\n'
                f'  Default Password: testpass123\n'
            )
        )
