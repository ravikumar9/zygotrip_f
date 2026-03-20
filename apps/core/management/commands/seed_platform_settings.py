from django.core.management.base import BaseCommand

from apps.core.models import PlatformSettings


class Command(BaseCommand):
    help = 'Create the singleton PlatformSettings row if missing and apply env defaults.'

    def handle(self, *args, **options):
        settings_obj = PlatformSettings.get_settings()
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS(f'Platform settings ready (id={settings_obj.id}).'))
