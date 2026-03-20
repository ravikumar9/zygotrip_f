from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_platformsettings_control_center'),
    ]

    operations = [
        migrations.AlterField(
            model_name='platformsettings',
            name='flights_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='maintenance_message',
            field=models.CharField(blank=True, default='Platform is under maintenance. Please try again shortly.', max_length=255),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='min_app_version_android',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='min_app_version_ios',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
