"""Migration: Add RoomMealPlan model."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0006_add_uuid_to_roomtype'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomMealPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(
                    choices=[
                        ('room_only', 'Room Only'),
                        ('breakfast', 'Room + Breakfast'),
                        ('half_board', 'Room + Breakfast + Dinner'),
                        ('full_board', 'Room + All Meals'),
                        ('all_inclusive', 'All Inclusive'),
                    ],
                    default='room_only',
                    max_length=30,
                )),
                ('name', models.CharField(max_length=100)),
                ('price_modifier', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Add-on price per room per night (INR). 0 = included in room rate.',
                    max_digits=10,
                )),
                ('description', models.TextField(blank=True)),
                ('is_available', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('room_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='meal_plans',
                    to='rooms.roomtype',
                )),
            ],
            options={
                'app_label': 'rooms',
                'ordering': ['display_order', 'id'],
                'unique_together': {('room_type', 'code')},
            },
        ),
    ]
