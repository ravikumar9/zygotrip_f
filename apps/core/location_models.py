"""
Location Hierarchy Models
Implements geo tree: Country → State → City → Area → Hotel

Critical for:
- Search context (CTXCR pattern)
- Bounding box search
- Hotel clustering
- Autocomplete rankings
"""
from django.db import models


class Country(models.Model):
    """Top-level geo entity"""
    code = models.CharField(max_length=2, unique=True, help_text="ISO 3166-1 alpha-2")
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Countries"
        indexes = [models.Index(fields=['code', 'is_active'])]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class State(models.Model):
    """State/Province level"""
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')
    code = models.CharField(max_length=10, help_text="State code")
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['code'])
        ]
        unique_together = ['country', 'code']
    
    def __str__(self):
        return f"{self.name}, {self.country.code}"


class City(models.Model):
    """City level - primary search context"""
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities')
    code = models.CharField(max_length=20, unique=True, help_text="CTXCR code for search")
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True, null=True, help_text="URL slug for routing")
    alternate_names = models.TextField(blank=True, help_text="Comma-separated aliases")
    
    # Geo data for bounding box search
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Bounding box coordinates (ne/sw pattern from logs)
    ne_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    ne_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    sw_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    sw_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    
    # Search ranking
    hotel_count = models.IntegerField(default=0)
    popularity_score = models.IntegerField(default=0, help_text="Based on search volume")
    is_top_destination = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Cities"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['state', 'is_active']),
            models.Index(fields=['-popularity_score']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_alternate_names_list(self):
        if self.alternate_names:
            return [name.strip() for name in self.alternate_names.split(',')]
        return []


class Locality(models.Model):
    """Area/Locality within city"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='localities')
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=120, blank=True, null=True, help_text="URL slug for routing")
    
    # Geo coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Intelligence signals
    hotel_count = models.IntegerField(default=0)
    avg_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    popularity_score = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Descriptors for search
    landmarks = models.TextField(blank=True, help_text="Comma-separated nearby landmarks")
    locality_type = models.CharField(
        max_length=50,
        choices=[
            ('business', 'Business District'),
            ('tourist', 'Tourist Area'),
            ('residential', 'Residential'),
            ('airport', 'Near Airport'),
            ('beach', 'Beach Area'),
            ('hill_station', 'Hill Station'),
        ],
        default='tourist'
    )
    
    class Meta:
        verbose_name_plural = "Localities"
        indexes = [
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['-popularity_score']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.city.name}"
    
    def get_landmarks_list(self):
        if self.landmarks:
            return [lm.strip() for lm in self.landmarks.split(',')]
        return []


class LocationSearchIndex(models.Model):
    """
    Unified search index for autocomplete
    
    Critical: This is what makes typing "Coorg" return instant results
    Pattern from logs: single context ID (CTXCR) maps to entire tree
    """
    ENTITY_TYPES = [
        ('country', 'Country'),
        ('state', 'State'),
        ('city', 'City'),
        ('locality', 'Locality'),
        ('hotel', 'Hotel'),
        ('landmark', 'Landmark'),
    ]
    
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.IntegerField(help_text="FK to actual entity")
    
    # Search fields
    display_name = models.CharField(max_length=200)
    search_text = models.TextField(help_text="Normalized text for fuzzy search")
    alternate_names = models.TextField(blank=True)
    
    # Context for hierarchical display
    context_city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, related_name='search_entries')
    context_state = models.ForeignKey(State, on_delete=models.CASCADE, null=True, related_name='search_entries')
    context_country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, related_name='search_entries')
    
    # Ranking signals
    search_score = models.IntegerField(default=0, help_text="Higher = better ranking")
    search_count = models.IntegerField(default=0, help_text="How many times searched")
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Search → booking %")
    
    # Geo for distance sorting
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    
    # Metadata
    is_clickable = models.BooleanField(default=True, help_text="Can user click to see results")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['search_text']),
            models.Index(fields=['-search_score', '-search_count']),
            models.Index(fields=['context_city', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.entity_type}: {self.display_name}"


class RegionGroup(models.Model):
    """
    Logical regions (not political boundaries)
    
    Examples:
    - "NCR" includes Delhi + Gurgaon + Noida
    - "Coorg" includes Madikeri + Virajpet
    """
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    
    # Multiple cities can be in one region
    cities = models.ManyToManyField(City, related_name='regions')
    
    # Search metadata
    description = models.TextField(blank=True)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [models.Index(fields=['code', 'is_active'])]
    
    def __str__(self):
        return self.display_name