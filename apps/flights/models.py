"""
Flight Booking System — OTA-grade flight search, booking, and ticketing.

Models:
  Airline, Airport, Flight, FlightLeg, FlightFareClass, BaggageAllowance,
  FlightBooking, FlightBookingHistory, FlightPassenger,
  FlightPriceBreakdown, FlightCancellationPolicy
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import TimeStampedModel


# ── Airlines ──────────────────────────────────────────────────────────

class Airline(TimeStampedModel):
    """Airline / carrier master data."""
    code = models.CharField(max_length=3, unique=True, db_index=True,
                            help_text="IATA 2-letter or ICAO 3-letter code")
    name = models.CharField(max_length=120)
    logo_url = models.URLField(blank=True)
    country = models.CharField(max_length=60, blank=True)
    is_lcc = models.BooleanField(default=False, help_text="Low-cost carrier flag")
    is_active = models.BooleanField(default=True)
    alliance = models.CharField(max_length=50, blank=True,
                                help_text="Star Alliance / OneWorld / SkyTeam")

    class Meta:
        app_label = 'flights'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"


# ── Airports ──────────────────────────────────────────────────────────

class Airport(TimeStampedModel):
    """Airport with IATA code and geo coordinates."""
    iata_code = models.CharField(max_length=3, unique=True, db_index=True)
    icao_code = models.CharField(max_length=4, blank=True)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, db_index=True)
    country = models.CharField(max_length=60)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    timezone_name = models.CharField(max_length=60, default='Asia/Kolkata')
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'flights'
        indexes = [models.Index(fields=['city', 'is_active'])]

    def __str__(self):
        return f"{self.iata_code} — {self.name}, {self.city}"


# ── Flights ───────────────────────────────────────────────────────────

class Flight(TimeStampedModel):
    """A scheduled flight (may be nonstop or master for multi-leg)."""
    TRIP_ONEWAY = 'oneway'
    TRIP_ROUNDTRIP = 'roundtrip'
    TRIP_MULTICITY = 'multicity'
    TRIP_CHOICES = [
        (TRIP_ONEWAY, 'One Way'),
        (TRIP_ROUNDTRIP, 'Round Trip'),
        (TRIP_MULTICITY, 'Multi-City'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    flight_number = models.CharField(max_length=10, db_index=True)
    airline = models.ForeignKey(Airline, on_delete=models.PROTECT,
                                related_name='flights')
    origin = models.ForeignKey(Airport, on_delete=models.PROTECT,
                               related_name='departures')
    destination = models.ForeignKey(Airport, on_delete=models.PROTECT,
                                    related_name='arrivals')
    departure_datetime = models.DateTimeField(db_index=True)
    arrival_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    stops = models.PositiveIntegerField(default=0)
    trip_type = models.CharField(max_length=10, choices=TRIP_CHOICES,
                                 default=TRIP_ONEWAY)
    aircraft_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    is_codeshare = models.BooleanField(default=False)
    operating_airline = models.ForeignKey(
        Airline, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operated_flights')
    supplier_code = models.CharField(max_length=50, blank=True)

    class Meta:
        app_label = 'flights'
        indexes = [
            models.Index(fields=['origin', 'destination', 'departure_datetime'],
                         name='flight_route_date_idx'),
            models.Index(fields=['airline', 'departure_datetime']),
            models.Index(fields=['flight_number', 'departure_datetime']),
        ]

    def __str__(self):
        return (f"{self.flight_number} {self.origin.iata_code}→"
                f"{self.destination.iata_code} "
                f"{self.departure_datetime:%Y-%m-%d %H:%M}")

    @property
    def duration_display(self):
        h, m = divmod(self.duration_minutes, 60)
        return f"{h}h {m}m"


class FlightLeg(TimeStampedModel):
    """Individual leg of a multi-stop flight itinerary."""
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE,
                               related_name='legs')
    leg_number = models.PositiveIntegerField(default=1)
    origin = models.ForeignKey(Airport, on_delete=models.PROTECT,
                               related_name='+')
    destination = models.ForeignKey(Airport, on_delete=models.PROTECT,
                                    related_name='+')
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    flight_number = models.CharField(max_length=10)
    airline = models.ForeignKey(Airline, on_delete=models.PROTECT,
                                related_name='+')
    aircraft_type = models.CharField(max_length=50, blank=True)
    layover_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'flights'
        ordering = ['flight', 'leg_number']
        unique_together = ('flight', 'leg_number')

    def __str__(self):
        return (f"Leg {self.leg_number}: {self.origin.iata_code}→"
                f"{self.destination.iata_code}")


# ── Fare Classes & Inventory ─────────────────────────────────────────

class FlightFareClass(TimeStampedModel):
    """Fare class with cabin type, seat count, and pricing."""
    CABIN_ECONOMY = 'economy'
    CABIN_PREMIUM_ECONOMY = 'premium_economy'
    CABIN_BUSINESS = 'business'
    CABIN_FIRST = 'first'
    CABIN_CHOICES = [
        (CABIN_ECONOMY, 'Economy'),
        (CABIN_PREMIUM_ECONOMY, 'Premium Economy'),
        (CABIN_BUSINESS, 'Business'),
        (CABIN_FIRST, 'First Class'),
    ]

    flight = models.ForeignKey(Flight, on_delete=models.CASCADE,
                               related_name='fare_classes')
    cabin_type = models.CharField(max_length=20, choices=CABIN_CHOICES,
                                  default=CABIN_ECONOMY)
    fare_class_code = models.CharField(max_length=5)
    base_fare = models.DecimalField(max_digits=12, decimal_places=2)
    taxes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fare = models.DecimalField(max_digits=12, decimal_places=2)
    total_seats = models.PositiveIntegerField(default=0)
    available_seats = models.PositiveIntegerField(default=0)
    is_refundable = models.BooleanField(default=False)
    baggage_allowance_kg = models.PositiveIntegerField(default=15)
    cabin_baggage_kg = models.PositiveIntegerField(default=7)
    meal_included = models.BooleanField(default=False)
    seat_selection_free = models.BooleanField(default=False)
    change_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                     default=Decimal('2500.00'))
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                           default=Decimal('3000.00'))
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'flights'
        unique_together = ('flight', 'fare_class_code')
        indexes = [
            models.Index(fields=['flight', 'cabin_type', 'is_active']),
        ]

    def __str__(self):
        return (f"{self.flight.flight_number} {self.fare_class_code} "
                f"({self.cabin_type})")

    def save(self, *args, **kwargs):
        if not self.total_fare:
            self.total_fare = self.base_fare + self.taxes
        super().save(*args, **kwargs)


class BaggageAllowance(TimeStampedModel):
    """Extra baggage purchase options per fare class."""
    fare_class = models.ForeignKey(FlightFareClass, on_delete=models.CASCADE,
                                   related_name='extra_baggage_options')
    weight_kg = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'flights'
        ordering = ['weight_kg']

    def __str__(self):
        return f"+{self.weight_kg}kg @ ₹{self.price}"


# ── Booking & PNR ────────────────────────────────────────────────────

class FlightBooking(TimeStampedModel):
    """Flight booking with PNR generation and state machine."""
    STATUS_INITIATED = 'initiated'
    STATUS_HOLD = 'hold'
    STATUS_TICKETED = 'ticketed'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_RESCHEDULED = 'rescheduled'
    STATUS_REFUND_PENDING = 'refund_pending'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_HOLD, 'Hold'),
        (STATUS_TICKETED, 'Ticketed'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_RESCHEDULED, 'Rescheduled'),
        (STATUS_REFUND_PENDING, 'Refund Pending'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    VALID_TRANSITIONS = {
        STATUS_INITIATED: {STATUS_HOLD, STATUS_CANCELLED},
        STATUS_HOLD: {STATUS_TICKETED, STATUS_CANCELLED},
        STATUS_TICKETED: {STATUS_CONFIRMED, STATUS_CANCELLED},
        STATUS_CONFIRMED: {STATUS_CANCELLED, STATUS_RESCHEDULED},
        STATUS_RESCHEDULED: {STATUS_CONFIRMED, STATUS_CANCELLED},
        STATUS_CANCELLED: {STATUS_REFUND_PENDING},
        STATUS_REFUND_PENDING: {STATUS_REFUNDED},
        STATUS_REFUNDED: set(),
    }

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    pnr = models.CharField(max_length=10, unique=True, db_index=True)
    public_booking_id = models.CharField(max_length=50, unique=True,
                                         editable=False, db_index=True,
                                         null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True,
                                        null=True, blank=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name='flight_bookings', null=True, blank=True)
    flight = models.ForeignKey(Flight, on_delete=models.PROTECT,
                               related_name='bookings')
    fare_class = models.ForeignKey(FlightFareClass, on_delete=models.PROTECT,
                                   related_name='bookings')
    return_flight = models.ForeignKey(
        Flight, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='return_bookings')
    return_fare_class = models.ForeignKey(
        FlightFareClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='return_bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_INITIATED)
    trip_type = models.CharField(max_length=10, choices=Flight.TRIP_CHOICES,
                                 default=Flight.TRIP_ONEWAY)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                       default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))
    final_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                       default=Decimal('0.00'))
    promo_code = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    ticket_number = models.CharField(max_length=30, blank=True)
    supplier_booking_ref = models.CharField(max_length=100, blank=True)
    special_requests = models.TextField(blank=True)

    class Meta:
        app_label = 'flights'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['pnr']),
            models.Index(fields=['status', 'hold_expires_at']),
        ]

    def __str__(self):
        return f"FlightBooking {self.pnr} ({self.status})"

    def transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status} → {new_status}. "
                f"Allowed: {allowed}")
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        FlightBookingHistory.objects.create(booking=self, status=new_status)

    def save(self, *args, **kwargs):
        if not self.pnr:
            self.pnr = self._generate_pnr()
        if not self.pk and not self.public_booking_id:
            date_str = timezone.now().strftime('%Y%m%d')
            short = str(self.uuid)[:8].upper()
            self.public_booking_id = f"BK-{date_str}-FLT-{short}"
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_pnr():
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        while True:
            pnr = ''.join(random.choices(chars, k=6))
            if not FlightBooking.objects.filter(pnr=pnr).exists():
                return pnr


class FlightBookingHistory(TimeStampedModel):
    """Immutable status change audit trail."""
    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE,
                                related_name='status_history')
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True)

    class Meta:
        app_label = 'flights'
        ordering = ['-created_at']


class FlightPassenger(TimeStampedModel):
    """Passenger manifest for a flight booking."""
    TYPE_ADULT = 'adult'
    TYPE_CHILD = 'child'
    TYPE_INFANT = 'infant'
    TYPE_CHOICES = [
        (TYPE_ADULT, 'Adult'),
        (TYPE_CHILD, 'Child (2-11)'),
        (TYPE_INFANT, 'Infant (0-2)'),
    ]
    TITLE_CHOICES = [
        ('mr', 'Mr'), ('mrs', 'Mrs'), ('ms', 'Ms'), ('mstr', 'Master'),
    ]

    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE,
                                related_name='passengers')
    title = models.CharField(max_length=5, choices=TITLE_CHOICES, default='mr')
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    pax_type = models.CharField(max_length=10, choices=TYPE_CHOICES,
                                default=TYPE_ADULT)
    date_of_birth = models.DateField(null=True, blank=True)
    passport_number = models.CharField(max_length=20, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=60, default='India')
    seat_number = models.CharField(max_length=5, blank=True)
    meal_preference = models.CharField(max_length=30, blank=True)
    extra_baggage_kg = models.PositiveIntegerField(default=0)
    fare_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                      default=Decimal('0.00'))

    class Meta:
        app_label = 'flights'

    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} ({self.pax_type})"


class FlightPriceBreakdown(TimeStampedModel):
    """Detailed fare breakdown for a flight booking."""
    booking = models.OneToOneField(FlightBooking, on_delete=models.CASCADE,
                                   related_name='price_breakdown')
    base_fare = models.DecimalField(max_digits=12, decimal_places=2)
    fuel_surcharge = models.DecimalField(max_digits=10, decimal_places=2,
                                         default=Decimal('0.00'))
    airline_gst = models.DecimalField(max_digits=10, decimal_places=2,
                                      default=Decimal('0.00'))
    passenger_service_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                                default=Decimal('0.00'))
    user_dev_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                       default=Decimal('0.00'))
    cute_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                   default=Decimal('0.00'))
    convenience_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))
    baggage_charges = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))
    meal_charges = models.DecimalField(max_digits=10, decimal_places=2,
                                       default=Decimal('0.00'))
    seat_charges = models.DecimalField(max_digits=10, decimal_places=2,
                                       default=Decimal('0.00'))
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                           default=Decimal('0.00'))
    promo_discount = models.DecimalField(max_digits=10, decimal_places=2,
                                         default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'flights'

    def calculate_total(self):
        self.total_amount = (
            self.base_fare + self.fuel_surcharge + self.airline_gst
            + self.passenger_service_fee + self.user_dev_fee + self.cute_fee
            + self.convenience_fee + self.baggage_charges + self.meal_charges
            + self.seat_charges + self.insurance_amount - self.promo_discount
        )
        return self.total_amount


class FlightCancellationPolicy(TimeStampedModel):
    """Time-tiered cancellation refund rules per fare class."""
    fare_class = models.ForeignKey(FlightFareClass, on_delete=models.CASCADE,
                                   related_name='cancellation_policies')
    hours_before_departure = models.PositiveIntegerField()
    refund_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                           default=Decimal('0.00'))

    class Meta:
        app_label = 'flights'
        ordering = ['-hours_before_departure']

    def __str__(self):
        return (f">{self.hours_before_departure}h: "
                f"{self.refund_percentage}% refund")
