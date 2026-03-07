import builtins
import uuid as _uuid_module
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
from apps.hotels.validators import validate_https_image_url
from apps.core.models import TimeStampedModel

# Import approval models
from apps.hotels.approval_models import AutoApprovalSettings, PendingPropertyChange
from apps.hotels.review_models import Review  # noqa: F401
from apps.hotels.review_fraud import ReviewFraudFlag  # noqa: F401


class Property(TimeStampedModel):
	# UUID for all frontend/API references — numeric PK must never appear in URLs
	uuid = models.UUIDField(default=_uuid_module.uuid4, unique=True, editable=False, db_index=True)
	owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='properties')
	name = models.CharField(max_length=140)
	slug = models.SlugField(unique=True, blank=True, null=True)
	property_type = models.CharField(max_length=80, default='Hotel')
	
	# LOCATION ARCHITECTURE: Hierarchical FKs (not text strings)
	# This enables: geo search, distance sorting, contextual navigation
	city = models.ForeignKey('core.City', on_delete=models.PROTECT, related_name='hotels')
	locality = models.ForeignKey('core.Locality', on_delete=models.SET_NULL, null=True, blank=True, related_name='hotels')
	
	# Legacy fields for backwards compatibility (DEPRECATED - use FKs above)
	city_text = models.CharField(max_length=80, blank=True, help_text="DEPRECATED: Use city FK")
	area = models.CharField(max_length=120, blank=True)
	landmark = models.CharField(max_length=120, blank=True)
	country = models.CharField(max_length=80, default='India')
	address = models.CharField(max_length=200)
	description = models.TextField()
	
	# INTELLIGENCE SIGNALS (what makes cards feel informative)
	rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	review_count = models.IntegerField(default=0, help_text="Total reviews")
	popularity_score = models.IntegerField(default=0, help_text="Booking velocity + search rank")
	star_category = models.IntegerField(
		default=3,
		choices=[(i, f"{i} Star") for i in range(1, 6)],
		help_text="Star rating category (1-5 stars)"
	)
	
	# Geo coordinates (REQUIRED for distance sorting)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	# Google Maps / Places API fields
	place_id = models.CharField(
		max_length=200, blank=True,
		help_text="Google Maps Place ID for autocomplete and map widget"
	)
	formatted_address = models.CharField(
		max_length=500, blank=True,
		help_text="Full formatted address string from Google Places API"
	)
	
	# PRICING: Moved to RoomType model (domain-driven design)
	# Property pricing is now COMPUTED from room types, not stored
	# Legacy fields removed - use @property base_price instead
	
	# BOOKING SIGNALS (displayed on card)
	bookings_today = models.IntegerField(default=0, help_text="Bookings in last 24h")
	bookings_this_week = models.IntegerField(default=0)
	is_trending = models.BooleanField(default=False, help_text="Hot property indicator")

	# PROPERTY TAGS — owner/admin set labels shown on cards (e.g. Couple Friendly, Mountain View)
	tags = models.JSONField(
		default=list, blank=True,
		help_text="List of tag strings e.g. ['Couple Friendly', 'Mountain View', 'Pool View']"
	)
	
	# POLICY SIGNALS (filter criteria)
	has_free_cancellation = models.BooleanField(default=True)
	cancellation_hours = models.IntegerField(default=24, help_text="Free cancellation window")
	pay_at_hotel = models.BooleanField(
		default=False,
		help_text="Allow guests to pay at hotel (no upfront payment required)"
	)
	
	# ==========================================
	# PHASE 4-6: VENDOR & COMMISSION CONTROL (NEW)
	# ==========================================
	status = models.CharField(
		max_length=20,
		choices=[
			('pending', 'Pending Approval'),
			('approved', 'Approved'),
			('rejected', 'Rejected'),
			('suspended', 'Suspended'),
		],
		default='pending',
		help_text="Approval status by admin"
	)
	
	commission_percentage = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=10.00,
		help_text="Commission percentage owed to platform on each booking"
	)
	
	agreement_file = models.FileField(
		upload_to='agreements/',
		null=True,
		blank=True,
		help_text="Auto-generated agreement PDF"
	)
	
	agreement_signed = models.BooleanField(
		default=False,
		help_text="Owner has accepted the agreement"
	)
	
	def get_distance_from(self, lat, lng):
		"""Calculate distance from given coordinates (km)"""
		from math import radians, cos, sin, asin, sqrt
		
		# Haversine formula
		lon1, lat1, lon2, lat2 = map(radians, [float(self.longitude), float(self.latitude), lng, lat])
		dlon = lon2 - lon1
		dlat = lat2 - lat1
		a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
		c = 2 * asin(sqrt(a))
		km = 6371 * c  # Earth radius in km
		return round(km, 1)
	
	@property
	def base_price(self):
		"""
		COMPUTED PROPERTY: Returns minimum room price.

		PERFORMANCE WARNING: This property fires one SQL query per call.
		In list views, always use the `min_room_price` annotation from
		ota_visible_properties() instead of accessing this property.

		This property exists only for single-object detail views.
		"""
		# Short-circuit: if annotated value already attached, use it (zero queries)
		if hasattr(self, 'min_room_price') and self.min_room_price is not None:
			return self.min_room_price
		from django.db.models import Min
		min_price = self.room_types.aggregate(Min('base_price'))['base_price__min']
		return min_price if min_price is not None else 0
	
	@property
	def discount_price(self):
		"""DEPRECATED: Use RoomType pricing with date-based RoomInventory"""
		return None
	
	@property
	def dynamic_price(self):
		"""DEPRECATED: Use RoomType pricing with date-based RoomInventory"""
		return None

	def clean(self):
		"""Validation firewall: reject invalid ratings"""
		if self.rating < 0 or self.rating > 5:
			raise ValidationError({'rating': 'Rating must be between 0 and 5'})

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)[:200]
		self.full_clean()
		super().save(*args, **kwargs)

	def __str__(self):
		return self.name

	class Meta:
		# Composite index for the canonical public listing query:
		# .filter(status='approved', agreement_signed=True)
		indexes = [
			models.Index(
				fields=['status', 'agreement_signed'],
				name='property_public_listing_idx',
			),
			models.Index(fields=['status'], name='property_status_idx'),
			models.Index(fields=['city'], name='property_city_fk_idx'),
			models.Index(fields=['rating'], name='property_rating_idx'),
			models.Index(fields=['is_trending'], name='property_trending_idx'),
			models.Index(fields=['has_free_cancellation'], name='property_free_cancel_idx'),
			models.Index(fields=['property_type'], name='property_type_idx'),
			# For sorting by popularity (bookings_today + updated_at)
			models.Index(fields=['-bookings_today', '-updated_at'], name='property_popularity_idx'),
			# For distance sorting and map viewport queries
			models.Index(fields=['latitude', 'longitude'], name='property_lat_lng_idx'),
		]


class PropertyImage(TimeStampedModel):
	"""Property images with featured flag"""
	property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
	image = models.ImageField(upload_to='hotels/', blank=True, null=True)
	image_url = models.URLField(blank=True, null=True)
	caption = models.CharField(max_length=200, blank=True)
	is_featured = models.BooleanField(default=False)
	display_order = models.IntegerField(default=0)

	class Meta:
		ordering = ['-is_featured', 'display_order']

	def clean(self):
		"""Validate image URL has proper extension or image upload present."""
		if not self.image and not self.image_url:
			raise ValidationError({'image_url': 'Provide an image upload or image URL.'})
		if self.image_url:
			validate_https_image_url(self.image_url)

	def save(self, *args, **kwargs):
		self.full_clean()
		super().save(*args, **kwargs)
		if self.is_featured:
			PropertyImage.objects.filter(property=self.property, is_featured=True).exclude(pk=self.pk).update(is_featured=False)

	def __str__(self):
		return f"{self.property.name} - Image {self.id}"

	@builtins.property
	def resolved_url(self):
		"""Prefer uploaded image, fallback to URL string."""
		if self.image and hasattr(self.image, 'url'):
			return self.image.url
		return self.image_url or ""


# PropertyOffer model moved to apps.offers app for better organization
# Use: from apps.offers.models import Offer, PropertyOffer


class RatingAggregate(TimeStampedModel):
	"""Aggregated ratings breakdown (like Goibibo's rating cards)"""
	property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='rating_breakdown')
	cleanliness = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	service = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	location = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	amenities = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	value_for_money = models.DecimalField(max_digits=3, decimal_places=1, default=0)
	total_reviews = models.IntegerField(default=0)

	def clean(self):
		"""Validate all ratings are between 0 and 5"""
		rating_fields = ['cleanliness', 'service', 'location', 'amenities', 'value_for_money']
		errors = {}
		for field in rating_fields:
			value = getattr(self, field)
			if value < 0 or value > 5:
				errors[field] = f'{field.replace("_", " ").title()} rating must be between 0 and 5'
		if errors:
			raise ValidationError(errors)
		if self.total_reviews < 0:
			raise ValidationError({'total_reviews': 'Total reviews cannot be negative'})

	def save(self, *args, **kwargs):
		self.full_clean()
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.property.name} - Rating Breakdown"


class Category(TimeStampedModel):
	"""Property categories for filtering and destination themes"""
	name = models.CharField(max_length=100, unique=True, help_text="e.g., Beach Vacations, Mountains Calling")
	slug = models.SlugField(unique=True)
	description = models.TextField(blank=True)
	icon = models.CharField(max_length=40, blank=True)
	image = models.ImageField(
		upload_to='destination_categories/', 
		blank=True, null=True,
		help_text="Category hero image for landing page"
	)
	display_order = models.IntegerField(default=0, help_text="Lower numbers appear first")

	class Meta:
		verbose_name_plural = 'Categories'
		ordering = ['display_order', 'name']

	def __str__(self):
		return self.name
	
	def get_properties(self):
		"""Get properties tagged with this category"""
		return Property.objects.filter(
			categories__category=self,
			status='approved',
			agreement_signed=True
		).distinct()


class PropertyCategory(TimeStampedModel):
	"""Many-to-many relationship for property categories"""
	property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='categories')
	category = models.ForeignKey(Category, on_delete=models.CASCADE)

	class Meta:
		unique_together = ['property', 'category']
		verbose_name_plural = 'Property Categories'

	def __str__(self):
		return f"{self.property.name} - {self.category.name}"

class PropertyPolicy(TimeStampedModel):
	"""Property policies (cancellation, check-in, etc)"""
	property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='policies')
	title = models.CharField(max_length=120)
	description = models.TextField()

	def __str__(self):
		return f"{self.property.name} - {self.title}"


class PropertyAmenity(TimeStampedModel):
	"""Property amenities with optional icons"""
	property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='amenities')
	name = models.CharField(max_length=120)
	icon = models.CharField(max_length=40, blank=True)

	class Meta:
		verbose_name_plural = 'Property Amenities'

	def __str__(self):
		return f"{self.property.name} - {self.name}"


class RecentSearch(models.Model):
	"""Track recent hotel searches for personalization"""
	
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
		null=True, blank=True, related_name='hotel_searches'
	)
	session_key = models.CharField(
		max_length=100, blank=True, 
		help_text="Session ID for anonymous users"
	)
	
	# Search parameters
	search_text = models.CharField(max_length=255, default='', blank=True, help_text="Location search text")
	checkin = models.DateField(null=True, blank=True)
	checkout = models.DateField(null=True, blank=True)
	adults = models.IntegerField(default=1)
	children = models.IntegerField(default=0)
	rooms = models.IntegerField(default=1)
	
	# Metadata
	created_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['-created_at']
		verbose_name = "Recent Hotel Search"
		verbose_name_plural = "Recent Hotel Searches"
		indexes = [
			models.Index(fields=['-created_at']),
			models.Index(fields=['user', '-created_at']),
			models.Index(fields=['session_key', '-created_at']),
		]
	
	def __str__(self):
		return f"{self.search_text or 'Any'} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"