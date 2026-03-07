# apps/hotels/filters.py
"""
OTA-Grade Filter Engine with Query Parser and Dynamic Selector Builder

RULES:
1. No ORM queries inside this module - only parse and return filter config
2. All filtering logic is applied in selectors.py
3. Filters are modular and reusable
4. All filters support querystring parsing
5. Caching is handled in services.py

PHASE 7: PUBLIC LISTING FILTERS
- Only approved + agreement_signed properties are visible to public
- Pending and rejected properties are hidden from listings/search
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def _has_relation(model, relation_name):
    return any(field.name == relation_name for field in model._meta.get_fields())


# ============================================================================
# PHASE 7: PUBLIC LISTING VISIBILITY FILTERS (NEW)
# ============================================================================

def get_public_properties_queryset(base_queryset=None):
	"""
	Get properties visible to the public/travelers.
	Only returns properties that are:
	1. Approved status
	2. Agreement signed
	3. Active
	
	Args:
		base_queryset: Optional initial queryset to filter (default: all Properties)
	
	Returns:
		Filtered queryset with public-only properties
	"""
	if base_queryset is None:
		from apps.hotels.models import Property
		base_queryset = Property.objects.all()
	
	return base_queryset.filter(
		status='approved',
		agreement_signed=True,
		is_active=True
	)


def get_pending_approvals_for_admin(owner=None):
	"""
	Get properties pending admin approval.
	Optionally filter by specific owner.
	"""
	from apps.hotels.models import Property
	queryset = Property.objects.filter(status='pending')
	
	if owner:
		queryset = queryset.filter(owner=owner)
	
	return queryset


def get_vendor_properties(vendor):
	"""Get all properties owned by a specific vendor (for dashboard)"""
	from apps.hotels.models import Property
	return Property.objects.filter(owner=vendor)


def get_pending_owner_action_properties(vendor):
	"""
	Get vendor's properties that are approved but awaiting owner action.
	(Agreement not yet signed by owner)
	"""
	from apps.hotels.models import Property
	return Property.objects.filter(
		owner=vendor,
		status='approved',
		agreement_file__isnull=False,
		agreement_signed=False
	)


def get_vendor_active_listings(vendor):
	"""Get vendor's properties that are publicly visible"""
	return get_public_properties_queryset(
		get_vendor_properties(vendor)
	)


def get_vendor_inactive_properties(vendor):
	"""Get vendor's properties not yet public"""
	from apps.hotels.models import Property
	return Property.objects.filter(owner=vendor).exclude(
		status='approved',
		agreement_signed=True
	)


# ============================================================================
# FILTER OPTION ENUMS
# ============================================================================

class SortOption(str, Enum):
    """Sorting options for hotel results"""
    POPULARITY = "popularity"  # Booking velocity + rating
    RATING = "rating"  # Top rated first
    PRICE_LOWEST = "price_lowest"  # Cheapest first
    PRICE_HIGHEST = "price_highest"  # Most expensive first
    NEWEST = "newest"  # Recently added
    DISTANCE = "distance"  # Nearest to user location


# ============================================================================
# FILTER DATA CLASSES (Parsed from querystring)
# ============================================================================

@dataclass
class PriceRangeFilter:
    """Price range filter parsed from querystring"""
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    
    def is_active(self) -> bool:
        """Check if any price filter is set"""
        return self.min_price is not None or self.max_price is not None
    
    def to_dict(self) -> Dict:
        """Convert to dict for template rendering"""
        return asdict(self)


@dataclass
class RatingFilter:
    """Rating filters from querystring"""
    min_rating: Optional[float] = None  # e.g., 4.5
    min_stars: Optional[int] = None  # e.g., 4 (star category)
    
    def is_active(self) -> bool:
        return self.min_rating is not None or self.min_stars is not None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LocationFilter:
    """Location-based filtering"""
    city_id: Optional[int] = None
    locality_id: Optional[int] = None
    area: Optional[str] = None  # Legacy field
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    max_distance_km: Optional[float] = None
    
    def is_location_based(self) -> bool:
        """Check if using lat/long for distance calculation"""
        return self.latitude is not None and self.longitude is not None
    
    def is_active(self) -> bool:
        """Check if any location filter is set"""
        return (
            self.city_id is not None or
            self.locality_id is not None or
            self.area is not None or
            self.is_location_based()
        )
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AmenityFilter:
    """Amenity-based filtering"""
    amenity_ids: List[int] = field(default_factory=list)  # IDs of selected amenities
    # For querystring: "amenities=wifi,pool,parking"
    
    def is_active(self) -> bool:
        return len(self.amenity_ids) > 0
    
    def to_dict(self) -> Dict:
        return {"amenity_ids": self.amenity_ids}


@dataclass
class PaymentMethodFilter:
    """Payment method filtering"""
    payment_method_ids: List[int] = field(default_factory=list)  # IDs of accepted methods
    
    def is_active(self) -> bool:
        return len(self.payment_method_ids) > 0
    
    def to_dict(self) -> Dict:
        return {"payment_method_ids": self.payment_method_ids}


@dataclass
class CancellationPolicyFilter:
    """Cancellation policy filtering"""
    policy_ids: List[int] = field(default_factory=list)  # IDs of accepted policies
    flexible_only: bool = False  # Only fully refundable
    non_refundable_acceptable: bool = True
    
    def is_active(self) -> bool:
        return len(self.policy_ids) > 0 or self.flexible_only
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BrandFilter:
    """Brand filtering"""
    brand_ids: List[int] = field(default_factory=list)  # Specific brands to include
    exclude_brands: bool = False  # If True, exclude these brands
    
    def is_active(self) -> bool:
        return len(self.brand_ids) > 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PropertyTypeFilter:
    """Property type filtering (Hotel, Resort, etc.)"""
    property_types: List[str] = field(default_factory=list)
    
    def is_active(self) -> bool:
        return len(self.property_types) > 0
    
    def to_dict(self) -> Dict:
        return {"property_types": self.property_types}


@dataclass
class AvailabilityFilter:
    """Availability/inventory filtering"""
    check_in_date: Optional[str] = None  # YYYY-MM-DD
    check_out_date: Optional[str] = None  # YYYY-MM-DD
    require_available: bool = True  # Only show properties with available rooms
    guests: int = 1  # Number of guests
    rooms: int = 1  # Number of rooms needed
    
    def is_active(self) -> bool:
        return (
            self.check_in_date is not None and
            self.check_out_date is not None
        )
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# MAIN FILTER CONTAINER
# ============================================================================

@dataclass
class HotelFilters:
    """
    Complete filter set parsed from querystring.
    
    USAGE:
        filters = HotelFiltersParser.parse(request.GET)
        queryset = get_filtered_hotels_queryset(filters)
    """
    
    # Search query
    search_query: str = ""
    
    # Sub-filters
    price_range: PriceRangeFilter = field(default_factory=PriceRangeFilter)
    rating: RatingFilter = field(default_factory=RatingFilter)
    location: LocationFilter = field(default_factory=LocationFilter)
    amenities: AmenityFilter = field(default_factory=AmenityFilter)
    payment_methods: PaymentMethodFilter = field(default_factory=PaymentMethodFilter)
    cancellation_policy: CancellationPolicyFilter = field(default_factory=CancellationPolicyFilter)
    brand: BrandFilter = field(default_factory=BrandFilter)
    property_type: PropertyTypeFilter = field(default_factory=PropertyTypeFilter)
    availability: AvailabilityFilter = field(default_factory=AvailabilityFilter)
    
    # Sorting & Pagination
    sort_by: SortOption = SortOption.POPULARITY
    page: int = 1
    page_size: int = 20
    
    # Caching control
    cache_key: Optional[str] = None  # Auto-generated by services
    
    def get_active_filters(self) -> List[str]:
        """List of active filter names for display"""
        active = []
        if self.search_query:
            active.append('search')
        if self.price_range.is_active():
            active.append('price')
        if self.rating.is_active():
            active.append('rating')
        if self.location.is_active():
            active.append('location')
        if self.amenities.is_active():
            active.append('amenities')
        if self.payment_methods.is_active():
            active.append('payment')
        if self.cancellation_policy.is_active():
            active.append('cancellation')
        if self.brand.is_active():
            active.append('brand')
        if self.property_type.is_active():
            active.append('property_type')
        if self.availability.is_active():
            active.append('availability')
        return active
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for template/API rendering"""
        return {
            'search_query': self.search_query,
            'price_range': self.price_range.to_dict(),
            'rating': self.rating.to_dict(),
            'location': self.location.to_dict(),
            'amenities': self.amenities.to_dict(),
            'payment_methods': self.payment_methods.to_dict(),
            'cancellation_policy': self.cancellation_policy.to_dict(),
            'brand': self.brand.to_dict(),
            'property_type': self.property_type.to_dict(),
            'availability': self.availability.to_dict(),
            'sort_by': self.sort_by.value,
            'page': self.page,
            'page_size': self.page_size,
            'active_filters': self.get_active_filters(),
        }


# ============================================================================
# QUERY PARSER - Convert Django QueryDict to HotelFilters
# ============================================================================

class HotelFiltersParser:
    """
    Parse HTTP querystring parameters into typed HotelFilters object.
    
    ROBUST IMPLEMENTATION:
    - Validates all inputs
    - Uses sensible defaults for missing values
    - Logs parsing errors without crashing
    - Preserves valid filters even if some fail
    """
    
    @staticmethod
    def parse(query_params) -> HotelFilters:
        """
        Parse Django request.GET or query dict into HotelFilters.
        
        Args:
            query_params: Django QueryDict (request.GET) or dict
            
        Returns:
            HotelFilters object with all parsed values
            
        Example:
            filters = HotelFiltersParser.parse(request.GET)
        """
        
        filters = HotelFilters()
        
        # Search query
        filters.search_query = HotelFiltersParser._parse_search(query_params)
        
        # Price range
        filters.price_range = HotelFiltersParser._parse_price_range(query_params)
        
        # Ratings
        filters.rating = HotelFiltersParser._parse_rating(query_params)
        
        # Location
        filters.location = HotelFiltersParser._parse_location(query_params)
        
        # Amenities
        filters.amenities = HotelFiltersParser._parse_amenities(query_params)
        
        # Payment methods
        filters.payment_methods = HotelFiltersParser._parse_payment_methods(query_params)
        
        # Cancellation policy
        filters.cancellation_policy = HotelFiltersParser._parse_cancellation_policy(query_params)
        
        # Brand
        filters.brand = HotelFiltersParser._parse_brand(query_params)
        
        # Property type
        filters.property_type = HotelFiltersParser._parse_property_type(query_params)
        
        # Availability
        filters.availability = HotelFiltersParser._parse_availability(query_params)
        
        # Sorting
        filters.sort_by = HotelFiltersParser._parse_sort_by(query_params)
        
        # Pagination
        filters.page = HotelFiltersParser._parse_pagination(query_params)
        filters.page_size = HotelFiltersParser._parse_page_size(query_params)
        
        logger.debug(f"Parsed filters: {filters.get_active_filters()}")
        
        return filters
    
    @staticmethod
    def _parse_search(params) -> str:
        """Extract search query"""
        return params.get('q', '').strip()[:200]  # Max 200 chars
    
    @staticmethod
    def _parse_price_range(params) -> PriceRangeFilter:
        """Parse price_min and price_max parameters"""
        pf = PriceRangeFilter()
        
        try:
            if 'price_min' in params:
                pf.min_price = Decimal(params.get('price_min'))
            if 'price_max' in params:
                pf.max_price = Decimal(params.get('price_max'))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid price parameters: {e}")
        
        return pf
    
    @staticmethod
    def _parse_rating(params) -> RatingFilter:
        """Parse rating filters"""
        rf = RatingFilter()
        
        try:
            if 'min_rating' in params:
                rf.min_rating = float(params.get('min_rating'))
                # Validate range
                if rf.min_rating < 0 or rf.min_rating > 5:
                    rf.min_rating = None
                    logger.warning("Rating out of range 0-5")
            
            if 'min_stars' in params:
                rf.min_stars = int(params.get('min_stars'))
                if rf.min_stars < 1 or rf.min_stars > 5:
                    rf.min_stars = None
                    logger.warning("Star rating out of range 1-5")
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid rating parameters: {e}")
        
        return rf
    
    @staticmethod
    def _parse_location(params) -> LocationFilter:
        """Parse location filters"""
        lf = LocationFilter()
        
        try:
            if 'city_id' in params:
                lf.city_id = int(params.get('city_id'))
            if 'locality_id' in params:
                lf.locality_id = int(params.get('locality_id'))
            if 'area' in params:
                lf.area = params.get('area').strip()[:100]
            
            # Geo-location based filtering
            if 'latitude' in params and 'longitude' in params:
                lf.latitude = float(params.get('latitude'))
                lf.longitude = float(params.get('longitude'))
            
            if 'distance_km' in params:
                lf.max_distance_km = float(params.get('distance_km'))
                if lf.max_distance_km < 0:
                    lf.max_distance_km = None
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid location parameters: {e}")
        
        return lf
    
    @staticmethod
    def _parse_amenities(params) -> AmenityFilter:
        """Parse amenity filters"""
        af = AmenityFilter()
        
        try:
            # Format: ?amenities=1,2,3 or ?amenities=wifi,pool,parking (names)
            amenities_param = params.get('amenities', '').strip()
            if amenities_param:
                # Try parsing as integers first (IDs)
                try:
                    af.amenity_ids = [int(x.strip()) for x in amenities_param.split(',')]
                except ValueError:
                    # If not integers, store as object for selector to resolve
                    logger.debug(f"Amenity names will be resolved in selector: {amenities_param}")
        except Exception as e:
            logger.warning(f"Invalid amenity parameters: {e}")
        
        return af
    
    @staticmethod
    def _parse_payment_methods(params) -> PaymentMethodFilter:
        """Parse payment method filters"""
        pmf = PaymentMethodFilter()
        
        try:
            methods_param = params.get('payment_methods', '').strip()
            if methods_param:
                pmf.payment_method_ids = [int(x.strip()) for x in methods_param.split(',')]
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid payment method parameters: {e}")
        
        return pmf
    
    @staticmethod
    def _parse_cancellation_policy(params) -> CancellationPolicyFilter:
        """Parse cancellation policy filters"""
        cpf = CancellationPolicyFilter()
        
        try:
            policies_param = params.get('policies', '').strip()
            if policies_param:
                cpf.policy_ids = [int(x.strip()) for x in policies_param.split(',')]
            
            # Special flags
            if 'flexible_only' in params:
                cpf.flexible_only = params.get('flexible_only').lower() in ['true', '1', 'yes']
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid cancellation policy parameters: {e}")
        
        return cpf
    
    @staticmethod
    def _parse_brand(params) -> BrandFilter:
        """Parse brand filters"""
        bf = BrandFilter()
        
        try:
            brands_param = params.get('brands', '').strip()
            if brands_param:
                bf.brand_ids = [int(x.strip()) for x in brands_param.split(',')]
            
            if 'exclude_brands' in params:
                bf.exclude_brands = params.get('exclude_brands').lower() in ['true', '1', 'yes']
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid brand parameters: {e}")
        
        return bf
    
    @staticmethod
    def _parse_property_type(params) -> PropertyTypeFilter:
        """Parse property type filters"""
        ptf = PropertyTypeFilter()
        
        try:
            types_param = params.get('property_type', '').strip()
            if types_param:
                ptf.property_types = [x.strip() for x in types_param.split(',')]
        except Exception as e:
            logger.warning(f"Invalid property type parameters: {e}")
        
        return ptf
    
    @staticmethod
    def _parse_availability(params) -> AvailabilityFilter:
        """Parse availability filters"""
        af = AvailabilityFilter()
        
        try:
            if 'check_in' in params:
                af.check_in_date = params.get('check_in').strip()  # Expect YYYY-MM-DD
            if 'check_out' in params:
                af.check_out_date = params.get('check_out').strip()
            if 'guests' in params:
                af.guests = max(1, int(params.get('guests')))
            if 'rooms' in params:
                af.rooms = max(1, int(params.get('rooms')))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid availability parameters: {e}")
        
        return af
    
    @staticmethod
    def _parse_sort_by(params) -> SortOption:
        """Parse sort_by parameter"""
        sort_param = params.get('sort_by', SortOption.POPULARITY.value).strip()
        
        try:
            return SortOption(sort_param)
        except ValueError:
            logger.warning(f"Invalid sort option: {sort_param}, using default")
            return SortOption.POPULARITY
    
    @staticmethod
    def _parse_pagination(params) -> int:
        """Parse page number"""
        try:
            page = int(params.get('page', 1))
            return max(1, page)  # Minimum page 1
        except (ValueError, TypeError):
            return 1
    
    @staticmethod
    def _parse_page_size(params) -> int:
        """Parse page size with limits"""
        try:
            page_size = int(params.get('page_size', 20))
            # Limits: min 1, max 100
            return max(1, min(100, page_size))
        except (ValueError, TypeError):
            return 20


# ============================================================================
# FILTER BUILDER - Build querysets from filters (used by selectors)
# ============================================================================

class FilterBuilder:
    """
    Builds Django querysets from HotelFilters object.
    
    USAGE (in selectors.py):
        filters = HotelFiltersParser.parse(request.GET)
        queryset = FilterBuilder.apply(Property.objects.all(), filters)
    
    PRINCIPLES:
    - Always use queryset chaining, never loops
    - Utilize select_related/prefetch_related
    - Index-aware filtering (use indexed fields first)
    - Early filtering (cheap operations first)
    """
    
    @staticmethod
    def apply(queryset, filters: HotelFilters):
        """
        Apply all filters to queryset.
        
        Returns: QuerySet (not executed, can chain more .filter() calls)
        """
        
        # Apply filters in order of cost (cheapest first)
        queryset = FilterBuilder._apply_search(queryset, filters)
        queryset = FilterBuilder._apply_price_range(queryset, filters)
        queryset = FilterBuilder._apply_location(queryset, filters)
        queryset = FilterBuilder._apply_rating(queryset, filters)
        queryset = FilterBuilder._apply_property_type(queryset, filters)
        queryset = FilterBuilder._apply_brand(queryset, filters)
        # More expensive filters (joins)
        queryset = FilterBuilder._apply_amenities(queryset, filters)
        queryset = FilterBuilder._apply_payment_methods(queryset, filters)
        queryset = FilterBuilder._apply_cancellation_policy(queryset, filters)
        queryset = FilterBuilder._apply_availability(queryset, filters)
        
        # Apply sorting
        queryset = FilterBuilder._apply_sorting(queryset, filters)
        
        return queryset
    
    @staticmethod
    def _apply_search(queryset, filters: HotelFilters):
        """Search by name, city, area"""
        if filters.search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=filters.search_query) |
                Q(city__name__icontains=filters.search_query) |
                Q(area__icontains=filters.search_query) |
                Q(landmark__icontains=filters.search_query)
            )
        return queryset
    
    @staticmethod
    def _apply_price_range(queryset, filters: HotelFilters):
        """Filter by room base_price through select_related"""
        pf = filters.price_range
        if pf.min_price:
            queryset = queryset.filter(room_types__base_price__gte=pf.min_price)
        if pf.max_price:
            queryset = queryset.filter(room_types__base_price__lte=pf.max_price)
        return queryset
    
    @staticmethod
    def _apply_location(queryset, filters: HotelFilters):
        """Filter by city, locality, or distance"""
        lf = filters.location
        
        if lf.city_id:
            queryset = queryset.filter(city_id=lf.city_id)
        
        if lf.locality_id:
            queryset = queryset.filter(locality_id=lf.locality_id)
        
        if lf.area:
            queryset = queryset.filter(area__icontains=lf.area)
        
        # Note: Distance filtering done in python post-query (see FilterBuilder.apply_distance)
        
        return queryset
    
    @staticmethod
    def _apply_rating(queryset, filters: HotelFilters):
        """Filter by guest rating or star category"""
        rf = filters.rating
        
        if rf.min_rating:
            queryset = queryset.filter(rating__gte=rf.min_rating)
        
        if rf.min_stars:
            queryset = queryset.filter(star_rating__stars__gte=rf.min_stars)
        
        return queryset
    
    @staticmethod
    def _apply_property_type(queryset, filters: HotelFilters):
        """Filter by property type"""
        ptf = filters.property_type
        if ptf.property_types:
            queryset = queryset.filter(property_type__in=ptf.property_types)
        return queryset
    
    @staticmethod
    def _apply_brand(queryset, filters: HotelFilters):
        """Filter by brand"""
        bf = filters.brand
        if bf.brand_ids:
            if bf.exclude_brands:
                queryset = queryset.exclude(brands__brand_id__in=bf.brand_ids)
            else:
                queryset = queryset.filter(brands__brand_id__in=bf.brand_ids)
        return queryset
    
    @staticmethod
    def _apply_amenities(queryset, filters: HotelFilters):
        """Filter by amenities using prefetch"""
        af = filters.amenities
        if af.amenity_ids:
            # Annotate with count of matching amenities
            from django.db.models import Count
            queryset = queryset.filter(
                filterable_amenities__amenity_id__in=af.amenity_ids
            ).annotate(
                matching_amenity_count=Count('filterable_amenities__amenity_id', distinct=True)
            ).filter(
                matching_amenity_count=len(af.amenity_ids)  # All requested amenities must match
            )
        return queryset
    
    @staticmethod
    def _apply_payment_methods(queryset, filters: HotelFilters):
        """Filter by accepted payment methods"""
        pmf = filters.payment_methods
        if pmf.payment_method_ids:
            queryset = queryset.filter(
                payment_methods__method_id__in=pmf.payment_method_ids,
                payment_methods__is_enabled=True
            )
        return queryset
    
    @staticmethod
    def _apply_cancellation_policy(queryset, filters: HotelFilters):
        """Filter by cancellation policy"""
        cpf = filters.cancellation_policy
        
        if cpf.flexible_only:
            queryset = queryset.filter(has_free_cancellation=True)
        
        if cpf.policy_ids:
            queryset = queryset.filter(
                cancellation_policies__policy_id__in=cpf.policy_ids
            )
        
        return queryset
    
    @staticmethod
    def _apply_availability(queryset, filters: HotelFilters):
        """Filter by availability (check_in, check_out dates)"""
        af = filters.availability
        
        if af.check_in_date and af.check_out_date:
            # Check if rooms are available for date range
            # This requires looking up room_inventory
            from datetime import datetime
            try:
                check_in = datetime.strptime(af.check_in_date, '%Y-%m-%d').date()
                check_out = datetime.strptime(af.check_out_date, '%Y-%m-%d').date()
				
                # Only return properties that have available rooms
                if _has_relation(queryset.model, "room_types"):
                    queryset = queryset.filter(
                        room_types__inventory__date__gte=check_in,
                        room_types__inventory__date__lt=check_out,
                        room_types__inventory__available_count__gte=af.rooms
                    ).distinct()
            except ValueError as e:
                logger.warning(f"Invalid date format: {e}")
        
        return queryset
    
    @staticmethod
    def _apply_sorting(queryset, filters: HotelFilters):
        """Apply sort order"""
        sort = filters.sort_by
        
        if sort == SortOption.POPULARITY:
            # Popularity: booking velocity + rating
            from django.db.models import F
            queryset = queryset.order_by('-bookings_this_week', '-rating', '-review_count')
        elif sort == SortOption.RATING:
            queryset = queryset.order_by('-rating', '-review_count')
        elif sort == SortOption.PRICE_LOWEST:
            if _has_relation(queryset.model, "room_types"):
                queryset = queryset.order_by('room_types__base_price')
        elif sort == SortOption.PRICE_HIGHEST:
            if _has_relation(queryset.model, "room_types"):
                queryset = queryset.order_by('-room_types__base_price')
        elif sort == SortOption.NEWEST:
            queryset = queryset.order_by('-created_at')
        elif sort == SortOption.DISTANCE:
            # Distance sorting requires lat/long from filters
            # Can't reliably order by distance in database
            queryset = queryset.order_by('latitude', 'longitude')
        
        return queryset