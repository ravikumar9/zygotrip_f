from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_holidaycalendar'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicefingerprint',
            name='fcm_token',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Firebase Cloud Messaging device token for push notifications',
                max_length=512,
            ),
        ),
    ]
