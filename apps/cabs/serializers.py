"""
DATA CONTRACT SERIALIZER for Cabs - Converts DB objects to render-ready format

RULE: Backend must send pre-formatted data.
RULE: UI never parses objects, unions, or nested dicts.
"""


class CabRenderReadySerializer:
    """Converts Cab model instance to render-ready card data."""

    @staticmethod
    def serialize_listing_card(cab_obj):
        """
        Convert Cab model instance to render-ready card data.
        
        REQUIRED FORMAT:
        {
            "id": int,
            "name": str,
            "location": str,
            "city": str,
            "seats": int,
            "fuel_type": str,
            "image_url": str or None,
            "price_current": float,
            "cta_url": str,
            "cta_label": str
        }
        """
        
        # Get first primary image, fallback to any image
        image_url = None
        if hasattr(cab_obj, 'images') and cab_obj.images.exists():
            primary_image = cab_obj.images.filter(is_primary=True).first()
            if primary_image:
                image_url = primary_image.image.url if primary_image.image else None
            else:
                image_url = cab_obj.images.first().image.url if cab_obj.images.first().image else None
        
        # Get fuel type display if it's a choice field
        fuel_type = cab_obj.fuel_type
        if hasattr(cab_obj, 'get_fuel_type_display'):
            fuel_type = cab_obj.get_fuel_type_display()
        
        return {
            "id": cab_obj.id,
            "name": cab_obj.name or "Unnamed Cab",
            "location": cab_obj.city or "Unknown",
            "city": cab_obj.city or "Unknown",
            "seats": cab_obj.seats or 0,
            "fuel_type": fuel_type,
            "image_url": image_url,
            "price_current": float(cab_obj.system_price_per_km),
            "cta_url": f"/cabs/{cab_obj.id}/",
            "cta_label": "View Details"
        }

    @staticmethod
    def serialize_listing_cards(queryset):
        """Convert multiple Cab objects to render-ready format."""
        return [CabRenderReadySerializer.serialize_listing_card(cab) for cab in queryset]

    @staticmethod
    def serialize_filters():
        """Return locked filter structure."""
        return {
            "cities": [],
            "seats": [],
            "fuel_types": [],
        }
