"""
Management command: cleanup_demo_data
Deletes all demo/test/seeded property records and their related data.
Identifies demo data by name patterns (Test, Demo, Sample, Grand Stay).
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Delete all demo/test/seeded properties and their related data'

    DEMO_NAME_PATTERNS = [
        'Test',
        'Demo',
        'Sample',
        'Grand Stay',
        'Seeded',
        'Dummy',
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        from apps.hotels.models import Property, PropertyImage
        from apps.rooms.models import RoomType

        dry_run = options['dry_run']
        force = options['force']

        # Build queryset of demo properties
        from django.db.models import Q
        pattern_filter = Q()
        for pattern in self.DEMO_NAME_PATTERNS:
            pattern_filter |= Q(name__icontains=pattern)

        demo_properties = Property.objects.filter(pattern_filter)
        count = demo_properties.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No demo properties found. Database is clean.'))
            return

        # List what will be deleted
        self.stdout.write(
            self.style.WARNING(f'\nFound {count} demo/test properties to delete:')
        )
        for prop in demo_properties.order_by('name')[:50]:
            image_count = PropertyImage.objects.filter(property=prop).count()
            room_count = RoomType.objects.filter(property=prop).count()
            self.stdout.write(
                f'  [{prop.id}] {prop.name} — {image_count} images, {room_count} rooms'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes made.'))
            return

        if not force:
            confirm = input(f'\nDelete {count} properties and ALL related data? [y/N] ')
            if confirm.strip().lower() != 'y':
                self.stdout.write('Aborted.')
                return

        # Execute deletion in a transaction (cascade deletes handle images/rooms)
        with transaction.atomic():
            from apps.booking.models import Booking
            from apps.booking.models import BookingContext

            prop_ids = list(demo_properties.values_list('id', flat=True))

            # Delete BookingContext first (FK to property)
            ctx_deleted, _ = BookingContext.objects.filter(property_id__in=prop_ids).delete()

            # Delete Bookings (FK to property)
            booking_deleted, _ = Booking.objects.filter(property_id__in=prop_ids).delete()

            # Delete PropertyImages
            image_deleted, _ = PropertyImage.objects.filter(property_id__in=prop_ids).delete()

            # Delete RoomTypes (cascade will handle RatePlans etc.)
            room_deleted, _ = RoomType.objects.filter(property_id__in=prop_ids).delete()

            # Delete Properties
            prop_deleted, _ = demo_properties.delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nCleanup complete:\n'
            f'  Properties deleted:    {count}\n'
            f'  Images deleted:        {image_deleted}\n'
            f'  Rooms deleted:         {room_deleted}\n'
            f'  Bookings deleted:      {booking_deleted}\n'
            f'  BookingContexts:       {ctx_deleted}'
        ))
