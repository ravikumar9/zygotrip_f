"""
Migration: Add uuid to RoomType.

Two-step to handle existing rows:
  1. Add uuid nullable (no unique constraint yet)
  2. Populate existing rows with uuid4
  3. Make it non-null and unique
"""
import uuid
from django.db import migrations, models


def populate_roomtype_uuids(apps, schema_editor):
    RoomType = apps.get_model('rooms', 'RoomType')
    for obj in RoomType.objects.filter(uuid__isnull=True):
        obj.uuid = uuid.uuid4()
        obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0005_add_meal_plan'),
    ]

    operations = [
        # Step 1: add nullable (no unique constraint yet)
        migrations.AddField(
            model_name='roomtype',
            name='uuid',
            field=models.UUIDField(null=True, blank=True),
        ),
        # Step 2: populate existing rows
        migrations.RunPython(populate_roomtype_uuids, migrations.RunPython.noop),
        # Step 3: make non-null and unique
        migrations.AlterField(
            model_name='roomtype',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True),
        ),
    ]
