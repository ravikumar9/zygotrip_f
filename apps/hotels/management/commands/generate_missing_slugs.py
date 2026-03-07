"""Management command to generate missing slugs for Property models."""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.hotels.models import Property


class Command(BaseCommand):
    help = 'Generate missing slugs for Property models'

    def handle(self, *args, **options):
        # Find properties without slugs
        missing_slug_count = Property.objects.filter(slug__isnull=True).count()
        empty_slug_count = Property.objects.filter(slug='').count()
        
        self.stdout.write(f"Found {missing_slug_count} properties with NULL slug")
        self.stdout.write(f"Found {empty_slug_count} properties with empty slug")
        
        count = 0
        failed = 0
        
        # Fix NULL slugs using bulk_update (bypasses field validation)
        properties_to_update = []
        for prop in Property.objects.filter(slug__isnull=True):
            new_slug = slugify(prop.name)[:200]
            prop.slug = new_slug
            properties_to_update.append(prop)
        
        if properties_to_update:
            try:
                Property.objects.bulk_update(properties_to_update, ['slug'], batch_size=100)
                self.stdout.write(self.style.SUCCESS(f"✅ Updated {len(properties_to_update)} properties with NULL slug"))
                count += len(properties_to_update)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Bulk update failed: {str(e)}"))
                failed += len(properties_to_update)
        
        # Fix empty slugs
        properties_to_update = []
        for prop in Property.objects.filter(slug=''):
            new_slug = slugify(prop.name)[:200]
            prop.slug = new_slug
            properties_to_update.append(prop)
        
        if properties_to_update:
            try:
                Property.objects.bulk_update(properties_to_update, ['slug'], batch_size=100)
                self.stdout.write(self.style.SUCCESS(f"✅ Updated {len(properties_to_update)} properties with empty slug"))
                count += len(properties_to_update)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Bulk update failed: {str(e)}"))
                failed += len(properties_to_update)
        
        # Verify
        remaining = Property.objects.filter(slug__isnull=True).count() + Property.objects.filter(slug='').count()
        self.stdout.write(self.style.SUCCESS(f"\n✅ Complete! Updated: {count}, Failed: {failed}, Remaining: {remaining}"))