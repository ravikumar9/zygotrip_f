from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checkout', '0002_cart_travelbundle_bundleitem_cartitem_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingsession',
            name='session_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Anonymous browser session key for guest checkout ownership',
                max_length=64,
            ),
        ),
        migrations.AddIndex(
            model_name='bookingsession',
            index=models.Index(fields=['session_key', 'session_status'], name='bs_session_status_idx'),
        ),
    ]
