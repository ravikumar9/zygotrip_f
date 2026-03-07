import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_future_date


FUEL_TYPE_CHOICES = [
    ('petrol', 'Petrol'),
    ('diesel', 'Diesel'),
    ('electric', 'Electric'),
    ('hybrid', 'Hybrid'),
]

SEAT_CHOICES = [
    (2, '2 Seater'),
    (3, '3 Seater'),
    (4, '4 Seater'),
    (5, '5 Seater'),
    (6, '6 Seater'),
    (7, '7 Seater'),
    (8, '8 Seater'),
    (12, '12 Seater'),
]

CITY_CHOICES = [
    ('delhi', 'Delhi'),
    ('mumbai', 'Mumbai'),
    ('bangalore', 'Bangalore'),
    ('hyderabad', 'Hyderabad'),
    ('chennai', 'Chennai'),
    ('goa', 'Goa'),
    ('jaipur', 'Jaipur'),
    ('pune', 'Pune'),
    ('kolkata', 'Kolkata'),
    ('ahmedabad', 'Ahmedabad'),
]


class CabType(TimeStampedModel):
	"""Cab type definitions"""
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)

	def __str__(self):
		return self.name


class Cab(TimeStampedModel):
	"""Cab model with owner for operator dashboard"""
	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_cabs', null=True, blank=True)
	name = models.CharField(max_length=100, default='Unnamed Cab')
	city = models.CharField(max_length=50, choices=CITY_CHOICES, default='delhi')
	seats = models.IntegerField(choices=SEAT_CHOICES, default=5, validators=[MinValueValidator(2), MaxValueValidator(12)])
	fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES, default='petrol')
	base_price_per_km = models.DecimalField(max_digits=8, decimal_places=2, default=10, validators=[MinValueValidator(0.01)])
	system_price_per_km = models.DecimalField(max_digits=8, decimal_places=2, default=13, validators=[MinValueValidator(0.01)])
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name_plural = "Cabs"
		indexes = [
			models.Index(fields=['city', 'is_active']),
			models.Index(fields=['owner', 'is_active']),
		]

	def __str__(self):
		return f"{self.name} - {self.city}"

	def clean(self):
		"""Validate model data"""
		from django.core.exceptions import ValidationError
		if self.base_price_per_km is not None and self.base_price_per_km <= 0:
			raise ValidationError({'base_price_per_km': 'Price must be greater than 0'})
		if self.system_price_per_km is not None and self.system_price_per_km <= 0:
			raise ValidationError({'system_price_per_km': 'Price must be greater than 0'})
		if self.seats is not None and self.seats < 2:
			raise ValidationError({'seats': 'Seats must be at least 2'})

	def save(self, *args, **kwargs):
		# Auto-calculate system price if owner price changed
		if self.base_price_per_km and not self.system_price_per_km:
			from django.conf import settings
			margin = getattr(settings, 'PLATFORM_CAB_MARGIN', 3)
			self.system_price_per_km = self.base_price_per_km + margin
		# Validate before saving
		self.clean()
		super().save(*args, **kwargs)


class CabImage(TimeStampedModel):
	"""Cab images for listing display"""
	cab = models.ForeignKey(Cab, on_delete=models.CASCADE, related_name='images')
	image = models.ImageField(upload_to='cabs/')
	is_primary = models.BooleanField(default=False)

	class Meta:
		verbose_name_plural = "Cab Images"

	def __str__(self):
		return f"Image for {self.cab.name}"


class CabAvailability(TimeStampedModel):
	"""Track cab availability by date"""
	cab = models.ForeignKey(Cab, on_delete=models.CASCADE, related_name='availability')
	date = models.DateField()
	is_available = models.BooleanField(default=True)

	class Meta:
		verbose_name_plural = "Cab Availability"
		unique_together = ('cab', 'date')
		indexes = [models.Index(fields=['cab', 'date'])]

	def __str__(self):
		return f"{self.cab.name} - {self.date}"


class CabBooking(TimeStampedModel):
	"""Cab booking with pricing calculation"""
	BOOKING_STATUS_CHOICES = [
		('pending', 'Pending'),
		('confirmed', 'Confirmed'),
		('completed', 'Completed'),
		('cancelled', 'Cancelled'),
	]

	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	public_booking_id = models.CharField(max_length=50, unique=True, editable=False, db_index=True, null=True, blank=True)
	idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
	cab = models.ForeignKey(Cab, on_delete=models.PROTECT, related_name='bookings')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cab_bookings')
	booking_date = models.DateField(validators=[validate_future_date])
	distance_km = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(1)])
	base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=50)
	price_per_km = models.DecimalField(max_digits=8, decimal_places=2)  # system_price_per_km at booking time
	total_price = models.DecimalField(max_digits=10, decimal_places=2)
	discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	final_price = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
	promo_code = models.CharField(max_length=50, blank=True)

	class Meta:
		verbose_name_plural = "Cab Bookings"
		indexes = [models.Index(fields=['user', 'booking_date']), models.Index(fields=['cab', 'booking_date'])]

	def __str__(self):
		return f"Booking {self.uuid} - {self.cab.name}"

	def calculate_total(self):
		"""Calculate total price from distance and rate, including 5% GST"""
		from decimal import Decimal
		distance = Decimal(str(self.distance_km or 0))
		price_per_km = Decimal(str(self.price_per_km or 0))
		base_fare_val = Decimal(str(self.base_fare or 0))
		discount = Decimal(str(self.discount_amount or 0))
		
		# Calculate base total (distance * rate + base fare)
		self.total_price = base_fare_val + (distance * price_per_km)
		
		# Apply 5% GST
		gst = (self.total_price * Decimal('0.05')).quantize(Decimal('0.01'))
		
		# Final price = total price + GST - discount
		self.final_price = (self.total_price + gst - discount).quantize(Decimal('0.01'))
		
		return self.final_price

	def save(self, *args, **kwargs):
		# Generate public_booking_id on first creation
		if not self.pk and not self.public_booking_id:
			date_str = timezone.now().strftime('%Y%m%d')
			short_id = str(self.uuid)[:8].upper()
			self.public_booking_id = f"BK-{date_str}-CAB-{short_id}"
		if self.distance_km and self.price_per_km:
			self.calculate_total()
		super().save(*args, **kwargs)