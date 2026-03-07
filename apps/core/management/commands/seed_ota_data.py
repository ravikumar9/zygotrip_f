from decimal import Decimal
import random
from datetime import timedelta, time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.location_models import Country, State, City, Locality
from apps.dashboard_admin.models import PropertyApproval
from apps.hotels.models import Property, PropertyImage, PropertyAmenity
from apps.rooms.models import RoomType, RoomInventory
from apps.offers.models import Offer, PropertyOffer
from apps.buses.models import Bus, BusType, BusSeat
from apps.cabs.models import Cab
from apps.packages.models import Package, PackageCategory, PackageItinerary, PackageImage

User = get_user_model()


class Command(BaseCommand):
    help = "Seed enterprise OTA data for hotels, buses, cabs, and packages."

    def handle(self, *args, **options):
        self.stdout.write("Seeding OTA data...")
        call_command("seed_locations", verbosity=0)

        admin = self._get_or_create_admin()
        self._create_test_users()
        self._ensure_cities()

        property_owner = User.objects.filter(email="property_owner@test.com").first()
        bus_operator = User.objects.filter(email="bus_operator_1@test.com").first()
        cab_owner = User.objects.filter(email="cab_owner_1@test.com").first()
        package_provider = User.objects.filter(email="package_provider_1@test.com").first()

        self._seed_hotels(admin)
        if property_owner:
            self._seed_owner_property(property_owner, admin)
        self._seed_buses(bus_operator)
        self._seed_cabs(cab_owner or admin)
        self._seed_packages(package_provider or admin)

        self.stdout.write(self.style.SUCCESS("OTA data seeded successfully."))

    def _get_or_create_admin(self):
        admin, created = User.objects.get_or_create(
            email="admin@zygotrip.com",
            defaults={"full_name": "Admin User", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("admin123")
            admin.save()
        return admin
    
    def _create_test_users(self):
        """Create test accounts for different roles."""
        from apps.accounts.models import Role, UserRole
        
        test_accounts = [
            {"email": "staff_admin@test.com", "password": "Test@123", "name": "Staff Admin", "is_staff": True, "is_superuser": True, "role": "staff_admin"},
            {"email": "customer@test.com", "password": "Test@123", "name": "Test Customer", "is_staff": False, "is_superuser": False, "role": "customer"},
            {"email": "property_owner@test.com", "password": "Test@123", "name": "Property Owner", "is_staff": False, "is_superuser": False, "role": "property_owner"},
            {"email": "bus_operator_1@test.com", "password": "Test@123", "name": "Bus Operator 1", "is_staff": False, "is_superuser": False, "role": "bus_operator"},
            {"email": "cab_owner_1@test.com", "password": "Test@123", "name": "Cab Owner 1", "is_staff": False, "is_superuser": False, "role": "cab_owner"},
            {"email": "package_provider_1@test.com", "password": "Test@123", "name": "Package Provider 1", "is_staff": False, "is_superuser": False, "role": "package_provider"},
            {"email": "admin@test.com", "password": "admin123", "name": "Test Admin", "is_staff": True, "is_superuser": True, "role": None},
            {"email": "owner@test.com", "password": "owner123", "name": "Test Owner", "is_staff": False, "is_superuser": False, "role": "owner"},
            {"email": "user@test.com", "password": "user123", "name": "Test User", "is_staff": False, "is_superuser": False, "role": "customer"},
            {"email": "operator@test.com", "password": "operator123", "name": "Test Operator", "is_staff": False, "is_superuser": False, "role": "operator"},
        ]
        
        for account in test_accounts:
            user, created = User.objects.get_or_create(
                email=account["email"],
                defaults={
                    "full_name": account["name"],
                    "is_staff": account["is_staff"],
                    "is_superuser": account["is_superuser"],
                }
            )
            user.set_password(account["password"])
            user.is_staff = account["is_staff"]
            user.is_superuser = account["is_superuser"]
            user.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created test account: {account['email']} / {account['password']}"))
            
            if account["role"]:
                role, _ = Role.objects.get_or_create(code=account["role"], defaults={"name": account["role"].title()})
                UserRole.objects.get_or_create(user=user, role=role)

    def _ensure_cities(self):
        india, _ = Country.objects.get_or_create(
            code="IN",
            defaults={"name": "India", "display_name": "India", "is_active": True},
        )

        city_specs = [
            {"state_code": "TG", "state_name": "Telangana", "city_code": "HYD", "name": "Hyderabad", "lat": "17.3850", "lng": "78.4867"},
            {"state_code": "KA", "state_name": "Karnataka", "city_code": "BLR", "name": "Bangalore", "lat": "12.9716", "lng": "77.5946"},
            {"state_code": "MH", "state_name": "Maharashtra", "city_code": "MUM", "name": "Mumbai", "lat": "19.0760", "lng": "72.8777"},
            {"state_code": "DL", "state_name": "Delhi", "city_code": "DEL", "name": "Delhi", "lat": "28.7041", "lng": "77.1025"},
            {"state_code": "TN", "state_name": "Tamil Nadu", "city_code": "CHE", "name": "Chennai", "lat": "13.0827", "lng": "80.2707"},
            {"state_code": "GA", "state_name": "Goa", "city_code": "GOA", "name": "Goa", "lat": "15.2993", "lng": "74.1240"},
            {"state_code": "KA", "state_name": "Karnataka", "city_code": "COORG", "name": "Coorg", "lat": "12.4244", "lng": "75.7382"},
            {"state_code": "RJ", "state_name": "Rajasthan", "city_code": "JAI", "name": "Jaipur", "lat": "26.9124", "lng": "75.7873"},
            {"state_code": "MH", "state_name": "Maharashtra", "city_code": "PUN", "name": "Pune", "lat": "18.5204", "lng": "73.8567"},
            {"state_code": "WB", "state_name": "West Bengal", "city_code": "KOL", "name": "Kolkata", "lat": "22.5726", "lng": "88.3639"},
        ]

        for spec in city_specs:
            state, _ = State.objects.get_or_create(
                country=india,
                code=spec["state_code"],
                defaults={"name": spec["state_name"], "display_name": spec["state_name"], "is_active": True},
            )
            city, _ = City.objects.get_or_create(
                state=state,
                code=spec["city_code"],
                defaults={
                    "name": spec["name"],
                    "display_name": spec["name"],
                    "latitude": Decimal(spec["lat"]),
                    "longitude": Decimal(spec["lng"]),
                    "is_active": True,
                },
            )

            locality_names = ["Central", "Downtown"]
            for offset, locality_name in enumerate(locality_names, start=1):
                Locality.objects.get_or_create(
                    city=city,
                    name=f"{city.name} {locality_name}",
                    defaults={
                        "display_name": f"{city.name} {locality_name}",
                        "latitude": city.latitude + Decimal("0.01") * offset,
                        "longitude": city.longitude + Decimal("0.01") * offset,
                        "locality_type": "tourist",
                        "is_active": True,
                    },
                )

    def _seed_hotels(self, admin):
        cities = list(City.objects.filter(is_active=True).order_by("name"))
        if not cities:
            return

        amenity_pool = [
            "Free WiFi",
            "Breakfast Included",
            "Swimming Pool",
            "Parking",
            "Gym",
            "Spa",
            "Restaurant",
            "Airport Shuttle",
        ]
        room_templates = [
            ("Standard Room", Decimal("2200.00"), 2),
            ("Deluxe Room", Decimal("3600.00"), 2),
            ("Executive Suite", Decimal("5200.00"), 3),
        ]
        # Multiple diverse image URLs to ensure variety
        image_urls = [
            "https://images.unsplash.com/photo-1566073771259-6a8506099945.jpg",  # Bedroom
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b.jpg",  # Luxury room
            "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb.jpg",  # Modern room
            "https://images.unsplash.com/photo-1590490360182-c33d57733427.jpg",  # Bathroom
            "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9.jpg",  # Living area
            "https://images.unsplash.com/photo-1551632786-de41ec16aSettings.jpg",  # Exterior
            "https://images.unsplash.com/photo-1578659688326-e4e59a94e8ee.jpg",  # Lobby
            "https://images.unsplash.com/photo-1563664194-4c8dda9c7d7d.jpg",  # Dining
        ]

        now = timezone.now()
        global_offer, _ = Offer.objects.get_or_create(
            coupon_code="GLOBAL10",
            defaults={
                "title": "Global 10% Off",
                "description": "Limited-time global discount",
                "offer_type": "percentage",
                "discount_percentage": Decimal("10.00"),
                "discount_flat": Decimal("0.00"),
                "start_datetime": now - timedelta(days=1),
                "end_datetime": now + timedelta(days=90),
                "is_active": True,
                "is_global": True,
                "created_by": admin,
            },
        )

        for city in cities:
            localities = list(city.localities.all())
            for index in range(5):
                hotel_name = f"{city.name} Grand Stay {index + 1}"
                slug_base = hotel_name.lower().replace(" ", "-")
                slug_value = f"{slug_base}-{city.code.lower()}"
                locality = localities[index % len(localities)] if localities else None
                property_obj, created = Property.objects.get_or_create(
                    slug=slug_value,
                    defaults={
                        "name": hotel_name,
                        "city": city,
                        "owner": admin,
                        "property_type": "Hotel",
                        "description": "Premium stay with modern amenities and curated experiences.",
                        "address": f"{random.randint(10, 999)} {city.name} Central Road",
                        "country": "India",
                        "area": locality.name if locality else "Central",
                        "landmark": "Main Square",
                        "latitude": city.latitude + Decimal("0.01") * (index + 1),
                        "longitude": city.longitude + Decimal("0.01") * (index + 1),
                        "rating": Decimal(str(round(random.uniform(3.8, 4.9), 1))),
                        "review_count": random.randint(40, 260),
                        "popularity_score": random.randint(20, 95),
                        "bookings_today": random.randint(1, 25),
                        "bookings_this_week": random.randint(5, 120),
                        "status": "approved",
                        "agreement_signed": True,
                        "has_free_cancellation": random.choice([True, False]),
                        "is_trending": random.choice([True, False]),
                    },
                )
                
                # Ensure existing properties are updated to approved status
                if not created:
                    property_obj.status = "approved"
                    property_obj.agreement_signed = True
                    property_obj.save()

                PropertyApproval.objects.get_or_create(
                    property=property_obj,
                    defaults={
                        "status": PropertyApproval.STATUS_APPROVED,
                        "decided_by": admin,
                        "decided_at": timezone.now(),
                        "notes": "Auto-approved seed property",
                    },
                )

                for amenity_name in random.sample(amenity_pool, 5):
                    PropertyAmenity.objects.get_or_create(property=property_obj, name=amenity_name)

                for room_name, base_price, capacity in room_templates:
                    RoomType.objects.get_or_create(
                        property=property_obj,
                        name=room_name,
                        defaults={
                            "description": f"{room_name} with curated comforts.",
                            "base_price": base_price + Decimal(index * 250),
                            "max_occupancy": capacity,
                            "max_guests": capacity,
                            "room_size": random.randint(240, 520),
                            "available_count": random.randint(6, 20),
                        },
                    )

                # Create 3+ real images per property
                if property_obj.images.count() < 3:
                    PropertyImage.objects.filter(property=property_obj).delete()
                    for image_index, url in enumerate(image_urls[:3]):
                        PropertyImage.objects.create(
                            property=property_obj,
                            image_url=url,
                            caption=f"{property_obj.name} view {image_index + 1}",
                            is_featured=image_index == 0,
                            display_order=image_index,
                        )

                # Seed 60 days of inventory for each room type
                inventory_start = now.date()
                inventory_days = 60
                for room in RoomType.objects.filter(property=property_obj):
                    base_available = max(1, room.available_count or 10)
                    for day_offset in range(inventory_days):
                        inv_date = inventory_start + timedelta(days=day_offset)
                        available_rooms = random.randint(3, base_available)
                        RoomInventory.objects.get_or_create(
                            room_type=room,
                            date=inv_date,
                            defaults={
                                "available_rooms": available_rooms,
                                "price": room.base_price,
                                "available_count": available_rooms,
                                "booked_count": 0,
                                "is_closed": False,
                            },
                        )

                # Seed property-specific offer (plus global offer above)
                property_offer_code = f"{property_obj.slug[:8].upper()}-{property_obj.id}"
                property_offer, _ = Offer.objects.get_or_create(
                    coupon_code=property_offer_code,
                    defaults={
                        "title": "Stay Saver Deal",
                        "description": "Exclusive savings for this property",
                        "offer_type": "flat",
                        "discount_percentage": Decimal("0.00"),
                        "discount_flat": Decimal("500.00"),
                        "start_datetime": now - timedelta(days=1),
                        "end_datetime": now + timedelta(days=60),
                        "is_active": True,
                        "is_global": False,
                        "created_by": admin,
                    },
                )
                PropertyOffer.objects.get_or_create(
                    offer=property_offer,
                    property=property_obj,
                )

    def _seed_owner_property(self, owner, admin):
        city = City.objects.filter(name__iexact="Bangalore").first() or City.objects.first()
        if not city:
            return

        property_obj, created = Property.objects.get_or_create(
            slug="aurora-bay-hotel",
            defaults={
                "name": "Aurora Bay Hotel",
                "city": city,
                "owner": owner,
                "property_type": "Hotel",
                "description": "Coastal-inspired stay with premium amenities.",
                "address": f"88 Bayfront Road, {city.name}",
                "country": "India",
                "area": "Central",
                "landmark": "Waterfront",
                "latitude": city.latitude,
                "longitude": city.longitude,
                "rating": Decimal("4.6"),
                "review_count": 120,
                "popularity_score": 80,
                "bookings_today": 6,
                "bookings_this_week": 42,
                "status": "approved",
                "agreement_signed": True,
                "has_free_cancellation": True,
                "is_trending": True,
            },
        )

        if not created:
            property_obj.owner = owner
            property_obj.status = "approved"
            property_obj.agreement_signed = True
            property_obj.save(update_fields=["owner", "status", "agreement_signed", "updated_at"])

        PropertyApproval.objects.get_or_create(
            property=property_obj,
            defaults={
                "status": PropertyApproval.STATUS_APPROVED,
                "decided_by": admin,
                "decided_at": timezone.now(),
                "notes": "Auto-approved test property",
            },
        )

        room_templates = [
            ("Deluxe Room", Decimal("4200.00"), 2),
            ("Executive Suite", Decimal("6200.00"), 3),
        ]
        for room_name, base_price, capacity in room_templates:
            RoomType.objects.get_or_create(
                property=property_obj,
                name=room_name,
                defaults={
                    "description": f"{room_name} with curated comforts.",
                    "base_price": base_price,
                    "max_occupancy": capacity,
                    "max_guests": capacity,
                    "room_size": 380,
                    "available_count": 8,
                },
            )

        inventory_start = timezone.now().date()
        for room in RoomType.objects.filter(property=property_obj):
            for day_offset in range(45):
                inv_date = inventory_start + timedelta(days=day_offset)
                RoomInventory.objects.get_or_create(
                    room_type=room,
                    date=inv_date,
                    defaults={
                        "available_rooms": 6,
                        "price": room.base_price,
                        "available_count": 6,
                        "booked_count": 0,
                        "is_closed": False,
                    },
                )

    def _seed_buses(self, operator=None):
        bus_types = [
            ("sleeper", Decimal("750.00"), 36),
            ("semi_sleeper", Decimal("650.00"), 40),
            ("ac", Decimal("820.00"), 40),
            ("seater", Decimal("520.00"), 45),
        ]
        for type_code, base_fare, capacity in bus_types:
            BusType.objects.get_or_create(
                name=type_code,
                defaults={"base_fare": base_fare, "capacity": capacity},
            )

        routes = [
            ("Hyderabad", "Bangalore"),
            ("Bangalore", "Chennai"),
            ("Mumbai", "Goa"),
            ("Delhi", "Jaipur"),
            ("Pune", "Mumbai"),
            ("Kolkata", "Delhi"),
        ]
        departure_times = [time(6, 15), time(9, 30), time(14, 45), time(18, 10), time(21, 0)]
        today = timezone.now().date()

        bus_type = BusType.objects.order_by("id").first()
        if not bus_type:
            return

        for route_index, route in enumerate(routes):
            from_city, to_city = route
            for bus_index in range(6):
                registration_number = f"ZY-OTA-{route_index + 1}-{bus_index + 1:02d}"
                bus, created = Bus.objects.get_or_create(
                    registration_number=registration_number,
                    defaults={
                        "operator": operator,
                        "operator_name": f"Zygotrip Express {route_index + 1}",
                        "bus_type": bus_type,
                        "from_city": from_city,
                        "to_city": to_city,
                        "departure_time": departure_times[(route_index + bus_index) % len(departure_times)],
                        "arrival_time": time(23, 30),
                        "journey_date": today + timedelta(days=bus_index + 2),
                        "price_per_seat": Decimal("650.00") + Decimal(bus_index * 20),
                        "available_seats": 36,
                        "amenities": "WiFi, Charging, Water",
                        "is_active": True,
                    },
                )

                if created and not bus.seats.exists():
                    self._create_bus_seats(bus, 40)

    def _create_bus_seats(self, bus, seat_count):
        rows = "ABCDEFGHIJ"
        seats_per_row = 4
        created = 0
        for row in rows:
            for col in range(1, seats_per_row + 1):
                if created >= seat_count:
                    return
                seat_number = f"{row}{col}"
                BusSeat.objects.get_or_create(
                    bus=bus,
                    seat_number=seat_number,
                    defaults={"row": row, "column": col},
                )
                created += 1

    def _seed_cabs(self, owner):
        city_choices = [
            "hyderabad",
            "bangalore",
            "mumbai",
            "delhi",
            "chennai",
            "goa",
            "coorg",
            "jaipur",
            "pune",
            "kolkata",
        ]
        vendors = ["Zygotrip", "SwiftRide", "MetroCab", "UrbanGo"]
        seat_options = [4, 5, 6, 7]
        fuel_options = ["petrol", "diesel", "hybrid", "electric"]

        for city in city_choices:
            for vendor_index, vendor in enumerate(vendors):
                cab_name = f"{vendor} {city.title()} {vendor_index + 1}"
                Cab.objects.get_or_create(
                    name=cab_name,
                    defaults={
                        "owner": owner,
                        "city": city,
                        "seats": seat_options[vendor_index % len(seat_options)],
                        "fuel_type": fuel_options[vendor_index % len(fuel_options)],
                        "base_price_per_km": Decimal("12.00") + Decimal(vendor_index * 2),
                        "system_price_per_km": Decimal("15.00") + Decimal(vendor_index * 2),
                        "is_active": True,
                    },
                )

    def _seed_packages(self, provider):
        categories = [
            ("Adventure", "High-energy trails and outdoor experiences"),
            ("Beach", "Relaxed coastal escapes"),
            ("Cultural", "Heritage, food, and local discovery"),
        ]
        category_objects = []
        for name, description in categories:
            category_objects.append(
                PackageCategory.objects.get_or_create(
                    name=name,
                    defaults={"description": description, "is_active": True},
                )[0]
            )

        destinations = [
            "Hyderabad",
            "Bangalore",
            "Mumbai",
            "Delhi",
            "Chennai",
            "Goa",
            "Coorg",
            "Jaipur",
            "Pune",
            "Kolkata",
        ]
        image_urls = [
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee.jpg",
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee.jpg",
            "https://images.unsplash.com/photo-1493558103817-58b2924bce98.jpg",
            "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee.jpg",
            "https://images.unsplash.com/photo-1493558103817-58b2924bce98.jpg",
        ]

        for destination_index, destination in enumerate(destinations):
            for package_index in range(3):
                package_name = f"{destination} Signature Escape {package_index + 1}"
                category = category_objects[(destination_index + package_index) % len(category_objects)]
                package, created = Package.objects.get_or_create(
                    name=package_name,
                    defaults={
                        "provider": provider,
                        "category": category,
                        "description": "Curated package with premium stays, local experiences, and guided tours.",
                        "destination": destination,
                        "duration_days": 4 + package_index,
                        "base_price": Decimal("18000.00") + Decimal(package_index * 2500),
                        "rating": Decimal("4.4"),
                        "review_count": 40 + package_index * 8,
                        "image_url": image_urls[0],
                        "inclusions": "Hotels, Breakfast, Transfers, Experiences",
                        "exclusions": "Flights, Personal expenses",
                        "max_group_size": 24,
                        "difficulty_level": Package.MODERATE,
                        "hotel_included": True,
                        "meals_included": True,
                        "transport_included": True,
                        "guide_included": package_index % 2 == 0,
                        "is_active": True,
                    },
                )

                if created:
                    for day in range(1, package.duration_days + 1):
                        PackageItinerary.objects.get_or_create(
                            package=package,
                            day_number=day,
                            defaults={
                                "title": f"Day {day} Highlights",
                                "description": "Guided tours, local cuisine, and curated activities.",
                                "accommodation": "Premium hotel stay",
                                "meals_included": PackageItinerary.MEALS_BREAKFAST,
                            },
                        )

                    for image_index, url in enumerate(image_urls):
                        PackageImage.objects.create(
                            package=package,
                            image_url=url,
                            is_featured=image_index == 0,
                            display_order=image_index,
                        )
