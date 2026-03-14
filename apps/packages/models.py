from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.text import slugify
import uuid
from apps.core.models import TimeStampedModel


class PackageCategory(TimeStampedModel):
	name = models.CharField(max_length=120, unique=True)
	slug = models.SlugField(unique=True, blank=True)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name_plural = "Package Categories"

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)[:200]
		super().save(*args, **kwargs)

	def __str__(self):
		return self.name


class Package(TimeStampedModel):
	EASY = "easy"
	MODERATE = "moderate"
	CHALLENGING = "challenging"

	DIFFICULTY_CHOICES = [
		(EASY, "Easy"),
		(MODERATE, "Moderate"),
		(CHALLENGING, "Challenging"),
	]

	provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	category = models.ForeignKey(PackageCategory, on_delete=models.SET_NULL, null=True, blank=True)
	name = models.CharField(max_length=160)
	slug = models.SlugField(unique=True, blank=True)
	description = models.TextField()
	destination = models.CharField(max_length=120)
	duration_days = models.PositiveIntegerField(default=3)
	base_price = models.DecimalField(max_digits=12, decimal_places=2)
	rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.3)
	review_count = models.PositiveIntegerField(default=0)
	image_url = models.URLField(blank=True)
	inclusions = models.TextField(blank=True)
	exclusions = models.TextField(blank=True)
	max_group_size = models.PositiveIntegerField(default=20)
	difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default=MODERATE)
	hotel_included = models.BooleanField(default=True)
	meals_included = models.BooleanField(default=True)
	transport_included = models.BooleanField(default=True)
	guide_included = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["-created_at"]

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)[:200]
		super().save(*args, **kwargs)

	@property
	def duration(self):
		return self.duration_days

	@property
	def price(self):
		return self.base_price

	def __str__(self):
		return self.name


class PackageImage(TimeStampedModel):
	package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="images")
	image_url = models.URLField()
	is_featured = models.BooleanField(default=False)
	display_order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ["-is_featured", "display_order"]

	def __str__(self):
		return f"{self.package.name} image"


class PackageItinerary(TimeStampedModel):
	MEALS_NONE = "N"
	MEALS_BREAKFAST = "B"
	MEALS_LUNCH = "L"
	MEALS_DINNER = "D"
	MEALS_ALL = "BLD"

	MEALS_CHOICES = [
		(MEALS_NONE, "No meals"),
		(MEALS_BREAKFAST, "Breakfast"),
		(MEALS_LUNCH, "Lunch"),
		(MEALS_DINNER, "Dinner"),
		(MEALS_ALL, "All meals"),
	]

	package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="itinerary")
	day_number = models.PositiveIntegerField()
	title = models.CharField(max_length=160)
	description = models.TextField()
	accommodation = models.CharField(max_length=160, blank=True)
	meals_included = models.CharField(max_length=5, choices=MEALS_CHOICES, default=MEALS_NONE)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["day_number"]

	def __str__(self):
		return f"{self.package.name} - Day {self.day_number}"


# ── Seasonal Pricing ──────────────────────────────────────────────────

class PackageSeasonalPrice(TimeStampedModel):
	"""Per-season price overrides for packages.

	Allows different pricing for peak/off-peak/festival seasons.
	Falls back to Package.base_price when no seasonal price matches.
	"""
	SEASON_CHOICES = [
		('peak', 'Peak Season'),
		('offpeak', 'Off-Peak Season'),
		('festival', 'Festival Season'),
		('monsoon', 'Monsoon Discount'),
	]

	package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='seasonal_prices')
	season_name = models.CharField(max_length=20, choices=SEASON_CHOICES)
	start_date = models.DateField()
	end_date = models.DateField()
	adult_price = models.DecimalField(max_digits=12, decimal_places=2)
	child_price = models.DecimalField(
		max_digits=12, decimal_places=2, default=0,
		help_text="Price per child (0 = free)",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['start_date']
		indexes = [
			models.Index(fields=['package', 'start_date', 'end_date']),
		]

	def __str__(self):
		return f"{self.package.name} — {self.get_season_name_display()} ₹{self.adult_price}"

	@classmethod
	def get_price_for_date(cls, package, travel_date):
		"""Get the applicable seasonal price for a given date, or base_price."""
		seasonal = cls.objects.filter(
			package=package,
			is_active=True,
			start_date__lte=travel_date,
			end_date__gte=travel_date,
		).first()

		if seasonal:
			return {
				'adult_price': seasonal.adult_price,
				'child_price': seasonal.child_price,
				'season': seasonal.get_season_name_display(),
			}
		return {
			'adult_price': package.base_price,
			'child_price': package.base_price * 0,  # Default: no child pricing
			'season': 'Regular',
		}


# ── Package Departure Dates / Availability ────────────────────────────

class PackageDeparture(TimeStampedModel):
	"""Fixed departure dates with capacity tracking for package tours."""
	package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='departures')
	departure_date = models.DateField()
	return_date = models.DateField()
	total_slots = models.PositiveIntegerField(default=20)
	booked_slots = models.PositiveIntegerField(default=0)
	is_guaranteed = models.BooleanField(
		default=False, help_text="Departure guaranteed regardless of bookings",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		unique_together = ('package', 'departure_date')
		ordering = ['departure_date']

	@property
	def available_slots(self):
		return max(0, self.total_slots - self.booked_slots)

	@property
	def is_sold_out(self):
		return self.available_slots <= 0

	def __str__(self):
		return f"{self.package.name} — {self.departure_date} ({self.available_slots} slots)"


# ── Package Booking ───────────────────────────────────────────────────

class PackageBooking(TimeStampedModel):
	"""Transactional booking model for travel packages.

	Tracks: user, package, departure, travelers, pricing, status.
	Supports group discounts and seasonal pricing.
	"""
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('confirmed', 'Confirmed'),
		('partially_paid', 'Partially Paid'),
		('completed', 'Completed'),
		('cancelled', 'Cancelled'),
		('refunded', 'Refunded'),
	]

	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	public_booking_id = models.CharField(
		max_length=50, unique=True, editable=False,
		db_index=True, null=True, blank=True,
	)
	idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
		related_name='package_bookings',
	)
	package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name='bookings')
	departure = models.ForeignKey(
		PackageDeparture, on_delete=models.SET_NULL, null=True, blank=True,
		related_name='bookings',
	)

	# Traveler counts
	adults = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
	children = models.PositiveIntegerField(default=0)

	# Pricing (snapshot at booking time)
	adult_price = models.DecimalField(max_digits=12, decimal_places=2)
	child_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	subtotal = models.DecimalField(max_digits=12, decimal_places=2)
	group_discount = models.DecimalField(
		max_digits=12, decimal_places=2, default=0,
		help_text="Discount for group bookings (5+ travelers)",
	)
	promo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2)
	promo_code = models.CharField(max_length=30, blank=True)

	# Status
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

	# Notes
	special_requests = models.TextField(blank=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['user', 'status']),
			models.Index(fields=['package', 'status']),
		]

	def save(self, *args, **kwargs):
		if not self.pk and not self.public_booking_id:
			date_str = timezone.now().strftime('%Y%m%d')
			short_id = str(self.uuid)[:8].upper()
			self.public_booking_id = f"BK-{date_str}-PKG-{short_id}"

		# Compute pricing
		if self.adult_price and not self.subtotal:
			self.calculate_total()

		super().save(*args, **kwargs)

	def calculate_total(self):
		"""Compute total with group discount and GST."""
		from decimal import Decimal
		adult_cost = Decimal(str(self.adult_price)) * self.adults
		child_cost = Decimal(str(self.child_price or 0)) * self.children
		self.subtotal = adult_cost + child_cost

		# Group discount: 5% off for 5+ travelers, 10% for 10+
		total_travelers = self.adults + self.children
		if total_travelers >= 10:
			self.group_discount = (self.subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
		elif total_travelers >= 5:
			self.group_discount = (self.subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
		else:
			self.group_discount = Decimal('0')

		after_discount = self.subtotal - self.group_discount - Decimal(str(self.promo_discount or 0))
		self.gst = (after_discount * Decimal('0.05')).quantize(Decimal('0.01'))
		self.total_amount = (after_discount + self.gst).quantize(Decimal('0.01'))
		return self.total_amount

	def __str__(self):
		return f"Package Booking {self.public_booking_id or self.uuid}"


class PackageBookingTraveler(TimeStampedModel):
	"""Individual traveler details for a package booking."""
	TRAVELER_TYPE_CHOICES = [
		('adult', 'Adult'),
		('child', 'Child'),
	]

	booking = models.ForeignKey(PackageBooking, on_delete=models.CASCADE, related_name='travelers')
	full_name = models.CharField(max_length=120)
	age = models.PositiveIntegerField()
	traveler_type = models.CharField(max_length=10, choices=TRAVELER_TYPE_CHOICES, default='adult')
	phone = models.CharField(max_length=15, blank=True)
	email = models.EmailField(blank=True)
	id_proof_type = models.CharField(max_length=50, blank=True)
	id_proof_number = models.CharField(max_length=50, blank=True)

	def __str__(self):
		return f"{self.full_name} ({self.get_traveler_type_display()})"


# ── Package Add-ons ──────────────────────────────────────────────────

class PackageAddon(TimeStampedModel):
	"""Optional add-on services that can be bundled with a package.

	Examples: airport transfer, local sightseeing, adventure activity,
	spa/wellness, photography, travel insurance, meals upgrade.
	"""
	ADDON_TYPE_CHOICES = [
		('airport_transfer', 'Airport Transfer'),
		('local_sightseeing', 'Local Sightseeing'),
		('adventure', 'Adventure Activity'),
		('spa_wellness', 'Spa & Wellness'),
		('photography', 'Photography'),
		('meals_upgrade', 'Meals Upgrade'),
		('travel_insurance', 'Travel Insurance'),
		('guide_private', 'Private Guide'),
		('room_upgrade', 'Room Upgrade'),
		('other', 'Other'),
	]

	PRICING_TYPE_CHOICES = [
		('per_person', 'Per Person'),
		('per_booking', 'Per Booking (flat)'),
		('per_day', 'Per Day'),
	]

	package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='addons')
	addon_type = models.CharField(max_length=30, choices=ADDON_TYPE_CHOICES)
	name = models.CharField(max_length=160)
	description = models.TextField(blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2)
	pricing_type = models.CharField(max_length=15, choices=PRICING_TYPE_CHOICES, default='per_person')
	max_quantity = models.PositiveIntegerField(
		default=1, help_text="Max units per booking (e.g., 2 sightseeing tours)",
	)
	is_popular = models.BooleanField(default=False, help_text="Show as recommended add-on")
	bundle_discount_pct = models.DecimalField(
		max_digits=5, decimal_places=2, default=0,
		help_text="Discount % when bundled with 2+ add-ons",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['-is_popular', 'price']
		indexes = [
			models.Index(fields=['package', 'addon_type']),
		]

	def effective_price(self, adults=1, children=0, days=1, bundle_count=0):
		"""Calculate effective price based on pricing type and bundle discounts.

		Args:
			adults: Number of adults
			children: Number of children (charged at 50%)
			days: Package duration in days
			bundle_count: Total add-ons in the bundle (for discount)
		"""
		from decimal import Decimal

		if self.pricing_type == 'per_person':
			base = self.price * adults + (self.price * Decimal('0.5') * children)
		elif self.pricing_type == 'per_day':
			base = self.price * days
		else:  # per_booking
			base = self.price

		# Apply bundle discount when 2+ add-ons selected
		if bundle_count >= 2 and self.bundle_discount_pct > 0:
			discount = (base * self.bundle_discount_pct / Decimal('100')).quantize(Decimal('0.01'))
			base -= discount

		return base.quantize(Decimal('0.01'))

	def __str__(self):
		return f"{self.name} — ₹{self.price} ({self.get_pricing_type_display()})"


class PackageBookingAddon(TimeStampedModel):
	"""Records which add-ons were selected for a specific booking."""
	booking = models.ForeignKey(PackageBooking, on_delete=models.CASCADE, related_name='booking_addons')
	addon = models.ForeignKey(PackageAddon, on_delete=models.PROTECT, related_name='booking_selections')
	quantity = models.PositiveIntegerField(default=1)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Snapshot at booking time")
	total_price = models.DecimalField(max_digits=10, decimal_places=2)

	class Meta:
		unique_together = ('booking', 'addon')

	def __str__(self):
		return f"{self.booking.public_booking_id} + {self.addon.name}"


# ── Dynamic Bundle Calculator ────────────────────────────────────────

class PackageBundleCalculator:
	"""Compute dynamic bundle pricing for a package + selected add-ons.

	Usage:
		calc = PackageBundleCalculator(package, travel_date, adults=2, children=1)
		calc.add_addon(addon_id=5, quantity=1)
		calc.add_addon(addon_id=8, quantity=2)
		result = calc.calculate()
		# result = {
		#   'base_price': ...,
		#   'season': 'Peak Season',
		#   'addons': [...],
		#   'addons_subtotal': ...,
		#   'bundle_savings': ...,
		#   'package_subtotal': ...,
		#   'group_discount': ...,
		#   'gst': ...,
		#   'total': ...,
		# }
	"""

	def __init__(self, package, travel_date=None, adults=1, children=0):
		from decimal import Decimal
		self.Decimal = Decimal
		self.package = package
		self.travel_date = travel_date or timezone.now().date()
		self.adults = adults
		self.children = children
		self._addon_selections = []  # list of (addon, quantity)

	def add_addon(self, addon_id=None, addon=None, quantity=1):
		"""Add an add-on to the bundle. Pass either addon_id or addon instance."""
		if addon is None:
			addon = PackageAddon.objects.get(id=addon_id, package=self.package, is_active=True)
		qty = min(quantity, addon.max_quantity)
		self._addon_selections.append((addon, qty))

	def calculate(self):
		D = self.Decimal

		# ── Base package price (seasonal) ──
		pricing = PackageSeasonalPrice.get_price_for_date(self.package, self.travel_date)
		adult_price = D(str(pricing['adult_price']))
		child_price = D(str(pricing['child_price']))
		season = pricing['season']

		base_cost = (adult_price * self.adults) + (child_price * self.children)

		# ── Add-ons ──
		bundle_count = len(self._addon_selections)
		addon_details = []
		addons_subtotal = D('0')
		addons_without_discount = D('0')

		for addon, qty in self._addon_selections:
			effective = addon.effective_price(
				adults=self.adults,
				children=self.children,
				days=self.package.duration_days,
				bundle_count=bundle_count,
			) * qty

			without_discount = addon.effective_price(
				adults=self.adults,
				children=self.children,
				days=self.package.duration_days,
				bundle_count=0,  # No discount for comparison
			) * qty

			addons_subtotal += effective
			addons_without_discount += without_discount

			addon_details.append({
				'addon_id': addon.id,
				'name': addon.name,
				'addon_type': addon.addon_type,
				'quantity': qty,
				'unit_price': float(addon.price),
				'pricing_type': addon.pricing_type,
				'effective_price': float(effective),
				'bundle_discount_pct': float(addon.bundle_discount_pct) if bundle_count >= 2 else 0,
			})

		bundle_savings = addons_without_discount - addons_subtotal

		# ── Group discount ──
		total_travelers = self.adults + self.children
		package_subtotal = base_cost + addons_subtotal

		if total_travelers >= 10:
			group_discount = (package_subtotal * D('0.10')).quantize(D('0.01'))
		elif total_travelers >= 5:
			group_discount = (package_subtotal * D('0.05')).quantize(D('0.01'))
		else:
			group_discount = D('0')

		after_discounts = package_subtotal - group_discount
		gst = (after_discounts * D('0.05')).quantize(D('0.01'))
		total = (after_discounts + gst).quantize(D('0.01'))

		return {
			'package_id': self.package.id,
			'package_name': self.package.name,
			'travel_date': str(self.travel_date),
			'season': season,
			'adults': self.adults,
			'children': self.children,
			'adult_price': float(adult_price),
			'child_price': float(child_price),
			'base_cost': float(base_cost),
			'addons': addon_details,
			'addons_subtotal': float(addons_subtotal),
			'bundle_savings': float(bundle_savings),
			'package_subtotal': float(package_subtotal),
			'group_discount': float(group_discount),
			'gst': float(gst),
			'total': float(total),
		}

	@classmethod
	def recommended_bundles(cls, package, travel_date=None, adults=1, children=0, top_n=3):
		"""Generate top-N recommended bundle combos based on popular add-ons.

		Returns pre-computed pricing for popular add-on combinations.
		"""
		popular = PackageAddon.objects.filter(
			package=package, is_active=True, is_popular=True,
		).order_by('-bundle_discount_pct', 'price')[:6]

		if not popular.exists():
			return []

		bundles = []

		# Bundle 1: Single most popular add-on
		if popular.count() >= 1:
			calc = cls(package, travel_date, adults, children)
			calc.add_addon(addon=popular[0])
			bundles.append({
				'bundle_name': f"Essential — {popular[0].name}",
				'addon_ids': [popular[0].id],
				**calc.calculate(),
			})

		# Bundle 2: Top 2 popular add-ons
		if popular.count() >= 2:
			calc = cls(package, travel_date, adults, children)
			calc.add_addon(addon=popular[0])
			calc.add_addon(addon=popular[1])
			bundles.append({
				'bundle_name': f"Value — {popular[0].name} + {popular[1].name}",
				'addon_ids': [popular[0].id, popular[1].id],
				**calc.calculate(),
			})

		# Bundle 3: Top 3 popular add-ons (best value)
		if popular.count() >= 3:
			calc = cls(package, travel_date, adults, children)
			for p in popular[:3]:
				calc.add_addon(addon=p)
			bundles.append({
				'bundle_name': "Premium — All Recommended",
				'addon_ids': [p.id for p in popular[:3]],
				**calc.calculate(),
			})

		return bundles[:top_n]
