"""
DATA CONTRACT SERIALIZER - Converts DB objects to render-ready format

RULE: Backend must send pre-formatted data.
RULE: UI never parses objects, unions, or nested dicts.
"""

from decimal import Decimal


class RenderReadySerializer:
    """Converts database objects to render-ready format for templates."""

    @staticmethod
    def serialize_listing_card(property_obj):
        """
        Convert Property model instance to render-ready card data.
        
        REQUIRED FORMAT:
        {
            "id": int,
            "name": str,
            "location": str,
            "image_url": str or None,
            "rating_value": float,
            "rating_count": int,
            "amenities": ["str", "str"],  # STRING ARRAY ONLY
            "price_current": float,
            "price_original": float or None,
            "discount_percent": float or None,
            "cta_url": str,
            "cta_label": str
        }
        """
        
        # Get first image URL
        image_url = None
        if hasattr(property_obj, 'featured_image') and property_obj.featured_image:
            image_url = property_obj.featured_image.url
        elif hasattr(property_obj, 'images') and property_obj.images.exists():
            image_url = property_obj.images.first().image_url
        
        # Extract amenities as STRING ARRAY ONLY (not dicts)
        amenities = []
        if hasattr(property_obj, 'amenities'):
            amenities = list(property_obj.amenities.values_list('name', flat=True))
        
        # Calculate discount if available
        original_price = None
        current_price = None
        discount_percent = None
        
        if hasattr(property_obj, 'base_price') and property_obj.base_price:
            original_price = float(property_obj.base_price)
            current_price = float(property_obj.base_price)
            
            if hasattr(property_obj, 'discount_price') and property_obj.discount_price:
                current_price = float(property_obj.discount_price)
                discount_percent = round(
                    ((original_price - current_price) / original_price) * 100,
                    1
                )
            elif hasattr(property_obj, 'dynamic_price') and property_obj.dynamic_price:
                current_price = float(property_obj.dynamic_price)
                discount_percent = round(
                    ((original_price - current_price) / original_price) * 100,
                    1
                )
        
        # Rating (flatten if object)
        rating_value = 0
        rating_count = 0
        
        if hasattr(property_obj, 'rating'):
            if isinstance(property_obj.rating, dict):
                rating_value = float(property_obj.rating.get('value', 0))
                rating_count = int(property_obj.rating.get('count', 0))
            else:
                rating_value = float(property_obj.rating) if property_obj.rating else 0
        
        if hasattr(property_obj, 'review_count'):
            rating_count = int(property_obj.review_count) if property_obj.review_count else 0
        
        return {
            "id": property_obj.id,
            "name": property_obj.name or "Unnamed Property",
            "location": f"{property_obj.city}, {property_obj.country}" if hasattr(property_obj, 'city') else "Unknown",
            "image_url": image_url,
            "rating_value": rating_value,
            "rating_count": rating_count,
            "amenities": amenities,  # STRING ARRAY - never dicts
            "price_current": current_price,
            "price_original": original_price,
            "discount_percent": discount_percent,
            "cta_url": f"/hotels/{property_obj.id}/",
            "cta_label": "View Details"
        }

    @staticmethod
    def serialize_listing_cards(queryset):
        """Convert multiple Property objects to cards."""
        return [RenderReadySerializer.serialize_listing_card(obj) for obj in queryset]

    @staticmethod
    def serialize_filters():
        """Serialize filter options (locked structure)."""
        return {
            "locations": [
                "Delhi",
                "Mumbai",
                "Bangalore",
                "Goa",
                "Jaipur",
                "Chennai"
            ],
            "price_ranges": [
                {"min": 0, "max": 3000},
                {"min": 3000, "max": 6000},
                {"min": 6000, "max": 10000},
                {"min": 10000, "max": 50000}
            ],
            "ratings": [5.0, 4.5, 4.0, 3.5, 3.0],
            "amenities": [
                "WiFi",
                "Breakfast",
                "Pool",
                "Gym",
                "Parking",
                "AC",
                "24/7 Support",
                "Restaurant"
            ]
        }