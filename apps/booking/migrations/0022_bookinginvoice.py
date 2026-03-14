from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0021_supplierreconciliation_supplierreconciliationitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingInvoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('invoice_number', models.CharField(help_text='e.g. ZT-20260311-000042', max_length=50, unique=True)),
                ('supplier_invoice_number', models.CharField(blank=True, max_length=50)),
                ('customer_name', models.CharField(max_length=200)),
                ('customer_email', models.EmailField(blank=True)),
                ('customer_phone', models.CharField(blank=True, max_length=20)),
                ('customer_gstin', models.CharField(blank=True, max_length=15)),
                ('customer_address', models.TextField(blank=True)),
                ('supplier_name', models.CharField(blank=True, max_length=200)),
                ('supplier_gstin', models.CharField(blank=True, max_length=15)),
                ('supplier_address', models.TextField(blank=True)),
                ('hotel_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('commission_percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('commission_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('commission_gst', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('gst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('gst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('service_fee', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('final_customer_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('owner_payout_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('issued', 'Issued'), ('cancelled', 'Cancelled'), ('amended', 'Amended')], db_index=True, default='draft', max_length=20)),
                ('issued_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('cancellation_reason', models.CharField(blank=True, max_length=200)),
                ('booking_date', models.DateField(blank=True, null=True)),
                ('check_in_date', models.DateField(blank=True, null=True)),
                ('check_out_date', models.DateField(blank=True, null=True)),
                ('nights', models.PositiveIntegerField(default=1)),
                ('rooms', models.PositiveIntegerField(default=1)),
                ('property_name', models.CharField(blank=True, max_length=200)),
                ('room_type_name', models.CharField(blank=True, max_length=200)),
                ('booking', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='invoice', to='booking.booking')),
            ],
            options={
                'verbose_name': 'Booking Invoice',
                'verbose_name_plural': 'Booking Invoices',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', '-created_at'], name='inv_status_created_idx'),
                    models.Index(fields=['booking'], name='inv_booking_idx'),
                    models.Index(fields=['issued_at'], name='inv_issued_idx'),
                ],
            },
        ),
    ]
