"""
Enhanced marketplace models for enterprise travel booking UX.
"""
from django.db import models
from django.utils.text import slugify
from django.urls import reverse


class Destination(models.Model):
    """Popular travel destinations for autocomplete and trending."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to='destinations/', null=True, blank=True)
    is_trending = models.BooleanField(default=False)
    priority = models.IntegerField(default=0, help_text="Higher = shows first")
    search_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-priority', '-search_count']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-is_trending', '-priority']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    """Service categories: Hotels, Buses, Cabs, Packages."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, help_text="Icon class name")
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return f'/{self.slug}/'


class Offer(models.Model):
    """Promotional offers and deals."""
    OFFER_TYPES = [
        ('PERCENTAGE', 'Percentage Discount'),
        ('FLAT', 'Flat Amount Off'),
        ('DEAL', 'Special Deal'),
    ]
    
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    code = models.CharField(max_length=50, unique=True, blank=True)
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(upload_to='offers/', null=True, blank=True)
    
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    min_booking_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    priority = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-priority', '-valid_from']
    
    def __str__(self):
        return self.title
    
    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_until


class SearchIndex(models.Model):
    """Unified search index for autocomplete across all entities."""
    INDEX_TYPES = [
        ('CITY', 'City'),
        ('AREA', 'Area'),
        ('LANDMARK', 'Landmark'),
        ('PROPERTY', 'Property Name'),
        ('DESTINATION', 'Destination'),
    ]
    
    search_type = models.CharField(max_length=20, choices=INDEX_TYPES)
    name = models.CharField(max_length=300)
    normalized_name = models.CharField(max_length=300, db_index=True)
    
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=200, blank=True)
    
    # Polymorphic reference - stores type and ID
    content_type = models.CharField(max_length=50, blank=True)
    object_id = models.IntegerField(null=True, blank=True)
    
    search_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-search_count', 'name']
        indexes = [
            models.Index(fields=['normalized_name']),
            models.Index(fields=['search_type', '-search_count']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.search_type})"
    
    def save(self, *args, **kwargs):
        self.normalized_name = self.name.lower().strip()
        super().save(*args, **kwargs)