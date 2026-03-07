"""
Constants for hotels app
Replaces magic numbers with named constants for maintainability
"""

# ============================================================================
# CACHING CONFIGURATION
# ============================================================================

# Cache TTLs (seconds)
CACHE_TTL_HOTEL_LIST = 60  # Search results cached for 1 minute
CACHE_TTL_HOTEL_DETAIL = 300  # Property detail cached for 5 minutes
CACHE_TTL_CATEGORIES = 3600  # Categories cached for 1 hour
CACHE_TTL_SEARCH_RESULTS = 120  # Search with ranking cached for 2 minutes

# Cache key prefixes
CACHE_KEY_PREFIX_HOTEL_LIST = "hotels:list"
CACHE_KEY_PREFIX_CATEGORIES = "categories"
CACHE_KEY_PREFIX_SEARCH = "hotels:search"


# ============================================================================
# PAGINATION
# ============================================================================

DEFAULT_PAGE_SIZE = 20  # Default properties per page
MAX_PAGE_SIZE = 100  # Maximum allowed page size for API
MIN_PAGE_SIZE = 1  # Minimum page size


# ============================================================================
# SEARCH RANKING WEIGHTS
# ============================================================================

# Composite relevance score weights (must sum to 1.0)
RANKING_WEIGHT_RATING = 0.30  # Quality signal (30%)
RANKING_WEIGHT_PRICE = 0.20  # Price competitiveness (20%)
RANKING_WEIGHT_DISTANCE = 0.25  # Proximity to user (25%)
RANKING_WEIGHT_POPULARITY = 0.15  # Booking velocity (15%)
RANKING_WEIGHT_AVAILABILITY = 0.10  # Room availability (10%)


# ============================================================================
# QUALITY THRESHOLDS
# ============================================================================

# Rating thresholds
MIN_RATING_EXCEPTIONAL = 4.8  # "Exceptional" badge
MIN_RATING_TOP_RATED = 4.5  # "Top Rated" badge
MIN_RATING_GOOD = 4.0  # Baseline good quality
MIN_RATING_ACCEPTABLE = 3.5  # Acceptable quality
MAX_RATING_VALUE = 5.0  # Maximum rating value

# Popularity thresholds
MIN_BOOKINGS_TRENDING = 5  # Bookings/day for "Trending" badge
MIN_BOOKINGS_POPULAR = 3  # Bookings/day for "Popular" badge
MIN_BOOKINGS_WEEK_POPULAR = 10  # Bookings/week for popularity signal

# Availability thresholds
MAX_ROOMS_SCARCITY_URGENT = 3  # "Only X rooms left" urgent badge
MAX_ROOMS_SCARCITY_WARNING = 5  # Scarcity warning badge


# ============================================================================
# PRICING
# ============================================================================

# Price thresholds for scoring (INR)
PRICE_THRESHOLD_BUDGET = 1000  # Budget tier
PRICE_THRESHOLD_MODERATE = 2000  # Moderate tier
PRICE_THRESHOLD_PREMIUM = 3000  # Premium tier
PRICE_THRESHOLD_LUXURY = 5000  # Luxury tier
PRICE_THRESHOLD_ULTRA = 8000  # Ultra luxury tier

# Discount thresholds
MIN_DISCOUNT_PERCENTAGE_DISPLAY = 5  # Minimum discount to display badge
SIGNIFICANT_DISCOUNT_PERCENTAGE = 20  # Significant discount threshold


# ============================================================================
# GEOLOCATION
# ============================================================================

EARTH_RADIUS_KM = 6371  # Earth radius for Haversine distance calculation
MAX_DISTANCE_KM_NEARBY = 2  # "Nearby" badge threshold
MAX_DISTANCE_KM_WALKABLE = 5  # Walking distance threshold


# ============================================================================
# TRUST SIGNALS
# ============================================================================

MAX_BADGES_PER_CARD = 3  # Maximum badges to display per property card

# Badge priority (lower = higher priority)
BADGE_PRIORITY = {
    'scarcity': 1,
    'quality': 2,
    'trending': 3,
    'popularity': 4,
    'value': 5,
    'flexibility': 6,
    'location': 7,
}

# Badge levels
BADGE_LEVEL_URGENT = 'urgent'
BADGE_LEVEL_PREMIUM = 'premium'
BADGE_LEVEL_HIGH = 'high'
BADGE_LEVEL_MEDIUM = 'medium'
BADGE_LEVEL_STANDARD = 'standard'


# ============================================================================
# AMENITIES
# ============================================================================

# Number of amenities to display in preview/card
AMENITIES_PREVIEW_COUNT = 5
AMENITIES_CARD_COUNT = 6


# ============================================================================
# IMAGES
# ============================================================================

# Gallery limits
MAX_IMAGES_GALLERY = 20  # Maximum images in gallery
FEATURED_PROPERTIES_COUNT = 6  # Featured properties on homepage


# ============================================================================
# CANCELLATION POLICY
# ============================================================================

MIN_CANCELLATION_HOURS_FLEXIBLE = 48  # Minimum hours for "Flexible" label
DEFAULT_CANCELLATION_HOURS = 24  # Default cancellation window


# ============================================================================
# API CONFIGURATION
# ============================================================================

# Rate limiting (requests per minute)
API_RATE_LIMIT_AUTHENTICATED = 120
API_RATE_LIMIT_ANONYMOUS = 30

# Timeout (seconds)
API_TIMEOUT_DEFAULT = 30


# ============================================================================
# VALIDATION LIMITS
# ============================================================================

# Property validation
MAX_PROPERTY_NAME_LENGTH = 140
MAX_DESCRIPTION_LENGTH = 5000
MIN_HOTEL_RATING = 0.0
MAX_HOTEL_RATING = 5.0

# Room type validation
MIN_ROOM_GUESTS = 1
MAX_ROOM_GUESTS = 10
MIN_ROOM_PRICE = 100  # INR
MAX_ROOM_PRICE = 100000  # INR

# Search query validation
MIN_SEARCH_QUERY_LENGTH = 2
MAX_SEARCH_QUERY_LENGTH = 200
