# Generated migration for adding meal_plan to RoomType

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0004_add_room_amenity'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomtype',
            name='meal_plan',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('room_only', 'Room Only'),
                    ('breakfast', 'Room + Breakfast'),
                    ('half_board', 'Room + Breakfast + Dinner'),
                    ('full_board', 'Room + All Meals'),
                    ('all_inclusive', 'All Inclusive'),
                ],
                default='room_only',
                help_text='Meal plan included with room'
            ),
        ),
    ]
