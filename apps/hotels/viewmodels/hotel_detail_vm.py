"""Hotel detail view model.

Transforms hotel data for detail/booking templates.
Encapsulates: full property info, all pricing, images, amenities, policies.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from decimal import Decimal


@dataclass
class RoomTypeVM:
    """Room type display model."""
    name: str
    type: str
    capacity: int
    available_count: int
    price: Decimal
    amenities: List[str] = field(default_factory=list)
    

@dataclass
class ReviewVM:
    """Guest review display model."""
    author_name: str
    rating: int
    title: str
    text: str
    date: str
    helpful_count: int = 0


@dataclass
class HotelDetailVM:
    """Complete hotel detail for booking view.
    
    This includes all information needed for the detail page:
    - Property information
    - Full pricing breakdown
    - All images
    - Complete amenities
    - Policies
    - Room types
    - Guest reviews
    """
    
    # Identity (required)
    id: int
    name: str
    slug: str
    property_type: str
    
    # Contact (required)
    phone_number: str
    email: str
    
    # Location (required)
    city: str
    area: str
    landmark: str
    address: str
    latitude: float
    longitude: float
    zip_code: str
    country: str
    
    # Description (required)
    description: str
    
    # Pricing (required)
    base_price: Decimal
    current_price: Decimal
    
    # Ratings (required)
    rating_value: Optional[float]
    rating_count: int
    rating_tier: str
    
    # Cancellation policy (required)
    cancellation_policy: str
    
    # Optional fields with defaults
    website: Optional[str] = None
    highlights: List[str] = field(default_factory=list)
    images: List[dict] = field(default_factory=list)  # [{url, alt, order}, ...]
    original_price: Optional[Decimal] = None
    discount_percent: int = 0
    taxes_and_fees: Decimal = Decimal('0')
    room_types: List[RoomTypeVM] = field(default_factory=list)
    amenities_popular: List[str] = field(default_factory=list)
    amenities_all: List[str] = field(default_factory=list)
    check_in_time: str = '14:00'
    check_out_time: str = '11:00'
    is_free_cancellation: bool = False
    payment_at_hotel: bool = False
    is_verified: bool = False
    verification_badge: str = ''
    reviews: List[ReviewVM] = field(default_factory=list)
    review_summary: dict = field(default_factory=dict)
    created_at: str = ''
    updated_at: str = ''
    
    @property
    def primary_image(self) -> Optional[dict]:
        """Get primary/first image."""
        if self.images:
            return self.images[0]
        return None
    
    @property
    def gallery_images(self) -> List[dict]:
        """Get non-primary images."""
        if len(self.images) > 1:
            return self.images[1:]
        return []
    
    @property
    def total_price_with_taxes(self) -> Decimal:
        """Calculate final price including taxes."""
        return self.current_price + self.taxes_and_fees
    
    @property
    def average_rating(self) -> str:
        """Format average rating."""
        if not self.rating_value:
            return 'Not rated'
        return f"{self.rating_value:.1f}"
    
    @property
    def review_percentage_by_score(self) -> dict:
        """Review breakdown by score (5-star, 4-star, etc)."""
        return self.review_summary.get('by_score', {})