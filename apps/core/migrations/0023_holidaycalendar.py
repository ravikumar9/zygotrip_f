from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_experiment'),
    ]

    operations = [
        migrations.CreateModel(
            name='HolidayCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('holiday_name', models.CharField(max_length=200)),
                ('country', models.CharField(db_index=True, default='IN', max_length=50)),
                ('state', models.CharField(blank=True, help_text='State code (e.g. MH, DL). Blank = nationwide.', max_length=100)),
                ('date', models.DateField(db_index=True)),
                ('holiday_type', models.CharField(choices=[('national', 'National Holiday'), ('regional', 'Regional Holiday'), ('festival', 'Religious / Cultural Festival'), ('tourism_peak', 'Tourism Peak Season'), ('school_holiday', 'School Holiday'), ('major_event', 'Major Event'), ('long_weekend', 'Long Weekend')], max_length=30)),
                ('demand_multiplier', models.DecimalField(decimal_places=2, default=1.0, help_text='Expected demand multiple (1.5 = 50% above normal, 0.8 = 20% below)', max_digits=4)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('city', models.ForeignKey(blank=True, help_text='City-specific holiday/event. Null = state or nationwide.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='holidays', to='core.city')),
            ],
            options={
                'verbose_name': 'Holiday Calendar Entry',
                'verbose_name_plural': 'Holiday Calendar',
                'ordering': ['date', 'country'],
                'indexes': [
                    models.Index(fields=['date', 'country', 'is_active'], name='hol_date_country_idx'),
                    models.Index(fields=['country', 'state', 'date'], name='hol_country_state_idx'),
                    models.Index(fields=['holiday_type', 'date'], name='hol_type_date_idx'),
                ],
            },
        ),
    ]
