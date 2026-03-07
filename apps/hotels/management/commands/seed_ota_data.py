"""
Management command: seed_ota_data
Seeds production-grade OTA hotel data for:
  Coorg, Bangalore, Hyderabad, Goa, Mumbai

Run:
  python manage.py seed_ota_data
  python manage.py seed_ota_data --city Coorg
  python manage.py seed_ota_data --inventory-days 365
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta


OTA_PROPERTIES = [
    # ══ COORG (Kodagu) ══════════════════════════════════════════════════════
    {
        "name": "Evolve Back Coorg",
        "property_type": "Luxury Resort",
        "address": "Pollibetta, Kodagu, Karnataka 571215",
        "description": (
            "Evolve Back Coorg is one of India's finest luxury resorts, "
            "nestled in a 300-acre coffee plantation in the Nalnad Estate. "
            "Its 14 beautifully crafted private pool villas blend Kodava heritage "
            "with contemporary luxury. Guests enjoy plantation walks, spice tours, "
            "a stunning infinity pool and award-winning cuisine."
        ),
        "city_name": "Coorg",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Pollibetta",
        "landmark": "Orange County Estate, 22 km from Madikeri",
        "latitude": Decimal("12.396800"),
        "longitude": Decimal("75.705200"),
        "place_id": "ChIJp7T9SmcIrDsRIBhnnF1xnXM",
        "formatted_address": "Pollibetta, Kodagu, Karnataka 571215, India",
        "rating": Decimal("4.9"),
        "review_count": 2876,
        "star_category": 5,
        "popularity_score": 980,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Heritage Villa", "base_price": Decimal("30000"), "capacity": 2, "bed_type": "King", "available_count": 6},
            {"name": "Plantation Pool Villa", "base_price": Decimal("50000"), "capacity": 3, "bed_type": "King", "available_count": 4},
            {"name": "Family Estate Villa", "base_price": Decimal("70000"), "capacity": 6, "bed_type": "King", "available_count": 2},
        ],
        "amenities": ["Free WiFi", "Private Pool", "Coffee Plantation Tour", "Spa", "Restaurant", "Outdoor Dining", "Campfire", "Cycling"],
        "images": [
            {"url": "https://picsum.photos/seed/evolve-back-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/evolve-back-coorg-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/evolve-back-coorg-3/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Madikeri Resort & Spa",
        "property_type": "Luxury Resort",
        "address": "Block 4, Galibeedu Post, Madikeri, Kodagu, Karnataka 571201",
        "description": (
            "Taj Madikeri Resort & Spa is a serene hilltop sanctuary in the misty "
            "mountains of Coorg. Its 57 beautifully appointed cottages and villas "
            "offer panoramic views of rainforest and paddy fields. The all-inclusive "
            "experience features local Kodava cuisine, guided forest treks and "
            "an award-winning spa."
        ),
        "city_name": "Coorg",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Galibeedu",
        "landmark": "8 km from Madikeri town",
        "latitude": Decimal("12.432700"),
        "longitude": Decimal("75.741300"),
        "place_id": "ChIJr9T3AqsIrDsRuoIUOxoUi-E",
        "formatted_address": "Block 4, Galibeedu Post, Madikeri, Kodagu 571201, India",
        "rating": Decimal("4.8"),
        "review_count": 1943,
        "star_category": 5,
        "popularity_score": 940,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Forest Cottage", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Valley View Villa", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 6},
            {"name": "Presidential Suite", "base_price": Decimal("55000"), "capacity": 4, "bed_type": "King", "available_count": 2},
        ],
        "amenities": ["Free WiFi", "Infinity Pool", "Spa", "Forest Treks", "Restaurant", "Bar", "Yoga", "Bird Watching"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-madikeri-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-madikeri-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Tamara Coorg",
        "property_type": "Luxury Resort",
        "address": "Yavakapadi Estate, Galibeedu, Coorg, Karnataka 571201",
        "description": (
            "The Tamara Coorg is a stunning 340-acre estate resort set among "
            "lush coffee, pepper and cardamom plantations. Each of the 24 villas "
            "enjoys complete privacy with a private deck. Guests can explore the "
            "estate on foot, kayak on the private lake and savour farm-to-table "
            "Kodava cuisine."
        ),
        "city_name": "Coorg",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Yavakapadi",
        "landmark": "Near Galibeedu Village",
        "latitude": Decimal("12.418900"),
        "longitude": Decimal("75.755600"),
        "place_id": "ChIJl8KKqKkIrDsR5_4TG8lJG_s",
        "formatted_address": "Yavakapadi Estate, Galibeedu, Coorg 571201, India",
        "rating": Decimal("4.7"),
        "review_count": 1287,
        "star_category": 5,
        "popularity_score": 890,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Estate Villa", "base_price": Decimal("22000"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Pool Villa", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Private Lake", "Kayaking", "Spa", "Restaurant", "Plantation Walks", "Bonfire"],
        "images": [
            {"url": "https://picsum.photos/seed/tamara-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/tamara-coorg-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Club Mahindra Madikeri",
        "property_type": "Resort",
        "address": "Keradala Keri, Madikeri, Kodagu, Karnataka 571201",
        "description": (
            "Club Mahindra Madikeri offers a great blend of comfort and natural "
            "beauty in the heart of Coorg. With well-appointed rooms, a refreshing "
            "pool, multi-cuisine restaurant and activities like coffee estate tours "
            "and trekking, it is perfect for families."
        ),
        "city_name": "Coorg",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Madikeri",
        "landmark": "Near Madikeri Fort",
        "latitude": Decimal("12.421100"),
        "longitude": Decimal("75.739400"),
        "place_id": "ChIJV1bEbfMIrDsRc0TlW5a1Xss",
        "formatted_address": "Keradala Keri, Madikeri, Kodagu 571201, India",
        "rating": Decimal("4.3"),
        "review_count": 2654,
        "star_category": 4,
        "popularity_score": 780,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Studio Room", "base_price": Decimal("4500"), "capacity": 2, "bed_type": "Double", "available_count": 25},
            {"name": "1BHK Cottage", "base_price": Decimal("7500"), "capacity": 4, "bed_type": "King", "available_count": 12},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Bar", "Coffee Estate Tour", "Indoor Games"],
        "images": [
            {"url": "https://picsum.photos/seed/club-mah-madikeri-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/club-mah-madikeri-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Amanvana Spa Resort Coorg",
        "property_type": "Spa Resort",
        "address": "Near Kushalnagar, Coorg, Karnataka 571234",
        "description": (
            "Amanvana Spa Resort is a wellness sanctuary nestled on the banks "
            "of the Cauvery River in Coorg. Set on 3.5 acres of tropical gardens, "
            "it offers private cottages, extensive spa treatments inspired by "
            "ancient Ayurvedic traditions and immersive nature experiences."
        ),
        "city_name": "Coorg",
        "state_name": "Karnataka",
        "state_code": "KA",
        "area": "Kushalnagar",
        "landmark": "On Cauvery River banks",
        "latitude": Decimal("12.459300"),
        "longitude": Decimal("75.963200"),
        "place_id": "ChIJo4dNqHIIrDsROHsSTYFCHeo",
        "formatted_address": "Near Kushalnagar, Coorg, Karnataka 571234, India",
        "rating": Decimal("4.6"),
        "review_count": 873,
        "star_category": 5,
        "popularity_score": 820,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Garden Cottage", "base_price": Decimal("9000"), "capacity": 2, "bed_type": "King", "available_count": 8},
            {"name": "River View Suite", "base_price": Decimal("16000"), "capacity": 2, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Spa", "Ayurveda", "River View", "Yoga", "Restaurant", "Meditation"],
        "images": [
            {"url": "https://picsum.photos/seed/amanvana-coorg-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/amanvana-coorg-2/800/600", "is_featured": False},
        ],
    },

    # ══ HYDERABAD ══════════════════════════════════════════════════════════
    {
        "name": "Park Hyatt Hyderabad",
        "property_type": "Luxury Hotel",
        "address": "Road No. 2, Banjara Hills, Hyderabad, Telangana 500034",
        "description": (
            "Park Hyatt Hyderabad is a contemporary luxury hotel in Banjara Hills, "
            "the upscale heart of the city of pearls. Featuring 215 spacious rooms "
            "and suites, multiple award-winning restaurants, a restorative spa "
            "and a stunning outdoor pool."
        ),
        "city_name": "Hyderabad",
        "state_name": "Telangana",
        "state_code": "TG",
        "area": "Banjara Hills",
        "landmark": "Near KBR National Park",
        "latitude": Decimal("17.425200"),
        "longitude": Decimal("78.452800"),
        "place_id": "ChIJYYGpGnqZyzsR1VOwx4YCYTQ",
        "formatted_address": "Road No. 2, Banjara Hills, Hyderabad 500034, India",
        "rating": Decimal("4.7"),
        "review_count": 2341,
        "star_category": 5,
        "popularity_score": 930,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Park Room", "base_price": Decimal("10000"), "capacity": 2, "bed_type": "King", "available_count": 20},
            {"name": "Park Deluxe", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 12},
            {"name": "Park Suite", "base_price": Decimal("28000"), "capacity": 3, "bed_type": "King", "available_count": 5},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Business Centre", "Valet Parking"],
        "images": [
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/park-hyatt-hyd-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "ITC Kohenur Hyderabad",
        "property_type": "Luxury Hotel",
        "address": "HITEC City, Madhapur, Hyderabad, Telangana 500081",
        "description": (
            "ITC Kohenur is Hyderabad's premier super-luxury hotel, strategically "
            "positioned in the heart of HITEC City, the global technology hub. "
            "Inspired by the Kohinoor diamond, this architectural gem offers "
            "world-class accommodation, three exceptional restaurants and "
            "ITC's celebrated wellness traditions."
        ),
        "city_name": "Hyderabad",
        "state_name": "Telangana",
        "state_code": "TG",
        "area": "HITEC City",
        "landmark": "Next to Shilparamam, HITEC City",
        "latitude": Decimal("17.449700"),
        "longitude": Decimal("78.387300"),
        "place_id": "ChIJn0D2c7iYyzsRfLfBnxbkVsg",
        "formatted_address": "HITEC City, Madhapur, Hyderabad 500081, India",
        "rating": Decimal("4.8"),
        "review_count": 1876,
        "star_category": 5,
        "popularity_score": 960,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "ITC One Deluxe", "base_price": Decimal("12000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Executive Club Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Kohenur Suite", "base_price": Decimal("45000"), "capacity": 4, "bed_type": "King", "available_count": 3},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Wellness Centre", "Restaurant", "Bar", "Concierge", "Business Centre"],
        "images": [
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/itc-kohenur-hyd-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Taj Falaknuma Palace Hyderabad",
        "property_type": "Heritage Hotel",
        "address": "Engine Bowli, Falaknuma, Hyderabad, Telangana 500053",
        "description": (
            "Taj Falaknuma Palace is a legendary heritage hotel that was once "
            "the private palace of the sixth Nizam. Perched 2000 feet above "
            "the city with stunning views of Hyderabad's skyline, it offers "
            "royal suites, horse-drawn carriage arrivals, impeccable butler "
            "service and the finest Hyderabadi cuisine."
        ),
        "city_name": "Hyderabad",
        "state_name": "Telangana",
        "state_code": "TG",
        "area": "Falaknuma",
        "landmark": "Near Charminar, hilltop location",
        "latitude": Decimal("17.331800"),
        "longitude": Decimal("78.472200"),
        "place_id": "ChIJcYuO9FuWyzsRBjBFHBwJYh8",
        "formatted_address": "Engine Bowli, Falaknuma, Hyderabad 500053, India",
        "rating": Decimal("4.9"),
        "review_count": 3102,
        "star_category": 5,
        "popularity_score": 990,
        "is_trending": True,
        "has_free_cancellation": False,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Jadoo Room", "base_price": Decimal("40000"), "capacity": 2, "bed_type": "King", "available_count": 8},
            {"name": "State Room", "base_price": Decimal("60000"), "capacity": 3, "bed_type": "King", "available_count": 4},
            {"name": "Palace Suite", "base_price": Decimal("120000"), "capacity": 4, "bed_type": "King", "available_count": 2},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Heritage Tours", "Restaurant", "Bar", "Horse Carriage", "Billiards Room"],
        "images": [
            {"url": "https://picsum.photos/seed/falaknuma-palace-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/falaknuma-palace-2/800/600", "is_featured": False},
            {"url": "https://picsum.photos/seed/falaknuma-palace-3/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Novotel Hyderabad Convention Centre",
        "property_type": "Business Hotel",
        "address": "Near Hitex Exhibition Centre, HITEC City, Hyderabad, Telangana 500084",
        "description": (
            "Novotel Hyderabad Convention Centre is a premier MICE hotel adjacent "
            "to the HITEX Exhibition Centre. Offering 292 contemporary rooms, "
            "India's largest hotel convention facility, multiple dining options "
            "and a full wellness centre."
        ),
        "city_name": "Hyderabad",
        "state_name": "Telangana",
        "state_code": "TG",
        "area": "HITEC City",
        "landmark": "Adjacent to HITEX Centre",
        "latitude": Decimal("17.436700"),
        "longitude": Decimal("78.381200"),
        "place_id": "ChIJR3JDmL6YyzsRMY3IEA80fwE",
        "formatted_address": "Near Hitex Exhibition Centre, HITEC City, Hyderabad 500084, India",
        "rating": Decimal("4.4"),
        "review_count": 1654,
        "star_category": 5,
        "popularity_score": 820,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Superior Room", "base_price": Decimal("7000"), "capacity": 2, "bed_type": "King", "available_count": 30},
            {"name": "Deluxe Room", "base_price": Decimal("9500"), "capacity": 2, "bed_type": "King", "available_count": 15},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Business Centre", "Restaurant", "Bar", "Tennis Court"],
        "images": [
            {"url": "https://picsum.photos/seed/novotel-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/novotel-hyd-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Lemon Tree Hotel HITEC City Hyderabad",
        "property_type": "Business Hotel",
        "address": "Plot No. 5, Survey No. 64, HITEC City, Madhapur, Hyderabad 500081",
        "description": (
            "Lemon Tree Hotel HITEC City is a contemporary upscale hotel "
            "in the tech corridor of Hyderabad. Offering vibrant modern rooms, "
            "refreshing pool, multi-cuisine restaurant and quick access to "
            "major IT parks of Madhapur."
        ),
        "city_name": "Hyderabad",
        "state_name": "Telangana",
        "state_code": "TG",
        "area": "HITEC City",
        "landmark": "Walking distance from Cyber Towers",
        "latitude": Decimal("17.447200"),
        "longitude": Decimal("78.381800"),
        "place_id": "ChIJK8sGwL2YyzsRmMH-J0oPtAA",
        "formatted_address": "Plot No. 5, HITEC City, Madhapur, Hyderabad 500081, India",
        "rating": Decimal("4.2"),
        "review_count": 1123,
        "star_category": 4,
        "popularity_score": 720,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Refreshing Room", "base_price": Decimal("4200"), "capacity": 2, "bed_type": "Double", "available_count": 35},
            {"name": "Premium Room", "base_price": Decimal("6000"), "capacity": 2, "bed_type": "King", "available_count": 18},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Fitness Center", "Restaurant", "Bar", "Concierge"],
        "images": [
            {"url": "https://picsum.photos/seed/lemon-tree-hyd-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/lemon-tree-hyd-2/800/600", "is_featured": False},
        ],
    },

    # ══ BANGALORE ══════════════════════════════════════════════════════════
    {
        "name": "The Leela Palace Bengaluru",
        "property_type": "Luxury Hotel",
        "address": "23, Old Airport Road, Kodihalli, Bengaluru, Karnataka 560008",
        "description": (
            "The Leela Palace Bengaluru is a magnificent blend of Vijayanagara "
            "architecture and modern luxury. Set on 7 acres of landscaped gardens, "
            "this iconic hotel offers imperial grandeur with world-class amenities, "
            "award-winning restaurants and a renowned spa."
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
            {"url": "https://picsum.photos/seed/leela-palace-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/leela-palace-blr-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "The Oberoi Bengaluru",
        "property_type": "Luxury Hotel",
        "address": "37-39, Mahatma Gandhi Road, Bengaluru, Karnataka 560001",
        "description": (
            "The Oberoi Bengaluru is an oasis of luxury in the heart of the city. "
            "Set amidst beautifully landscaped gardens, it offers guests a serene "
            "sanctuary with impeccable service and fine dining in the bustling "
            "city centre."
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
            {"url": "https://picsum.photos/seed/oberoi-blr-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/oberoi-blr-2/800/600", "is_featured": False},
        ],
    },

    # ══ GOA ══════════════════════════════════════════════════════════════
    {
        "name": "Grand Hyatt Goa",
        "property_type": "Resort",
        "address": "Bambolim Beach Resort, Bambolim, Goa 403202",
        "description": (
            "Grand Hyatt Goa is a stunning resort nestled on the banks of the "
            "Zuari River. Just 15 minutes from Panaji, it features expansive "
            "lagoon pools, pristine beaches, multiple restaurants, a full-service "
            "Celine Spa and a wide range of water sports."
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
            {"url": "https://picsum.photos/seed/grand-hyatt-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/grand-hyatt-goa-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "W Goa",
        "property_type": "Luxury Resort",
        "address": "Vagator Beach, Bardez, Goa 403509",
        "description": (
            "W Goa is an ultra-cool beach resort set on the clifftops above "
            "Vagator Beach in North Goa. Known for its bold design, rooftop "
            "SPICE restaurant, two infinity pools and legendary WET pool parties, "
            "it is the most coveted party-meets-luxury escape in India."
        ),
        "city_name": "Goa",
        "state_name": "Goa",
        "state_code": "GA",
        "area": "Vagator",
        "landmark": "Above Vagator Beach, North Goa",
        "latitude": Decimal("15.604700"),
        "longitude": Decimal("73.742200"),
        "place_id": "ChIJRc3z_O8OvzsR9LtMFv47hOg",
        "formatted_address": "Vagator Beach, Bardez, Goa 403509, India",
        "rating": Decimal("4.5"),
        "review_count": 1987,
        "star_category": 5,
        "popularity_score": 950,
        "is_trending": True,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Wonderful Room", "base_price": Decimal("18000"), "capacity": 2, "bed_type": "King", "available_count": 15},
            {"name": "Spectacular Suite", "base_price": Decimal("35000"), "capacity": 3, "bed_type": "King", "available_count": 6},
        ],
        "amenities": ["Free WiFi", "Infinity Pool", "Spa", "Restaurant", "Beach Access", "Bar", "DJ Pool Parties", "Water Sports"],
        "images": [
            {"url": "https://picsum.photos/seed/w-goa-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/w-goa-2/800/600", "is_featured": False},
        ],
    },

    # ══ MUMBAI ═══════════════════════════════════════════════════════════
    {
        "name": "Taj Lands End Mumbai",
        "property_type": "Luxury Hotel",
        "address": "Bandstand, Bandra West, Mumbai, Maharashtra 400050",
        "description": (
            "Taj Lands End sits on a dramatic promontory overlooking the Arabian "
            "Sea in Bandra. One of Mumbai's most iconic hotels, it offers sweeping "
            "ocean views from most rooms, award-winning dining at Masala Bay and "
            "quintessential Taj service in the heart of suburban Mumbai."
        ),
        "city_name": "Mumbai",
        "state_name": "Maharashtra",
        "state_code": "MH",
        "area": "Bandra",
        "landmark": "Bandstand Promenade, Bandra West",
        "latitude": Decimal("19.046100"),
        "longitude": Decimal("72.823700"),
        "place_id": "ChIJT2lMb4-35zsReUE5LvI0gO8",
        "formatted_address": "Bandstand, Bandra West, Mumbai 400050, India",
        "rating": Decimal("4.7"),
        "review_count": 2456,
        "star_category": 5,
        "popularity_score": 940,
        "is_trending": False,
        "has_free_cancellation": True,
        "status": "approved",
        "agreement_signed": True,
        "room_types": [
            {"name": "Deluxe Sea View", "base_price": Decimal("14000"), "capacity": 2, "bed_type": "King", "available_count": 18},
            {"name": "Taj Club Room", "base_price": Decimal("20000"), "capacity": 2, "bed_type": "King", "available_count": 10},
            {"name": "Junior Suite", "base_price": Decimal("38000"), "capacity": 3, "bed_type": "King", "available_count": 4},
        ],
        "amenities": ["Free WiFi", "Swimming Pool", "Spa", "Fitness Center", "Restaurant", "Bar", "Concierge", "Sea View"],
        "images": [
            {"url": "https://picsum.photos/seed/taj-lands-end-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/taj-lands-end-2/800/600", "is_featured": False},
        ],
    },
    {
        "name": "Trident Bandra Kurla Mumbai",
        "property_type": "Luxury Hotel",
        "address": "C-56, G-Block, Bandra Kurla Complex, Mumbai, Maharashtra 400051",
        "description": (
            "Trident Bandra Kurla is the ultimate address for business travel "
            "in Mumbai. Situated in the prestigious Bandra Kurla Complex, "
            "this elegant hotel offers spacious rooms with stunning skyline views, "
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
            {"url": "https://picsum.photos/seed/trident-bkc-1/800/600", "is_featured": True},
            {"url": "https://picsum.photos/seed/trident-bkc-2/800/600", "is_featured": False},
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed production-grade OTA hotel data for Coorg, Hyderabad, Bangalore, Goa, Mumbai'

    def add_arguments(self, parser):
        parser.add_argument(
            '--inventory-days', type=int, default=180,
            help='Days ahead to seed RoomInventory (default: 180)'
        )
        parser.add_argument(
            '--city', type=str, default='',
            help='Seed only hotels in this city (case-insensitive)'
        )
        parser.add_argument(
            '--update', action='store_true',
            help='Update existing hotels matched by name'
        )
        parser.add_argument(
            '--inventory-only', action='store_true',
            help='Only seed RoomInventory for existing approved properties'
        )

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

        # Ensure system admin owner
        admin, _ = User.objects.get_or_create(
            email='admin@zygotrip.com',
            defaults={
                'full_name': 'ZygoTrip Admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )

        # Country: India
        india, _ = Country.objects.get_or_create(
            code='IN',
            defaults={'name': 'India', 'display_name': 'India', 'is_active': True}
        )

        if not inventory_only:
            props_to_seed = OTA_PROPERTIES
            if city_filter:
                props_to_seed = [
                    p for p in OTA_PROPERTIES
                    if p['city_name'].lower() == city_filter
                ]
                if not props_to_seed:
                    self.stdout.write(
                        self.style.WARNING(f'No properties found for city: {city_filter}')
                    )
                    return

            self.stdout.write(self.style.HTTP_INFO(
                f'\n=== Seeding {len(props_to_seed)} properties ==='
            ))

            for prop_data in props_to_seed:
                with transaction.atomic():
                    self._seed_property(
                        prop_data, india, admin, update_existing,
                        Property, PropertyImage, PropertyAmenity,
                        RoomType, State, City, slugify
                    )

        self.stdout.write('\n--- Seeding RoomInventory ---')
        self._seed_inventory(inventory_days)

        # Rebuild search index so autosuggest reflects seeded cities/properties
        self.stdout.write('\n--- Rebuilding SearchIndex ---')
        try:
            from apps.search.index_builder import rebuild_search_index
            totals = rebuild_search_index()
            self.stdout.write(self.style.SUCCESS(
                f'  SearchIndex rebuilt: cities={totals["cities"]}, '
                f'areas={totals["areas"]}, properties={totals["properties"]}'
            ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  SearchIndex rebuild skipped: {exc}'))

        self.stdout.write(self.style.SUCCESS('\n[OK] seed_ota_data complete!\n'))

    def _seed_property(
        self, data, india, admin, update_existing,
        Property, PropertyImage, PropertyAmenity,
        RoomType, State, City, slugify
    ):
        # State
        state, _ = State.objects.get_or_create(
            code=data['state_code'],
            country=india,
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
                'code': data['state_code'] + '_' + data['city_name'][:3].upper(),
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'is_active': True,
                'is_top_destination': True,
            }
        )

        # Property
        existing = Property.objects.filter(name=data['name']).first()
        if existing and not update_existing:
            self.stdout.write(f'  [SKIP] {data["name"]} (already exists)')
            return
        elif existing and update_existing:
            prop = existing
            self.stdout.write(f'  [UPDATE] {data["name"]}')
        else:
            prop = Property(name=data['name'])
            self.stdout.write(f'  [CREATE] {data["name"]}')

        prop.slug = slugify(data['name'])
        prop.property_type = data['property_type']
        prop.address = data['address']
        prop.description = data['description']
        prop.city = city
        prop.area = data.get('area', '')
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

        # Amenities
        prop.amenities.all().delete()
        for name in data.get('amenities', []):
            PropertyAmenity.objects.get_or_create(property=prop, name=name)

        # Images
        prop.images.all().delete()
        for i, img in enumerate(data.get('images', [])):
            url = img['url'] if isinstance(img, dict) else img
            is_featured = img.get('is_featured', i == 0) if isinstance(img, dict) else (i == 0)
            PropertyImage.objects.create(
                property=prop,
                image_url=url,
                is_featured=is_featured,
                display_order=i,
            )

        # Room types
        prop.room_types.all().delete()
        for rt in data.get('room_types', []):
            RoomType.objects.create(
                property=prop,
                name=rt['name'],
                description=rt.get('description', ''),
                capacity=rt.get('capacity', 2),
                base_price=rt['base_price'],
                bed_type=rt.get('bed_type', 'King'),
                available_count=rt.get('available_count', 10),
            )

        self.stdout.write(self.style.SUCCESS(
            f'         {prop.room_types.count()} rooms | '
            f'{prop.images.count()} images | '
            f'{prop.amenities.count()} amenities [id={prop.id}]'
        ))

    def _seed_inventory(self, days_ahead: int):
        from apps.hotels.models import Property
        from apps.rooms.models import RoomType, RoomInventory

        start = date.today()
        all_dates = [start + timedelta(days=d) for d in range(days_ahead)]
        end = start + timedelta(days=days_ahead)

        approved = Property.objects.filter(status='approved', agreement_signed=True)
        total_created = 0

        for prop in approved:
            for rt in prop.room_types.all():
                existing_dates = set(
                    RoomInventory.objects.filter(
                        room_type=rt, date__gte=start, date__lt=end
                    ).values_list('date', flat=True)
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
            f'{approved.count()} approved properties for {days_ahead} days'
        ))
