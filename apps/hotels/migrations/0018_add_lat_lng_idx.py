"""
Migration 0018: Add compound (latitude, longitude) index to hotels_property.

This index is used by distance-sorting queries and map viewport filtering.
Required for: ORDER BY distance, filter by bounding box.
"""
# Generated manually 2026-03-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0017_booking_context_and_lifecycle_states'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='property',
            index=models.Index(
                fields=['latitude', 'longitude'],
                name='property_lat_lng_idx',
            ),
        ),
    ]
