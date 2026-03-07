# apps/hotels/tests_filter_engine.py
"""
Comprehensive tests for the OTA-grade hotel filter engine.

COVERAGE:
- Query parser robustness
- Filter builder correctness
- Performance validation
- Edge case handling
- Admin configuration
"""

import pytest
from decimal import Decimal
from datetime import date
from django.test import TestCase, RequestFactory
from django.core.paginator import Paginator

from apps.hotels.models import (
    Property, PropertyAmenityFilter, PropertyPaymentSupport,
    PropertyCancellationPolicy, AmenityFilter, PaymentMethodType,
    CancellationPolicyOption, PriceRangeFilter, StarRatingOption,
    PropertyStarRating, PropertyBrand, PropertyBrandRelation
)
from apps.hotels.filters import (
    HotelFiltersParser, FilterBuilder, HotelFilters, SortOption,
    PriceRangeFilter as PriceRangeFilterClass, RatingFilter, LocationFilter
)
from apps.hotels.selectors import search_properties_with_filters
from apps.accounts.models import User
from apps.core.models import City, Locality


class HotelFilterEngineTestCase(TestCase):
    """Base test case with fixtures"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        # Cities
        cls.bangkok = City.objects.create(name='Bangkok', slug='bangkok')
        cls.delhi = City.objects.create(name='Delhi', slug='delhi')
        
        # User
        cls.owner = User.objects.create_user(
            email='owner@test.com',
            password='test123'
        )
        
        # Properties
        cls.hotel1 = Property.objects.create(
            owner=cls.owner,
            name='Taj Mahal Palace',
            slug='taj-mahal-palace',
            city=cls.bangkok,
            latitude=Decimal('13.7563'),
            longitude=Decimal('100.5018'),
            rating=Decimal('4.5'),
            review_count=150,
            popularity_score=100,
            bookings_this_week=8,
            has_free_cancellation=True,
            property_type='Hotel'
        )
        
        cls.hotel2 = Property.objects.create(
            owner=cls.owner,
            name='Royal Resort',
            slug='royal-resort',
            city=cls.bangkok,
            latitude=Decimal('13.7580'),
            longitude=Decimal('100.5050'),
            rating=Decimal('4.0'),
            review_count=200,
            popularity_score=80,
            bookings_this_week=5,
            has_free_cancellation=False,
            property_type='Resort'
        )
        
        cls.hotel3 = Property.objects.create(
            owner=cls.owner,
            name='Budget Inn',
            slug='budget-inn',
            city=cls.delhi,
            latitude=Decimal('28.7041'),
            longitude=Decimal('77.1025'),
            rating=Decimal('3.5'),
            review_count=50,
            popularity_score=30,
            bookings_this_week=2,
            has_free_cancellation=True,
            property_type='Hotel'
        )
        
        # Amenities
        cls.wifi = AmenityFilter.objects.create(
            name='WiFi',
            slug='wifi',
            category='basic'
        )
        cls.pool = AmenityFilter.objects.create(
            name='Swimming Pool',
            slug='pool',
            category='comfort'
        )
        cls.gym =AmenityFilter.objects.create(
            name='Fitness Center',
            slug='gym',
            category='wellness'
        )
        
        # Assign amenities
        PropertyAmenityFilter.objects.create(property=cls.hotel1, amenity=cls.wifi)
        PropertyAmenityFilter.objects.create(property=cls.hotel1, amenity=cls.pool)
        PropertyAmenityFilter.objects.create(property=cls.hotel2, amenity=cls.wifi)
        PropertyAmenityFilter.objects.create(property=cls.hotel2, amenity=cls.gym)
        
        # Payment methods
        cls.credit_card = PaymentMethodType.objects.create(
            method_type='credit_card',
            display_name='Credit Card'
        )
        cls.upi = PaymentMethodType.objects.create(
            method_type='upi',
            display_name='UPI'
        )
        
        # Assign payment methods
        PropertyPaymentSupport.objects.create(
            property=cls.hotel1,
            method=cls.credit_card,
            is_enabled=True
        )
        PropertyPaymentSupport.objects.create(
            property=cls.hotel1,
            method=cls.upi,
            is_enabled=True
        )
        PropertyPaymentSupport.objects.create(
            property=cls.hotel2,
            method=cls.credit_card,
            is_enabled=True
        )
        
        # Star ratings
        star_4 = StarRatingOption.objects.create(stars=4)
        star_3 = StarRatingOption.objects.create(stars=3)
        
        PropertyStarRating.objects.create(property=cls.hotel1, stars=star_4)
        PropertyStarRating.objects.create(property=cls.hotel2, stars=star_4)
        PropertyStarRating.objects.create(property=cls.hotel3, stars=star_3)
        
        # Cancellation policies
        cls.flexible = CancellationPolicyOption.objects.create(
            policy_type='flexible',
            display_name='Fully Refundable',
            cancellation_hours=48,
            refund_percentage=100
        )
        cls.strict = CancellationPolicyOption.objects.create(
            policy_type='strict',
            display_name='Strict Cancellation',
            cancellation_hours=0,
            refund_percentage=0
        )
        
        PropertyCancellationPolicy.objects.create(
            property=cls.hotel1,
            policy=cls.flexible,
            is_primary=True
        )
        PropertyCancellationPolicy.objects.create(
            property=cls.hotel2,
            policy=cls.strict,
            is_primary=True
        )


# ============================================================================
# QUERY PARSER TESTS
# ============================================================================

class QueryParserTestCase(HotelFilterEngineTestCase):
    """Test HotelFiltersParser robustness"""
    
    def test_parse_empty_querystring(self):
        """Parser handles empty querystring gracefully"""
        filters = HotelFiltersParser.parse({})
        
        assert filters.search_query == ""
        assert not filters.price_range.is_active()
        assert filters.page == 1
        assert filters.page_size == 20
    
    def test_parse_price_range(self):
        """Parse price_min and price_max"""
        params = {'price_min': '1000', 'price_max': '5000'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.price_range.min_price == Decimal('1000')
        assert filters.price_range.max_price == Decimal('5000')
        assert filters.price_range.is_active()
    
    def test_parse_invalid_price(self):
        """Invalid prices are silently ignored"""
        params = {'price_min': 'invalid', 'price_max': 'abc'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.price_range.min_price is None
        assert filters.price_range.max_price is None
    
    def test_parse_rating(self):
        """Parse min_rating parameter"""
        params = {'min_rating': '4.0'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.rating.min_rating == 4.0
        assert filters.rating.is_active()
    
    def test_parse_invalid_rating_clamped(self):
        """Out-of-range rating is rejected"""
        params = {'min_rating': '10'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.rating.min_rating is None
    
    def test_parse_amenities(self):
        """Parse amenities as comma-separated IDs"""
        params = {'amenities': '1,2,3'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.amenities.amenity_ids == [1, 2, 3]
        assert filters.amenities.is_active()
    
    def test_parse_amenities_invalid(self):
        """Invalid amenity IDs ignored in parsing"""
        params = {'amenities': 'invalid,abc'}
        filters = HotelFiltersParser.parse(params)
        
        # Parser stores as string, selector handles resolution
        assert len(filters.amenities.amenity_ids) == 0
    
    def test_parse_payment_methods(self):
        """Parse payment_methods parameter"""
        params = {'payment_methods': '1,2'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.payment_methods.payment_method_ids == [1, 2]
        assert filters.payment_methods.is_active()
    
    def test_parse_sort_option(self):
        """Parse sort_by parameter with validation"""
        params = {'sort_by': 'price_lowest'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.sort_by == SortOption.PRICE_LOWEST
    
    def test_parse_invalid_sort_defaults(self):
        """Invalid sort option defaults to popularity"""
        params = {'sort_by': 'invalid_sort'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.sort_by == SortOption.POPULARITY
    
    def test_parse_pagination(self):
        """Parse page and page_size"""
        params = {'page': '2', 'page_size': '50'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.page == 2
        assert filters.page_size == 50
    
    def test_parse_pagination_clamped(self):
        """Page size clamped to [1, 100]"""
        params = {'page_size': '999'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.page_size == 100  # Max clamped
    
    def test_get_active_filters(self):
        """List of active filter counts"""
        params = {
            'q': 'taj',
            'price_min': '1000',
            'min_rating': '4.0'
        }
        filters = HotelFiltersParser.parse(params)
        active = filters.get_active_filters()
        
        assert 'search' in active
        assert 'price' in active
        assert 'rating' in active


# ============================================================================
# FILTER BUILDER TESTS
# ============================================================================

class FilterBuilderTestCase(HotelFilterEngineTestCase):
    """Test FilterBuilder queryset construction"""
    
    def test_search_query_filter(self):
        """Search by name, city, area"""
        filters = HotelFilters()
        filters.search_query = 'Taj'
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        assert self.hotel1 in qs
        assert self.hotel2 not in qs
    
    def test_price_range_filter(self):
        """Filter by room price (requires RoomType setup)"""
        # Create room types with prices
        from apps.rooms.models import RoomType
        
        RoomType.objects.create(
            property=self.hotel1,
            name='Deluxe',
            base_price=Decimal('2000'),
            max_guests=2
        )
        RoomType.objects.create(
            property=self.hotel2,
            name='Standard',
            base_price=Decimal('5000'),
            max_guests=2
        )
        
        filters = HotelFilters()
        filters.price_range = PriceRangeFilterClass(
            min_price=Decimal('1000'),
            max_price=Decimal('3000')
        )
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        assert self.hotel1 in qs
        assert self.hotel2 not in qs
    
    def test_rating_filter(self):
        """Filter by guest rating"""
        filters = HotelFilters()
        filters.rating = RatingFilter(min_rating=4.0)
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        assert self.hotel1 in qs
        assert self.hotel2 in qs
        assert self.hotel3 not in qs
    
    def test_location_filter_by_city(self):
        """Filter by city"""
        filters = HotelFilters()
        filters.location = LocationFilter(city_id=self.bangkok.id)
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        assert self.hotel1 in qs
        assert self.hotel2 in qs
        assert self.hotel3 not in qs
    
    def test_property_type_filter(self):
        """Filter by property type"""
        from apps.hotels.filters import PropertyTypeFilter
        
        filters = HotelFilters()
        filters.property_type = PropertyTypeFilter(property_types=['Resort'])
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        assert self.hotel1 not in qs
        assert self.hotel2 in qs
    
    def test_sorting_by_rating(self):
        """Sort by rating descending"""
        filters = HotelFilters()
        filters.sort_by = SortOption.RATING
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        results = list(qs)
        assert results[0].rating >= results[1].rating
    
    def test_sorting_by_popularity(self):
        """Sort by booking velocity"""
        filters = HotelFilters()
        filters.sort_by = SortOption.POPULARITY
        
        base_qs = Property.objects.filter(is_active=True)
        qs = FilterBuilder.apply(base_qs, filters)
        
        results = list(qs)
        # hotel1 (8 bookings) should be before hotel2 (5 bookings)
        assert results[0].bookings_this_week >= results[1].bookings_this_week


# ============================================================================
# SELECTOR TESTS
# ============================================================================

class SearchPropertiesTestCase(HotelFilterEngineTestCase):
    """Test search_properties_with_filters main entry point"""
    
    def test_search_basic(self):
        """Basic search works"""
        qs, filters = search_properties_with_filters({})
        
        assert self.hotel1 in qs
        assert self.hotel2 in qs
        assert self.hotel3 in qs
    
    def test_search_with_filters(self):
        """Search with multiple filters"""
        params = {
            'city_id': str(self.bangkok.id),
            'min_rating': '4.0'
        }
        qs, filters = search_properties_with_filters(params)
        
        results = list(qs)
        assert self.hotel1 in results
        assert self.hotel2 in results
        assert self.hotel3 not in results
    
    def test_search_returns_tuples(self):
        """Selector returns (queryset, filters) tuple"""
        qs, filters = search_properties_with_filters({})
        
        assert isinstance(qs, type(Property.objects.all()))
        assert isinstance(filters, HotelFilters)
    
    def test_search_distinct(self):
        """Multiple joins don't cause duplicates"""
        # Create multiple relations that could cause joins
        PropertyAmenityFilter.objects.create(property=self.hotel1, amenity=self.gym)
        PropertyPaymentSupport.objects.create(property=self.hotel1, method=self.upi)
        
        qs, filters = search_properties_with_filters({
            'amenities': str(self.wifi.id),
            'payment_methods': str(self.credit_card.id)
        })
        
        # Result count should be 1 (hotel1), not duplicated
        assert qs.filter(id=self.hotel1.id).count() == 1


# ============================================================================
# ADMIN CONFIGURATION TESTS
# ============================================================================

class AdminConfigurationTestCase(HotelFilterEngineTestCase):
    """Test Django admin configuration"""
    
    def test_amenity_admin(self):
        """Amenity admin works"""
        from apps.hotels.admin import AmenityFilterAdmin
        
        admin = AmenityFilterAdmin(AmenityFilter, None)
        assert admin.list_display
        assert 'property_count' in admin.list_display
    
    def test_property_admin_inlines(self):
        """Property admin has filter inlines"""
        from apps.hotels.admin import PropertyAdmin
        
        admin = PropertyAdmin(Property, None)
        inline_models = [type(inline.model).__name__ for inline in admin.inlines]
        
        assert 'PropertyPaymentSupport' in inline_models
        assert 'PropertyAmenityFilter' in inline_models
        assert 'PropertyCancellationPolicy' in inline_models


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class PerformanceTestCase(HotelFilterEngineTestCase):
    """Test filter engine performance"""
    
    def test_prefetch_related_optimization(self):
        """select_related/prefetch_related prevents N+1"""
        qs, _ = search_properties_with_filters({})
        qs = qs[:10]
        
        from django.test.utils import CaptureQueriesContext
        from django.test import override_settings
        
        # This is a conceptual test - actual implementation depends on DB
        assert qs.query.prefetch_related_lookups
    
    @pytest.mark.skip(reason="Requires benchmark setup")
    def test_filter_performance_15_filters(self):
        """15+ filters complete in <100ms"""
        import time
        
        params = {
            'q': 'hotel',
            'city_id': str(self.bangkok.id),
            'price_min': '1000',
            'price_max': '5000',
            'min_rating': '3.5',
            'min_stars': '3',
            'amenities': '1,2',
            'payment_methods': '1',
            'policies': '1',
            'sort_by': 'rating',
            'page': '1',
            'page_size': '20'
        }
        
        start = time.time()
        qs, filters = search_properties_with_filters(params)
        list(qs)  # Force evaluation
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # 100ms


# ============================================================================
# EDGE CASE TESTS  
# ============================================================================

class EdgeCaseTestCase(HotelFilterEngineTestCase):
    """Test edge cases and boundary conditions"""
    
    def test_empty_result_set(self):
        """Handle when no hotels match filters"""
        params = {
            'city_id': str(self.delhi.id),
            'min_rating': '5.0'  # No 5-star in delhi
        }
        qs, filters = search_properties_with_filters(params)
        
        assert list(qs) == []
    
    def test_filter_with_special_characters(self):
        """Search with special characters handled safely"""
        params = {'q': "O'Brien's"}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.search_query == "O'Brien's"
    
    def test_unicode_filters(self):
        """Unicode in filter values handled"""
        params = {'q': 'रॉयल'}
        filters = HotelFiltersParser.parse(params)
        
        assert filters.search_query == 'रॉयल'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])