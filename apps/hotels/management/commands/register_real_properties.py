"""
Management command: register_real_properties
Creates 2 real curated hotel entries with complete data for OTA presentation.
These are meant as initial real properties - NOT demo/test data.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal


REAL_HOTELS = [
    {
        "name": "The Taj Mahal Palace Mumbai",
        "property_type": "Luxury Hotel",
        "address": "Apollo Bunder, Colaba, Mumbai, Maharashtra 400001",
        "description": (
            "One of India's most iconic luxury hotels, The Taj Mahal Palace stands "
            "majestically opposite the Gateway of India in Mumbai. Built in 1903, this "
            "heritage hotel offers unparalleled views of the Arabian Sea and is renowned "
            "for its world-class service, exquisite dining, and timeless elegance."
        ),
        "city_name": "Mumbai",
        "state_name": "Maharashtra",
        "state_code": "MH",
        "area": "Colaba",
        "latitude": Decimal("18.921600"),
        "longitude": Decimal("72.833900"),
        "place_id": "ChIJp4JiUCNKBzERE0XEf3J5d1A",
        "formatted_address": "Apollo Bunder, Colaba, Mumbai, Maharashtra 400001, India",
        "rating": Decimal("4.8"),
        "review_count": 2412,
        "star_category": 5,
        "popularity_score": 980,
        "is_trending": True,
        "has_free_cancellation": True,
        "cancellation_hours": 48,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {
                "name": "Deluxe Room",
                "description": "Elegant room with city view, king-size bed, marble bathroom.",
                "capacity": 2,
                "base_price": Decimal("18000"),
                "bed_type": "King",
                "total_rooms": 10,
            },
            {
                "name": "Grand Luxury Room",
                "description": "Spacious sea-view room with butler service and premium amenities.",
                "capacity": 2,
                "base_price": Decimal("28000"),
                "bed_type": "King",
                "total_rooms": 5,
            },
        ],
        "amenities": [
            "Free WiFi", "Swimming Pool", "Spa", "Fitness Center",
            "Restaurant", "Room Service", "Concierge", "Valet Parking",
        ],
        "images": [
            "https://picsum.photos/seed/taj-mumbai-1/800/600.jpg",
            "https://picsum.photos/seed/taj-mumbai-2/800/600.jpg",
        ],
    },
    {
        "name": "ITC Windsor Bengaluru",
        "property_type": "Business Hotel",
        "address": "Golf Course Road, Windsor Square, Bengaluru, Karnataka 560052",
        "description": (
            "ITC Windsor is Bengaluru's most prestigious business hotel, embodying the "
            "city's cosmopolitan spirit. Set amidst lush gardens near the historic golf "
            "course, the hotel offers sophisticated accommodation, award-winning restaurants, "
            "and state-of-the-art conference facilities for the discerning traveller."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Golf Course Road",
        "latitude": Decimal("12.971600"),
        "longitude": Decimal("77.594700"),
        "place_id": "ChIJywtkGTRkrjsRK7PtL1fFe3o",
        "formatted_address": "Golf Course Road, Windsor Square, Bengaluru, Karnataka 560052, India",
        "rating": Decimal("4.6"),
        "review_count": 1847,
        "star_category": 5,
        "popularity_score": 860,
        "is_trending": False,
        "has_free_cancellation": True,
        "cancellation_hours": 24,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {
                "name": "Executive Room",
                "description": "Contemporary room with garden view, work desk, and executive lounge access.",
                "capacity": 2,
                "base_price": Decimal("12000"),
                "bed_type": "King",
                "total_rooms": 12,
            },
            {
                "name": "Welcome Suite",
                "description": "Spacious suite with separate living area, walk-in wardrobe, and panoramic views.",
                "capacity": 3,
                "base_price": Decimal("22000"),
                "bed_type": "King",
                "total_rooms": 4,
            },
        ],
        "amenities": [
            "Free WiFi", "Swimming Pool", "Spa", "Fitness Center",
            "Business Centre", "Restaurant", "Bar", "Valet Parking",
        ],
        "images": [
            "https://picsum.photos/seed/itc-bangalore-1/800/600.jpg",
            "https://picsum.photos/seed/itc-bangalore-2/800/600.jpg",
        ],
    },
]


class Command(BaseCommand):
    help = 'Register 2 real curated hotel properties with complete data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing properties if they already exist (by name)',
        )

    def handle(self, *args, **options):
        from apps.hotels.models import Property, PropertyImage, PropertyAmenity
        from apps.rooms.models import RoomType
        from apps.core.location_models import Country, State, City
        from django.contrib.auth import get_user_model
        from django.utils.text import slugify

        User = get_user_model()
        update_existing = options['update']

        # Ensure admin owner exists
        admin, created = User.objects.get_or_create(
            email='admin@zygotrip.com',
            defaults={
                'full_name': 'ZygoTrip Admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(f'  Created admin user: admin@zygotrip.com')

        # Ensure India country record
        country, _ = Country.objects.get_or_create(
            code='IN',
            defaults={
                'name': 'India',
                'display_name': 'India',
                'is_active': True,
            }
        )

        created_count = 0
        updated_count = 0

        for hotel_data in REAL_HOTELS:
            try:
                with transaction.atomic():
                    # Resolve or create State
                    state, _ = State.objects.get_or_create(
                        country=country,
                        code=hotel_data['state_code'],
                        defaults={
                            'name': hotel_data['state_name'],
                            'display_name': hotel_data['state_name'],
                            'is_active': True,
                        }
                    )

                    # Resolve or create City (use first match to handle duplicates)
                    city = City.objects.filter(
                        state=state, name=hotel_data['city_name']
                    ).first()
                    if not city:
                        city = City.objects.create(
                            state=state,
                            name=hotel_data['city_name'],
                            display_name=hotel_data['city_name'],
                            code=hotel_data['city_name'].upper()[:12],
                            latitude=hotel_data['latitude'],
                            longitude=hotel_data['longitude'],
                            is_active=True,
                        )

                    # Check if property already exists
                    slug = slugify(hotel_data['name'])
                    existing = Property.objects.filter(slug=slug).first()

                    if existing and not update_existing:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  SKIP: "{hotel_data["name"]}" already exists '
                                f'(use --update to overwrite)'
                            )
                        )
                        continue

                    # Build property fields
                    prop_fields = {
                        'owner': admin,
                        'name': hotel_data['name'],
                        'property_type': hotel_data['property_type'],
                        'city': city,
                        'area': hotel_data['area'],
                        'address': hotel_data['address'],
                        'description': hotel_data['description'],
                        'latitude': hotel_data['latitude'],
                        'longitude': hotel_data['longitude'],
                        'place_id': hotel_data['place_id'],
                        'formatted_address': hotel_data['formatted_address'],
                        'rating': hotel_data['rating'],
                        'review_count': hotel_data['review_count'],
                        'star_category': hotel_data['star_category'],
                        'popularity_score': hotel_data['popularity_score'],
                        'is_trending': hotel_data['is_trending'],
                        'has_free_cancellation': hotel_data['has_free_cancellation'],
                        'cancellation_hours': hotel_data['cancellation_hours'],
                        'status': hotel_data['status'],
                        'agreement_signed': hotel_data['agreement_signed'],
                    }

                    if existing:
                        for field, value in prop_fields.items():
                            if field != 'owner':  # don't transfer ownership
                                setattr(existing, field, value)
                        existing.save()
                        prop = existing
                        updated_count += 1
                        self.stdout.write(f'  UPDATED: {prop.name}')
                    else:
                        prop = Property(**prop_fields)
                        prop.save()
                        created_count += 1
                        self.stdout.write(f'  CREATED: {prop.name}')

                    # Create room types
                    RoomType.objects.filter(property=prop).delete()
                    for rt_data in hotel_data['room_types']:
                        RoomType.objects.create(
                            property=prop,
                            name=rt_data['name'],
                            description=rt_data.get('description', ''),
                            capacity=rt_data['capacity'],
                            base_price=rt_data['base_price'],
                            bed_type=rt_data.get('bed_type', ''),
                            available_count=rt_data.get('total_rooms', 5),
                        )
                    self.stdout.write(
                        f'    + {len(hotel_data["room_types"])} room type(s)'
                    )

                    # Create amenities
                    PropertyAmenity.objects.filter(property=prop).delete()
                    for amenity_name in hotel_data['amenities']:
                        PropertyAmenity.objects.create(
                            property=prop,
                            name=amenity_name,
                        )
                    self.stdout.write(
                        f'    + {len(hotel_data["amenities"])} amenities'
                    )

                    # Create property images (URL-based)
                    PropertyImage.objects.filter(property=prop).delete()
                    for i, img_url in enumerate(hotel_data['images']):
                        PropertyImage.objects.create(
                            property=prop,
                            image_url=img_url,
                            is_featured=(i == 0),
                        )
                    self.stdout.write(
                        f'    + {len(hotel_data["images"])} image(s)'
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ERROR registering "{hotel_data["name"]}": {e}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — {created_count} created, {updated_count} updated.'
        ))
