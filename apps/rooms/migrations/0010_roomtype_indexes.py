# Generated migration for RoomType performance indexes.
# Adds indexes on property FK, base_price, and composite property+base_price
# for search ranking and room listing queries.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0024_alter_ratingaggregate_property_alter_review_booking_and_more'),
        ('rooms', '0009_alter_roominventory_room_type_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='roomtype',
            index=models.Index(fields=['property'], name='roomtype_property_idx'),
        ),
        migrations.AddIndex(
            model_name='roomtype',
            index=models.Index(fields=['base_price'], name='roomtype_baseprice_idx'),
        ),
        migrations.AddIndex(
            model_name='roomtype',
            index=models.Index(fields=['property', 'base_price'], name='roomtype_prop_price_idx'),
        ),
    ]
