"""Hotel card view model.

Transforms hotel data for list/search templates.
Encapsulates: property, pricing, analytics, trust signals.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class HotelCardVM:
    """Presentation model for hotel cards in search/list views.
    
    This is the ONLY object passed to hotel card templates.
    No ORM instances, no raw database values.
    """
    
    # Core identity
    id: int
    name: str
    slug: str
    
    # Location
    city: str
    area: str
    landmark: str
    latitude: float
    longitude: float
    
    # Image
    image_url: Optional[str]
    image_alt: str
    
    # Pricing (Phase 2: price transparency)
    price_current: Decimal
    price_original: Optional[Decimal] = None
    discount_percent: int = 0
    savings_amount: Decimal = Decimal('0')
    
    # Ratings (Phase 3: trust)
    rating_value: Optional[float] = None
    rating_count: int = 0
    rating_tier: str = 'average'  # poor, average, good, excellent
    
    # Analytics (Phase 4: urgency & social proof)
    rooms_left: int = 0
    booked_today: int = 0
    viewers_now: int = 0
    
    # Trust badges (Phase 5: OTA conversion signals)
    is_verified: bool = False
    is_best_rating: bool = False
    is_lowest_price: bool = False
    is_best_deal: bool = False
    is_best_value: bool = False
    
    # Amenities
    amenities: list[str] = None
    
    # Policies
    free_cancellation: bool = False
    pay_at_hotel: bool = False
    
    # Metadata
    property_type: str = 'hotel'
    cta_url: str = ''
    relevance_score: float = 0.0
    
    def __post_init__(self):
        """Initialize with safe defaults."""
        if self.amenities is None:
            self.amenities = []
        
        # Type coercion
        self.price_current = Decimal(str(self.price_current))
        if self.price_original:
            self.price_original = Decimal(str(self.price_original))
        if self.savings_amount:
            self.savings_amount = Decimal(str(self.savings_amount))
    
    @property
    def has_discount(self) -> bool:
        """Check if property has discount."""
        return self.discount_percent > 0
    
    @property
    def is_urgent(self) -> bool:
        """Urgency indicator: low room availability."""
        return self.rooms_left > 0 and self.rooms_left <= 5
    
    @property
    def is_hot(self) -> bool:
        """Hot indicator: high booking/viewer activity."""
        return self.booked_today >= 10 or self.viewers_now >= 20
    
    @property
    def rating_stars(self) -> str:
        """Human readable rating."""
        if not self.rating_value:
            return 'Not rated'
        return f"{self.rating_value:.1f} ⭐"
    
    @property
    def availability_status(self) -> str:
        """Availability text for UI."""
        if self.rooms_left == 0:
            return 'no-rooms'
        elif self.rooms_left <= 3:
            return 'very-limited'
        elif self.rooms_left <= 10:
            return 'limited'
        else:
            return 'available'
    
    @property
    def availability_label(self) -> str:
        """Availability label for display."""
        status_map = {
            'no-rooms': 'Sold Out',
            'very-limited': f'Only {self.rooms_left} left',
            'limited': f'{self.rooms_left} rooms left',
            'available': 'Available'
        }
        return status_map.get(self.availability_status, 'Available')