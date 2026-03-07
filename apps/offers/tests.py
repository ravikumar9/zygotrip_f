from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.offers.models import Offer, PropertyOffer
from apps.offers.selectors import get_active_offers_for_property
from apps.accounts.models import User
from apps.hotels.models import Property


class OfferTestCase(TestCase):
    
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            email="test@test.com",
            full_name="Test User",
            password="test123"
        )
        
        # Create test property
        self.property = Property.objects.create(
            name="Test Hotel",
            slug="test-hotel",
            owner=self.user,
            property_type="Hotel",
            status="approved",
            agreement_signed=True
        )
        
        # Create global offer
        self.global_offer = Offer.objects.create(
            title="Global 20% Off",
            coupon_code="GLOBAL20",
            offer_type="percentage",
            discount_percentage=Decimal("20"),
            start_datetime=timezone.now() - timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=30),
            is_active=True,
            is_global=True,
            created_by=self.user
        )
        
        # Create property-specific offer
        self.property_offer = Offer.objects.create(
            title="Free Breakfast",
            coupon_code="BREAKFAST",
            offer_type="flat",
            discount_flat=Decimal("500"),
            start_datetime=timezone.now() - timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=15),
            is_active=True,
            is_global=False,
            created_by=self.user
        )
        PropertyOffer.objects.create(offer=self.property_offer, property=self.property)
    
    def test_active_global_offer(self):
        """Global offers should appear for any property"""
        offers = get_active_offers_for_property(self.property)
        self.assertIn(self.global_offer, offers)
    
    def test_property_specific_offer(self):
        """Property-specific offers should only appear for that property"""
        offers = get_active_offers_for_property(self.property)
        self.assertIn(self.property_offer, offers)
    
    def test_expired_offers_excluded(self):
        """Expired offers should not appear"""
        expired_offer = Offer.objects.create(
            title="Expired",
            coupon_code="EXPIRED",
            offer_type="percentage",
            discount_percentage=Decimal("10"),
            start_datetime=timezone.now() - timedelta(days=30),
            end_datetime=timezone.now() - timedelta(days=1),
            is_active=True,
            is_global=True,
            created_by=self.user
        )
        
        offers = get_active_offers_for_property(self.property)
        self.assertNotIn(expired_offer, offers)
    
    def test_disabled_offers_excluded(self):
        """Disabled offers should not appear"""
        disabled_offer = Offer.objects.create(
            title="Disabled",
            coupon_code="DISABLED",
            offer_type="percentage",
            discount_percentage=Decimal("15"),
            start_datetime=timezone.now() - timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=30),
            is_active=False,
            is_global=True,
            created_by=self.user
        )
        
        offers = get_active_offers_for_property(self.property)
        self.assertNotIn(disabled_offer, offers)
