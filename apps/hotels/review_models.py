"""
Review & Rating Models — Guest reviews for properties.

- One review per booking (enforce via unique_together)
- Only CONFIRMED/COMPLETED bookings can be reviewed
- Sub-ratings: cleanliness, service, location, amenities, value_for_money
- Auto-updates Property.rating and Property.review_count on save
- Auto-updates RatingAggregate breakdowns
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Avg, Count

from apps.core.models import TimeStampedModel

# Save reference — the Review model has a field named 'property' that shadows the builtin
_property = property


class Review(TimeStampedModel):
    """
    Individual guest review for a property, linked to a booking.
    """
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Moderation'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    booking = models.OneToOneField(
        'booking.Booking', on_delete=models.PROTECT,
        related_name='review',
        help_text='One review per booking',
    )
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True,
        related_name='reviews',
    )

    # Overall rating (1.0 – 5.0)
    overall_rating = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )

    # Sub-ratings (1.0 – 5.0 each)
    cleanliness = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )
    service = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )
    location = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )
    amenities = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )
    value_for_money = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
    )

    # Text review
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(max_length=2000)

    @_property
    def staff(self):
        """Alias: 'staff' maps to 'service' rating for API compatibility."""
        return self.service

    @staff.setter
    def staff(self, value):
        self.service = value

    # Traveller type
    traveller_type = models.CharField(
        max_length=20,
        choices=[
            ('solo', 'Solo'),
            ('couple', 'Couple'),
            ('family', 'Family'),
            ('business', 'Business'),
            ('group', 'Group'),
        ],
        blank=True,
    )

    # Moderation
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    moderation_note = models.TextField(blank=True)

    # Owner response
    owner_response = models.TextField(blank=True)
    owner_responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'hotels'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property', 'status', '-created_at'], name='review_prop_status_idx'),
            models.Index(fields=['user', '-created_at'], name='review_user_idx'),
        ]

    def __str__(self):
        return f"Review by {self.user.email} for {self.property.name} ({self.overall_rating}★)"

    def clean(self):
        from apps.booking.models import Booking
        # Ensure booking is completed/confirmed/checked_out
        if self.booking:
            reviewable_statuses = (
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_CHECKED_OUT,
                Booking.STATUS_SETTLED,
            )
            if self.booking.status not in reviewable_statuses:
                raise ValidationError('Can only review confirmed or completed bookings.')
            if self.booking.property_id != self.property_id:
                raise ValidationError('Booking does not match the property.')
            if self.booking.user_id != self.user_id:
                raise ValidationError('You can only review your own bookings.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Auto-update property rating aggregate
        if self.status == self.STATUS_APPROVED:
            self._update_property_rating()

    @transaction.atomic
    def _update_property_rating(self):
        """Recalculate Property.rating and RatingAggregate from all approved reviews."""
        from apps.hotels.models import Property, RatingAggregate

        approved = Review.objects.filter(
            property=self.property, status=self.STATUS_APPROVED,
        )

        agg = approved.aggregate(
            avg_overall=Avg('overall_rating'),
            avg_cleanliness=Avg('cleanliness'),
            avg_service=Avg('service'),
            avg_location=Avg('location'),
            avg_amenities=Avg('amenities'),
            avg_value=Avg('value_for_money'),
            count=Count('id'),
        )

        # Update Property
        prop = Property.objects.select_for_update().get(pk=self.property_id)
        prop.rating = Decimal(str(round(agg['avg_overall'] or 0, 1)))
        prop.review_count = agg['count'] or 0
        prop.save(update_fields=['rating', 'review_count', 'updated_at'])

        # Update or create RatingAggregate
        rating_agg, _ = RatingAggregate.objects.get_or_create(property=self.property)
        rating_agg.cleanliness = Decimal(str(round(agg['avg_cleanliness'] or 0, 1)))
        rating_agg.service = Decimal(str(round(agg['avg_service'] or 0, 1)))
        rating_agg.location = Decimal(str(round(agg['avg_location'] or 0, 1)))
        rating_agg.amenities = Decimal(str(round(agg['avg_amenities'] or 0, 1)))
        rating_agg.value_for_money = Decimal(str(round(agg['avg_value'] or 0, 1)))
        rating_agg.total_reviews = agg['count'] or 0
        rating_agg.save()


class ReviewPhoto(TimeStampedModel):
    """User-uploaded photo attached to a review (max 5 per review)."""
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE,
        related_name='photos',
    )
    image = models.ImageField(upload_to='review_photos/%Y/%m/')
    caption = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'hotels'
        ordering = ['display_order']

    def __str__(self):
        return f"Photo for review #{self.review_id}"

    def clean(self):
        if self.review_id:
            existing = ReviewPhoto.objects.filter(review=self.review).exclude(pk=self.pk).count()
            if existing >= 5:
                from django.core.exceptions import ValidationError
                raise ValidationError('Maximum 5 photos per review.')


class ReviewHelpfulness(TimeStampedModel):
    """Tracks helpful / not-helpful votes on reviews."""
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE,
        related_name='helpfulness_votes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
    )
    is_helpful = models.BooleanField(
        help_text="True = helpful, False = not helpful",
    )

    class Meta:
        app_label = 'hotels'
        unique_together = ('review', 'user')
        indexes = [
            models.Index(fields=['review', 'is_helpful'], name='review_helpful_idx'),
        ]

    def __str__(self):
        vote = 'helpful' if self.is_helpful else 'not helpful'
        return f"User {self.user_id} marked review #{self.review_id} as {vote}"
