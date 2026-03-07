"""
DEPRECATED: This module has been consolidated into ota_selectors.py
These functions are kept for backwards compatibility only.
All new code MUST use ota_selectors.py instead.
"""
from django.db.models import Q
from apps.hotels.ota_selectors import ota_visible_properties

# Backwards compatibility aliases
def public_properties_queryset():
	"""DEPRECATED: Use ota_visible_properties() instead"""
	return ota_visible_properties()


def get_property_detail(identifier):
	"""DEPRECATED: Use ota_visible_properties().filter(slug|pk=identifier).first() instead"""
	lookup = Q(slug=str(identifier))
	try:
		lookup |= Q(pk=int(identifier))
	except (TypeError, ValueError):
		pass
	return (
		ota_visible_properties()
		# Extra prefetches needed only for the detail page serializer
		.prefetch_related('policies', 'rating_breakdown')
		.filter(lookup)
		.first()
	)


def apply_hotel_filters(queryset, params):
	"""DEPRECATED: Use apps.hotels.ota_selectors.apply_search_filters() instead"""
	# This was a legacy implementation - redirect to new pipeline
	from apps.hotels.ota_selectors import apply_search_filters
	return apply_search_filters(queryset, params)
