"""
OTA FILTER ENGINE - Backend-Driven QuerySet Logic
Enforces 8 Rules with strict data integrity
"""
import logging
from datetime import date, timedelta
from django.db.models import (
    Q, Count, Min, Max, Avg, F, Value, Case, When,
    BooleanField, DecimalField, IntegerField, CharField, OuterRef, Subquery
)
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.core.paginator import Paginator
from django.utils import timezone
from apps.hotels.models import Property
from apps.core.models import City
from apps.rooms.models import RoomInventory
from apps.offers.selectors import get_active_offers_for_property, serialize_offer

logger = logging.getLogger('zygotrip.hotels')


def ota_visible_properties():
    """RULE 1: ZERO HARDCODED COUNTS
    
    Returns base queryset with all approved+signed properties only.
    ALL counts must come from database, not strings or constants.
    
    STRICT RULES:
    - status must be 'approved'
    - agreement_signed must be True
    - Seed data is responsible for creating valid properties
    """
    from apps.search.models import PropertySearchIndex

    search_index = PropertySearchIndex.objects.filter(property_id=OuterRef('pk'))

    return (
        Property.objects
        .filter(status='approved', agreement_signed=True)
        .select_related('owner', 'city')
        .prefetch_related(
            'images', 
            'amenities', 
            'room_types',
            'room_types__amenities',  # Prefetch room-specific amenities
            'room_types__images',      # Prefetch room-specific photos
            'room_types__meal_plans',  # Prefetch meal plans for has_breakfast check
        )
        .annotate(
            # Pricing: computed from RoomType
            min_room_price=Min('room_types__base_price'),
            max_room_price=Max('room_types__base_price'),
            
            # Ratings: Use existing review_count field, compute avg from rating if available
            actual_review_count=F('review_count'),
            avg_rating=Coalesce(F('rating'), Value(0, output_field=DecimalField())),
            
            # Conversion/search signals from the denormalized search index.
            recent_bookings=Coalesce(
                Subquery(
                    search_index.values('recent_bookings')[:1],
                    output_field=IntegerField(),
                ),
                Value(0, output_field=IntegerField()),
            ),
            _available_rooms=Coalesce(
                Subquery(
                    search_index.values('rooms_left')[:1],
                    output_field=IntegerField(),
                ),
                Subquery(
                    search_index.values('available_rooms')[:1],
                    output_field=IntegerField(),
                ),
                Value(0, output_field=IntegerField()),
            ),
            _cashback_amount=Coalesce(
                Subquery(
                    search_index.values('cashback_amount')[:1],
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
            _has_breakfast=Coalesce(
                Subquery(
                    search_index.values('has_breakfast')[:1],
                    output_field=BooleanField(),
                ),
                Value(False, output_field=BooleanField()),
            ),
            _distance_km=Subquery(
                search_index.values('distance_km')[:1],
                output_field=DecimalField(max_digits=6, decimal_places=2),
            ),
        )
    )


def get_popular_areas(queryset, location: str = '') -> list:
    """Return top 8 area/neighbourhood chips for the searched location.

    Used by the listing page to render Goibibo-style "Popular Locations in X" chips.
    Only areas with 1+ properties are included, sorted by property count desc.
    """
    try:
        area_qs = queryset
        if location:
            area_qs = queryset.filter(
                Q(city__name__icontains=location) |
                Q(area__icontains=location) |
                Q(landmark__icontains=location)
            )
        rows = (
            area_qs
            .exclude(area='')
            .exclude(area__isnull=True)
            .values('area')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count')[:8]
        )
        return [{'area': r['area'], 'count': r['count']} for r in rows]
    except Exception:
        return []


def get_filter_counts(queryset):
    """RULE 1: Compute all filter counts from queryset.

    Returns dict with dynamic counts for each filter section.
    NOT hardcoded. NOT preset. Recomputed per request.

    PERFORMANCE: Cached per queryset SQL for 5 minutes to avoid redundant
    COUNT queries on every page load.
    """
    # Build a stable cache key from the queryset SQL + params
    try:
        qs_sql = str(queryset.query)
        cache_key = 'filter_counts_' + str(hash(qs_sql) & 0x7FFFFFFF)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("get_filter_counts: cache HIT key=%s", cache_key)
            return cached
        logger.debug("get_filter_counts: cache MISS key=%s", cache_key)
    except Exception:
        cache_key = None

    base_qs = queryset
    now = timezone.now()

    logger.debug("get_filter_counts: computing dynamic filter counts")

    # Compute amenity counts per display filter term (icontains so "WiFi"→"Free WiFi" etc.)
    # One query per term — acceptable for the fixed set of 8 filter amenities.
    _FILTER_AMENITY_TERMS = ['WiFi', 'Pool', 'Parking', 'Gym', 'Spa', 'Restaurant', 'AC', 'Breakfast']
    amenity_counts = {
        term: base_qs.filter(amenities__name__icontains=term).distinct().count()
        for term in _FILTER_AMENITY_TERMS
    }
    logger.debug("get_filter_counts: amenity_counts=%s", amenity_counts)
    
    counts = {
        # Property Type counts
        'property_types': dict(
            base_qs.values('property_type')
            .annotate(count=Count('id', distinct=True))
            .values_list('property_type', 'count')
        ),
        
        # Cities
        'cities': dict(
            base_qs.values('city__name')
            .annotate(count=Count('id', distinct=True))
            .filter(city__name__isnull=False)
            .values_list('city__name', 'count')
        ),
        
        # Star ratings (based on rating field)
        # Use template-friendly keys (no + or . characters)
        'ratings': {
            'rating_5': base_qs.filter(rating=5).count(),
            'rating_4plus': base_qs.filter(rating__gte=4).count(),
            'rating_3plus': base_qs.filter(rating__gte=3).count(),
            'rating_2plus': base_qs.filter(rating__gte=2).count(),
        },
        
        # User ratings (based on actual reviews)
        # Use 'rating' field directly — safe whether or not avg_rating annotation exists
        # Use template-friendly keys (no + or . characters)
        'user_ratings': {
            'rating_4_5plus': base_qs.filter(rating__gte=4.5).count(),
            'rating_4_0plus': base_qs.filter(rating__gte=4.0).count(),
            'rating_3_5plus': base_qs.filter(rating__gte=3.5).count(),
        },
        
        # Popular filters (keys match frontend fc.free_cancellation, fc.breakfast, fc.pay_at_hotel)
        'free_cancellation': base_qs.filter(has_free_cancellation=True).count(),
        # Breakfast: check both legacy CharField and new RoomMealPlan relation
        'breakfast': base_qs.filter(
            Q(room_types__meal_plan__in=['breakfast', 'half_board', 'full_board', 'all_inclusive']) |
            Q(room_types__meal_plans__code__in=['breakfast', 'half_board', 'full_board', 'all_inclusive'],
              room_types__meal_plans__is_available=True)
        ).distinct().count(),
        'pay_at_hotel': base_qs.filter(pay_at_hotel=True).count(),
        'trending': base_qs.filter(is_trending=True).count(),
        'deals': base_qs.filter(
            offers__offer__is_active=True,
            offers__offer__start_datetime__lte=now,
            offers__offer__end_datetime__gte=now,
        ).distinct().count(),
        
        # Amenities (from PropertyAmenity through FK)
        'amenities': amenity_counts,
    }

    # Write to cache if key was successfully computed (5-minute TTL)
    if cache_key:
        cache.set(cache_key, counts, 300)
        logger.debug("get_filter_counts: cached key=%s ttl=300s", cache_key)

    return counts


def apply_search_filters(queryset, params):
    """RULE 2: URL-STATEFUL SEARCH

    Binds request.GET parameters to QuerySet filtering.
    All search values come from query string, never hardcoded.

    URL format: ?city=...&checkin=...&checkout=...&guests=...
    &min_price=...&max_price=...&free_cancellation=on&sort=...
    """
    # LOCATION: Bind to request params (Rule 2)
    location = (params.get('location', '') or '').strip()
    if location:
        logger.debug("apply_search_filters: location=%s", location)
        queryset = queryset.filter(
            Q(city__name__icontains=location) |
            Q(area__icontains=location) |
            Q(landmark__icontains=location) |
            Q(name__icontains=location)
        )

    # CITY CHECKBOX: Explicit city filter from sidebar
    cities = params.getlist('city')
    if cities:
        queryset = queryset.filter(city__name__in=cities)
    
    # PRICE FILTER: Min/Max from request GET
    min_price = params.get('min_price', '')
    max_price = params.get('max_price', '')
    
    if min_price:
        try:
            min_val = int(min_price)
            logger.debug("apply_search_filters: min_price>=%s", min_val)
            queryset = queryset.filter(min_room_price__gte=min_val)
        except (ValueError, TypeError):
            pass

    if max_price:
        try:
            max_val = int(max_price)
            logger.debug("apply_search_filters: max_price<=%s", max_val)
            queryset = queryset.filter(min_room_price__lte=max_val)
        except (ValueError, TypeError):
            pass

    # CANCELLATION: Checkbox binding (Rule 2)
    if params.get('free_cancellation'):
        logger.debug("apply_search_filters: free_cancellation=True")
        queryset = queryset.filter(has_free_cancellation=True)

    # DEALS: Via PropertyOffer relationship
    if params.get('deals'):
        now = timezone.now()
        logger.debug("apply_search_filters: active deals filter")
        queryset = queryset.filter(
            offers__offer__is_active=True,
            offers__offer__start_datetime__lte=now,
            offers__offer__end_datetime__gte=now,
        ).distinct()

    # OFFER CODE: Filter properties eligible for a specific coupon
    offer_code = (params.get('offer_code') or params.get('offer') or '').strip()
    if offer_code:
        now = timezone.now()
        logger.debug("apply_search_filters: offer_code=%s", offer_code)
        try:
            from apps.offers.models import Offer
            global_offer = Offer.objects.filter(
                is_global=True,
                is_active=True,
                start_datetime__lte=now,
                end_datetime__gte=now,
                coupon_code__iexact=offer_code,
            ).first()
        except Exception:
            global_offer = None

        if not global_offer:
            queryset = queryset.filter(
                offers__offer__is_active=True,
                offers__offer__start_datetime__lte=now,
                offers__offer__end_datetime__gte=now,
                offers__offer__coupon_code__iexact=offer_code,
            ).distinct()

    # OFFER ID: Optional explicit offer id filter
    offer_id = (params.get('offer_id') or '').strip()
    if offer_id:
        now = timezone.now()
        logger.debug("apply_search_filters: offer_id=%s", offer_id)
        queryset = queryset.filter(
            offers__offer__is_active=True,
            offers__offer__start_datetime__lte=now,
            offers__offer__end_datetime__gte=now,
            offers__offer__id=offer_id,
        ).distinct()
    
    # STAR RATING: From property.rating field (Rule 8: real data)
    # Accepts both legacy ?star_5=1 form AND frontend's ?stars=5 form
    ratings_filter = Q()
    if params.get('star_5'):
        ratings_filter |= Q(rating=5)
    if params.get('star_4'):
        ratings_filter |= Q(rating__gte=4)
    if params.get('star_3'):
        ratings_filter |= Q(rating__gte=3)

    # Frontend sends ?stars=5 (single value via updateParam)
    # Filters by star_category (hotel classification 1-5), not user review rating
    stars_val = (params.get('stars') or '').strip()
    if stars_val:
        try:
            s = int(stars_val)
            if 1 <= s <= 5:
                ratings_filter |= Q(star_category=s)
        except (ValueError, TypeError):
            pass

    if ratings_filter:
        queryset = queryset.filter(ratings_filter).distinct()
    
    # USER RATING: From actual review averages (Rule 8: real data)
    # Supports BOTH legacy boolean params AND numeric threshold param:
    #   Legacy: ?rating_4_5=1  ?rating_4=1  ?rating_3_5=1
    #   Modern: ?user_rating=4.5  (Phase 4 — Goibibo parity)
    user_ratings_filter = Q()
    if params.get('rating_4_5'):
        user_ratings_filter |= Q(avg_rating__gte=4.5)
    if params.get('rating_4'):
        user_ratings_filter |= Q(avg_rating__gte=4.0)
    if params.get('rating_3_5'):
        user_ratings_filter |= Q(avg_rating__gte=3.5)

    # Phase 4: numeric threshold param — ?user_rating=4.5 → avg_rating >= 4.5
    user_rating_val = (params.get('user_rating') or '').strip()
    if user_rating_val:
        try:
            threshold = float(user_rating_val)
            user_ratings_filter |= Q(avg_rating__gte=threshold)
        except (ValueError, TypeError):
            pass

    if user_ratings_filter:
        queryset = queryset.filter(user_ratings_filter).distinct()
    
    # PROPERTY TYPE: Checkbox list binding (Rule 2)
    property_types = params.getlist('property_type')
    if property_types:
        queryset = queryset.filter(property_type__in=property_types)
    
    # AMENITIES: Many-to-many checkbox binding (Rule 2)
    # Uses icontains so "WiFi" matches "Free WiFi", "Pool" matches "Swimming Pool", etc.
    amenities = params.getlist('amenity')
    if amenities:
        logger.debug("apply_search_filters: amenities=%s", amenities)
        # All selected amenities must be present (AND logic)
        for amenity_name in amenities:
            queryset = queryset.filter(amenities__name__icontains=amenity_name)
        queryset = queryset.distinct()

    # BREAKFAST INCLUDED: Filter properties that have at least one room with
    # a meal plan that includes breakfast (breakfast, half_board, full_board, all_inclusive)
    # Checks both legacy meal_plan CharField AND new RoomMealPlan relation
    if params.get('breakfast_included') in ('true', '1', 'on', True):
        logger.debug("apply_search_filters: breakfast_included=True")
        breakfast_codes = ['breakfast', 'half_board', 'full_board', 'all_inclusive']
        queryset = queryset.filter(
            Q(room_types__meal_plan__in=breakfast_codes) |
            Q(room_types__meal_plans__code__in=breakfast_codes,
              room_types__meal_plans__is_available=True)
        ).distinct()

    # PAY AT HOTEL: Phase 4 — filter properties where no upfront payment required
    if params.get('pay_at_hotel') in ('true', '1', 'on', True):
        logger.debug("apply_search_filters: pay_at_hotel=True")
        queryset = queryset.filter(pay_at_hotel=True)

    # ROOM AMENITIES: Filter by room-level amenities (distinct from property amenities)
    # ?room_amenity=Bathtub&room_amenity=Safe  (AND logic — all must be present)
    room_amenities = params.getlist('room_amenity')
    if room_amenities:
        logger.debug("apply_search_filters: room_amenities=%s", room_amenities)
        for amen_name in room_amenities:
            queryset = queryset.filter(
                room_types__amenities__name__icontains=amen_name
            )
        queryset = queryset.distinct()

    return queryset


def apply_date_inventory_filter(queryset, params):
    """Filter properties by date-range availability using RoomInventory.
    
    GRACEFUL MODE: If no RoomInventory records exist for the properties in this
    queryset at all, skip date filtering entirely and show all properties.
    This prevents a fresh/empty inventory setup from hiding all results.
    Properties only get excluded if inventory IS tracked AND shows no availability.
    """
    checkin_raw = (params.get("checkin") or params.get("check_in") or "").strip()
    checkout_raw = (params.get("checkout") or params.get("check_out") or "").strip()
    if not checkin_raw or not checkout_raw:
        return queryset

    try:
        checkin_date = date.fromisoformat(checkin_raw)
        checkout_date = date.fromisoformat(checkout_raw)
    except ValueError:
        return queryset

    if checkout_date <= checkin_date:
        return queryset

    logger.debug("apply_date_inventory_filter: %s -> %s", checkin_date, checkout_date)
    nights = (checkout_date - checkin_date).days

    # Check if any inventory records exist for properties in this queryset
    property_ids_in_qs = list(queryset.values_list('id', flat=True))
    if not property_ids_in_qs:
        return queryset

    any_inventory = RoomInventory.objects.filter(
        room_type__property_id__in=property_ids_in_qs
    ).exists()

    if not any_inventory:
        # No inventory tracked yet — show all properties (graceful mode)
        logger.debug("apply_date_inventory_filter: no inventory records found, skipping date filter (graceful mode)")
        return queryset

    inventory_qs = RoomInventory.objects.filter(
        date__gte=checkin_date,
        date__lt=checkout_date,
        available_rooms__gt=0,
        is_closed=False,
        room_type__property_id__in=property_ids_in_qs,
    )
    available_property_ids = (
        inventory_qs.values("room_type__property_id")
        .annotate(available_days=Count("date", distinct=True))
        .filter(available_days__gte=nights)
        .values_list("room_type__property_id", flat=True)
    )
    available_ids_list = list(available_property_ids)

    # Properties with NO inventory tracking at all still show (only exclude if
    # inventory is tracked AND shows blocked/sold-out for the date range)
    tracked_property_ids = list(
        RoomInventory.objects.filter(room_type__property_id__in=property_ids_in_qs)
        .values_list("room_type__property_id", flat=True)
        .distinct()
    )
    untracked_ids = [pid for pid in property_ids_in_qs if pid not in tracked_property_ids]
    show_ids = list(set(available_ids_list) | set(untracked_ids))

    logger.debug(
        "apply_date_inventory_filter: %d available, %d untracked, %d total shown",
        len(available_ids_list), len(untracked_ids), len(show_ids)
    )
    return queryset.filter(id__in=show_ids)


def apply_sorting(queryset, sort_param):
    """RULE 3: SORT PILLS MUST MODIFY QUERYSET

    All sorting is QuerySet.order_by(), not UI cosmetics.
    Results actually reorder based on sort selection.

    Valid values: popular, price_asc, price_desc, rating, newest
    """
    if not sort_param:
        sort_param = 'popular'

    sort_param = sort_param.lower().strip()
    logger.debug("apply_sorting: sort=%s", sort_param)

    if sort_param in ('price_asc', 'price_low', 'price_low_high'):
        return queryset.order_by('min_room_price')

    elif sort_param in ('price_desc', 'price_high', 'price_high_low'):
        return queryset.order_by('-min_room_price')

    elif sort_param in ('rating', 'rating_high', 'best_reviewed', 'rating_desc'):
        return queryset.order_by('-avg_rating', '-actual_review_count')

    elif sort_param in ('newest', 'new'):
        return queryset.order_by('-created_at')

    else:  # 'popular' (default)
        return queryset.order_by('-recent_bookings', '-is_trending', '-updated_at')


def _compute_compare_price(min_price, serialized_offers):
    """Return original pre-discount price when an active offer exists, else None."""
    if not min_price or not serialized_offers:
        return None
    best_offer = max(serialized_offers, key=lambda o: o.get('discount_percentage', 0), default=None)
    if not best_offer:
        return None
    discount_pct = best_offer.get('discount_percentage', 0)
    if discount_pct > 0:
        # work backwards: compare_price * (1 - pct/100) = min_price
        return int(round(min_price / (1 - discount_pct / 100)))
    return None


def _compute_discount_percent(min_price, serialized_offers):
    """Return best offer discount percentage for display on card."""
    if not serialized_offers:
        return None
    pct = max((o.get('discount_percentage', 0) for o in serialized_offers), default=0)
    return pct if pct > 0 else None


def serialize_hotel_card(property_obj):
    """RULE 4: SERIALIZE CARD DATA FROM DATABASE.

    No hardcoded pricing, fake ratings, or placeholder data.
    All values computed from actual model fields.

    PERFORMANCE: Uses annotated fields (min_room_price, avg_rating) to avoid
    additional DB queries. Uses prefetched images/amenities to avoid N+1.
    """
    # Use annotation — never call base_price property (N+1)
    min_price = getattr(property_obj, 'min_room_price', None) or 0

    offers = get_active_offers_for_property(property_obj)
    serialized_offers = [serialize_offer(offer, min_price) for offer in offers]

    # FIX N+1: use prefetched images list, never .exists()/.first()/.filter() on images
    prefetched_images = list(property_obj.images.all())  # uses prefetch cache
    featured = next((img for img in prefetched_images if img.is_featured), None)
    first_image = featured or (prefetched_images[0] if prefetched_images else None)
    image_url = first_image.resolved_url if first_image else ''

    # FIX N+1: use prefetched amenities list, never .values_list() on amenities
    amenities_list = [a.name for a in property_obj.amenities.all()]

    return {
        'id': property_obj.id,
        'slug': property_obj.slug,
        'name': property_obj.name,
        'property_type': property_obj.property_type,

        # Location
        'city': property_obj.city.name if property_obj.city else 'Unknown',
        'area': property_obj.area or '',
        'location': f"{property_obj.city.name if property_obj.city else ''}, {property_obj.area}" if property_obj.area else (property_obj.city.name if property_obj.city else 'Unknown'),
        'landmark': property_obj.landmark or '',
        'address': property_obj.address or '',
        'latitude': float(property_obj.latitude) if property_obj.latitude else None,
        'longitude': float(property_obj.longitude) if property_obj.longitude else None,

        # Pricing: from annotation, never from property method
        'min_price': int(min_price) if min_price else 0,
        'min_room_price': int(min_price) if min_price else 0,

        # Ratings
        'rating': float(property_obj.rating or 0),
        'review_count': property_obj.review_count or 0,
        'star_category': property_obj.star_category,

        # Amenities: from prefetch, no extra query
        'amenities': amenities_list,

        # Image: from prefetch, no extra query
        'image_url': image_url or '',

        # Signals
        'has_free_cancellation': property_obj.has_free_cancellation,
        'pay_at_hotel': property_obj.pay_at_hotel,
        'is_trending': property_obj.is_trending,
        'bookings_today': property_obj.bookings_today if property_obj.bookings_today > 0 else None,
        'offers': serialized_offers,

        # Pricing display: compare_price for strikethrough when offer discount exists
        'compare_price': _compute_compare_price(min_price, serialized_offers),
        'discount_percent': _compute_discount_percent(min_price, serialized_offers),
    }


def get_ota_context(request):
    """RULE 7: BUILD COMPLETE CONTEXT WITH VALIDATED DATA
    
    Returns context dict with:
    - listings: Queryset filtered by request params
    - filter_counts: Dynamic counts from database
    - selected_filters: Current filter state (for UI checkbox binding)
    - sort: Current sort param
    - total_count: Actual result count
    - empty_state_message: Semantic message based on situation
    
    NO fake data. NO hardcoded counts. NO UI illusions.
    """
    params = request.GET
    
    logger.debug("get_ota_context: params=%s", dict(params))

    # Start with base queryset
    base_qs = ota_visible_properties()
    base_count = base_qs.count()  # needed for semantic empty-state message

    # Apply all filters
    filtered_qs = apply_search_filters(base_qs, params)
    filtered_qs = apply_date_inventory_filter(filtered_qs, params)
    
    # Apply sorting (Rule 3)
    sort_param = params.get('sort', 'popular')
    sorted_qs = apply_sorting(filtered_qs, sort_param)

    # Paginate after sorting
    try:
        page_number = int(params.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1
    paginator = Paginator(sorted_qs, 20)
    page_obj = paginator.get_page(page_number)
    
    # Compute filter counts from filtered queryset (Rule 1)
    # This ensures counts only reflect currently available results
    filter_options = get_filter_counts(filtered_qs)
    
    # Serialize hotel cards from database (Rule 4)
    hotels = [
        serialize_hotel_card(prop)
        for prop in page_obj.object_list
    ]
    
    # Track which filters are selected (Rule 5: persistence)
    selected_filters = {
        'location': params.get('location', ''),
        'min_price': params.get('min_price', ''),
        'max_price': params.get('max_price', ''),
        'free_cancellation': bool(params.get('free_cancellation')),
        'deals': bool(params.get('deals')),
        'property_types': params.getlist('property_type'),
        'amenities': params.getlist('amenity'),
        'cities': params.getlist('city'),
        'star_ratings': [k for k in ['star_3', 'star_4', 'star_5'] if params.get(k)],
        'user_ratings': [k for k in ['rating_3_5', 'rating_4', 'rating_4_5'] if params.get(k)],
    }
    
    # RULE 7: Semantic empty state messages
    # Differentiate between: no base properties vs filters removing all
    total_results = paginator.count
    if total_results == 0:
        if base_count == 0:
            # No properties in database at all
            empty_state_message = "No properties available. Please check back soon!"
        else:
            # Properties exist but filters removed them
            empty_state_message = "No properties match your filters. Try adjusting your search."
    else:
        empty_state_message = ""

    # --- Compute popular areas for the searched location (Goibibo-style chips) ---
    location_q = (params.get('location', '') or '').strip()
    popular_areas = []
    try:
        area_qs = (
            base_qs
            .filter(
                Q(city__name__icontains=location_q) |
                Q(area__icontains=location_q) |
                Q(name__icontains=location_q)
            ) if location_q else base_qs
        )
        area_rows = (
            area_qs
            .exclude(area='')
            .values('area')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count')[:8]
        )
        popular_areas = [
            {'area': row['area'], 'count': row['count']}
            for row in area_rows
        ]
    except Exception:
        popular_areas = []

    # --- Search context for sticky top bar ---
    search_location = location_q
    checkin_raw = params.get('checkin', '')
    checkout_raw = params.get('checkout', '')
    adults = params.get('adults', 1)
    children = params.get('children', 0)
    rooms = params.get('rooms', 1)
    try:
        from datetime import datetime as _dt
        checkin_display = _dt.strptime(checkin_raw, '%Y-%m-%d').strftime('%a, %d %b %Y') if checkin_raw else ''
        checkout_display = _dt.strptime(checkout_raw, '%Y-%m-%d').strftime('%a, %d %b %Y') if checkout_raw else ''
        nights_count = (_dt.strptime(checkout_raw, '%Y-%m-%d') - _dt.strptime(checkin_raw, '%Y-%m-%d')).days if (checkin_raw and checkout_raw) else 1
    except Exception:
        checkin_display = checkin_raw
        checkout_display = checkout_raw
        nights_count = 1
    guest_summary = f"{adults} Adult{'s' if int(adults) != 1 else ''}, {rooms} Room{'s' if int(rooms) != 1 else ''}"

    return {
        'hotels': hotels,
        'empty_state': total_results == 0,
        'empty_state_message': empty_state_message,
        'total_count': total_results,
        'base_count': base_count,
        'filter_options': filter_options,
        'selected_filters': selected_filters,
        'current_sort': sort_param,
        'current_query': dict(params),
        'page_obj': page_obj,
        # Search context for top bar
        'search_location': search_location,
        'checkin': checkin_raw,
        'checkout': checkout_raw,
        'checkin_display': checkin_display,
        'checkout_display': checkout_display,
        'nights_count': nights_count,
        'adults': adults,
        'children': children,
        'rooms': rooms,
        'guest_summary': guest_summary,
        # Popular areas chips (Goibibo-style)
        'popular_areas': popular_areas,
    }
