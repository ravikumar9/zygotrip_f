"""
Offers selector functions for backend-driven offer management
"""
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from apps.offers.models import Offer


def get_active_offers_for_property(property_obj):
    """Get all currently active offers for a specific property
    
    Returns only offers where:
    - is_active=True
    - start_datetime <= now <= end_datetime
    - Offer is either global OR explicitly linked to this property
    """
    now = timezone.now()
    
    return Offer.objects.filter(
        is_active=True,
        start_datetime__lte=now,
        end_datetime__gte=now,
    ).filter(
        Q(is_global=True) | Q(applicable_properties__property=property_obj)
    ).distinct()


def serialize_offer(offer, base_price=None):
    """Convert offer object to dictionary suitable for frontend display
    
    Args:
        offer: Offer object
        base_price: Optional base price to calculate discount on
    
    Returns:
        dict with offer details
    """
    discount_amount = Decimal('0')
    if base_price and offer.offer_type == 'percentage':
        discount_amount = (base_price * offer.discount_percentage) / 100
    elif base_price and offer.offer_type == 'flat':
        discount_amount = offer.discount_flat
    
    return {
        'id': offer.id,
        'title': offer.title,
        'description': offer.description,
        'offer_type': offer.offer_type,
        'coupon_code': offer.coupon_code,
        'discount_percentage': float(offer.discount_percentage),
        'discount_flat': float(offer.discount_flat),
        'discount_amount': float(discount_amount) if base_price else 0,
        'is_currently_active': offer.is_currently_active(),
    }


def get_offers_context(property_obj=None):
    """Build offers context for templates
    
    Args:
        property_obj: Optional property to get offers for
    
    Returns:
        dict with offers data
    """
    if property_obj:
        offers = get_active_offers_for_property(property_obj)
        serialized_offers = [serialize_offer(offer) for offer in offers]
    else:
        # Return all active global offers
        now = timezone.now()
        offers = Offer.objects.filter(
            is_active=True,
            is_global=True,
            start_datetime__lte=now,
            end_datetime__gte=now
        )
        serialized_offers = [serialize_offer(offer) for offer in offers]
    
    return {
        'offers': serialized_offers,
        'offer_count': len(serialized_offers),
        'has_offers': len(serialized_offers) > 0,
    }
