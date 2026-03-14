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
	cab_type = models.ForeignKey(CabType, on_delete=models.SET_NULL, null=True, blank=True, related_name='cabs')
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
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cab_bookings')
	driver = models.ForeignKey('cabs.Driver', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
	booking_date = models.DateField(validators=[validate_future_date])
	pickup_address = models.CharField(max_length=255, blank=True, help_text="Pickup location address")
	drop_address = models.CharField(max_length=255, blank=True, help_text="Drop-off location address")
	pickup_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	pickup_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	drop_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	drop_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	distance_km = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(1)])
	base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=50)
	price_per_km = models.DecimalField(max_digits=8, decimal_places=2)  # system_price_per_km at booking time
	surge_multiplier = models.DecimalField(
		max_digits=4, decimal_places=2, default=1.0,
		help_text="Surge multiplier at time of booking",
	)
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
		"""Calculate total price from distance and rate, including 5% GST and surge."""
		from decimal import Decimal
		distance = Decimal(str(self.distance_km or 0))
		price_per_km = Decimal(str(self.price_per_km or 0))
		base_fare_val = Decimal(str(self.base_fare or 0))
		discount = Decimal(str(self.discount_amount or 0))
		surge = Decimal(str(self.surge_multiplier or '1.0'))
		
		# Calculate base total (distance * rate + base fare) * surge
		subtotal = base_fare_val + (distance * price_per_km)
		self.total_price = (subtotal * surge).quantize(Decimal('0.01'))
		
		# Apply 5% GST
		gst = (self.total_price * Decimal('0.05')).quantize(Decimal('0.01'))
		
		# Final price = total price + GST - discount (floor at 0)
		self.final_price = max(
			Decimal('0'),
			(self.total_price + gst - discount).quantize(Decimal('0.01')),
		)
		
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


# ── Surge Pricing Model ────────────────────────────────────────────────

class SurgePricing(TimeStampedModel):
	"""Demand-based surge pricing rules.

	Multiplier applied on top of base fare during high-demand periods.
	Evaluated per city + time window.
	"""
	city = models.CharField(max_length=50, choices=CITY_CHOICES, db_index=True)
	day_of_week = models.IntegerField(
		null=True, blank=True,
		help_text="0=Monday..6=Sunday, null=all days",
		validators=[MinValueValidator(0), MaxValueValidator(6)],
	)
	start_hour = models.IntegerField(
		default=0, validators=[MinValueValidator(0), MaxValueValidator(23)],
		help_text="Start hour (24h format)",
	)
	end_hour = models.IntegerField(
		default=23, validators=[MinValueValidator(0), MaxValueValidator(23)],
		help_text="End hour (24h format)",
	)
	multiplier = models.DecimalField(
		max_digits=4, decimal_places=2, default=1.0,
		validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
		help_text="Surge multiplier (1.0=no surge, 2.0=2x)",
	)
	is_active = models.BooleanField(default=True)
	reason = models.CharField(
		max_length=100, blank=True,
		help_text="e.g. 'Peak morning hours', 'Rain surge', 'Event surge'",
	)

	class Meta:
		verbose_name_plural = "Surge Pricing Rules"
		ordering = ['-multiplier']
		indexes = [
			models.Index(fields=['city', 'is_active']),
		]

	def __str__(self):
		return f"{self.city} {self.start_hour}:00-{self.end_hour}:00 x{self.multiplier}"

	@classmethod
	def get_current_multiplier(cls, city):
		"""Get the highest active surge multiplier for a city right now."""
		from decimal import Decimal
		now = timezone.localtime()
		hour = now.hour
		day = now.weekday()

		surges = cls.objects.filter(
			city=city,
			is_active=True,
			start_hour__lte=hour,
			end_hour__gte=hour,
		).filter(
			models.Q(day_of_week__isnull=True) | models.Q(day_of_week=day),
		)

		if surges.exists():
			return surges.order_by('-multiplier').first().multiplier
		return Decimal('1.0')


# ── Driver Model ──────────────────────────────────────────────────────

class Driver(TimeStampedModel):
	"""Driver assigned to a cab with availability status."""
	STATUS_CHOICES = [
		('available', 'Available'),
		('on_trip', 'On Trip'),
		('offline', 'Offline'),
		('break', 'On Break'),
	]

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
		related_name='driver_profile',
	)
	cab = models.ForeignKey(
		Cab, on_delete=models.SET_NULL, null=True, blank=True,
		related_name='drivers',
	)
	license_number = models.CharField(max_length=30, unique=True)
	phone = models.CharField(max_length=15)
	city = models.CharField(max_length=50, choices=CITY_CHOICES)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
	current_latitude = models.DecimalField(
		max_digits=10, decimal_places=7, null=True, blank=True,
	)
	current_longitude = models.DecimalField(
		max_digits=10, decimal_places=7, null=True, blank=True,
	)
	rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)
	total_trips = models.PositiveIntegerField(default=0)
	is_verified = models.BooleanField(default=False)

	class Meta:
		indexes = [
			models.Index(fields=['city', 'status']),
			models.Index(fields=['cab']),
		]

	def __str__(self):
		return f"Driver {self.user.get_full_name() if hasattr(self.user, 'get_full_name') else self.user_id} ({self.status})"

	@classmethod
	def find_nearest_available(cls, city, latitude=None, longitude=None, limit=5):
		"""Find nearest available drivers in a city.

		If lat/lng provided, sorts by approximate distance (Euclidean on coords).
		Otherwise returns by rating.
		"""
		drivers = cls.objects.filter(
			city=city, status='available', is_verified=True,
		).select_related('cab')

		if latitude and longitude:
			from django.db.models import F
			# Approximate distance using Euclidean on decimal coords
			# Fine for short-distance driver matching (<50km)
			drivers = drivers.annotate(
				approx_dist=(
					(F('current_latitude') - latitude) ** 2
					+ (F('current_longitude') - longitude) ** 2
				),
			).order_by('approx_dist')
		else:
			drivers = drivers.order_by('-rating', '-total_trips')

		return drivers[:limit]


# ── Cab Price Breakdown ───────────────────────────────────────────────

class CabPriceBreakdown(TimeStampedModel):
	"""Detailed price breakdown for cab bookings (parity with BusPriceBreakdown)."""
	booking = models.OneToOneField(CabBooking, on_delete=models.CASCADE, related_name='price_breakdown')
	base_fare = models.DecimalField(max_digits=10, decimal_places=2)
	distance_charge = models.DecimalField(max_digits=10, decimal_places=2)
	surge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	gst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	promo_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	total_amount = models.DecimalField(max_digits=10, decimal_places=2)

	class Meta:
		verbose_name_plural = "Cab Price Breakdowns"

	def __str__(self):
		return f"Price Breakdown - {self.booking.uuid}"


# ── Trip Tracking (real-time ride progress) ──────────────────────────

class CabTrip(TimeStampedModel):
	"""Real-time trip tracking for active cab rides."""
	TRIP_STATUS_CHOICES = [
		('driver_assigned', 'Driver Assigned'),
		('en_route_pickup', 'En Route to Pickup'),
		('arrived_pickup', 'Arrived at Pickup'),
		('trip_started', 'Trip Started'),
		('trip_completed', 'Trip Completed'),
		('trip_cancelled', 'Trip Cancelled'),
	]

	booking = models.OneToOneField(CabBooking, on_delete=models.CASCADE, related_name='trip')
	driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name='trips')
	trip_status = models.CharField(max_length=20, choices=TRIP_STATUS_CHOICES, default='driver_assigned')

	assigned_at = models.DateTimeField(auto_now_add=True)
	pickup_arrived_at = models.DateTimeField(null=True, blank=True)
	trip_started_at = models.DateTimeField(null=True, blank=True)
	trip_completed_at = models.DateTimeField(null=True, blank=True)

	current_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	current_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	eta_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="ETA in minutes")

	actual_distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
	actual_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
	otp_code = models.CharField(max_length=6, blank=True, help_text="Ride start OTP")

	class Meta:
		verbose_name_plural = "Cab Trips"
		indexes = [
			models.Index(fields=['driver', 'trip_status']),
			models.Index(fields=['trip_status', '-assigned_at']),
		]

	def __str__(self):
		return f"Trip {self.booking.uuid} ({self.trip_status})"

	def advance_status(self, new_status):
		VALID_TRANSITIONS = {
			'driver_assigned': ['en_route_pickup', 'trip_cancelled'],
			'en_route_pickup': ['arrived_pickup', 'trip_cancelled'],
			'arrived_pickup': ['trip_started', 'trip_cancelled'],
			'trip_started': ['trip_completed'],
			'trip_completed': [],
			'trip_cancelled': [],
		}
		allowed = VALID_TRANSITIONS.get(self.trip_status, [])
		if new_status not in allowed:
			raise ValueError(f"Cannot transition from '{self.trip_status}' to '{new_status}'")
		self.trip_status = new_status
		now = timezone.now()
		if new_status == 'arrived_pickup':
			self.pickup_arrived_at = now
		elif new_status == 'trip_started':
			self.trip_started_at = now
		elif new_status == 'trip_completed':
			self.trip_completed_at = now
			self.driver.status = 'available'
			self.driver.total_trips += 1
			self.driver.save(update_fields=['status', 'total_trips', 'updated_at'])
		self.save()


# ── Driver Reviews ────────────────────────────────────────────────────

class DriverReview(TimeStampedModel):
	"""Post-ride review for driver with sub-ratings."""
	booking = models.OneToOneField(CabBooking, on_delete=models.CASCADE, related_name='driver_review')
	driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='reviews')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cab_reviews')
	rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
	comment = models.TextField(blank=True, max_length=500)
	safety_rating = models.PositiveIntegerField(
		null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
	cleanliness_rating = models.PositiveIntegerField(
		null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
	punctuality_rating = models.PositiveIntegerField(
		null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])

	class Meta:
		unique_together = ('booking', 'user')
		ordering = ['-created_at']

	def __str__(self):
		return f"Review for {self.driver} by {self.user_id} ({self.rating}★)"

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		from django.db.models import Avg
		avg = self.driver.reviews.aggregate(avg=Avg('rating'))['avg']
		if avg:
			self.driver.rating = round(avg, 1)
			self.driver.save(update_fields=['rating', 'updated_at'])


# Import models from dispatch_engine for migration generation
from .dispatch_engine import DriverLocation, DispatchRequest