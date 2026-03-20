import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('booking', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='LoyaltyAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('points_balance', models.PositiveIntegerField(default=0)),
                ('lifetime_points', models.PositiveIntegerField(default=0)),
                ('tier', models.CharField(
                    choices=[('silver', 'Silver'), ('gold', 'Gold'), ('platinum', 'Platinum'), ('elite', 'Elite')],
                    db_index=True, default='silver', max_length=20,
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='loyalty_account',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'app_label': 'loyalty'},
        ),
        migrations.CreateModel(
            name='PointsTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('transaction_type', models.CharField(
                    choices=[
                        ('earned_booking', 'Earned from Booking'),
                        ('redeemed', 'Redeemed'),
                        ('expired', 'Expired'),
                        ('bonus', 'Bonus'),
                        ('referral', 'Referral Reward'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('points', models.IntegerField()),
                ('description', models.CharField(blank=True, max_length=255)),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transactions',
                    to='loyalty.loyaltyaccount',
                    db_index=True,
                )),
                ('booking', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='loyalty_transactions',
                    to='booking.booking',
                )),
            ],
            options={
                'app_label': 'loyalty',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['account', '-created_at'], name='loyalty_acct_date_idx'),
                    models.Index(fields=['expires_at'], name='loyalty_expiry_idx'),
                ],
            },
        ),
    ]
