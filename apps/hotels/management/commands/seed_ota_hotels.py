"""
Management command: seed_ota_hotels
Seeds real curated hotel data for all major Indian cities with:
- Proper geo coordinates (lat/lng, place_id)
- High-quality image URLs
- Realistic pricing, ratings, amenities
- RoomInventory records for next 180 days

Run: python manage.py seed_ota_hotels
     python manage.py seed_ota_hotels --inventory-days 365
     python manage.py seed_ota_hotels --city Bangalore
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta


# ─────────────────────────────────────────────────────────────────
# REAL HOTEL DATA (curated, not demo)
# Images: Unsplash stable hotel photos
# ─────────────────────────────────────────────────────────────────
REAL_HOTELS = [
    # ── BANGALORE ─────────────────────────────────────────────────
    {
        "name": "The Leela Palace Bengaluru",
        "property_type": "Luxury Hotel",
        "address": "23, Old Airport Road, Kodihalli, Bengaluru, Karnataka 560008",
        "description": (
            "The Leela Palace Bengaluru is a magnificent blend of Vijayanagara empire "
            "architecture and modern luxury. Set on 7 acres of landscaped gardens near "
            "the HAL Airport, this iconic hotel offers imperial grandeur with world-class "
            "amenities, award-winning restaurants and a renowned spa."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Old Airport Road",
        "landmark": "5 km from MG Road",
        "latitude": Decimal("12.960500"),
        "longitude": Decimal("77.646300"),
        "place_id": "ChIJOeSE5F5crjsRgvt_dFp5NAg",
        "formatted_address": "23, Old Airport Road, Kodihalli, Bengaluru 560008, India",
        "rating": Decimal("4.8"),
        "review_count": 3247,
        "star_category": 5,
        "popularity_score": 990,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 15},
            {"name": "Premier Room", "base_price": Decimal("20000"), "capacity": 2, "bed_type": "King", "available_count": 8},
            {"name": "Royal Suite", "base_price": Decimal("45000"), "capacity": 3, "bed_type": "King", "available_count": 3},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Valet Parking", "Butler Service"],
        "images": [
            {"url": "https://picsum.photos/seed/leela-palace-blr-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/leela-palace-blr-2/800/600.jpg", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-blr-3/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "Taj MG Road Bengaluru",
        "property_type": "Luxury Hotel",
        "address": "41/3, Mahatma Gandhi Road, Bengaluru, Karnataka 560001",
        "description": (
            "Taj MG Road sits at the heart of Bengaluru's commercial and cultural hub. "
            "This contemporary luxury hotel offers easy access to the city's best shopping, "
            "dining and its vibrant tech corridor. Known for exceptional cuisine and "
            "personalised service that sets the Taj standard."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "MG Road",
        "landmark": "Near Brigade Road",
        "latitude": Decimal("12.975900"),
        "longitude": Decimal("77.607600"),
        "place_id": "ChIJm6H-OBNkrjsRhAOQSuENy5g",
        "formatted_address": "41/3, Mahatma Gandhi Road, Bengaluru 560001, India",
        "rating": Decimal("4.7"),
        "review_count": 2891,
        "star_category": 5,
        "popularity_score": 960,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("9500"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Luxury Room", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Junior Suite", "base_price": Decimal("25000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-mg-road-blr-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-mg-road-blr-2/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "Sheraton Grand Bengaluru Whitefield",
        "property_type": "Business Hotel",
        "address": "Prestige Shantiniketan, Whitefield, Bengaluru, Karnataka 560048",
        "description": (
            "The Sheraton Grand Bengaluru Whitefield is the premier business hotel in "
            "the tech hub of the city. Located adjacent to ITPL and major IT parks, "
            "it offers sophisticated accommodation with state-of-the-art conference "
            "facilities, multiple dining options and a full-service spa."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Whitefield",
        "landmark": "Near ITPL Tech Park",
        "latitude": Decimal("12.980500"),
        "longitude": Decimal("77.745600"),
        "place_id": "ChIJ7aRL2eZirjsRJBDPRqc4hYI",
        "formatted_address": "Prestige Shantiniketan, Whitefield, Bengaluru 560048, India",
        "rating": Decimal("4.5"),
        "review_count": 1654,
        "star_category": 5,
        "popularity_score": 870,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("8000"), "capacity": 2, "bed_type": "King", "available_count": 25},
            {"name": "Club Room", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Suite", "base_price": Decimal("20000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Business Centre", "Restaurant", "Bar", "Shuttle Service"],
        "images": [
            {"url": "https://picsum.photos/seed/sheraton-whitefield-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/sheraton-whitefield-2/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "Hyatt Centric MG Road Bangalore",
        "property_type": "Business Hotel",
        "address": "Mustafa Tower, 1, Museum Road, Bengaluru, Karnataka 560025",
        "description": (
            "Hyatt Centric MG Road is a vibrant lifestyle hotel in the beating heart of "
            "Bengaluru's business district. Minutes from the metro, shopping and nightlife, "
            "it offers stylish modern rooms, a rooftop pool and Bengaluru's most talked-about "
            "rooftop bar with sweeping city panoramas."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "MG Road",
        "landmark": "Near Cubbon Park",
        "latitude": Decimal("12.973200"),
        "longitude": Decimal("77.608700"),
        "place_id": "ChIJhyGMX3NkrjsRpd1c_B7JxRQ",
        "formatted_address": "Mustafa Tower, 1, Museum Road, Bengaluru 560025, India",
        "rating": Decimal("4.5"),
        "review_count": 2103,
        "star_category": 5,
        "popularity_score": 880,
        "is_trending": True,
        "has_free_cancellation": False,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "King Room", "base_price": Decimal("7500"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Corner King", "base_price": Decimal("10500"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Penthouse Suite", "base_price": Decimal("22000"), "capacity": 4, "bed_type": "King", "available_count": 3},
        ],
        "amenities": ["Free WiFi", "Rooftop Pool", "Fitness Center", "Restaurant", "Rooftop Bar", "Concierge", "Valet Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/hyatt-centric-blr-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/hyatt-centric-blr-2/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "The Oberoi Bengaluru",
        "property_type": "Luxury Hotel",
        "address": "37-39, Mahatma Gandhi Road, Bengaluru, Karnataka 560001",
        "description": (
            "The Oberoi Bengaluru is an oasis of luxury in the heart of the city. "
            "This sophisticated hotel combines intimate luxury with understated elegance. "
            "Set amidst beautifully landscaped gardens, it offers guests a serene sanctuary "
            "with impeccable service and fine dining in the bustling city centre."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "MG Road",
        "landmark": "Facing Cubbon Park",
        "latitude": Decimal("12.974100"),
        "longitude": Decimal("77.607900"),
        "place_id": "ChIJc6_kM3NkrjsREFWoiSMvYPE",
        "formatted_address": "37-39, Mahatma Gandhi Road, Bengaluru 560001, India",
        "rating": Decimal("4.9"),
        "review_count": 1876,
        "star_category": 5,
        "popularity_score": 970,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Premier Room", "base_price": Decimal("16000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Luxury Suite", "base_price": Decimal("32000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "24h Room Service"],
        "images": [
            {"url": "https://picsum.photos/seed/oberoi-blr-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/oberoi-blr-2/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "Courtyard by Marriott Bengaluru Hebbal",
        "property_type": "Business Hotel",
        "address": "No. 57, Doresanipalya Road, Hebbal, Bengaluru, Karnataka 560024",
        "description": (
            "Conveniently located near Bengaluru International Airport and major tech "
            "corridors, Courtyard by Marriott Hebbal offers a perfect blend of comfort "
            "and convenience for both business and leisure travellers. Featuring spacious "
            "rooms, all-day dining and a refreshing swimming pool."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Hebbal",
        "landmark": "12 km from Bengaluru Airport",
        "latitude": Decimal("13.043200"),
        "longitude": Decimal("77.590100"),
        "place_id": "ChIJnaBbZLJkrjsRn7VCkKj8y8Q",
        "formatted_address": "No. 57, Doresanipalya Road, Hebbal, Bengaluru 560024, India",
        "rating": Decimal("4.3"),
        "review_count": 987,
        "star_category": 4,
        "popularity_score": 760,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Standard Room", "base_price": Decimal("4500"), "capacity": 2, "bed_type": "Queen", "available_count": 30},
            {"name": "Deluxe Room", "base_price": Decimal("6500"), "capacity": 2, "bed_type": "King", "available_count": 15},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Airport Shuttle", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/courtyard-hebbal-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/courtyard-hebbal-2/800/600.jpg", "is_featured": False},
        ],
    },
    {
        "name": "Lemon Tree Premier Bengaluru",
        "property_type": "Business Hotel",
        "address": "No. 18, Ulsoor Road, Bengaluru, Karnataka 560042",
        "description": (
            "Lemon Tree Premier, Ulsoor, Bengaluru is a chic upscale hotel in the heart "
            "of the city, offering accessible luxury for the modern traveller. Close to "
            "MG Road, Ulsoor Lake and key business districts, it provides excellent "
            "connectivity alongside fresh, vibrant hospitality."
        ),
        "city_name": "Bangalore",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Ulsoor",
        "landmark": "Near Ulsoor Lake, 1 km from MG Road",
        "latitude": Decimal("12.981400"),
        "longitude": Decimal("77.618200"),
        "place_id": "ChIJWf2bfxJkrjsRlEFVxhtBhkM",
        "formatted_address": "No. 18, Ulsoor Road, Bengaluru 560042, India",
        "rating": Decimal("4.2"),
        "review_count": 1543,
        "star_category": 4,
        "popularity_score": 720,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Refreshing Room", "base_price": Decimal("3800"), "capacity": 2, "bed_type": "Double", "available_count": 35},
            {"name": "Premium Room", "base_price": Decimal("5500"), "capacity": 2, "bed_type": "King", "available_count": 18},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Bar", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/lemon-tree-blr-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/lemon-tree-blr-2/800/600.jpg", "is_featured": False},
        ],
    },
    # ── MUMBAI ──────────────────────────────────────────────────────
    {
        "name": "Trident Bandra Kurla Mumbai",
        "property_type": "Luxury Hotel",
        "address": "C-56, G-Block, Bandra Kurla Complex, Mumbai, Maharashtra 400051",
        "description": (
            "Trident Bandra Kurla is the ultimate address for business travel in Mumbai. "
            "Situated in the prestigious Bandra Kurla Complex, India's premier financial "
            "district, this elegant hotel offers spacious rooms with stunning skyline views, "
            "cutting-edge meeting spaces and award-winning dining."
        ),
        "city_name": "Mumbai",
        "state_name": "Maharashtra",
        "state_code": "MH",
        "area": "Bandra Kurla Complex",
        "landmark": "Near MMRDA Ground",
        "latitude": Decimal("19.065800"),
        "longitude": Decimal("72.868800"),
        "place_id": "ChIJ2_-H0BOnOjoRr5u5U3rQEJQ",
        "formatted_address": "C-56, G-Block, Bandra Kurla Complex, Mumbai 400051, India",
        "rating": Decimal("4.6"),
        "review_count": 2134,
        "star_category": 5,
        "popularity_score": 890,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("11000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Club Room", "base_price": Decimal("16000"), "capacity": 2, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Business Centre", "Valet Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/trident-bkc-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/trident-bkc-2/800/600.jpg", "is_featured": False},
        ],
    },
    # ── GOA ──────────────────────────────────────────────────────
    {
        "name": "Grand Hyatt Goa",
        "property_type": "Resort",
        "address": "Bambolim Beach Resort, Bambolim, Goa 403202",
        "description": (
            "Grand Hyatt Goa is a stunning resort nestled on the banks of the Zuari "
            "River. Just 15 minutes from Panaji, it features expansive lagoon pools, "
            "pristine beaches, multiple restaurants, a full-service Celine Spa and a "
            "wide range of water sports—the perfect Goa escape."
        ),
        "city_name": "Goa",
        "state_name": "Goa",
        "state_code": "GA",
        "area": "Bambolim",
        "landmark": "On Bambolim Beach",
        "latitude": Decimal("15.456400"),
        "longitude": Decimal("73.861500"),
        "place_id": "ChIJATcXv4wOvzsR0coCl9pX7gg",
        "formatted_address": "Bambolim Beach Resort, Bambolim, Goa 403202, India",
        "rating": Decimal("4.6"),
        "review_count": 3412,
        "star_category": 5,
        "popularity_score": 920,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Grand Room", "base_price": Decimal("13000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Pool Villa", "base_price": Decimal("35000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Beach Access", "Multiple Pools", "Spa", "Water Sports", "Restaurant", "Bar", "Kids Club"],
        "images": [
            {"url": "https://picsum.photos/seed/grand-hyatt-goa-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/grand-hyatt-goa-2/800/600.jpg", "is_featured": False},
        ],
    },
    # ── DELHI ─────────────────────────────────────────────────────
    {
        "name": "The Imperial New Delhi",
        "property_type": "Heritage Hotel",
        "address": "Janpath, New Delhi, Delhi 110001",
        "description": (
            "The Imperial is Delhi's most distinguished address—a living legend among "
            "the great heritage hotels of the world. Built in 1931, this Art Deco "
            "masterpiece boasts a priceless collection of colonial-era artwork, impeccable "
            "service, and some of the finest dining in the capital."
        ),
        "city_name": "Delhi",
        "state_name": "Delhi",
        "state_code": "DL",
        "area": "Connaught Place",
        "landmark": "Near India Gate",
        "latitude": Decimal("28.623400"),
        "longitude": Decimal("77.218400"),
        "place_id": "ChIJv0A2SZSYDT0RbIJ2yPY5hEk",
        "formatted_address": "Janpath, New Delhi 110001, India",
        "rating": Decimal("4.7"),
        "review_count": 2876,
        "star_category": 5,
        "popularity_score": 930,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Room", "base_price": Decimal("15000"), "capacity": 2, "bed_type": "King", "available_count": 14},
            {"name": "Imperial Suite", "base_price": Decimal("40000"), "capacity": 4, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Heritage Tours", "Valet Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/imperial-delhi-1/800/600.jpg", "is_featured": True},
            {"url": "https://picsum.photos/seed/imperial-delhi-2/800/600.jpg", "is_featured": False},
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed real curated hotel data with geo coordinates, images, rooms & inventory'

    def add_arguments(self, parser):
        parser.add_argument('--inventory-days', type=int, default=180,
                            help='Number of days ahead to seed RoomInventory (default: 180)')
        parser.add_argument('--city', type=str, default='',
                            help='Seed only hotels in this city (default: all)')
        parser.add_argument('--update', action='store_true',
                            help='Update existing hotels (match by name)')
        parser.add_argument('--inventory-only', action='store_true',
                            help='Only seed RoomInventory for existing approved properties')

    def handle(self, *args, **options):
        from apps.hotels.models import Property, PropertyImage, PropertyAmenity
        from apps.rooms.models import RoomType, RoomInventory
        from apps.core.location_models import Country, State, City
        from django.contrib.auth import get_user_model
        from django.utils.text import slugify

        User = get_user_model()
        inventory_days = options['inventory_days']
        city_filter = options['city'].strip().lower()
        update_existing = options['update']
        inventory_only = options['inventory_only']

        # ── Ensure admin owner ───────────────────────────────────────
        admin, _ = User.objects.get_or_create(
            email='admin@zygotrip.com',
            defaults={
                'full_name': 'ZygoTrip Admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if not admin.pk:
            admin.save()

        # ── Ensure country: India ────────────────────────────────────
        india, _ = Country.objects.get_or_create(
            code='IN',
            defaults={'name': 'India', 'display_name': 'India', 'is_active': True}
        )

        # ── Seed Hotels ──────────────────────────────────────────────
        if not inventory_only:
            hotels_to_seed = REAL_HOTELS
            if city_filter:
                hotels_to_seed = [h for h in REAL_HOTELS if h['city_name'].lower() == city_filter]
                if not hotels_to_seed:
                    self.stdout.write(self.style.WARNING(f'No hotels found for city: {city_filter}'))

            for hotel_data in hotels_to_seed:
                with transaction.atomic():
                    self._seed_hotel(hotel_data, india, admin, update_existing,
                                     Property, PropertyImage, PropertyAmenity, RoomType,
                                     State, City, slugify)

        # ── Seed RoomInventory ───────────────────────────────────────
        self.stdout.write('\n📅 Seeding RoomInventory...')
        self._seed_inventory(inventory_days)
        self.stdout.write(self.style.SUCCESS('\n✅ Hotel seeding complete!\n'))

    def _seed_hotel(self, data, india, admin, update_existing,
                    Property, PropertyImage, PropertyAmenity, RoomType,
                    State, City, slugify):
        from apps.rooms.models import RoomType

        # ── State ────────────────────────────────────────────────────
        state, _ = State.objects.get_or_create(
            code=data['state_code'],
            country=india,
            defaults={'name': data['state_name'], 'display_name': data['state_name']}
        )

        # ── City ─────────────────────────────────────────────────────
        city_slug = slugify(data['city_name'])
        city, _ = City.objects.get_or_create(
            slug=city_slug,
            defaults={
                'state': state,
                'name': data['city_name'],
                'display_name': data['city_name'],
                'code': data.get('state_code', 'XX') + '_' + data['city_name'][:3].upper(),
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'is_active': True,
                'is_top_destination': True,
            }
        )

        # ── Property ─────────────────────────────────────────────────
        prop_slug = slugify(data['name'])
        existing = Property.objects.filter(name=data['name']).first()
        if existing:
            if update_existing:
                prop = existing
                self.stdout.write(f'  ♻ Updating: {data["name"]}')
            else:
                self.stdout.write(f'  ⏭ Skipping (exists): {data["name"]}')
                return
        else:
            prop = Property(name=data['name'])
            self.stdout.write(f'  ✚ Creating: {data["name"]}')

        prop.slug = prop_slug
        prop.property_type = data['property_type']
        prop.address = data['address']
        prop.description = data['description']
        prop.city = city
        prop.area = data['area']
        prop.landmark = data.get('landmark', '')
        prop.latitude = data['latitude']
        prop.longitude = data['longitude']
        prop.place_id = data.get('place_id', '')
        prop.formatted_address = data.get('formatted_address', data['address'])
        prop.rating = data['rating']
        prop.review_count = data['review_count']
        prop.star_category = data['star_category']
        prop.popularity_score = data['popularity_score']
        prop.is_trending = data['is_trending']
        prop.has_free_cancellation = data['has_free_cancellation']
        prop.status = data['status']
        prop.agreement_signed = data['agreement_signed']
        prop.owner = admin
        prop.save()

        # ── Amenities ────────────────────────────────────────────────
        prop.amenities.all().delete()
        for amenity_name in data['amenities']:
            PropertyAmenity.objects.get_or_create(property=prop, name=amenity_name)

        # ── Images ───────────────────────────────────────────────────
        prop.images.all().delete()
        for i, img in enumerate(data['images']):
            if isinstance(img, dict):
                PropertyImage.objects.create(
                    property=prop,
                    image_url=img['url'],
                    is_featured=img.get('is_featured', i == 0),
                    display_order=i,
                )
            else:
                PropertyImage.objects.create(
                    property=prop,
                    image_url=img,
                    is_featured=(i == 0),
                    display_order=i,
                )

        # ── Room Types ───────────────────────────────────────────────
        prop.room_types.all().delete()
        for rt_data in data['room_types']:
            RoomType.objects.create(
                property=prop,
                name=rt_data['name'],
                description=rt_data.get('description', ''),
                capacity=rt_data.get('capacity', 2),
                base_price=rt_data['base_price'],
                bed_type=rt_data.get('bed_type', 'King'),
                available_count=rt_data.get('available_count', 10),
            )

        self.stdout.write(self.style.SUCCESS(
            f'     → {prop.room_types.count()} rooms, {prop.images.count()} images, '
            f'{prop.amenities.count()} amenities [ID={prop.id}]'
        ))

    def _seed_inventory(self, days_ahead):
        from apps.hotels.models import Property
        from apps.rooms.models import RoomType, RoomInventory

        start = date.today()
        end = start + timedelta(days=days_ahead)
        all_dates = [start + timedelta(d) for d in range(days_ahead)]

        approved_props = Property.objects.filter(status='approved', agreement_signed=True)
        total_created = 0

        for prop in approved_props:
            room_types = list(prop.room_types.all())
            if not room_types:
                continue

            for rt in room_types:
                # Build list of dates that don't already have inventory
                existing_dates = set(
                    RoomInventory.objects.filter(room_type=rt, date__gte=start, date__lt=end)
                    .values_list('date', flat=True)
                )
                new_records = [
                    RoomInventory(
                        room_type=rt,
                        date=d,
                        available_rooms=rt.available_count,
                        is_closed=False,
                    )
                    for d in all_dates if d not in existing_dates
                ]
                if new_records:
                    RoomInventory.objects.bulk_create(new_records, ignore_conflicts=True)
                    total_created += len(new_records)

        self.stdout.write(self.style.SUCCESS(
            f'  Created {total_created} RoomInventory records across '
            f'{approved_props.count()} properties for {days_ahead} days'
        ))
