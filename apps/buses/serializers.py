"""
DATA CONTRACT SERIALIZER for Buses - Converts DB objects to render-ready format

RULE: Backend must send pre-formatted data.
RULE: UI never parses objects, unions, or nested dicts.
"""


class BusRenderReadySerializer:
    """Converts Bus model instance to render-ready card data."""

    @staticmethod
    def serialize_listing_card(bus_obj):
        """
        Convert Bus model instance to render-ready card data.
        
        REQUIRED FORMAT:
        {
            "id": int,
            "name": str,
            "from_city": str,
            "to_city": str,
            "departure_time": str,
            "arrival_time": str,
            "bus_type": str,
            "amenities": ["str", "str"],  # STRING ARRAY ONLY
            "price_current": float,
            "cta_url": str,
            "cta_label": str
        }
        """
        
        # Convert amenities to string array
        amenities = bus_obj.get_amenities_list() if bus_obj.amenities else []
        
        # Format times
        departure_time = bus_obj.departure_time.strftime("%H:%M") if bus_obj.departure_time else ""
        arrival_time = bus_obj.arrival_time.strftime("%H:%M") if bus_obj.arrival_time else ""
        
        # Get bus type display name
        bus_type = ""
        if bus_obj.bus_type and hasattr(bus_obj.bus_type, 'get_name_display'):
            bus_type = bus_obj.bus_type.get_name_display()
        
        return {
            "id": bus_obj.id,
            "name": bus_obj.operator_name or "Bus Service",
            "from_city": bus_obj.from_city,
            "to_city": bus_obj.to_city,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "bus_type": bus_type,
            "amenities": amenities,  # STRING ARRAY - never dicts
            "price_current": float(bus_obj.price_per_seat),
            "cta_url": f"/buses/{bus_obj.id}/",
            "cta_label": "Select Seats"
        }

    @staticmethod
    def serialize_listing_cards(queryset):
        """Convert multiple Bus objects to render-ready format."""
        return [BusRenderReadySerializer.serialize_listing_card(bus) for bus in queryset]

    @staticmethod
    def serialize_filters():
        """Return locked filter structure."""
        return {
            "from_city": [],
            "to_city": [],
            "bus_type": [],
        }
