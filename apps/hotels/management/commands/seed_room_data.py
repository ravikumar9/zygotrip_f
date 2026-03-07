"""
Phase 3 — Seed Room Images and Amenities for all existing RoomTypes.

This command populates:
  - RoomImage  (CDN URLs from Unsplash/Picsum keyed by room type name)
  - RoomAmenity (standard hotel room amenities)

Usage:
  python manage.py seed_room_data
  python manage.py seed_room_data --clear   # wipe and re-seed
  python manage.py seed_room_data --limit 50  # only process N room types
"""
import logging
from django.core.management.base import BaseCommand
from apps.rooms.models import RoomType, RoomImage, RoomAmenity

logger = logging.getLogger(__name__)

# ── CDN image pools keyed by room-type keyword ──────────────────────────────
# Picsum photos are stable CDN URLs — no API key required.
# Format: picsum.photos/seed/<seed>/W/H
_PICSUM = "https://picsum.photos/seed"

ROOM_IMAGE_POOLS = {
    # Default pool (catch-all)
    "default": [
        f"{_PICSUM}/room_d1/800/600",
        f"{_PICSUM}/room_d2/800/600",
        f"{_PICSUM}/room_d3/800/600",
    ],
    "standard": [
        f"{_PICSUM}/std1/800/600",
        f"{_PICSUM}/std2/800/600",
        f"{_PICSUM}/std3/800/600",
    ],
    "deluxe": [
        f"{_PICSUM}/dlx1/800/600",
        f"{_PICSUM}/dlx2/800/600",
        f"{_PICSUM}/dlx3/800/600",
    ],
    "suite": [
        f"{_PICSUM}/suite1/800/600",
        f"{_PICSUM}/suite2/800/600",
        f"{_PICSUM}/suite3/800/600",
    ],
    "villa": [
        f"{_PICSUM}/villa1/800/600",
        f"{_PICSUM}/villa2/800/600",
        f"{_PICSUM}/villa3/800/600",
    ],
    "cottage": [
        f"{_PICSUM}/cottage1/800/600",
        f"{_PICSUM}/cottage2/800/600",
    ],
    "heritage": [
        f"{_PICSUM}/heritage1/800/600",
        f"{_PICSUM}/heritage2/800/600",
    ],
    "executive": [
        f"{_PICSUM}/exec1/800/600",
        f"{_PICSUM}/exec2/800/600",
        f"{_PICSUM}/exec3/800/600",
    ],
    "luxury": [
        f"{_PICSUM}/lux1/800/600",
        f"{_PICSUM}/lux2/800/600",
        f"{_PICSUM}/lux3/800/600",
    ],
    "premium": [
        f"{_PICSUM}/prem1/800/600",
        f"{_PICSUM}/prem2/800/600",
    ],
    "superior": [
        f"{_PICSUM}/sup1/800/600",
        f"{_PICSUM}/sup2/800/600",
    ],
    "classic": [
        f"{_PICSUM}/cls1/800/600",
        f"{_PICSUM}/cls2/800/600",
    ],
    "grand": [
        f"{_PICSUM}/grand1/800/600",
        f"{_PICSUM}/grand2/800/600",
    ],
    "pool": [
        f"{_PICSUM}/pool1/800/600",
        f"{_PICSUM}/pool2/800/600",
        f"{_PICSUM}/pool3/800/600",
    ],
    "ocean": [
        f"{_PICSUM}/ocean1/800/600",
        f"{_PICSUM}/ocean2/800/600",
    ],
    "jungle": [
        f"{_PICSUM}/jungle1/800/600",
        f"{_PICSUM}/jungle2/800/600",
    ],
    "plantation": [
        f"{_PICSUM}/plant1/800/600",
        f"{_PICSUM}/plant2/800/600",
    ],
}

# ── Standard room amenities (covers most hotel room types) ──────────────────
ROOM_AMENITIES = [
    {"name": "Free Wi-Fi",       "icon": "wifi"},
    {"name": "Air Conditioning", "icon": "snowflake"},
    {"name": "Flat-screen TV",   "icon": "tv"},
    {"name": "Private Bathroom", "icon": "bath"},
    {"name": "Minibar",          "icon": "wine"},
    {"name": "Safe",             "icon": "lock"},
    {"name": "Hair Dryer",       "icon": "wind"},
    {"name": "Room Service",     "icon": "bell"},
]

DELUXE_AMENITIES = ROOM_AMENITIES + [
    {"name": "Bathtub",          "icon": "bath"},
    {"name": "King Bed",         "icon": "bed"},
    {"name": "City View",        "icon": "eye"},
]

SUITE_AMENITIES = DELUXE_AMENITIES + [
    {"name": "Living Area",      "icon": "sofa"},
    {"name": "Kitchenette",      "icon": "utensils"},
    {"name": "Butler Service",   "icon": "star"},
    {"name": "Nespresso Machine","icon": "coffee"},
]

VILLA_AMENITIES = SUITE_AMENITIES + [
    {"name": "Private Pool",     "icon": "droplet"},
    {"name": "Garden",           "icon": "tree"},
    {"name": "Plunge Pool",      "icon": "droplet"},
]


def _get_image_pool(room_name: str):
    """Return appropriate image pool based on room name keywords."""
    name_lower = room_name.lower()
    for keyword in [
        "villa", "suite", "deluxe", "standard", "executive", "luxury",
        "premium", "superior", "heritage", "grand", "classic", "cottage",
        "pool", "ocean", "jungle", "plantation",
    ]:
        if keyword in name_lower:
            return ROOM_IMAGE_POOLS.get(keyword, ROOM_IMAGE_POOLS["default"])
    return ROOM_IMAGE_POOLS["default"]


def _get_amenity_set(room_name: str):
    """Return appropriate amenity set based on room name keywords."""
    name_lower = room_name.lower()
    if any(k in name_lower for k in ["villa", "plantation", "cottage"]):
        return VILLA_AMENITIES
    if any(k in name_lower for k in ["suite", "executive", "luxury", "premium", "grand"]):
        return SUITE_AMENITIES
    if any(k in name_lower for k in ["deluxe", "superior", "heritage"]):
        return DELUXE_AMENITIES
    return ROOM_AMENITIES


class Command(BaseCommand):
    help = "Seed RoomImage and RoomAmenity records for all existing RoomTypes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing RoomImage and RoomAmenity records first.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process this many RoomTypes (for testing).",
        )

    def handle(self, *args, **options):
        clear = options["clear"]
        limit = options["limit"]

        if clear:
            img_count = RoomImage.objects.count()
            amen_count = RoomAmenity.objects.count()
            RoomImage.objects.all().delete()
            RoomAmenity.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared {img_count} RoomImages and {amen_count} RoomAmenities."
                )
            )

        qs = RoomType.objects.select_related("property").order_by("id")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Seeding room data for {total} RoomTypes...")

        images_created = 0
        amenities_created = 0
        skipped = 0

        images_to_create = []
        amenities_to_create = []

        for rt in qs:
            # Skip if already has data (idempotent)
            if not clear:
                if RoomImage.objects.filter(room_type=rt).exists():
                    skipped += 1
                    continue

            pool = _get_image_pool(rt.name)
            amenity_set = _get_amenity_set(rt.name)

            # Create images
            for order, url in enumerate(pool):
                images_to_create.append(
                    RoomImage(
                        room_type=rt,
                        image_url=url,
                        alt_text=f"{rt.name} at {rt.property.name}",
                        is_primary=(order == 0),
                        is_featured=(order == 0),
                        display_order=order,
                    )
                )

            # Create amenities
            for amen in amenity_set:
                amenities_to_create.append(
                    RoomAmenity(
                        room_type=rt,
                        name=amen["name"],
                        icon=amen["icon"],
                    )
                )

        # Bulk create for performance
        if images_to_create:
            created = RoomImage.objects.bulk_create(
                images_to_create, ignore_conflicts=True
            )
            images_created = len(created)

        if amenities_to_create:
            created = RoomAmenity.objects.bulk_create(
                amenities_to_create, ignore_conflicts=True
            )
            amenities_created = len(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[OK] Done!\n"
                f"   RoomImages created   : {images_created}\n"
                f"   RoomAmenities created: {amenities_created}\n"
                f"   RoomTypes skipped (already had data): {skipped}\n"
                f"   Total RoomTypes processed: {total - skipped}"
            )
        )
