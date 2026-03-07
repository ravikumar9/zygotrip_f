"""
Migration: Add uuid to BookingContext.

Two-step to handle existing rows:
  1. Add uuid nullable (no unique constraint yet)
  2. Populate existing rows with uuid4
  3. Make it non-null, unique, and indexed
"""
import uuid
from django.db import migrations, models


def populate_bookingcontext_uuids(apps, schema_editor):
    BookingContext = apps.get_model('booking', 'BookingContext')
    for obj in BookingContext.objects.filter(uuid__isnull=True):
        obj.uuid = uuid.uuid4()
        obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0011_delete_bookingretryqueue'),
    ]

    operations = [
        # Step 1: add nullable (no unique constraint yet)
        migrations.AddField(
            model_name='bookingcontext',
            name='uuid',
            field=models.UUIDField(null=True, blank=True),
        ),
        # Step 2: populate existing rows
        migrations.RunPython(populate_bookingcontext_uuids, migrations.RunPython.noop),
        # Step 3: make non-null, unique, indexed
        migrations.AlterField(
            model_name='bookingcontext',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True),
        ),
    ]
