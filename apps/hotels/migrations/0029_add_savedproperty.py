# Generated migration for SavedProperty model defined in apps/hotels/wishlist_api.py
# This is a manually created migration because SavedProperty lives outside models.py
# to keep wishlist logic self-contained.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0028_add_property_checkin_times_house_rules'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedProperty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_properties',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('property', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_by_users',
                    to='hotels.property',
                )),
            ],
            options={
                'verbose_name': 'Saved Property',
                'verbose_name_plural': 'Saved Properties',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'property')},
            },
        ),
        migrations.AddIndex(
            model_name='savedproperty',
            index=models.Index(fields=['user', '-created_at'], name='hotels_save_user_id_8bf49f_idx'),
        ),
    ]
