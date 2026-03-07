from django.core.management.base import BaseCommand

from apps.search.index_builder import rebuild_search_index


class Command(BaseCommand):
    help = "Rebuild unified SearchIndex entries for autocomplete"

    def handle(self, *args, **options):
        totals = rebuild_search_index()
        self.stdout.write(
            self.style.SUCCESS(
                f"SearchIndex rebuilt: cities={totals['cities']}, "
                f"areas={totals['areas']}, properties={totals['properties']}"
            )
        )
