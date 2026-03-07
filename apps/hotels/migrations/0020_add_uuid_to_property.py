"""
Migration: Add uuid to Property (two-step for existing rows).
"""
import uuid
from django.db import migrations, models


def populate_property_uuids(apps, schema_editor):
    Property = apps.get_model('hotels', 'Property')
    for obj in Property.objects.filter(uuid__isnull=True):
        obj.uuid = uuid.uuid4()
        obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0019_add_pay_at_hotel'),
    ]

    operations = [
        # Step 1: add nullable (no unique yet)
        migrations.AddField(
            model_name='property',
            name='uuid',
            field=models.UUIDField(null=True, blank=True),
        ),
        # Step 2: populate existing rows
        migrations.RunPython(populate_property_uuids, migrations.RunPython.noop),
        # Step 3: make non-null, unique, indexed
        migrations.AlterField(
            model_name='property',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True),
        ),
    ]
