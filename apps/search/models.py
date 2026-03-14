from django.db import models
from django.utils.text import slugify
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from apps.core.models import TimeStampedModel


class SearchIndex(models.Model):
    TYPE_CITY = "city"
    TYPE_AREA = "area"
    TYPE_PROPERTY = "property"

    TYPE_CHOICES = [
        (TYPE_CITY, "City"),
        (TYPE_AREA, "Area"),
        (TYPE_PROPERTY, "Property"),
    ]

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    property_count = models.IntegerField(null=True, blank=True)
    slug = models.SlugField(max_length=220)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["type", "name"]),
            models.Index(fields=["slug"]),
        ]
        unique_together = ["type", "slug"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type}: {self.name}"


# ============================================================================
# PHASE 8: DENORMALIZED PROPERTY SEARCH INDEX
# ============================================================================

class PropertySearchIndex(TimeStampedModel):
    """
    Denormalized search index for fast property queries.

    Populated by a management command / Celery task that reads from
    Property, RoomType, RatingAggregate, and InventoryCalendar.

    Query pattern: filter by city, price range, rating, amenities, availability.
    Single-table scan — no JOINs needed for search results page.
    """
    property = models.OneToOneField(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='search_index_entry',
    )

    # Denormalized fields from Property
    property_name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, db_index=True)
    property_type = models.CharField(max_length=80, db_index=True)
    city_id = models.IntegerField(db_index=True)
    city_name = models.CharField(max_length=100, db_index=True)
    locality_name = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    star_category = models.IntegerField(default=3)

    # Pricing (computed from cheapest room type)
    price_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cheapest room type base price",
    )
    price_max = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Most expensive room type base price",
    )

    # Ratings
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    review_count = models.IntegerField(default=0)
    review_score = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        help_text="Weighted review score for ranking",
    )

    # Signals
    popularity_score = models.IntegerField(default=0)
    is_trending = models.BooleanField(default=False, db_index=True)
    has_free_cancellation = models.BooleanField(default=True, db_index=True)
    pay_at_hotel = models.BooleanField(default=False, db_index=True)

    # Amenities (JSON array for filtering)
    amenities = models.JSONField(
        default=list, blank=True,
        help_text="List of amenity names for faceted search",
    )
    tags = models.JSONField(
        default=list, blank=True,
        help_text="Property tags (Couple Friendly, Mountain View, etc.)",
    )

    # Images
    featured_image_url = models.URLField(blank=True)

    # Availability summary (updated by daily sync)
    has_availability = models.BooleanField(
        default=True, db_index=True,
        help_text="Has at least one room available in next 30 days",
    )
    available_rooms = models.IntegerField(
        default=0,
        help_text="Total rooms available in next 30 days (for urgency signals)",
    )

    # Pre-computed ranking score (persisted to avoid runtime re-computation)
    ranking_score = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        db_index=True,
        help_text="Pre-computed ranking score from enhanced_ranking engine",
    )

    # ── Conversion Signals (Goibibo-parity) ──────────────────────
    rooms_left = models.IntegerField(
        default=0, help_text="Rooms left for nearest check-in date (urgency)",
    )
    recent_bookings = models.IntegerField(
        default=0, help_text="Bookings in last 24h (social proof)",
    )
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Current discount % vs rack rate",
    )
    rack_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Rack/strikethrough price for discount display",
    )
    deal_score = models.IntegerField(
        default=0, help_text="0-100 deal quality score",
    )
    has_breakfast = models.BooleanField(
        default=False, db_index=True,
        help_text="At least one room type includes breakfast",
    )
    cashback_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Max cashback available",
    )
    distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Distance from city center in km",
    )

    # ── CTR / Engagement Tracking (S1: Search ranking signals) ────
    total_impressions = models.PositiveIntegerField(
        default=0, help_text="Total search result impressions",
    )
    total_clicks = models.PositiveIntegerField(
        default=0, help_text="Total clicks from search results",
    )
    click_through_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        db_index=True,
        help_text="CTR = clicks / impressions (updated by Celery task)",
    )
    total_views = models.PositiveIntegerField(
        default=0, help_text="Total detail page views",
    )
    total_bookings = models.PositiveIntegerField(
        default=0, help_text="Total confirmed bookings (for conversion rate)",
    )

    # ── Reliability / Quality Signals ─────────────────────────────────
    cancellation_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        db_index=True,
        help_text="Cancellation rate = cancellations / total bookings (lower is better)",
    )
    availability_reliability = models.DecimalField(
        max_digits=5, decimal_places=4, default=1,
        help_text="How often rooms are actually available when listed (0-1)",
    )
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=15,
        help_text="OTA commission % for margin scoring",
    )

    # S11: Full-text search vector (populated by Celery task / signal)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        app_label = 'search'
        indexes = [
            models.Index(fields=['city_id', 'price_min']),
            models.Index(fields=['city_name', 'rating']),
            models.Index(fields=['price_min', 'rating']),
            models.Index(fields=['popularity_score', '-rating']),
            models.Index(fields=['-ranking_score', 'city_id']),
            models.Index(fields=['is_trending', '-popularity_score']),
            models.Index(fields=['has_free_cancellation', 'price_min']),
            models.Index(fields=['star_category', 'price_min']),
            models.Index(fields=['latitude', 'longitude']),
            GinIndex(fields=['search_vector'], name='search_fts_gin_idx'),
            GinIndex(fields=['amenities'], name='search_amenities_gin_idx'),
            GinIndex(fields=['tags'], name='search_tags_gin_idx'),
        ]

    def __str__(self):
        return f"SearchIdx: {self.property_name} ({self.city_name}) ₹{self.price_min}"


# No models in search app - uses other app models
class SearchResult:
    """
    Unified search result object (Step 5: HARD STABILIZATION).
    Replaces tuple returns from search operations.
    Provides consistent interface across all search domains.
    
    Usage:
        result = SearchResult(
            result_id=1,
            title="Hotel Name",
            description="Description",
            result_type='hotel',
            price=5000,
            rating=4.5
        )
    """
    
    def __init__(self, result_id, title, description, result_type, 
                 price=None, rating=None, location=None, details=None, metadata=None):
        self.id = result_id
        self.title = title
        self.description = description
        self.type = result_type  # 'hotel', 'package', 'bus', 'cab', etc.
        self.price = price
        self.rating = rating
        self.location = location
        self.details = details or {}
        self.metadata = metadata or {}
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'price': self.price,
            'rating': self.rating,
            'location': self.location,
            'details': self.details,
            'metadata': self.metadata,
        }
    
    def to_json(self):
        """Serialize to JSON-compatible dict."""
        import json
        return json.dumps(self.to_dict())
    
    def __repr__(self):
        return f"<SearchResult: {self.type} | {self.title}>"
    
    def __str__(self):
        return f"{self.title} ({self.type})"
    
    @classmethod
    def from_hotel(cls, hotel_obj):
        """Create SearchResult from Hotel model."""
        return cls(
            result_id=hotel_obj.id,
            title=hotel_obj.name,
            description=hotel_obj.description[:200] if hotel_obj.description else '',
            result_type='hotel',
            price=float(hotel_obj.base_price) if hotel_obj.base_price else None,
            rating=float(hotel_obj.rating) if hotel_obj.rating else None,
            location=getattr(hotel_obj.city, 'name', None),
            details={
                'property_type': hotel_obj.property_type,
                'address': hotel_obj.address,
            },
            metadata={
                'slug': hotel_obj.slug,
                'images': list(hotel_obj.images.values_list('image_url', flat=True))[:3],
            }
        )


# Import personalization model so Django discovers it for migrations
from apps.search.personalization import UserSearchProfile  # noqa: F401, E402