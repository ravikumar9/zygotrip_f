from django.core.management.base import BaseCommand

from apps.core.feature_flags import FeatureFlag


DEFAULT_FLAGS = [
    ('enable_hotels', True, 'Hotels vertical availability switch'),
    ('enable_buses', True, 'Buses vertical availability switch'),
    ('enable_cabs', True, 'Cabs vertical availability switch'),
    ('enable_packages', True, 'Packages vertical availability switch'),
    ('enable_ai_assistant', True, 'AI assistant availability switch'),
    ('enable_loyalty', True, 'Loyalty engine availability switch'),
    ('enable_promos', True, 'Promo engine availability switch'),
    ('enable_owner_command_center', True, 'Owner command center dashboards'),
    ('enable_dynamic_pricing', True, 'Dynamic pricing workflows'),
    ('enable_supplier_sync', True, 'Supplier synchronization jobs'),
]


class Command(BaseCommand):
    help = 'Seed default feature flags used by platform control center.'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for name, enabled, description in DEFAULT_FLAGS:
            flag, was_created = FeatureFlag.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'is_enabled': enabled,
                    'rollout_percentage': 100,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
            else:
                dirty = False
                if flag.description != description:
                    flag.description = description
                    dirty = True
                if flag.rollout_percentage != 100:
                    flag.rollout_percentage = 100
                    dirty = True
                if not flag.is_active:
                    flag.is_active = True
                    dirty = True
                if dirty:
                    flag.save(update_fields=['description', 'rollout_percentage', 'is_active', 'updated_at'])
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'Feature flags seeded. created={created}, updated={updated}'))
