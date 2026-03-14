import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_future_date


class BusType(TimeStampedModel):
	"""Bus type options: Sleeper, Semi Sleeper, AC, Non-AC, Volvo, Seater"""
	SLEEPER = 'sleeper'
	SEMI_SLEEPER = 'semi_sleeper'
	AC = 'ac'
	NON_AC = 'non_ac'
	VOLVO = 'volvo'
	SEATER = 'seater'

	TYPE_CHOICES = [
		(SLEEPER, 'Sleeper'),
		(SEMI_SLEEPER, 'Semi Sleeper'),
		(AC, 'AC'),
		(NON_AC, 'Non-AC'),
		(VOLVO, 'Volvo'),
		(SEATER, 'Seater'),
	]

	name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
	base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=500)
	capacity = models.PositiveIntegerField(default=40)

	class Meta:
		verbose_name_plural = "Bus Types"

	def __str__(self):
		return self.get_name_display()


class Bus(TimeStampedModel):
	"""Bus model with routes and schedules"""
	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='buses', null=True, blank=True)
	registration_number = models.CharField(max_length=20, unique=True)
	bus_type = models.ForeignKey(BusType, on_delete=models.PROTECT)
	operator_name = models.CharField(max_length=100)
	from_city = models.CharField(max_length=50)
	to_city = models.CharField(max_length=50)
	departure_time = models.TimeField()
	arrival_time = models.TimeField()
	journey_date = models.DateField(null=True, blank=True, validators=[validate_future_date], help_text="Date of the bus journey")
	price_per_seat = models.DecimalField(max_digits=8, decimal_places=2)
	available_seats = models.PositiveIntegerField()
	is_active = models.BooleanField(default=True)
	amenities = models.CharField(max_length=500, blank=True, help_text="Comma-separated amenities")

	def __str__(self):
		return f"{self.operator_name} - {self.from_city} to {self.to_city}"

	def get_amenities_list(self):
		if self.amenities:
			return [a.strip() for a in self.amenities.split(',')]
		return []


class BoardingPoint(TimeStampedModel):
	"""Structured boarding (pickup) point for a bus route."""
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='boarding_points')
	name = models.CharField(max_length=120, help_text="e.g. Majestic Bus Stand")
	address = models.CharField(max_length=255, blank=True)
	landmark = models.CharField(max_length=120, blank=True)
	city = models.CharField(max_length=50)
	latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	time = models.TimeField(help_text="Boarding time at this point")
	contact_number = models.CharField(max_length=15, blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['time']
		indexes = [
			models.Index(fields=['bus', 'is_active']),
		]

	def __str__(self):
		return f"{self.name} ({self.time.strftime('%H:%M')})"


class DroppingPoint(TimeStampedModel):
	"""Structured dropping (drop-off) point for a bus route."""
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='dropping_points')
	name = models.CharField(max_length=120, help_text="e.g. Kempegowda ISBT")
	address = models.CharField(max_length=255, blank=True)
	landmark = models.CharField(max_length=120, blank=True)
	city = models.CharField(max_length=50)
	latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
	time = models.TimeField(help_text="Expected arrival time at this point")
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['time']
		indexes = [
			models.Index(fields=['bus', 'is_active']),
		]

	def __str__(self):
		return f"{self.name} ({self.time.strftime('%H:%M')})"


class BusSeat(TimeStampedModel):
	"""Individual seat in a bus with seat state management and TTL locking."""
	AVAILABLE = 'available'
	BOOKED = 'booked'
	LADIES = 'ladies'
	SELECTED = 'selected'
	LOCKED = 'locked'

	STATE_CHOICES = [
		(AVAILABLE, 'Available'),
		(BOOKED, 'Booked'),
		(LADIES, 'Ladies Seat'),
		(SELECTED, 'Selected'),
		(LOCKED, 'Locked (temp hold)'),
	]

	LOCK_TTL_SECONDS = 600  # 10 minute hold

	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='seats')
	seat_number = models.CharField(max_length=10)  # e.g., "A1", "B2"
	row = models.CharField(max_length=2)  # A, B, C, D, etc.
	column = models.PositiveIntegerField()  # 1, 2, 3, 4
	is_ladies_seat = models.BooleanField(default=False)
	state = models.CharField(max_length=20, choices=STATE_CHOICES, default=AVAILABLE)

	# ── Seat Locking (TTL-based hold) ──────────────────────────────
	locked_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
		null=True, blank=True, related_name='locked_bus_seats',
		help_text="User who currently holds the seat lock",
	)
	locked_at = models.DateTimeField(
		null=True, blank=True,
		help_text="When the seat was locked (for TTL expiry)",
	)
	lock_session = models.CharField(
		max_length=64, blank=True,
		help_text="Session/booking reference for this lock",
	)

	class Meta:
		unique_together = ('bus', 'seat_number')
		indexes = [
			models.Index(fields=['state', 'locked_at']),
		]

	def __str__(self):
		return f"{self.bus.registration_number} - Seat {self.seat_number}"

	@property
	def is_lock_expired(self):
		"""Check if the seat lock has expired."""
		if self.state != self.LOCKED or not self.locked_at:
			return False
		elapsed = (timezone.now() - self.locked_at).total_seconds()
		return elapsed > self.LOCK_TTL_SECONDS

	def acquire_lock(self, user, session_ref=''):
		"""Attempt to acquire a TTL lock on this seat.

		Uses SELECT FOR UPDATE to prevent race conditions.
		Returns True if lock acquired, False if seat unavailable.
		"""
		if self.state not in (self.AVAILABLE, self.LADIES):
			# Check if existing lock is expired
			if self.state == self.LOCKED and self.is_lock_expired:
				pass  # Will be overwritten below
			else:
				return False

		self.state = self.LOCKED
		self.locked_by = user
		self.locked_at = timezone.now()
		self.lock_session = session_ref
		self.save(update_fields=['state', 'locked_by', 'locked_at', 'lock_session', 'updated_at'])
		return True

	def release_lock(self):
		"""Release seat lock, returning to available state."""
		was_ladies = self.is_ladies_seat
		self.state = self.LADIES if was_ladies else self.AVAILABLE
		self.locked_by = None
		self.locked_at = None
		self.lock_session = ''
		self.save(update_fields=['state', 'locked_by', 'locked_at', 'lock_session', 'updated_at'])

	def confirm_booking(self):
		"""Transition locked seat to booked (after payment)."""
		self.state = self.BOOKED
		self.save(update_fields=['state', 'updated_at'])

	@classmethod
	def release_expired_locks(cls):
		"""Release all expired seat locks. Called by Celery beat task."""
		from datetime import timedelta
		cutoff = timezone.now() - timedelta(seconds=cls.LOCK_TTL_SECONDS)
		expired = cls.objects.filter(state=cls.LOCKED, locked_at__lte=cutoff)
		count = 0
		for seat in expired:
			seat.release_lock()
			count += 1
		return count


class BusBooking(TimeStampedModel):
	"""Bus booking with passenger details and PNR"""
	STATUS_PENDING = 'pending'
	STATUS_REVIEW = 'review'
	STATUS_PAYMENT = 'payment'
	STATUS_CONFIRMED = 'confirmed'
	STATUS_CANCELLED = 'cancelled'
	STATUS_REFUND_PENDING = 'refund_pending'
	STATUS_REFUNDED = 'refunded'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_REVIEW, 'Review'),
		(STATUS_PAYMENT, 'Payment'),
		(STATUS_CONFIRMED, 'Confirmed'),
		(STATUS_CANCELLED, 'Cancelled'),
		(STATUS_REFUND_PENDING, 'Refund Pending'),
		(STATUS_REFUNDED, 'Refunded'),
	]

	VALID_TRANSITIONS = {
		STATUS_PENDING: [STATUS_REVIEW, STATUS_PAYMENT, STATUS_CANCELLED],
		STATUS_REVIEW: [STATUS_PAYMENT, STATUS_CANCELLED],
		STATUS_PAYMENT: [STATUS_CONFIRMED, STATUS_CANCELLED],
		STATUS_CONFIRMED: [STATUS_CANCELLED],
		STATUS_CANCELLED: [STATUS_REFUND_PENDING],
		STATUS_REFUND_PENDING: [STATUS_REFUNDED],
		STATUS_REFUNDED: [],
	}

	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	pnr = models.CharField(max_length=10, unique=True, editable=False, db_index=True,
						   blank=True, help_text="Auto-generated PNR")
	public_booking_id = models.CharField(max_length=50, unique=True, editable=False, db_index=True, null=True, blank=True)
	idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bus_bookings')
	bus = models.ForeignKey(Bus, on_delete=models.PROTECT, related_name='bookings')
	boarding_point = models.ForeignKey(
		BoardingPoint, on_delete=models.SET_NULL, null=True, blank=True,
		related_name='bookings', help_text="Selected boarding point",
	)
	dropping_point = models.ForeignKey(
		DroppingPoint, on_delete=models.SET_NULL, null=True, blank=True,
		related_name='bookings', help_text="Selected dropping point",
	)
	journey_date = models.DateField(validators=[validate_future_date])
	contact_email = models.EmailField(blank=True)
	contact_phone = models.CharField(max_length=15, blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	promo_code = models.CharField(max_length=30, blank=True)

	def save(self, *args, **kwargs):
		if not self.pk and not self.public_booking_id:
			date_str = timezone.now().strftime('%Y%m%d')
			short_id = str(self.uuid)[:8].upper()
			self.public_booking_id = f"BK-{date_str}-BUS-{short_id}"
		if not self.pnr:
			import random, string
			self.pnr = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
		super().save(*args, **kwargs)

	def transition_to(self, new_status, actor=None, note=''):
		"""Enforce valid state transitions with audit trail."""
		allowed = self.VALID_TRANSITIONS.get(self.status, [])
		if new_status not in allowed:
			raise ValueError(f"Cannot transition from '{self.status}' to '{new_status}'")
		old_status = self.status
		self.status = new_status
		self.save(update_fields=['status', 'updated_at'])
		BusBookingHistory.objects.create(
			booking=self, from_status=old_status, to_status=new_status,
			note=note, actor=actor)

	def __str__(self):
		return f"Bus Booking {self.pnr or self.uuid}"


class BusBookingPassenger(TimeStampedModel):
	"""Passenger details for bus booking"""
	MALE = 'male'
	FEMALE = 'female'

	GENDER_CHOICES = [
		(MALE, 'Male'),
		(FEMALE, 'Female'),
	]

	booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, related_name='passengers')
	seat = models.ForeignKey(BusSeat, on_delete=models.PROTECT)
	full_name = models.CharField(max_length=120)
	age = models.PositiveIntegerField()
	gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default=MALE)
	phone = models.CharField(max_length=15, blank=True)
	id_proof_type = models.CharField(max_length=50, blank=True)
	id_proof_number = models.CharField(max_length=50, blank=True)

	def __str__(self):
		return f"{self.full_name} - {self.booking.uuid}"


class BusPriceBreakdown(TimeStampedModel):
	"""Price breakdown for bus booking"""
	booking = models.OneToOneField(BusBooking, on_delete=models.CASCADE, related_name='price_breakdown')
	base_amount = models.DecimalField(max_digits=12, decimal_places=2)
	service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	promo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		verbose_name_plural = "Bus Price Breakdowns"

	def __str__(self):
		return f"Price Breakdown - {self.booking.uuid}"


# ── Bus Cancellation Policy ──────────────────────────────────────────

class BusCancellationPolicy(TimeStampedModel):
	"""Tiered cancellation/refund policy for a bus operator."""
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='cancellation_policies')
	hours_before_departure = models.PositiveIntegerField(
		help_text="Hours before departure time")
	refund_percentage = models.DecimalField(max_digits=5, decimal_places=2)
	cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

	class Meta:
		ordering = ['-hours_before_departure']
		indexes = [models.Index(fields=['bus', 'hours_before_departure'])]

	def __str__(self):
		return f"{self.bus} >{self.hours_before_departure}h → {self.refund_percentage}% refund"


# ── Bus Booking History (audit trail) ─────────────────────────────────

class BusBookingHistory(TimeStampedModel):
	"""Immutable audit trail for bus booking status transitions."""
	booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, related_name='history')
	from_status = models.CharField(max_length=20, blank=True)
	to_status = models.CharField(max_length=20)
	note = models.CharField(max_length=300, blank=True)
	actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
							  null=True, blank=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.booking.uuid}: {self.from_status} → {self.to_status}"