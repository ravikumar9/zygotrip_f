from django.core.management.base import BaseCommand

from apps.hotels.models import Property
from apps.hotels.semantic_search import upsert_hotel_embedding


class Command(BaseCommand):
    help = 'Generate or refresh semantic embeddings for approved properties.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Optional max properties to process')

    def handle(self, *args, **options):
        limit = options.get('limit') or 0
        qs = Property.objects.filter(status='approved', agreement_signed=True).select_related('city').order_by('id')
        if limit > 0:
            qs = qs[:limit]

        processed = 0
        skipped = 0
        for property_obj in qs:
            embed = upsert_hotel_embedding(property_obj)
            if embed:
                processed += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Hotel embeddings refresh completed: processed={processed}, skipped={skipped}'
        ))
