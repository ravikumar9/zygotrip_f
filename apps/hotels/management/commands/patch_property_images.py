"""
Management command: patch_property_images
Adds deterministic picsum.photos placeholder images to any property that has
NO valid images (either no PropertyImage rows or all rows have an empty URL
and no uploaded file).

Idempotent — safe to run multiple times.

Usage:
    python manage.py patch_property_images                    # all properties
    python manage.py patch_property_images --city Coorg       # one city
    python manage.py patch_property_images --force            # re-seed even if images exist
"""
from django.core.management.base import BaseCommand
from django.db.models import Q


# Image themes matched to property types — keeps visuals contextually relevant.
SEED_TAGS = {
    'Luxury Resort':    ['resort-pool', 'resort-suite', 'resort-spa', 'resort-lobby', 'resort-dining'],
    'Luxury Hotel':     ['luxury-hotel', 'hotel-suite', 'hotel-lobby', 'hotel-rooftop', 'hotel-pool'],
    'Business Hotel':   ['business-hotel', 'hotel-room', 'hotel-meeting', 'hotel-desk', 'hotel-pool'],
    'Boutique Hotel':   ['boutique-hotel', 'boutique-room', 'boutique-lounge', 'boutique-garden'],
    'Heritage Hotel':   ['heritage-hotel', 'heritage-corridor', 'heritage-suite', 'heritage-garden'],
    'Budget Hotel':     ['hotel-standard', 'hotel-lobby', 'hotel-breakfast'],
    'Hostel':           ['hostel-dorm', 'hostel-common', 'hostel-reception'],
    'Villa':            ['villa-exterior', 'villa-pool', 'villa-living', 'villa-bedroom'],
    'Apartment':        ['apartment-living', 'apartment-bedroom', 'apartment-kitchen'],
    'Guesthouse':       ['guesthouse-room', 'guesthouse-garden', 'guesthouse-lobby'],
}
DEFAULT_TAGS = ['hotel-exterior', 'hotel-room', 'hotel-lobby', 'hotel-pool', 'hotel-dining']


def _pick_tags(property_type: str, n: int) -> list[str]:
    """Return n seed tags for the given property type (cycle if needed)."""
    tags = SEED_TAGS.get(property_type, DEFAULT_TAGS)
    return [tags[i % len(tags)] for i in range(n)]


def _has_valid_images(prop) -> bool:
    """Return True if property has at least one resolvable image URL."""
    for img in prop.images.all():
        # Uploaded file
        if img.image and hasattr(img.image, 'url') and img.image.name:
            return True
        # CDN / URL string
        if img.image_url and img.image_url.strip():
            return True
    return False


class Command(BaseCommand):
    help = 'Patch missing property images with deterministic picsum.photos placeholders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city', type=str, default='',
            help='Limit to properties in this city (case-insensitive)',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Re-seed images even for properties that already have valid images',
        )
        parser.add_argument(
            '--count', type=int, default=4,
            help='Number of images to add per property (default: 4)',
        )

    def handle(self, *args, **options):
        from apps.hotels.models import Property, PropertyImage

        city_filter = options['city'].strip().lower()
        force = options['force']
        img_count = max(1, min(options['count'], 8))

        qs = Property.objects.filter(
            status='approved',
            agreement_signed=True,
        ).prefetch_related('images')

        if city_filter:
            qs = qs.filter(city__name__icontains=city_filter)

        total = qs.count()
        self.stdout.write(self.style.HTTP_INFO(
            f'\n=== patch_property_images ==='
            f'\n  Scanning {total} approved properties'
            f'{" in " + city_filter if city_filter else ""}...\n'
        ))

        patched = 0
        skipped = 0

        for prop in qs:
            already_ok = _has_valid_images(prop)

            if already_ok and not force:
                skipped += 1
                continue

            # Remove any invalid image records (empty URLs, no file) to keep DB clean
            if force:
                prop.images.all().delete()
            else:
                prop.images.filter(
                    Q(image='') | Q(image__isnull=True),
                    Q(image_url='') | Q(image_url__isnull=True),
                ).delete()

            # Build deterministic picsum URLs based on property slug + theme
            slug = prop.slug or f'property-{prop.id}'
            tags = _pick_tags(prop.property_type or '', img_count)

            for i, tag in enumerate(tags):
                seed_key = f'{slug}-{tag}'
                url = f'https://picsum.photos/seed/{seed_key}/800/600'
                PropertyImage.objects.create(
                    property=prop,
                    image_url=url,
                    caption=prop.name,
                    is_featured=(i == 0),
                    display_order=i,
                )

            patched += 1
            self.stdout.write(
                f'  [OK] {prop.name[:50]}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] patch_property_images done!'
            f'\n     patched={patched}  skipped={skipped}\n'
        ))
