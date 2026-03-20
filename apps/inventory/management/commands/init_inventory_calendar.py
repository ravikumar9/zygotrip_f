from datetime import date, timedelta

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.exceptions import FieldError

from apps.inventory.services import init_calendar


class Command(BaseCommand):
    help = 'Initialize InventoryCalendar for all active room types for next N days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days ahead to initialize (default: 365)',
        )

    def handle(self, *args, **options):
        RoomType = apps.get_model('rooms', 'RoomType')

        days = options['days']
        start = date.today()
        end = start + timedelta(days=days)

        try:
            room_types = RoomType.objects.filter(is_active=True).select_related('property')
        except FieldError:
            room_types = RoomType.objects.select_related('property')
        total = 0

        for rt in room_types:
            available = getattr(rt, 'available_count', None) or getattr(rt, 'total_rooms', None) or 10
            created = init_calendar(rt, start, end, total_rooms=available)
            total += len(created)
            if created:
                self.stdout.write(
                    f'  {rt.property.name} / {rt.name}: {len(created)} days initialized'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. {total} InventoryCalendar rows created for {room_types.count()} room types.'
            )
        )
