"""
DRF Serializers for Hotel API v1.

Response contract:
  All list endpoints return:
  {
      "success": true,
      "data": {
          "results": [...],
          "pagination": { "count": N, "next": "url|null", "previous": "url|null" }
      }
  }

  All detail endpoints return:
  {
      "success": true,
      "data": { ... }
  }

  All errors return (via drf_exception_handler):
  {
      "success": false,
      "error": { "code": "...", "message": "...", "detail": null|{} }
  }
"""
from rest_framework import serializers
from apps.hotels.models import Property, PropertyImage, PropertyAmenity, RatingAggregate, PropertyPolicy
from apps.rooms.models import RoomType, RoomImage, RoomAmenity, RoomMealPlan


class PropertyImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'url', 'caption', 'is_featured', 'display_order']

    def get_url(self, obj):
        return obj.resolved_url


class PropertyAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAmenity
        fields = ['name', 'icon']


class RoomImageSerializer(serializers.ModelSerializer):
    """Room-level image serializer — prefers image_url (CDN) over uploaded file."""
    url = serializers.SerializerMethodField()

    class Meta:
        model = RoomImage
        fields = ['id', 'url', 'alt_text', 'is_primary', 'is_featured', 'display_order']

    def get_url(self, obj):
        # Prefer CDN URL; fall back to uploaded file URL
        if obj.image_url:
            return obj.image_url
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return ''


class RoomAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomAmenity
        fields = ['name', 'icon']


class RoomMealPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomMealPlan
        fields = ['code', 'name', 'price_modifier', 'description', 'is_available', 'display_order']


class RoomTypeSerializer(serializers.ModelSerializer):
    """
    Full room type serializer.

    Includes:
      - uuid            — stable UUID for URL routing
      - images          — room-specific gallery (from RoomImage)
      - amenities       — room-specific amenities (from RoomAmenity)
      - meal_plans      — from RoomMealPlan table (fallback to legacy meal_plan field)
      - room_size       — square footage
      - inventory_remaining — live count from RoomInventory (today) or available_count
      - cancellation_policy — 'free' | 'non_refundable' from parent property
    """
    images = RoomImageSerializer(many=True, read_only=True)
    amenities = RoomAmenitySerializer(many=True, read_only=True)
    meal_plans = serializers.SerializerMethodField()
    inventory_remaining = serializers.SerializerMethodField()
    cancellation_policy = serializers.SerializerMethodField()

    class Meta:
        model = RoomType
        fields = [
            'id', 'uuid', 'name', 'description', 'capacity', 'max_occupancy',
            'bed_type', 'meal_plan', 'base_price', 'available_count',
            'room_size', 'images', 'amenities', 'meal_plans',
            'inventory_remaining', 'cancellation_policy',
        ]

    def get_meal_plans(self, obj):
        """Return meal plans from RoomMealPlan table; fallback to legacy meal_plan CharField."""
        qs = obj.meal_plans.filter(is_available=True).order_by('display_order')
        if qs.exists():
            return RoomMealPlanSerializer(qs, many=True).data
        # Legacy fallback: expose the single CharField value as a list
        if obj.meal_plan:
            choices = dict(obj._meta.get_field('meal_plan').choices)
            return [{
                'code': obj.meal_plan,
                'name': choices.get(obj.meal_plan, obj.meal_plan.replace('_', ' ').title()),
                'price_modifier': '0.00',
                'description': '',
                'is_available': True,
                'display_order': 0,
            }]
        return []

    def get_inventory_remaining(self, obj):
        """Return today's live inventory from RoomInventory, fallback to available_count."""
        from datetime import date
        from apps.rooms.models import RoomInventory
        try:
            inv = RoomInventory.objects.get(room_type=obj, date=date.today(), is_closed=False)
            return inv.available_rooms
        except RoomInventory.DoesNotExist:
            return obj.available_count

    def get_cancellation_policy(self, obj):
        """Return 'free' if parent property has free cancellation, else 'non_refundable'."""
        if obj.property and obj.property.has_free_cancellation:
            return 'free'
        return 'non_refundable'


class PropertyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyPolicy
        fields = ['id', 'title', 'description']


class PropertyCardSerializer(serializers.ModelSerializer):
    """
    Compact serializer for listing cards.
    Uses pre-annotated fields (min_room_price, avg_rating) — zero extra queries.
    Includes has_breakfast, rack_rate, available_rooms, cashback_amount, distance_km
    for OTA-grade hotel card UI.
    """
    city_name = serializers.CharField(source='city.name', default='')
    min_price = serializers.SerializerMethodField()
    rack_rate = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    amenity_names = serializers.SerializerMethodField()
    rating_tier = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    room_types_count = serializers.SerializerMethodField()
    recent_bookings = serializers.IntegerField(read_only=True)
    has_breakfast = serializers.SerializerMethodField()
    available_rooms = serializers.SerializerMethodField()
    cashback_amount = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    discount_badge = serializers.SerializerMethodField()
    landmark_distance = serializers.SerializerMethodField()
    trust_badges = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'slug', 'name', 'property_type',
            'city_name', 'area', 'landmark', 'address',
            'latitude', 'longitude',
            'rating', 'review_count', 'star_category',
            'min_price', 'rack_rate',
            'primary_image',
            'amenity_names',
            'rating_tier',
            'has_free_cancellation',
            'pay_at_hotel',
            'is_trending',
            'bookings_today',
            'recent_bookings',
            'tags',
            'image_count',
            'room_types_count',
            'has_breakfast',
            'available_rooms',
            'cashback_amount',
            'distance_km',
            'discount_badge',
            'landmark_distance',
            'trust_badges',
        ]

    def get_min_price(self, obj):
        # Always use annotation — never call .base_price property in a list
        val = getattr(obj, 'min_room_price', None)
        return int(val) if val else 0

    def get_rack_rate(self, obj):
        """Original room price before discounts (for strikethrough display)."""
        val = getattr(obj, 'max_room_price', None)
        min_val = getattr(obj, 'min_room_price', None)
        # Only return rack_rate if it's meaningfully higher than min_price (> 5% diff)
        if val and min_val and float(val) > float(min_val) * 1.05:
            return int(val)
        return None

    def get_primary_image(self, obj):
        # Uses prefetch cache — no extra query
        images = list(obj.images.all())
        img = next((i for i in images if i.is_featured), None) or (images[0] if images else None)
        return img.resolved_url if img else ''

    def get_amenity_names(self, obj):
        # Uses prefetch cache — no extra query
        return [a.name for a in obj.amenities.all()]

    def get_rating_tier(self, obj):
        rating = float(obj.rating or 0)
        if rating >= 4.5:
            return 'excellent'
        if rating >= 3.5:
            return 'good'
        if rating >= 2.5:
            return 'average'
        return 'below_average'

    def get_image_count(self, obj):
        # Uses prefetch cache — no extra query
        return len(list(obj.images.all()))

    def get_room_types_count(self, obj):
        return obj.room_types.count()

    def get_has_breakfast(self, obj):
        """Check if any room type has a breakfast meal plan (CP/R+B)."""
        val = getattr(obj, '_has_breakfast', None)
        if val is not None:
            return val
        # Fallback: check meal plans (uses prefetch if available)
        for rt in obj.room_types.all():
            for mp in rt.meal_plans.all():
                if mp.code in ('CP', 'R+B', 'R+B+L/D', 'AP', 'MAP'):
                    return True
        return False

    def get_available_rooms(self, obj):
        """Total available rooms across all room types."""
        val = getattr(obj, '_available_rooms', None)
        if val is not None:
            return val
        return None

    def get_cashback_amount(self, obj):
        """Cashback amount from search index if annotated."""
        val = getattr(obj, '_cashback_amount', None)
        return float(val) if val else None

    def get_distance_km(self, obj):
        """Distance from search center if annotated by the view."""
        val = getattr(obj, '_distance_km', None)
        return float(val) if val else None

    def get_discount_badge(self, obj):
        """Discount percentage badge for strikethrough display (e.g. '30% OFF')."""
        rack = getattr(obj, 'max_room_price', None)
        min_p = getattr(obj, 'min_room_price', None)
        if rack and min_p and float(rack) > 0:
            discount_pct = int(round((1 - float(min_p) / float(rack)) * 100))
            if discount_pct >= 5:
                return f'{discount_pct}% OFF'
        return None

    def get_landmark_distance(self, obj):
        """
        Nearest landmark distance label (e.g. '500m from MG Road').
        Uses pre-computed GeoIndex or computes on the fly.
        """
        # Try pre-computed from GeoIndex
        try:
            gi = getattr(obj, 'geo_index', None)
            if gi and gi.nearest_landmark:
                return gi.nearest_landmark
        except Exception:
            pass
        # Fallback: compute from property landmark field
        try:
            from apps.core.geo_utils import get_nearby_landmarks_for_property
            landmarks = get_nearby_landmarks_for_property(obj, radius_km=5, limit=1)
            if landmarks:
                return landmarks[0].get('label', '')
        except Exception:
            pass
        return None

    def get_trust_badges(self, obj):
        """Trust badges from HotelQualityScore: Top Rated, Value Pick, Trending."""
        badges = []
        try:
            from apps.core.intelligence import HotelQualityScore
            quality = HotelQualityScore.objects.filter(property=obj).first()
            if quality:
                if quality.is_top_rated:
                    badges.append('Top Rated')
                if quality.is_value_pick:
                    badges.append('Value Pick')
                if getattr(quality, 'is_trending', False):
                    badges.append('Trending')
        except Exception:
            pass
        return badges


class PropertyDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for property detail page.
    Includes rooms (with images+amenities), images gallery, amenities, policies, and rating breakdown.
    Safely handles missing intelligence records (HotelQualityScore, DemandForecast, etc.).
    """
    city_name = serializers.CharField(source='city.name', default='')
    locality_name = serializers.CharField(source='locality.name', default='')
    min_price = serializers.SerializerMethodField()
    images = PropertyImageSerializer(many=True, read_only=True)
    amenities = PropertyAmenitySerializer(many=True, read_only=True)
    room_types = RoomTypeSerializer(many=True, read_only=True)
    policies = PropertyPolicySerializer(many=True, read_only=True)
    rating_tier = serializers.SerializerMethodField()
    rating_breakdown = serializers.SerializerMethodField()
    quality_score = serializers.SerializerMethodField()
    conversion_signals = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'uuid', 'slug', 'name', 'property_type', 'description',
            'city_name', 'locality_name', 'area', 'landmark', 'address', 'country',
            'latitude', 'longitude',
            'rating', 'review_count', 'star_category',
            'min_price',
            'rating_tier',
            'has_free_cancellation', 'cancellation_hours',
            'pay_at_hotel',
            'is_trending', 'bookings_today',
            'tags',
            'images', 'amenities', 'room_types',
            'policies', 'rating_breakdown',
            'quality_score', 'conversion_signals',
        ]

    def get_min_price(self, obj):
        val = getattr(obj, 'min_room_price', None) or obj.base_price
        return int(val) if val else 0

    def get_rating_tier(self, obj):
        rating = float(obj.rating or 0)
        if rating >= 4.5:
            return 'excellent'
        if rating >= 3.5:
            return 'good'
        return 'average'

    def get_rating_breakdown(self, obj):
        """Return the first RatingAggregate entry as a flat dict, or None."""
        try:
            agg = obj.rating_breakdown.first()
        except Exception:
            return None
        if not agg:
            return None
        return {
            'cleanliness': str(agg.cleanliness),
            'service': str(agg.service),
            'location': str(agg.location),
            'amenities': str(agg.amenities),
            'value_for_money': str(agg.value_for_money),
            'total_reviews': agg.total_reviews,
        }

    def get_quality_score(self, obj):
        """Safe access to HotelQualityScore — returns None if missing."""
        try:
            qs = getattr(obj, 'quality_score', None)
            if qs is None:
                return None
            return {
                'overall_score': qs.overall_score,
                'satisfaction_score': qs.satisfaction_score,
                'pricing_score': qs.pricing_score,
                'trust_badges': qs.trust_badges if hasattr(qs, 'trust_badges') else [],
            }
        except Exception:
            return None

    def get_conversion_signals(self, obj):
        """Return conversion optimization signals (scarcity, social proof, etc.)."""
        try:
            from apps.core.intelligence import ConversionSignals
            return ConversionSignals.get_signals(obj)
        except Exception:
            return {}
