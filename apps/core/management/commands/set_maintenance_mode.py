from django.core.management.base import BaseCommand

from apps.core.models import PlatformSettings


class Command(BaseCommand):
    help = 'Toggle maintenance mode from CLI.'

    def add_arguments(self, parser):
        parser.add_argument('--on', action='store_true', help='Enable maintenance mode.')
        parser.add_argument('--off', action='store_true', help='Disable maintenance mode.')
        parser.add_argument('--message', type=str, default='', help='Maintenance message override.')

    def handle(self, *args, **options):
        if options['on'] and options['off']:
            self.stderr.write('Use either --on or --off, not both.')
            return

        settings_obj = PlatformSettings.get_settings()
        if options['on']:
            settings_obj.maintenance_mode = True
        if options['off']:
            settings_obj.maintenance_mode = False
        if options['message']:
            settings_obj.maintenance_message = options['message']
        settings_obj.save()

        state = 'ON' if settings_obj.maintenance_mode else 'OFF'
        self.stdout.write(self.style.SUCCESS(f'Maintenance mode: {state}'))
