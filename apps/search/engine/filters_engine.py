"""Filters Engine for search filters."""

from django.db.models import Q


class FiltersEngine:
    """Apply query filters to hotel results."""

    def apply_filters(self, queryset, filters=None):
        if not filters:
            return queryset

        city = (filters.get("city") or "").strip()
        area = (filters.get("area") or "").strip()
        hotel_name = (filters.get("hotel_name") or "").strip()
        rating = filters.get("rating")
        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        amenities = filters.get("amenities") or []

        if city:
            queryset = queryset.filter(Q(city__name__icontains=city) | Q(city_text__icontains=city))

        if hotel_name:
            queryset = queryset.filter(name__icontains=hotel_name)

        if area:
            queryset = queryset.filter(Q(locality__name__icontains=area) | Q(area__icontains=area))

        if rating:
            try:
                rating_value = float(rating)
                queryset = queryset.filter(rating__gte=rating_value)
            except (TypeError, ValueError):
                pass

        if min_price:
            try:
                queryset = queryset.filter(min_room_price__gte=float(min_price))
            except (TypeError, ValueError):
                pass

        if max_price:
            try:
                queryset = queryset.filter(min_room_price__lte=float(max_price))
            except (TypeError, ValueError):
                pass

        if amenities:
            if isinstance(amenities, str):
                amenities = [value.strip() for value in amenities.split(',') if value.strip()]
            queryset = queryset.filter(amenities__name__in=amenities).distinct()

        return queryset

    def get_available_filters(self, queryset):
        return {
            "min_price": queryset.order_by("min_room_price").values_list("min_room_price", flat=True).first(),
            "max_price": queryset.order_by("-min_room_price").values_list("min_room_price", flat=True).first(),
        }




