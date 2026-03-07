# Performance optimization: Add database indexes
# Improves query performance for search and filtering

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0002_remove_pricing_fields'),
    ]

    operations = [
        # Index for city filtering (most common filter)
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['city'], name='hotels_prop_city_idx'),
        ),
        # Index for rating sorting
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['-rating'], name='hotels_prop_rating_idx'),
        ),
        # Composite index for active properties with approval
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['is_active', '-rating'], name='hotels_prop_active_rating_idx'),
        ),
        # Index for geo coordinates (distance queries)
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['latitude', 'longitude'], name='hotels_prop_geo_idx'),
        ),
        # Index for trending properties
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['is_trending', '-bookings_today'], name='hotels_prop_trending_idx'),
        ),
        # Index for popularity score
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['-popularity_score'], name='hotels_prop_popularity_idx'),
        ),
    ]