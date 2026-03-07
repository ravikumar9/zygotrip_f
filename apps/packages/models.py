from django.db import models
from django.conf import settings
from django.utils.text import slugify
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
