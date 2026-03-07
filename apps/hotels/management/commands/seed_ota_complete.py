"""
Management command: seed_ota_complete
Full 10-city OTA data seeder.
Covers: Coorg, Goa, Bangalore, Hyderabad, Chennai, Mumbai, Delhi, Ooty, Mysore, Pondicherry
5 properties per city · 5 images per property · locality FK · room types · amenities

Usage:
  python manage.py seed_ota_complete
  python manage.py seed_ota_complete --city Delhi
  python manage.py seed_ota_complete --fresh      (wipe & re-seed)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta


# ─────────────────────────────────────────────────────────────────────────────
#  MASTER PROPERTY LIST  (10 cities × 5 properties = 50 hotels)
# ─────────────────────────────────────────────────────────────────────────────
OTA_PROPERTIES = [

    # ══════════════════════════════════════════════════════════════════════════
    #  COORG  (Kodagu, Karnataka)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Evolve Back Coorg",
        "property_type": "Luxury Resort",
        "address": "Pollibetta, Kodagu, Karnataka 571215",
        "description": "A 300-acre coffee plantation resort with private pool villas blending Kodava heritage with contemporary luxury.",
        "city_name": "Coorg", "state_name": "Karnataka", "state_code": "KA",
        "area": "Pollibetta", "landmark": "Orange County Estate",
        "latitude": Decimal("12.396800"), "longitude": Decimal("75.705200"),
        "rating": Decimal("4.9"), "review_count": 2876, "star_category": 5,
        "popularity_score": 980, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Villa", "base_price": Decimal("30000"), "capacity": 2, "bed_type": "King", "available_count": 6},
            {"name": "Plantation Pool Villa", "base_price": Decimal("50000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Private Pool", "Coffee Plantation Tour", "Spa", "Restaurant", "Campfire", "Cycling"],
        "images": [
            {"url": "https://picsum.photos/seed/evolve-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/evolve-coorg-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/evolve-coorg-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/evolve-coorg-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/evolve-coorg-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Madikeri Resort & Spa",
        "property_type": "Luxury Resort",
        "address": "Block 4, Galibeedu Post, Madikeri, Kodagu, Karnataka 571201",
        "description": "Serene hilltop sanctuary in misty mountains with panoramic rainforest views and award-winning spa.",
        "city_name": "Coorg", "state_name": "Karnataka", "state_code": "KA",
        "area": "Galibeedu", "landmark": "8 km from Madikeri town",
        "latitude": Decimal("12.432700"), "longitude": Decimal("75.741300"),
        "rating": Decimal("4.8"), "review_count": 1943, "star_category": 5,
        "popularity_score": 940, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Forest Cottage", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Valley View Villa", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Infinity Pool", "Spa", "Forest Treks", "Restaurant", "Bar", "Bird Watching"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-madikeri-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-madikeri-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-madikeri-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-madikeri-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-madikeri-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Tamara Coorg",
        "property_type": "Luxury Resort",
        "address": "Yavakapadi Estate, Galibeedu, Coorg, Karnataka 571201",
        "description": "A stunning 340-acre estate resort with private villas, a private lake, kayaking, and farm-to-table Kodava cuisine.",
        "city_name": "Coorg", "state_name": "Karnataka", "state_code": "KA",
        "area": "Yavakapadi", "landmark": "Near Galibeedu Village",
        "latitude": Decimal("12.418900"), "longitude": Decimal("75.755600"),
        "rating": Decimal("4.7"), "review_count": 1287, "star_category": 5,
        "popularity_score": 890, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Estate Villa", "base_price": Decimal("22000"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Pool Villa", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Private Lake", "Kayaking", "Spa", "Restaurant", "Plantation Walks", "Bonfire"],
        "images": [
            {"url": "https://picsum.photos/seed/tamara-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/tamara-coorg-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/tamara-coorg-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/tamara-coorg-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/tamara-coorg-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Club Mahindra Madikeri",
        "property_type": "Resort",
        "address": "Keradala Keri, Madikeri, Kodagu, Karnataka 571201",
        "description": "Family-friendly resort with coffee estate tours, swimming pool, and multi-cuisine restaurant in the heart of Coorg.",
        "city_name": "Coorg", "state_name": "Karnataka", "state_code": "KA",
        "area": "Madikeri", "landmark": "Near Madikeri Fort",
        "latitude": Decimal("12.421100"), "longitude": Decimal("75.739400"),
        "rating": Decimal("4.3"), "review_count": 2654, "star_category": 4,
        "popularity_score": 780, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Studio Room", "base_price": Decimal("4500"), "capacity": 2, "bed_type": "Double", "available_count": 25},
            {"name": "1BHK Cottage", "base_price": Decimal("7500"), "capacity": 4, "bed_type": "King", "available_count": 12},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Bar", "Coffee Estate Tour", "Indoor Games"],
        "images": [
            {"url": "https://picsum.photos/seed/club-mah-madikeri-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/club-mah-madikeri-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/club-mah-madikeri-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/club-mah-madikeri-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/club-mah-madikeri-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Amanvana Spa Resort Coorg",
        "property_type": "Spa Resort",
        "address": "Near Kushalnagar, Coorg, Karnataka 571234",
        "description": "Wellness sanctuary on the banks of the Cauvery River with Ayurvedic spa and tropical garden cottages.",
        "city_name": "Coorg", "state_name": "Karnataka", "state_code": "KA",
        "area": "Kushalnagar", "landmark": "On Cauvery River banks",
        "latitude": Decimal("12.459300"), "longitude": Decimal("75.963200"),
        "rating": Decimal("4.6"), "review_count": 873, "star_category": 5,
        "popularity_score": 820, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Garden Cottage", "base_price": Decimal("9000"), "capacity": 2, "bed_type": "King", "available_count": 8},
            {"name": "River View Suite", "base_price": Decimal("16000"), "capacity": 2, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Spa", "Ayurveda", "River View", "Yoga", "Restaurant", "Meditation"],
        "images": [
            {"url": "https://picsum.photos/seed/amanvana-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/amanvana-coorg-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/amanvana-coorg-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/amanvana-coorg-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/amanvana-coorg-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  GOA
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Taj Exotica Resort & Spa Goa",
        "property_type": "Luxury Resort",
        "address": "Calwaddo, Benaulim, South Goa 403716",
        "description": "Mediterranean-inspired luxury resort on 59 acres of pristine South Goa beachfront with private lagoon.",
        "city_name": "Goa", "state_name": "Goa", "state_code": "GA",
        "area": "Benaulim", "landmark": "Benaulim Beach, South Goa",
        "latitude": Decimal("15.260600"), "longitude": Decimal("73.920300"),
        "rating": Decimal("4.8"), "review_count": 3421, "star_category": 5,
        "popularity_score": 970, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Lagoon Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Beach Villa", "base_price": Decimal("45000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Private Beach", "Swimming Pool", "Spa", "Restaurant", "Water Sports", "Tennis Court"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-exotica-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-exotica-goa-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-exotica-goa-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-exotica-goa-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-exotica-goa-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "W Goa",
        "property_type": "Luxury Hotel",
        "address": "Vagator Beach, North Goa 403509",
        "description": "Vibrant lifestyle hotel perched on Vagator cliffs with stunning Arabian Sea views and Goa's best rooftop pool.",
        "city_name": "Goa", "state_name": "Goa", "state_code": "GA",
        "area": "Vagator", "landmark": "Vagator Beach Cliffs",
        "latitude": Decimal("15.598200"), "longitude": Decimal("73.742200"),
        "rating": Decimal("4.7"), "review_count": 2187, "star_category": 5,
        "popularity_score": 950, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Wonderful Room", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "WOW Suite", "base_price": Decimal("32000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Rooftop Pool", "Spa", "Beach Club", "Restaurant", "Bar", "DJ Nights"],
        "images": [
            {"url": "https://picsum.photos/seed/w-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/w-goa-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/w-goa-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/w-goa-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/w-goa-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Alila Diwa Goa",
        "property_type": "Resort",
        "address": "Adao Waddo, Majorda, South Goa 403713",
        "description": "Lush tropical resort set within rice paddies offering a serene South Goa escape with infinity pool and spa.",
        "city_name": "Goa", "state_name": "Goa", "state_code": "GA",
        "area": "Majorda", "landmark": "Near Majorda Beach",
        "latitude": Decimal("15.296900"), "longitude": Decimal("73.929100"),
        "rating": Decimal("4.6"), "review_count": 1654, "star_category": 5,
        "popularity_score": 870, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Pool View Room", "base_price": Decimal("9500"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Pool Villa", "base_price": Decimal("22000"), "capacity": 2, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Infinity Pool", "Spa", "Yoga", "Restaurant", "Cycling", "Paddy Field Walks"],
        "images": [
            {"url": "https://picsum.photos/seed/alila-diwa-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/alila-diwa-goa-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/alila-diwa-goa-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/alila-diwa-goa-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/alila-diwa-goa-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Novotel Goa Candolim",
        "property_type": "Hotel",
        "address": "Candolim Beach Road, North Goa 403515",
        "description": "Contemporary beach hotel steps from Candolim Beach with large pool, multiple dining options, and free beach access.",
        "city_name": "Goa", "state_name": "Goa", "state_code": "GA",
        "area": "Candolim", "landmark": "Candolim Beach",
        "latitude": Decimal("15.512100"), "longitude": Decimal("73.762000"),
        "rating": Decimal("4.3"), "review_count": 3102, "star_category": 4,
        "popularity_score": 810, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("6500"), "capacity": 2, "bed_type": "Double", "available_count": 30},
            {"name": "Deluxe Pool View", "base_price": Decimal("9000"), "capacity": 2, "bed_type": "King", "available_count": 15},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Beach Access", "Fitness Center", "Kids Club"],
        "images": [
            {"url": "https://picsum.photos/seed/novotel-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/novotel-goa-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-goa-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-goa-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-goa-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Pousada Tauma Goa",
        "property_type": "Boutique Hotel",
        "address": "Porba Waddo, Calangute, North Goa 403516",
        "description": "Award-winning boutique hotel with a curated gallery, designer rooms, and a stunning mosaic pool in quiet Calangute.",
        "city_name": "Goa", "state_name": "Goa", "state_code": "GA",
        "area": "Calangute", "landmark": "Near Calangute Beach",
        "latitude": Decimal("15.544400"), "longitude": Decimal("73.752800"),
        "rating": Decimal("4.5"), "review_count": 897, "star_category": 4,
        "popularity_score": 750, "is_trending": False, "has_free_cancellation": False,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Gallery Room", "base_price": Decimal("7500"), "capacity": 2, "bed_type": "Queen", "available_count": 10},
            {"name": "Suite", "base_price": Decimal("13000"), "capacity": 2, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Mosaic Pool", "Art Gallery", "Restaurant", "Bar", "Yoga"],
        "images": [
            {"url": "https://picsum.photos/seed/pousada-tauma-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/pousada-tauma-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/pousada-tauma-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/pousada-tauma-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/pousada-tauma-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  BANGALORE
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "The Oberoi Bangalore",
        "property_type": "Luxury Hotel",
        "address": "37-39, Mahatma Gandhi Road, Bangalore, Karnataka 560001",
        "description": "The city's most prestigious address, combining timeless elegance with impeccable service on MG Road.",
        "city_name": "Bangalore", "state_name": "Karnataka", "state_code": "KA",
        "area": "MG Road", "landmark": "MG Road Metro Station",
        "latitude": Decimal("12.974900"), "longitude": Decimal("77.614600"),
        "rating": Decimal("4.9"), "review_count": 2965, "star_category": 5,
        "popularity_score": 975, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Premier Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Luxury Suite", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "Valet Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/oberoi-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/oberoi-blr-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-blr-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-blr-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-blr-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "ITC Gardenia Bangalore",
        "property_type": "Luxury Hotel",
        "address": "1, Residency Road, Bangalore, Karnataka 560025",
        "description": "India's first LEED Platinum certified hotel. Green luxury at its finest, set in Bangalore's commercial heart.",
        "city_name": "Bangalore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Residency Road", "landmark": "Near Trinity Metro Station",
        "latitude": Decimal("12.968200"), "longitude": Decimal("77.606500"),
        "rating": Decimal("4.7"), "review_count": 1876, "star_category": 5,
        "popularity_score": 920, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "ITC One Room", "base_price": Decimal("11000"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Executive Suite", "base_price": Decimal("24000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/itc-gardenia-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/itc-gardenia-blr-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-gardenia-blr-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-gardenia-blr-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-gardenia-blr-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Leela Palace Bangalore",
        "property_type": "Palace Hotel",
        "address": "23, Airport Road, Kodihalli, Bangalore, Karnataka 560008",
        "description": "Majestic palace hotel inspired by Hoysala architecture. Opulent rooms, rooftop pool and exceptional dining.",
        "city_name": "Bangalore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Kodihalli", "landmark": "Near HAL Airport Road",
        "latitude": Decimal("12.959800"), "longitude": Decimal("77.645200"),
        "rating": Decimal("4.8"), "review_count": 2543, "star_category": 5,
        "popularity_score": 960, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("12500"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Royal Suite", "base_price": Decimal("45000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Rooftop Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Butler Service"],
        "images": [
            {"url": "https://picsum.photos/seed/leela-palace-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/leela-palace-blr-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-blr-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-blr-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-blr-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj MG Road Bangalore",
        "property_type": "Hotel",
        "address": "41/3, Mahatma Gandhi Road, Bangalore, Karnataka 560001",
        "description": "Iconic business hotel on MG Road with contemporary rooms, rooftop bar and celebrated Southern Indian cuisine.",
        "city_name": "Bangalore", "state_name": "Karnataka", "state_code": "KA",
        "area": "MG Road", "landmark": "MG Road, Opposite Brigade Road",
        "latitude": Decimal("12.975600"), "longitude": Decimal("77.613000"),
        "rating": Decimal("4.5"), "review_count": 3210, "star_category": 5,
        "popularity_score": 880, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("8500"), "capacity": 2, "bed_type": "King", "available_count": 25},
            {"name": "Junior Suite", "base_price": Decimal("18000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "Fitness Center", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-mg-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-mg-blr-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mg-blr-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mg-blr-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mg-blr-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Radisson Blu Atria Bangalore",
        "property_type": "Hotel",
        "address": "1, Palace Road, Bangalore, Karnataka 560001",
        "description": "Contemporary hotel in the heart of Bangalore with an impressive atrium lobby, pool and extensive dining.",
        "city_name": "Bangalore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Palace Road", "landmark": "Near Raj Bhavan",
        "latitude": Decimal("12.985300"), "longitude": Decimal("77.594600"),
        "rating": Decimal("4.3"), "review_count": 1987, "star_category": 4,
        "popularity_score": 800, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("5800"), "capacity": 2, "bed_type": "Double", "available_count": 28},
            {"name": "Business Class Room", "base_price": Decimal("9000"), "capacity": 2, "bed_type": "King", "available_count": 14},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "Business Centre", "Fitness Center"],
        "images": [
            {"url": "https://picsum.photos/seed/radisson-atria-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/radisson-atria-blr-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-atria-blr-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-atria-blr-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-atria-blr-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  HYDERABAD
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Park Hyatt Hyderabad",
        "property_type": "Luxury Hotel",
        "address": "Road No. 2, Banjara Hills, Hyderabad, Telangana 500034",
        "description": "Contemporary luxury in Banjara Hills with 215 rooms, award-winning restaurants and a stunning outdoor pool.",
        "city_name": "Hyderabad", "state_name": "Telangana", "state_code": "TG",
        "area": "Banjara Hills", "landmark": "Near KBR National Park",
        "latitude": Decimal("17.425200"), "longitude": Decimal("78.452800"),
        "rating": Decimal("4.7"), "review_count": 2341, "star_category": 5,
        "popularity_score": 930, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Park Room", "base_price": Decimal("10000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Park Suite", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "ITC Kohenur Hyderabad",
        "property_type": "Luxury Hotel",
        "address": "HITEC City, Madhapur, Hyderabad, Telangana 500081",
        "description": "Hyderabad's premier super-luxury hotel in HITEC City, inspired by the Kohinoor diamond with exceptional dining.",
        "city_name": "Hyderabad", "state_name": "Telangana", "state_code": "TG",
        "area": "HITEC City", "landmark": "Next to Shilparamam",
        "latitude": Decimal("17.449700"), "longitude": Decimal("78.387300"),
        "rating": Decimal("4.8"), "review_count": 1876, "star_category": 5,
        "popularity_score": 960, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "ITC One Deluxe", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Presidential Suite", "base_price": Decimal("55000"), "capacity": 4, "bed_type": "King", "available_count": 2},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Novotel Hyderabad Convention Centre",
        "property_type": "Hotel",
        "address": "Novotel & HICC Complex, Madhapur, Hyderabad, Telangana 500081",
        "description": "Largest MICE hotel in India adjacent to India's biggest convention centre, ideal for business and leisure.",
        "city_name": "Hyderabad", "state_name": "Telangana", "state_code": "TG",
        "area": "Madhapur", "landmark": "Adjacent to HICC Convention Centre",
        "latitude": Decimal("17.442100"), "longitude": Decimal("78.379800"),
        "rating": Decimal("4.4"), "review_count": 4231, "star_category": 5,
        "popularity_score": 870, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("7500"), "capacity": 2, "bed_type": "Double", "available_count": 35},
            {"name": "Executive Room", "base_price": Decimal("11000"), "capacity": 2, "bed_type": "King", "available_count": 20},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Bar", "Business Centre", "Conference Rooms"],
        "images": [
            {"url": "https://picsum.photos/seed/novotel-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/novotel-hyd-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-hyd-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-hyd-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/novotel-hyd-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Krishna Hyderabad",
        "property_type": "Luxury Hotel",
        "address": "Road No. 1, Banjara Hills, Hyderabad, Telangana 500034",
        "description": "Iconic Hyderabad institution with warmth of Nizam hospitality, refined cuisine and a stunning poolside garden.",
        "city_name": "Hyderabad", "state_name": "Telangana", "state_code": "TG",
        "area": "Banjara Hills", "landmark": "Road No. 1, Banjara Hills",
        "latitude": Decimal("17.426900"), "longitude": Decimal("78.447200"),
        "rating": Decimal("4.5"), "review_count": 3154, "star_category": 5,
        "popularity_score": 850, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("9500"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Junior Suite", "base_price": Decimal("20000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "Tennis Court", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-krishna-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-krishna-hyd-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-krishna-hyd-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-krishna-hyd-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-krishna-hyd-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Marriott Hyderabad",
        "property_type": "Hotel",
        "address": "Tank Bund Road, Hussain Sagar, Hyderabad, Telangana 500080",
        "description": "Overlooking Hussain Sagar Lake, this contemporary Marriott offers spectacular city views and superior comfort.",
        "city_name": "Hyderabad", "state_name": "Telangana", "state_code": "TG",
        "area": "Tank Bund", "landmark": "Hussain Sagar Lake",
        "latitude": Decimal("17.435600"), "longitude": Decimal("78.474300"),
        "rating": Decimal("4.4"), "review_count": 2678, "star_category": 5,
        "popularity_score": 820, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("7500"), "capacity": 2, "bed_type": "King", "available_count": 28},
            {"name": "Executive Suite", "base_price": Decimal("18000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Lake View"],
        "images": [
            {"url": "https://picsum.photos/seed/marriott-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/marriott-hyd-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/marriott-hyd-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/marriott-hyd-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/marriott-hyd-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  CHENNAI
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "ITC Grand Chola Chennai",
        "property_type": "Luxury Hotel",
        "address": "63, Mount Road, Guindy, Chennai, Tamil Nadu 600032",
        "description": "India's largest luxury hotel, inspired by the great Chola temples, with palatial rooms and 15 dining outlets.",
        "city_name": "Chennai", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Guindy", "landmark": "Near Guindy National Park",
        "latitude": Decimal("13.010700"), "longitude": Decimal("80.211800"),
        "rating": Decimal("4.9"), "review_count": 3876, "star_category": 5,
        "popularity_score": 980, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "ITC One Room", "base_price": Decimal("13000"), "capacity": 2, "bed_type": "King", "available_count": 30},
            {"name": "Grand Chola Suite", "base_price": Decimal("50000"), "capacity": 4, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/itc-chola-chn-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/itc-chola-chn-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-chola-chn-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-chola-chn-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-chola-chn-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Leela Palace Chennai",
        "property_type": "Palace Hotel",
        "address": "MRC Nagar, Raja Annamalai Puram, Chennai, Tamil Nadu 600028",
        "description": "A grand bayfront palace offering sweeping Bay of Bengal views, elegant rooms and a legendary spa.",
        "city_name": "Chennai", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "MRC Nagar", "landmark": "Opposite Chennai Boat Club",
        "latitude": Decimal("13.001500"), "longitude": Decimal("80.270600"),
        "rating": Decimal("4.8"), "review_count": 2198, "star_category": 5,
        "popularity_score": 955, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("11500"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Bay Suite", "base_price": Decimal("32000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Sea View Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Butler Service"],
        "images": [
            {"url": "https://picsum.photos/seed/leela-palace-chn-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/leela-palace-chn-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-chn-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-chn-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-chn-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Coromandel Chennai",
        "property_type": "Luxury Hotel",
        "address": "37, Mahatma Gandhi Road, Nungambakkam, Chennai, Tamil Nadu 600034",
        "description": "Enduring landmark of Tamil Nadu's hospitality. Art-filled corridors, award-winning dining, central location.",
        "city_name": "Chennai", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Nungambakkam", "landmark": "Nungambakkam High Road",
        "latitude": Decimal("13.063400"), "longitude": Decimal("80.254800"),
        "rating": Decimal("4.7"), "review_count": 3012, "star_category": 5,
        "popularity_score": 910, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Taj Club Room", "base_price": Decimal("9500"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Luxury Suite", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-coromandel-chn-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-coromandel-chn-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-coromandel-chn-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-coromandel-chn-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-coromandel-chn-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Hyatt Regency Chennai",
        "property_type": "Hotel",
        "address": "365, Anna Salai, Teynampet, Chennai, Tamil Nadu 600018",
        "description": "Modern high-rise on Anna Salai with panoramic city views, rooftop pool and Chennai's best Sunday brunch.",
        "city_name": "Chennai", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Teynampet", "landmark": "Anna Salai, Near Gemini Flyover",
        "latitude": Decimal("13.042900"), "longitude": Decimal("80.255600"),
        "rating": Decimal("4.5"), "review_count": 2543, "star_category": 5,
        "popularity_score": 860, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "King Room", "base_price": Decimal("7800"), "capacity": 2, "bed_type": "King", "available_count": 25},
            {"name": "Regency Suite", "base_price": Decimal("20000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Rooftop Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/hyatt-regency-chn-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/hyatt-regency-chn-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/hyatt-regency-chn-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/hyatt-regency-chn-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/hyatt-regency-chn-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Trident Chennai",
        "property_type": "Hotel",
        "address": "1/24, GST Road, Chennai, Tamil Nadu 600027",
        "description": "Elegant business hotel near the airport with warm hospitality, a lovely pool garden and excellent dining.",
        "city_name": "Chennai", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Meenambakkam", "landmark": "Near Chennai International Airport",
        "latitude": Decimal("12.993600"), "longitude": Decimal("80.177500"),
        "rating": Decimal("4.4"), "review_count": 1876, "star_category": 5,
        "popularity_score": 820, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("6800"), "capacity": 2, "bed_type": "King", "available_count": 24},
            {"name": "Junior Suite", "base_price": Decimal("14000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "Fitness Center", "Airport Transfer"],
        "images": [
            {"url": "https://picsum.photos/seed/trident-chn-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/trident-chn-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/trident-chn-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/trident-chn-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/trident-chn-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  MUMBAI
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Taj Mahal Palace Mumbai",
        "property_type": "Heritage Hotel",
        "address": "Apollo Bunder, Colaba, Mumbai, Maharashtra 400001",
        "description": "India's most iconic hotel, standing since 1903 opposite the Gateway of India. Timeless grandeur, legendary service.",
        "city_name": "Mumbai", "state_name": "Maharashtra", "state_code": "MH",
        "area": "Colaba", "landmark": "Opposite Gateway of India",
        "latitude": Decimal("18.921900"), "longitude": Decimal("72.833100"),
        "rating": Decimal("4.9"), "review_count": 8765, "star_category": 5,
        "popularity_score": 999, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("22000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Heritage Grand Luxury", "base_price": Decimal("65000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Butler Service", "Heritage Tour"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-palace-mum-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-palace-mum-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-palace-mum-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-palace-mum-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-palace-mum-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Oberoi Mumbai",
        "property_type": "Luxury Hotel",
        "address": "Nariman Point, Mumbai, Maharashtra 400021",
        "description": "Contemporary masterpiece on Marine Drive offering floor-to-ceiling ocean views and butler-serviced rooms.",
        "city_name": "Mumbai", "state_name": "Maharashtra", "state_code": "MH",
        "area": "Nariman Point", "landmark": "Marine Drive, Nariman Point",
        "latitude": Decimal("18.926300"), "longitude": Decimal("72.823500"),
        "rating": Decimal("4.9"), "review_count": 4321, "star_category": 5,
        "popularity_score": 990, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Premier Room", "base_price": Decimal("20000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Ocean View Suite", "base_price": Decimal("55000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "Sea View"],
        "images": [
            {"url": "https://picsum.photos/seed/oberoi-mum-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/oberoi-mum-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-mum-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-mum-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-mum-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "JW Marriott Mumbai Juhu",
        "property_type": "Luxury Hotel",
        "address": "Juhu Tara Road, Mumbai, Maharashtra 400049",
        "description": "Beachfront luxury in Bollywood's neighbourhood. Vibrant dining, spa and direct access to Juhu Beach.",
        "city_name": "Mumbai", "state_name": "Maharashtra", "state_code": "MH",
        "area": "Juhu", "landmark": "Juhu Beach",
        "latitude": Decimal("19.100200"), "longitude": Decimal("72.826600"),
        "rating": Decimal("4.6"), "review_count": 3987, "star_category": 5,
        "popularity_score": 930, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Ocean Suite", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Beach Access", "Pool", "Spa", "Restaurant", "Bar", "Fitness Center"],
        "images": [
            {"url": "https://picsum.photos/seed/jw-juhu-mum-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/jw-juhu-mum-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/jw-juhu-mum-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/jw-juhu-mum-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/jw-juhu-mum-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Lands End Mumbai",
        "property_type": "Luxury Hotel",
        "address": "Bandstand, Bandra West, Mumbai, Maharashtra 400050",
        "description": "Bandra's iconic seafront hotel with dramatic sea views, celebrity neighbourhood and award-winning restaurants.",
        "city_name": "Mumbai", "state_name": "Maharashtra", "state_code": "MH",
        "area": "Bandra West", "landmark": "Bandstand, Bandra",
        "latitude": Decimal("19.051400"), "longitude": Decimal("72.817500"),
        "rating": Decimal("4.7"), "review_count": 2876, "star_category": 5,
        "popularity_score": 940, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Sea View", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Junior Suite", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Sea View"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-lands-end-mum-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-lands-end-mum-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-lands-end-mum-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-lands-end-mum-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-lands-end-mum-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Four Seasons Hotel Mumbai",
        "property_type": "Luxury Hotel",
        "address": "114, Dr E Moses Road, Worli, Mumbai, Maharashtra 400018",
        "description": "Stunning 34-floor tower in Worli with panoramic skyline views, rooftop infinity pool and world-class dining.",
        "city_name": "Mumbai", "state_name": "Maharashtra", "state_code": "MH",
        "area": "Worli", "landmark": "Near Bandra-Worli Sea Link",
        "latitude": Decimal("19.015900"), "longitude": Decimal("72.815500"),
        "rating": Decimal("4.8"), "review_count": 2134, "star_category": 5,
        "popularity_score": 960, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "City View Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Sky Suite", "base_price": Decimal("60000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Rooftop Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "City View"],
        "images": [
            {"url": "https://picsum.photos/seed/four-seasons-mum-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/four-seasons-mum-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/four-seasons-mum-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/four-seasons-mum-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/four-seasons-mum-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  DELHI  (NCR)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "The Imperial New Delhi",
        "property_type": "Heritage Hotel",
        "address": "Janpath Lane, New Delhi 110001",
        "description": "Delhi's most iconic address since 1936. Art Deco masterpiece with a legendary collection of colonial artworks.",
        "city_name": "Delhi", "state_name": "Delhi", "state_code": "DL",
        "area": "Connaught Place", "landmark": "Janpath, Near Connaught Place",
        "latitude": Decimal("28.627800"), "longitude": Decimal("77.220800"),
        "rating": Decimal("4.8"), "review_count": 5432, "star_category": 5,
        "popularity_score": 985, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("15000"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Imperial Suite", "base_price": Decimal("55000"), "capacity": 4, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Heritage Walk", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/imperial-del-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/imperial-del-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/imperial-del-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/imperial-del-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/imperial-del-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Oberoi New Delhi",
        "property_type": "Luxury Hotel",
        "address": "Dr Zakir Hussain Marg, New Delhi 110003",
        "description": "Overlooking the Delhi Golf Course, this serene oasis offers contemporary luxury with personalised butler service.",
        "city_name": "Delhi", "state_name": "Delhi", "state_code": "DL",
        "area": "Golf Course", "landmark": "Facing Delhi Golf Course",
        "latitude": Decimal("28.592700"), "longitude": Decimal("77.231900"),
        "rating": Decimal("4.9"), "review_count": 3210, "star_category": 5,
        "popularity_score": 975, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Luxury Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Golf View Suite", "base_price": Decimal("48000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Golf Course View", "Restaurant", "Bar", "Butler Service"],
        "images": [
            {"url": "https://picsum.photos/seed/oberoi-del-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/oberoi-del-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-del-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-del-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/oberoi-del-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Mahal Hotel New Delhi",
        "property_type": "Luxury Hotel",
        "address": "1 Man Singh Road, New Delhi 110011",
        "description": "Landmark hotel opposite India Gate, combining Mughal-inspired architecture with 21st-century luxury.",
        "city_name": "Delhi", "state_name": "Delhi", "state_code": "DL",
        "area": "India Gate", "landmark": "Opposite India Gate",
        "latitude": Decimal("28.610900"), "longitude": Decimal("77.228400"),
        "rating": Decimal("4.8"), "review_count": 4123, "star_category": 5,
        "popularity_score": 965, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Taj Club Room", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Luxury Suite", "base_price": Decimal("40000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-mahal-del-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-mahal-del-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mahal-del-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mahal-del-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-mahal-del-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "ITC Maurya New Delhi",
        "property_type": "Luxury Hotel",
        "address": "Sardar Patel Marg, Diplomatic Enclave, New Delhi 110021",
        "description": "In the heart of the Diplomatic Enclave, home to the legendary Bukhara and Dum Pukht restaurants.",
        "city_name": "Delhi", "state_name": "Delhi", "state_code": "DL",
        "area": "Chanakyapuri", "landmark": "Diplomatic Enclave",
        "latitude": Decimal("28.596400"), "longitude": Decimal("77.178200"),
        "rating": Decimal("4.7"), "review_count": 3456, "star_category": 5,
        "popularity_score": 930, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "ITC One Room", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 22},
            {"name": "Diplomatic Suite", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/itc-maurya-del-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/itc-maurya-del-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-maurya-del-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-maurya-del-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/itc-maurya-del-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Leela Palace New Delhi",
        "property_type": "Palace Hotel",
        "address": "Chanakyapuri, New Delhi 110023",
        "description": "Delhi's most opulent palace hotel at Chanakyapuri, with gilded Rajasthani architecture and Michelin-starred dining.",
        "city_name": "Delhi", "state_name": "Delhi", "state_code": "DL",
        "area": "Chanakyapuri", "landmark": "Near US Embassy",
        "latitude": Decimal("28.592100"), "longitude": Decimal("77.186800"),
        "rating": Decimal("4.9"), "review_count": 2987, "star_category": 5,
        "popularity_score": 980, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("20000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Royal Suite", "base_price": Decimal("70000"), "capacity": 4, "bed_type": "King", "available_count": 3},
        ],
        "amenities": ["Free WiFi", "Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Butler Service", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/leela-palace-del-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/leela-palace-del-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-del-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-del-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/leela-palace-del-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  OOTY  (Udhagamandalam, Tamil Nadu)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Taj Savoy Hotel Ooty",
        "property_type": "Heritage Hotel",
        "address": "77, Sylks Road, Ooty, Tamil Nadu 643001",
        "description": "Victorian-era heritage hotel nestled in lush gardens, opened in 1829. The quintessential Ooty experience.",
        "city_name": "Ooty", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Charring Cross", "landmark": "Near Charring Cross, Ooty Town",
        "latitude": Decimal("11.406500"), "longitude": Decimal("76.695200"),
        "rating": Decimal("4.5"), "review_count": 1876, "star_category": 4,
        "popularity_score": 900, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Room", "base_price": Decimal("6500"), "capacity": 2, "bed_type": "Queen", "available_count": 16},
            {"name": "Garden Cottage", "base_price": Decimal("12000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Garden", "Restaurant", "Bar", "Billiards Room", "Tennis Court", "Fireplace"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-savoy-ooty-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-savoy-ooty-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-savoy-ooty-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-savoy-ooty-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-savoy-ooty-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Fortune Sullivan Court Ooty",
        "property_type": "Hotel",
        "address": "Sullivan Court, Ooty, Tamil Nadu 643001",
        "description": "Well-appointed hotel with mountain views, a warm fireplace lounge and authentic Tamil Nilgiri cuisine.",
        "city_name": "Ooty", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Charring Cross", "landmark": "Near Ooty Lake",
        "latitude": Decimal("11.412300"), "longitude": Decimal("76.697100"),
        "rating": Decimal("4.3"), "review_count": 1543, "star_category": 4,
        "popularity_score": 830, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("4800"), "capacity": 2, "bed_type": "Double", "available_count": 20},
            {"name": "Suite", "base_price": Decimal("9000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Restaurant", "Bar", "Fitness Center", "Fireplace Lounge", "Garden"],
        "images": [
            {"url": "https://picsum.photos/seed/fortune-ooty-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/fortune-ooty-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-ooty-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-ooty-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-ooty-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Sinclairs Retreat Ooty",
        "property_type": "Resort",
        "address": "Sheddon Road, Ooty, Tamil Nadu 643001",
        "description": "Charming Ooty retreat with cottages perched on a hillside, surrounded by eucalyptus and tea garden views.",
        "city_name": "Ooty", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Sheddon Road", "landmark": "Opposite Ooty Club",
        "latitude": Decimal("11.399800"), "longitude": Decimal("76.694600"),
        "rating": Decimal("4.2"), "review_count": 987, "star_category": 4,
        "popularity_score": 760, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("3800"), "capacity": 2, "bed_type": "Double", "available_count": 18},
            {"name": "Hill View Cottage", "base_price": Decimal("6500"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Restaurant", "Garden", "Bonfire", "Tea Garden View", "Cycling"],
        "images": [
            {"url": "https://picsum.photos/seed/sinclairs-ooty-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/sinclairs-ooty-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sinclairs-ooty-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sinclairs-ooty-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sinclairs-ooty-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Fern Hill Ooty",
        "property_type": "Heritage Resort",
        "address": "Fern Hill, Ooty, Tamil Nadu 643004",
        "description": "Former Maharaja's summer palace converted into a luxury resort in a 3-acre Victorian garden estate.",
        "city_name": "Ooty", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Fern Hill", "landmark": "Fern Hill Palace Estate",
        "latitude": Decimal("11.395200"), "longitude": Decimal("76.702100"),
        "rating": Decimal("4.6"), "review_count": 1234, "star_category": 5,
        "popularity_score": 870, "is_trending": True, "has_free_cancellation": False,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Room", "base_price": Decimal("8500"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Palace Suite", "base_price": Decimal("22000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Victorian Garden", "Restaurant", "Bar", "Spa", "Horse Riding", "Heritage Tours"],
        "images": [
            {"url": "https://picsum.photos/seed/fern-hill-ooty-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/fern-hill-ooty-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fern-hill-ooty-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fern-hill-ooty-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fern-hill-ooty-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Sterling Ooty Elk Hill",
        "property_type": "Resort",
        "address": "Elk Hill Road, Ooty, Tamil Nadu 643002",
        "description": "Perched on Elk Hill with breathtaking 360° views of the Nilgiris. Private cottages amid pine and eucalyptus.",
        "city_name": "Ooty", "state_name": "Tamil Nadu", "state_code": "TN",
        "area": "Elk Hill", "landmark": "Elk Hill, Near Nilgiri Mountain Railway",
        "latitude": Decimal("11.403600"), "longitude": Decimal("76.700400"),
        "rating": Decimal("4.1"), "review_count": 2109, "star_category": 3,
        "popularity_score": 730, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Cottage Room", "base_price": Decimal("3200"), "capacity": 2, "bed_type": "Twin", "available_count": 22},
            {"name": "Hill View Suite", "base_price": Decimal("5500"), "capacity": 3, "bed_type": "Double", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Restaurant", "Bonfire", "Mountain Views", "Trekking", "Cycling"],
        "images": [
            {"url": "https://picsum.photos/seed/sterling-ooty-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/sterling-ooty-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sterling-ooty-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sterling-ooty-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/sterling-ooty-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  MYSORE  (Mysuru, Karnataka)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Radisson Blu Plaza Hotel Mysore",
        "property_type": "Hotel",
        "address": "No. 1, Nazarbad Main Road, Mysore, Karnataka 570010",
        "description": "Contemporary luxury hotel in the cultural capital of Karnataka with a striking outdoor pool and rooftop dining.",
        "city_name": "Mysore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Nazarbad", "landmark": "Near Mysore Palace",
        "latitude": Decimal("12.301200"), "longitude": Decimal("76.643500"),
        "rating": Decimal("4.5"), "review_count": 2109, "star_category": 5,
        "popularity_score": 880, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("5800"), "capacity": 2, "bed_type": "King", "available_count": 24},
            {"name": "Junior Suite", "base_price": Decimal("10000"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "Fitness Center", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/radisson-mys-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/radisson-mys-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-mys-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-mys-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/radisson-mys-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Lalitha Mahal Palace Hotel",
        "property_type": "Heritage Hotel",
        "address": "Lalitha Mahal Road, T. Narasipura Road, Mysore, Karnataka 570011",
        "description": "Majestic heritage palace built in 1921 for the Viceroy, now a government hotel preserving royal grandeur.",
        "city_name": "Mysore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Lalitha Mahal", "landmark": "Lalitha Mahal Road",
        "latitude": Decimal("12.287600"), "longitude": Decimal("76.668400"),
        "rating": Decimal("4.3"), "review_count": 1432, "star_category": 5,
        "popularity_score": 820, "is_trending": True, "has_free_cancellation": False,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Regency Room", "base_price": Decimal("4200"), "capacity": 2, "bed_type": "Double", "available_count": 18},
            {"name": "Viceroy Suite", "base_price": Decimal("12000"), "capacity": 4, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Heritage Tours", "Garden", "Billiards"],
        "images": [
            {"url": "https://picsum.photos/seed/lalitha-mahal-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/lalitha-mahal-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/lalitha-mahal-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/lalitha-mahal-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/lalitha-mahal-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Windflower Spa & Resort Mysore",
        "property_type": "Spa Resort",
        "address": "Mysore-Bangalore Highway, Mysore, Karnataka 570018",
        "description": "A 7-acre wellness resort on the Bangalore highway with Ayurvedic spa, organic cuisine and a serene pool garden.",
        "city_name": "Mysore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Highway Area", "landmark": "Mysore-Bangalore Highway",
        "latitude": Decimal("12.359800"), "longitude": Decimal("76.608900"),
        "rating": Decimal("4.6"), "review_count": 1876, "star_category": 5,
        "popularity_score": 860, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Luxury Room", "base_price": Decimal("6500"), "capacity": 2, "bed_type": "King", "available_count": 16},
            {"name": "Pool Cottage", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Ayurveda", "Yoga", "Restaurant", "Organic Garden"],
        "images": [
            {"url": "https://picsum.photos/seed/windflower-mys-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/windflower-mys-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/windflower-mys-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/windflower-mys-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/windflower-mys-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Fortune JP Palace Mysore",
        "property_type": "Hotel",
        "address": "3, JC Road, Gandhi Square, Mysore, Karnataka 570001",
        "description": "Central business and leisure hotel in the heart of Mysore near Gandhi Square with excellent city connectivity.",
        "city_name": "Mysore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Gandhi Square", "landmark": "Near Gandhi Square",
        "latitude": Decimal("12.304700"), "longitude": Decimal("76.637200"),
        "rating": Decimal("4.2"), "review_count": 2543, "star_category": 4,
        "popularity_score": 790, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("3800"), "capacity": 2, "bed_type": "Double", "available_count": 22},
            {"name": "Junior Suite", "base_price": Decimal("7500"), "capacity": 3, "bed_type": "King", "available_count": 8},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Business Centre", "Fitness Center"],
        "images": [
            {"url": "https://picsum.photos/seed/fortune-jp-mys-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/fortune-jp-mys-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-jp-mys-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-jp-mys-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/fortune-jp-mys-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Royal Orchid Metropole Mysore",
        "property_type": "Heritage Hotel",
        "address": "5, Jhansi Lakshmibai Road, Mysore, Karnataka 570005",
        "description": "Heritage boutique hotel built in 1920 adjacent to Mysore Palace, retaining colonial-era charm and elegance.",
        "city_name": "Mysore", "state_name": "Karnataka", "state_code": "KA",
        "area": "Mysore Palace Area", "landmark": "Adjacent to Mysore Palace",
        "latitude": Decimal("12.306900"), "longitude": Decimal("76.654200"),
        "rating": Decimal("4.4"), "review_count": 1987, "star_category": 4,
        "popularity_score": 830, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Room", "base_price": Decimal("4500"), "capacity": 2, "bed_type": "Queen", "available_count": 14},
            {"name": "Palace View Suite", "base_price": Decimal("9000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Heritage Garden", "Palace View"],
        "images": [
            {"url": "https://picsum.photos/seed/royal-orchid-mys-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/royal-orchid-mys-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/royal-orchid-mys-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/royal-orchid-mys-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/royal-orchid-mys-5/800/600", "is_featured": False},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    #  PONDICHERRY  (Puducherry)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "name": "Le Dupleix Pondicherry",
        "property_type": "Boutique Hotel",
        "address": "5, La Bourdonnais Street, White Town, Pondicherry 605001",
        "description": "Beautifully restored 18th-century French mansion in White Town. The best of Pondicherry's French quarter.",
        "city_name": "Pondicherry", "state_name": "Puducherry", "state_code": "PY",
        "area": "White Town", "landmark": "La Bourdonnais Street, French Quarter",
        "latitude": Decimal("11.934900"), "longitude": Decimal("79.833600"),
        "rating": Decimal("4.7"), "review_count": 1876, "star_category": 5,
        "popularity_score": 920, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Room", "base_price": Decimal("8500"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Suite", "base_price": Decimal("18000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Restaurant", "Bar", "French Heritage Tours", "Yoga"],
        "images": [
            {"url": "https://picsum.photos/seed/le-dupleix-pon-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/le-dupleix-pon-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/le-dupleix-pon-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/le-dupleix-pon-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/le-dupleix-pon-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Palais de Mahe",
        "property_type": "Boutique Hotel",
        "address": "3, Rue Surcouf, White Town, Pondicherry 605001",
        "description": "A 21-room boutique hotel in a carefully restored French colonial building, steps from the Promenade Beach.",
        "city_name": "Pondicherry", "state_name": "Puducherry", "state_code": "PY",
        "area": "White Town", "landmark": "Near Promenade Beach",
        "latitude": Decimal("11.931200"), "longitude": Decimal("79.836400"),
        "rating": Decimal("4.6"), "review_count": 1243, "star_category": 4,
        "popularity_score": 860, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Room", "base_price": Decimal("7000"), "capacity": 2, "bed_type": "Queen", "available_count": 12},
            {"name": "Premium Suite", "base_price": Decimal("14000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Heritage Building", "Beach Proximity"],
        "images": [
            {"url": "https://picsum.photos/seed/palais-mahe-pon-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/palais-mahe-pon-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/palais-mahe-pon-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/palais-mahe-pon-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/palais-mahe-pon-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Promenade Pondicherry",
        "property_type": "Hotel",
        "address": "5, Beach Road, White Town, Pondicherry 605001",
        "description": "Beachfront hotel on the famous Promenade, with contemporary rooms, sea views and Pondicherry's best brunch.",
        "city_name": "Pondicherry", "state_name": "Puducherry", "state_code": "PY",
        "area": "Promenade Beach", "landmark": "Beach Road Promenade",
        "latitude": Decimal("11.930400"), "longitude": Decimal("79.838200"),
        "rating": Decimal("4.4"), "review_count": 2310, "star_category": 4,
        "popularity_score": 830, "is_trending": False, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Sea View Room", "base_price": Decimal("6500"), "capacity": 2, "bed_type": "King", "available_count": 14},
            {"name": "Deluxe Suite", "base_price": Decimal("12000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Restaurant", "Bar", "Sea View", "Beach Access"],
        "images": [
            {"url": "https://picsum.photos/seed/promenade-pon-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/promenade-pon-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/promenade-pon-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/promenade-pon-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/promenade-pon-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Villa Shanti Pondicherry",
        "property_type": "Boutique Hotel",
        "address": "14, Suffren Street, White Town, Pondicherry 605001",
        "description": "Charming 16-room boutique hotel in the French Quarter. Award-winning restaurant and rooftop yoga deck.",
        "city_name": "Pondicherry", "state_name": "Puducherry", "state_code": "PY",
        "area": "White Town", "landmark": "Suffren Street, French Quarter",
        "latitude": Decimal("11.932700"), "longitude": Decimal("79.834900"),
        "rating": Decimal("4.5"), "review_count": 987, "star_category": 4,
        "popularity_score": 790, "is_trending": False, "has_free_cancellation": False,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Classic Room", "base_price": Decimal("5500"), "capacity": 2, "bed_type": "Queen", "available_count": 10},
            {"name": "Heritage Suite", "base_price": Decimal("10000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Rooftop Terrace", "Restaurant", "Yoga Deck", "French Heritage", "Bicycle Rental"],
        "images": [
            {"url": "https://picsum.photos/seed/villa-shanti-pon-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/villa-shanti-pon-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/villa-shanti-pon-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/villa-shanti-pon-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/villa-shanti-pon-5/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Fisherman's Cove Chennai",
        "property_type": "Luxury Resort",
        "address": "Covelong Beach, Kanchipuram District, Tamil Nadu 603112",
        "description": "Secluded beachfront resort near Pondicherry on the Coromandel Coast with private beach and water sports.",
        "city_name": "Pondicherry", "state_name": "Puducherry", "state_code": "PY",
        "area": "Covelong", "landmark": "Covelong Beach, East Coast Road",
        "latitude": Decimal("12.773800"), "longitude": Decimal("80.249600"),
        "rating": Decimal("4.7"), "review_count": 3210, "star_category": 5,
        "popularity_score": 890, "is_trending": True, "has_free_cancellation": True,
        "status": "approved", "agreement_signed": True,
        "room_types": [
            {"name": "Sea View Room", "base_price": Decimal("11000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Beach Villa", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Private Beach", "Swimming Pool", "Spa", "Restaurant", "Water Sports", "Fishing"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-fishermans-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-fishermans-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-fishermans-3/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-fishermans-4/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/taj-fishermans-5/800/600", "is_featured": False},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
#  MANAGEMENT COMMAND
# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Seed complete OTA hotel data — 10 cities, 5 properties each, 5 images each.'

    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, default='', help='Only seed one city')
        parser.add_argument('--fresh', action='store_true', help='Delete all existing properties first')
        parser.add_argument('--inventory-days', type=int, default=180)

    def handle(self, *args, **options):
        from apps.hotels.models import Property, PropertyImage, PropertyAmenity
        from apps.rooms.models import RoomType, RoomInventory
        from apps.core.location_models import Country, State, City, Locality
        from django.contrib.auth import get_user_model
        from django.utils.text import slugify

        User = get_user_model()
        city_filter = options['city'].strip().lower()
        fresh = options['fresh']
        inventory_days = options['inventory_days']

        if fresh:
            self.stdout.write(self.style.WARNING('--fresh: deleting all properties...'))
            Property.objects.all().delete()

        # System admin owner
        admin, _ = User.objects.get_or_create(
            email='admin@zygotrip.com',
            defaults={'full_name': 'ZygoTrip Admin', 'is_staff': True, 'is_superuser': True}
        )
        india, _ = Country.objects.get_or_create(
            code='IN',
            defaults={'name': 'India', 'display_name': 'India', 'is_active': True}
        )

        props_to_seed = OTA_PROPERTIES
        if city_filter:
            props_to_seed = [p for p in OTA_PROPERTIES if p['city_name'].lower() == city_filter]

        self.stdout.write(self.style.HTTP_INFO(f'\n=== Seeding {len(props_to_seed)} properties ==='))

        created = skipped = 0
        for prop_data in props_to_seed:
            with transaction.atomic():
                result = self._seed_property(
                    prop_data, india, admin,
                    Property, PropertyImage, PropertyAmenity,
                    RoomType, State, City, Locality, slugify
                )
                if result == 'created':
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(f'\n  Created: {created}  Skipped (existing): {skipped}')

        # Seed RoomInventory
        self.stdout.write('\n--- Seeding RoomInventory ---')
        self._seed_inventory(inventory_days, RoomInventory, RoomType)

        # Rebuild search index
        self.stdout.write('\n--- Rebuilding SearchIndex ---')
        try:
            from apps.search.index_builder import rebuild_search_index
            totals = rebuild_search_index()
            self.stdout.write(self.style.SUCCESS(
                f'  SearchIndex rebuilt: cities={totals["cities"]}, '
                f'areas={totals["areas"]}, properties={totals["properties"]}, '
                f'location_idx={totals.get("location_entries", "?")}'
            ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  SearchIndex rebuild skipped: {exc}'))

        self.stdout.write(self.style.SUCCESS('\n[OK] seed_ota_complete done!\n'))

    def _seed_property(
        self, data, india, admin,
        Property, PropertyImage, PropertyAmenity,
        RoomType, State, City, Locality, slugify
    ):
        # State
        state, _ = State.objects.get_or_create(
            code=data['state_code'], country=india,
            defaults={'name': data['state_name'], 'display_name': data['state_name']}
        )

        # City
        city_slug = slugify(data['city_name'])
        city, _ = City.objects.get_or_create(
            slug=city_slug,
            defaults={
                'state': state,
                'name': data['city_name'],
                'display_name': data['city_name'],
                'code': data['state_code'] + '_' + data['city_name'][:4].upper(),
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'is_active': True,
                'is_top_destination': True,
            }
        )

        # Locality (area within city)
        locality = None
        if data.get('area'):
            locality_slug = slugify(f"{data['area']}-{data['city_name']}")
            try:
                locality, _ = Locality.objects.get_or_create(
                    city=city,
                    name=data['area'],
                    defaults={
                        'display_name': data['area'],
                        'slug': locality_slug[:120],
                        'latitude': data['latitude'],
                        'longitude': data['longitude'],
                        'is_active': True,
                        'locality_type': 'tourist',
                    }
                )
            except Exception:
                pass  # Locality creation is best-effort

        # Skip if already exists
        prop_slug = slugify(data['name'])
        if Property.objects.filter(slug=prop_slug).exists():
            self.stdout.write(f'  [SKIP] {data["name"]}')
            return 'skipped'

        prop = Property(
            owner=admin,
            name=data['name'],
            slug=prop_slug,
            property_type=data['property_type'],
            address=data['address'],
            description=data['description'],
            city=city,
            locality=locality,
            area=data.get('area', ''),
            landmark=data.get('landmark', ''),
            latitude=data['latitude'],
            longitude=data['longitude'],
            rating=data['rating'],
            review_count=data['review_count'],
            star_category=data['star_category'],
            popularity_score=data['popularity_score'],
            is_trending=data['is_trending'],
            has_free_cancellation=data['has_free_cancellation'],
            status=data['status'],
            agreement_signed=data['agreement_signed'],
        )
        # Bypass slug generation in save()
        prop.slug = prop_slug
        prop.full_clean()
        prop.save()

        # Room types
        for rt_data in data.get('room_types', []):
            RoomType.objects.get_or_create(
                property=prop,
                name=rt_data['name'],
                defaults={
                    'base_price': rt_data['base_price'],
                    'capacity': rt_data['capacity'],
                    'bed_type': rt_data.get('bed_type', 'King'),
                    'available_count': rt_data.get('available_count', 10),
                }
            )

        # Images (exactly 5)
        for i, img in enumerate(data.get('images', [])[:5]):
            PropertyImage.objects.get_or_create(
                property=prop,
                image_url=img['url'],
                defaults={'is_featured': img.get('is_featured', i == 0), 'display_order': i}
            )

        # Amenities
        for amenity_name in data.get('amenities', []):
            PropertyAmenity.objects.get_or_create(
                property=prop,
                name=amenity_name,
                defaults={'icon': ''}
            )

        self.stdout.write(self.style.SUCCESS(f'  [CREATE] {data["name"]}'))
        return 'created'

    def _seed_inventory(self, days, RoomInventory, RoomType):
        from apps.hotels.models import Property
        today = date.today()
        props = Property.objects.filter(status='approved', agreement_signed=True)
        total = 0
        for prop in props:
            for rt in RoomType.objects.filter(property=prop):
                inv_bulk = []
                for d in range(days):
                    target = today + timedelta(days=d)
                    if not RoomInventory.objects.filter(room_type=rt, date=target).exists():
                        inv_bulk.append(RoomInventory(
                            room_type=rt,
                            date=target,
                            available_count=rt.available_count,
                            price=rt.base_price,
                        ))
                if inv_bulk:
                    RoomInventory.objects.bulk_create(inv_bulk, ignore_conflicts=True)
                    total += len(inv_bulk)
        self.stdout.write(f'  RoomInventory rows created: {total}')
