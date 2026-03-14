"""
Activities & Experiences — tours, attractions, events, adventure sports.

Models:
  ActivityCategory, Activity, ActivityImage, ActivityTimeSlot,
  ActivityBooking, ActivityBookingParticipant, ActivityPriceBreakdown,
  ActivityReview, ActivityCancellationPolicy
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel


# ── Categories ────────────────────────────────────────────────────────

class ActivityCategory(TimeStampedModel):
    """Top-level categories: Sightseeing, Adventure, Culture, Food, etc."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name or CSS class")
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'activities'
        verbose_name_plural = 'Activity Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


# ── Activity ──────────────────────────────────────────────────────────

class Activity(TimeStampedModel):
    """An experience, tour, or attraction available for booking."""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'), ('moderate', 'Moderate'),
        ('challenging', 'Challenging'), ('extreme', 'Extreme'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=250, db_index=True)
    slug = models.SlugField(max_length=260, unique=True)
    category = models.ForeignKey(
        ActivityCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activities')
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='supplied_activities',
        help_text="Activity operator / supplier")
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    highlights = models.JSONField(default=list, blank=True,
                                  help_text="List of highlight strings")
    inclusions = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)

    # ── Location ─────────────────
    city = models.CharField(max_length=100, db_index=True)
    address = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # ── Logistics ────────────────
    duration_minutes = models.PositiveIntegerField(
        help_text="Duration of activity in minutes")
    max_participants = models.PositiveIntegerField(default=20)
    min_participants = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(max_length=15, choices=DIFFICULTY_CHOICES, default='easy')
    min_age = models.PositiveIntegerField(default=0)
    languages = models.JSONField(default=list, blank=True,
                                 help_text='["English", "Hindi"]')

    # ── Pricing ──────────────────
    adult_price = models.DecimalField(max_digits=10, decimal_places=2,
                                      validators=[MinValueValidator(Decimal('0.01'))])
    child_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    group_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        help_text="Discount % for groups >= min_group_size")
    min_group_size = models.PositiveIntegerField(default=5)

    # ── Flags ────────────────────
    is_instant_confirmation = models.BooleanField(default=True)
    is_free_cancellation = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    # ── Ratings (denormalized for fast listing) ──
    avg_rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0'))
    review_count = models.PositiveIntegerField(default=0)

    supplier_code = models.CharField(max_length=100, blank=True, db_index=True,
                                     help_text="External supplier ref")

    class Meta:
        app_label = 'activities'
        ordering = ['-is_featured', '-avg_rating']
        indexes = [
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['-avg_rating', '-review_count']),
        ]

    def __str__(self):
        return self.title

    @property
    def duration_display(self):
        h, m = divmod(self.duration_minutes, 60)
        if h and m:
            return f"{h}h {m}m"
        return f"{h}h" if h else f"{m}m"


# ── Images ────────────────────────────────────────────────────────────

class ActivityImage(TimeStampedModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='activities/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'activities'
        ordering = ['sort_order']

    def __str__(self):
        return f"Image for {self.activity.title}"


# ── Time Slots ────────────────────────────────────────────────────────

class ActivityTimeSlot(TimeStampedModel):
    """A bookable slot for an activity on a specific date/time."""
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='time_slots')
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_capacity = models.PositiveIntegerField()
    booked_count = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Override adult price for this slot (peak pricing)")

    class Meta:
        app_label = 'activities'
        unique_together = ('activity', 'date', 'start_time')
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['activity', 'date']),
        ]

    def __str__(self):
        return f"{self.activity.title} — {self.date} {self.start_time}"

    @property
    def available_spots(self):
        return max(0, self.max_capacity - self.booked_count)

    @property
    def effective_price(self):
        return self.price_override or self.activity.adult_price


# ── Booking ───────────────────────────────────────────────────────────

class ActivityBooking(TimeStampedModel):
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refund_pending', 'Refund Pending'),
        ('refunded', 'Refunded'),
        ('no_show', 'No Show'),
    ]

    VALID_TRANSITIONS = {
        'initiated': ['confirmed', 'cancelled'],
        'confirmed': ['completed', 'cancelled', 'no_show'],
        'completed': [],
        'cancelled': ['refund_pending'],
        'refund_pending': ['refunded'],
        'refunded': [],
        'no_show': [],
    }

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    booking_ref = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name='activity_bookings')
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, related_name='bookings')
    time_slot = models.ForeignKey(ActivityTimeSlot, on_delete=models.PROTECT,
                                  related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')

    adults = models.PositiveIntegerField(default=1)
    children = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    promo_code = models.CharField(max_length=50, blank=True)

    contact_name = models.CharField(max_length=150)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    special_requests = models.TextField(blank=True)

    supplier_booking_ref = models.CharField(max_length=100, blank=True)

    class Meta:
        app_label = 'activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['activity', 'status']),
        ]

    def __str__(self):
        return f"{self.booking_ref} — {self.activity.title}"

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            date_str = timezone.now().strftime('%Y%m%d')
            short = str(self.uuid)[:6].upper()
            self.booking_ref = f"ACT-{date_str}-{short}"
        super().save(*args, **kwargs)

    def transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{self.status}' to '{new_status}'")
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])


# ── Booking Participants ──────────────────────────────────────────────

class ActivityBookingParticipant(TimeStampedModel):
    PAX_CHOICES = [('adult', 'Adult'), ('child', 'Child')]

    booking = models.ForeignKey(ActivityBooking, on_delete=models.CASCADE,
                                related_name='participants')
    name = models.CharField(max_length=150)
    pax_type = models.CharField(max_length=10, choices=PAX_CHOICES, default='adult')
    age = models.PositiveIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)

    class Meta:
        app_label = 'activities'

    def __str__(self):
        return f"{self.name} ({self.pax_type})"


# ── Price Breakdown ───────────────────────────────────────────────────

class ActivityPriceBreakdown(TimeStampedModel):
    booking = models.OneToOneField(ActivityBooking, on_delete=models.CASCADE,
                                   related_name='price_breakdown')
    adult_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    child_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    group_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    gst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    promo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'activities'

    def __str__(self):
        return f"Breakdown for {self.booking.booking_ref}"


# ── Reviews ───────────────────────────────────────────────────────────

class ActivityReview(TimeStampedModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='activity_reviews')
    booking = models.OneToOneField(ActivityBooking, on_delete=models.SET_NULL,
                                   null=True, blank=True)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=150, blank=True)
    comment = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False,
                                      help_text="Verified via completed booking")

    class Meta:
        app_label = 'activities'
        unique_together = ('activity', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.activity.title} ({self.rating}★)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update denormalized rating on Activity
        from django.db.models import Avg, Count
        stats = self.activity.reviews.aggregate(
            avg=Avg('rating'), cnt=Count('id'))
        Activity.objects.filter(pk=self.activity_id).update(
            avg_rating=stats['avg'] or 0,
            review_count=stats['cnt'] or 0)


# ── Cancellation Policy ──────────────────────────────────────────────

class ActivityCancellationPolicy(TimeStampedModel):
    """Tiered cancellation policy for an activity."""
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE,
                                 related_name='cancellation_policies')
    hours_before = models.PositiveIntegerField(
        help_text="Hours before activity start")
    refund_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    class Meta:
        app_label = 'activities'
        ordering = ['-hours_before']

    def __str__(self):
        return f"{self.activity.title}: >{self.hours_before}h → {self.refund_percentage}%"
