from django.db import models
from django.utils import timezone
from decimal import Decimal


class Offer(models.Model):
    """Offer model for discounts and promotions"""
    
    OFFER_TYPE_CHOICES = [
        ('percentage', 'Percentage Discount'),
        ('flat', 'Flat Amount Discount'),
        ('bogo', 'Buy One Get One'),
        ('bundle', 'Bundle Offer'),
    ]
    
    title = models.CharField(max_length=200, help_text="Offer title displayed to users")
    description = models.TextField(blank=True, help_text="Detailed offer description")
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE_CHOICES)
    coupon_code = models.CharField(max_length=50, unique=True, help_text="Coupon code for applying offer")
    
    # Discount fields
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, 
        help_text="Percentage discount (0-100)"
    )
    discount_flat = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Flat amount discount"
    )
    
    # Date/Time fields
    start_datetime = models.DateTimeField(
        help_text="When offer becomes active"
    )
    end_datetime = models.DateTimeField(
        help_text="When offer expires"
    )
    
    # Control fields
    is_active = models.BooleanField(default=True)
    is_global = models.BooleanField(
        default=False, 
        help_text="True = applies to all properties. False = specific properties only"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, 
        related_name='created_offers'
    )
    
    class Meta:
        ordering = ['-start_datetime']
        verbose_name = "Offer"
        verbose_name_plural = "Offers"
    
    def __str__(self):
        return f"{self.title} ({self.coupon_code})"
    
    def is_currently_active(self):
        """Check if offer is active right now"""
        now = timezone.now()
        return (
            self.is_active and 
            self.start_datetime <= now <= self.end_datetime
        )
    
    def get_discount_value(self, base_price):
        """Calculate discount amount based on offer type"""
        if self.offer_type == 'percentage':
            return (base_price * self.discount_percentage) / 100
        elif self.offer_type == 'flat':
            return self.discount_flat
        return Decimal('0')


class PropertyOffer(models.Model):
    """Mapping between offers and specific properties"""
    
    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, 
        related_name='applicable_properties'
    )
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='offers'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('offer', 'property')
        verbose_name = "Property Offer"
        verbose_name_plural = "Property Offers"
    
    def __str__(self):
        return f"{self.offer.title} for {self.property.name}"
