from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_rename_hol_date_country_idx_core_holida_date_2e9cc7_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsettings',
            name='activities_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='ai_assistant_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='bookings_enabled',
            field=models.BooleanField(default=True, help_text='Master booking switch for all verticals'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='buses_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='cabs_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='default_currency',
            field=models.CharField(default='INR', max_length=10),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='flights_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='hotels_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='loyalty_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='maintenance_mode',
            field=models.BooleanField(default=False, help_text='If enabled, non-admin traffic can be gated by middleware/UI'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='max_coupon_discount_percent',
            field=models.DecimalField(decimal_places=2, default=50.0, help_text='Global cap for promo percentage discounts', max_digits=5),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='packages_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='payments_enabled',
            field=models.BooleanField(default=True, help_text='Master payment switch for checkout/payment APIs'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='promos_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='support_phone',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='system_notice',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
