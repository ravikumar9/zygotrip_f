# Generated migration to remove pricing fields from Property model
# Pricing is now domain-driven: stored in RoomType, computed for Property

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='base_price',
        ),
        migrations.RemoveField(
            model_name='property',
            name='discount_price',
        ),
        migrations.RemoveField(
            model_name='property',
            name='dynamic_price',
        ),
    ]