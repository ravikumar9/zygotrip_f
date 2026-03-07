"""Filter view models.

Transforms filter data for dynamic filter UI.
Enables server-driven filter generation (not hardcoded in templates).
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FilterOptionVM:
    """Single filter option."""
    label: str
    value: str
    count: int = 0  # Number of results with this option
    is_selected: bool = False


@dataclass
class PriceFilterVM:
    """Price range filter."""
    min_price: int
    max_price: int
    current_min: Optional[int] = None
    current_max: Optional[int] = None
    
    @property
    def selected_min(self) -> int:
        return self.current_min or self.min_price
    
    @property
    def selected_max(self) -> int:
        return self.current_max or self.max_price


@dataclass
class FiltersVM:
    """Complete filter state for search page.
    
    Server generates this based on available data.
    Templates read from this - no hardcoding.
    
    Example:
        filters = FiltersVM(
            price=PriceFilterVM(min_price=500, max_price=10000),
            ratings=[
                FilterOptionVM('5 Star', '5', count=24),
                FilterOptionVM('4+ Star', '4', count=156),
            ],
            amenities=[
                FilterOptionVM('Free WiFi', 'wifi', count=342),
                FilterOptionVM('Swimming Pool', 'pool', count=198),
            ]
        )
    """
    
    # Price filter
    price: PriceFilterVM
    
    # Star rating filter
    ratings: List[FilterOptionVM] = field(default_factory=list)
    
    # Review score filter
    review_scores: List[FilterOptionVM] = field(default_factory=list)
    
    # Amenities filter
    amenities: List[FilterOptionVM] = field(default_factory=list)
    
    # Property type filter
    property_types: List[FilterOptionVM] = field(default_factory=list)
    
    # Policies filter
    policies: List[FilterOptionVM] = field(default_factory=list)
    
    # Location radius (for map view)
    location_radius: Optional[int] = None
    
    @property
    def has_active_filters(self) -> bool:
        """Check if any filters are selected."""
        checks = [
            any(opt.is_selected for opt in self.ratings),
            any(opt.is_selected for opt in self.amenities),
            any(opt.is_selected for opt in self.property_types),
            any(opt.is_selected for opt in self.review_scores),
            any(opt.is_selected for opt in self.policies),
            (self.price.current_min and self.price.current_min > self.price.min_price),
            (self.price.current_max and self.price.current_max < self.price.max_price),
        ]
        return any(checks)
    
    @property
    def active_filter_count(self) -> int:
        """Count active filters."""
        count = 0
        count += sum(1 for opt in self.ratings if opt.is_selected)
        count += sum(1 for opt in self.amenities if opt.is_selected)
        count += sum(1 for opt in self.property_types if opt.is_selected)
        count += sum(1 for opt in self.review_scores if opt.is_selected)
        count += sum(1 for opt in self.policies if opt.is_selected)
        if self.price.current_min and self.price.current_min > self.price.min_price:
            count += 1
        if self.price.current_max and self.price.current_max < self.price.max_price:
            count += 1
        return count


# Factory for creating VM from querystring/filters
def build_filters_vm(request, properties_qs) -> FiltersVM:
    """Build filter view model from request and available properties.
    
    This is called by search view to generate server-driven filters.
    """
    from django.db.models import Q, Count, Min, Max
    
    # Get min/max prices from available properties
    price_stats = properties_qs.aggregate(
        min_price=Min('price__current'),
        max_price=Max('price__current')
    )
    
    min_price = int(price_stats['min_price'] or 1000)
    max_price = int(price_stats['max_price'] or 10000)
    
    # Get requested filters from querystring
    req_min_price = request.GET.get('price_min')
    req_max_price = request.GET.get('price_max')
    
    # Build rating options with counts
    ratings = []
    for star in [5, 4, 3, 2]:
        count = properties_qs.filter(rating__gte=star).count()
        ratings.append(FilterOptionVM(
            label=f'{star}+ Star',
            value=str(star),
            count=count,
            is_selected=request.GET.get('rating') == str(star)
        ))
    
    # Build amenity options with counts
    amenities = []
    amenity_counts = {}
    for prop in properties_qs:
        for amenity in prop.amenities or []:
            amenity_counts[amenity] = amenity_counts.get(amenity, 0) + 1
    
    for amenity, count in sorted(amenity_counts.items()):
        selected_amenities = request.GET.getlist('amenities')
        amenities.append(FilterOptionVM(
            label=amenity,
            value=amenity.lower().replace(' ', '-'),
            count=count,
            is_selected=amenity in selected_amenities
        ))
    
    return FiltersVM(
        price=PriceFilterVM(
            min_price=min_price,
            max_price=max_price,
            current_min=int(req_min_price) if req_min_price else None,
            current_max=int(req_max_price) if req_max_price else None,
        ),
        ratings=ratings,
        amenities=amenities,
    )