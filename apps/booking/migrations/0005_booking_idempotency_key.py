from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0004_bookingretryqueue'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='idempotency_key',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True),
        ),
    ]