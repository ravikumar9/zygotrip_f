"""Seed 25 OTA-grade demo hotels with rooms, images, and amenities."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.hotels.models import Property, PropertyImage, PropertyAmenity
from apps.rooms.models import RoomType
from apps.dashboard_admin.models import PropertyApproval
from apps.core.location_models import Country, State, City, Locality
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds 25 demo hotels with complete data for OTA testing'

    def handle(self, *args, **options):
        self.stdout.write('Seeding 25 demo hotels...')
        
        # Get or create admin user
        admin, _ = User.objects.get_or_create(
            email='admin@zygotrip.com',
            defaults={
                'full_name': 'Admin User',
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        # Create location hierarchy: Country → State → City
        country, _ = Country.objects.get_or_create(
            code='IN',
            defaults={'name': 'India', 'display_name': 'India', 'is_active': True}
        )
        
        # Get or create states
        states_data = [
            {'code': 'MH', 'name': 'Maharashtra', 'display_name': 'Maharashtra'},
            {'code': 'DL', 'name': 'Delhi', 'display_name': 'Delhi'},
            {'code': 'KA', 'name': 'Karnataka', 'display_name': 'Karnataka'},
            {'code': 'GA', 'name': 'Goa', 'display_name': 'Goa'},
            {'code': 'RJ', 'name': 'Rajasthan', 'display_name': 'Rajasthan'},
        ]
        
        states = {}
        for state_data in states_data:
            state, _ = State.objects.get_or_create(
                country=country,
                code=state_data['code'],
                defaults={
                    'name': state_data['name'],
                    'display_name': state_data['display_name'],
                    'is_active': True
                }
            )
            states[state_data['name']] = state
        
        # Get or create cities
        cities_data = [
            {'name': 'Mumbai', 'state_name': 'Maharashtra', 'code': 'MUMBAI'},
            {'name': 'Delhi', 'state_name': 'Delhi', 'code': 'DELHI'},
            {'name': 'Bangalore', 'state_name': 'Karnataka', 'code': 'BANGALORE'},
            {'name': 'Goa', 'state_name': 'Goa', 'code': 'GOA'},
            {'name': 'Jaipur', 'state_name': 'Rajasthan', 'code': 'JAIPUR'},
        ]
        
        cities = []
        for city_data in cities_data:
            state = states[city_data['state_name']]
            city, _ = City.objects.get_or_create(
                state=state,
                code=city_data['code'],
                defaults={
                    'name': city_data['name'],
                    'display_name': city_data['name'],
                    'latitude': Decimal(f"{random.uniform(10, 30):.6f}"),
                    'longitude': Decimal(f"{random.uniform(70, 85):.6f}"),
                    'is_active': True
                }
            )
            cities.append(city)
        
        # Get or create localities (optional - cities are enough)
        localities_data = [
            ('Andheri West', cities[0]),
            ('Bandra', cities[0]),
            ('Connaught Place', cities[1]),
            ('Koramangala', cities[2]),
            ('Candolim Beach', cities[3]),
            ('Old Jaipur', cities[4]),
        ]
        
        localities = []
        for loc_name, city in localities_data:
            loc, _ = Locality.objects.get_or_create(
                name=loc_name,
                city=city,
                defaults={
                    'display_name': loc_name,
                    'latitude': city.latitude + Decimal('0.01'),
                    'longitude': city.longitude + Decimal('0.01'),
                    'is_active': True
                }
            )
            localities.append(loc)
        
        # Amenity names for PropertyAmenity model
        amenity_names = [
            'Free WiFi', 'Swimming Pool', 'Gym', 'Restaurant', 
            'Room Service', 'Spa', 'Bar', 'Parking',
            'Airport Shuttle', 'Business Center', 'Conference Room',
            'Pet Friendly', 'Laundry', 'Air Conditioning'
        ]
        
        # Hotel templates
        hotel_templates = [
            {
                'name': 'Grand Heritage Palace',
                'property_type': 'HOTEL',
                'rating': 4.8,
                'description': 'Luxury heritage hotel with traditional architecture and modern amenities. Experience royal hospitality in the heart of the city.',
                'rooms_count': 120,
                'area': 'Heritage District',
                'landmark': 'Near City Palace',
                'price_range': (5000, 15000),
            },
            {
                'name': 'Oceanview Beach Resort',
                'property_type': 'RESORT',
                'rating': 4.7,
                'description': 'Beachfront resort with private beach access, infinity pool, and spa. Perfect for romantic getaways and family vacations.',
                'rooms_count': 85,
                'area': 'Beachfront',
                'landmark': 'Beach Road',
                'price_range': (8000, 20000),
            },
            {
                'name': 'Business Express Inn',
                'property_type': 'HOTEL',
                'rating': 4.3,
                'description': 'Modern business hotel near airport and convention center. High-speed WiFi and meeting rooms available.',
                'rooms_count': 150,
                'area': 'Business District',
                'landmark': 'Near Airport',
                'price_range': (3000, 8000),
            },
            {
                'name': 'Boutique Residency',
                'property_type': 'BOUTIQUE',
                'rating': 4.9,
                'description': 'Intimate boutique hotel with personalized service and artistic décor. Each room uniquely designed.',
                'rooms_count': 25,
                'area': 'Art District',
                'landmark': 'Near Art Gallery',
                'price_range': (6000, 12000),
            },
            {
                'name': 'Budget Comfort Lodge',
                'property_type': 'HOTEL',
                'rating': 4.0,
                'description': 'Clean and comfortable budget accommodation with essential amenities. Great value for money.',
                'rooms_count': 80,
                'area': 'Central Area',
                'landmark': 'Railway Station',
                'price_range': (1500, 4000),
            },
        ]
        
        # Room type templates
        room_types_templates = [
            {'name': 'Standard Room', 'capacity': 2, 'price_multiplier': 1.0},
            {'name': 'Deluxe Room', 'capacity': 2, 'price_multiplier': 1.5},
            {'name': 'Executive Suite', 'capacity': 3, 'price_multiplier': 2.0},
            {'name': 'Family Room', 'capacity': 4, 'price_multiplier': 1.8},
            {'name': 'Presidential Suite', 'capacity': 4, 'price_multiplier': 3.0},
        ]
        
        created_count = 0
        hotel_id = 1
        
        # Create 25 hotels (5 templates × 5 cities)
        for city in cities:
            for template in hotel_templates:
                try:
                    # Find locality for this city
                    locality = next((loc for loc in localities if loc.city == city), None)
                    
                    # Create unique hotel name with ID
                    hotel_name = f"{template['name']} {city.name} #{hotel_id}"
                    hotel_id += 1
                    
                    # Create property
                    property_obj = Property.objects.create(
                        name=hotel_name,
                        property_type=template['property_type'],
                        description=template['description'],
                        address=f"{random.randint(1, 999)} {template['area']}, {city.name}",
                        city=city,
                        locality=locality,
                        area=template['area'],
                        landmark=template['landmark'],
                        latitude=Decimal(f"{random.uniform(10, 30):.6f}"),
                        longitude=Decimal(f"{random.uniform(70, 85):.6f}"),
                        rating=Decimal(str(template['rating'])),
                        owner=admin,
                    )
                    
                    # Create room types
                    min_price, max_price = template['price_range']
                    base_price = random.randint(min_price, max_price)
                    
                    for room_template in random.sample(room_types_templates, 3):
                        RoomType.objects.create(
                            property=property_obj,
                            name=room_template['name'],
                            description=f"{room_template['name']} with modern amenities",
                            base_price=Decimal(base_price * room_template['price_multiplier']),
                            max_occupancy=room_template['capacity'],
                            room_size=random.randint(250, 600),
                            available_count=random.randint(5, 20),
                        )
                    
                    # Add amenities (5-10 random amenities per hotel)
                    for amenity_name in random.sample(amenity_names, random.randint(5, 10)):
                        PropertyAmenity.objects.create(
                            property=property_obj,
                            name=amenity_name,
                            icon='check'
                        )
                    
                    # Add property images (3-6 images)
                    image_urls = [
                        'https://images.unsplash.com/photo-1566073771259-6a8506099945/hotel1.jpg',
                        'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b/hotel2.jpg',
                        'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb/hotel3.jpg',
                        'https://images.unsplash.com/photo-1590490360182-c33d57733427/hotel4.jpg',
                        'https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9/hotel5.jpg',
                        'https://images.unsplash.com/photo-1445019980597-93fa8acb246c/hotel6.jpg',
                    ]
                    
                    for idx, url in enumerate(random.sample(image_urls, random.randint(3, 6))):
                        PropertyImage.objects.create(
                            property=property_obj,
                            image_url=url,
                            caption=f"{property_obj.name} - View {idx + 1}",
                            is_featured=(idx == 0),
                            display_order=idx
                        )
                    
                    # Auto-approve the property
                    from django.utils import timezone
                    PropertyApproval.objects.create(
                        property=property_obj,
                        status='approved',
                        decided_by=admin,
                        decided_at=timezone.now(),
                        notes='Auto-approved demo hotel'
                    )
                    
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"[OK] Created: {property_obj.name}"))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"[ERROR] Error creating hotel: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n[SUCCESS] Successfully created {created_count} demo hotels"))
        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Each hotel has 3 room types, 5-10 amenities, and 3-6 images"))
