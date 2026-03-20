from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referral_code', models.CharField(db_index=True, max_length=12, unique=True)),
                ('total_referrals', models.PositiveIntegerField(default=0)),
                ('successful_referrals', models.PositiveIntegerField(default=0)),
                ('total_wallet_credits', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_loyalty_points', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-updated_at',),
            },
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referral_code', models.CharField(db_index=True, max_length=12)),
                ('status', models.CharField(choices=[('signed_up', 'Signed Up'), ('completed', 'Completed'), ('rewarded', 'Rewarded')], default='signed_up', max_length=16)),
                ('referee_wallet_credit', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('referrer_loyalty_points', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('referee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_received', to=settings.AUTH_USER_MODEL)),
                ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
                'constraints': [models.UniqueConstraint(fields=('referrer', 'referee'), name='unique_referrer_referee_pair')],
            },
        ),
    ]
