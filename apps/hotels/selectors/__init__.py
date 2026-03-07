from django.db.models import Count, Min, Q
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from apps.hotels.models import Property


def _supports_field(model, field_name: str) -> bool:
	try:
		model._meta.get_field(field_name)
		return True
	except FieldDoesNotExist:
		return False


def _supports_relation(model, relation_name: str) -> bool:
	return any(field.name == relation_name for field in model._meta.get_fields())


def public_properties_queryset():
	"""Get ONLY publicly visible properties.
	
	CRITICAL: Must match BOTH conditions:
	- status='approved' (admin approved)
	- agreement_signed=True (owner accepted)
	
	If either is False, NOT visible."""
	filters = {
		"status": "approved",
		"agreement_signed": True,
	}
	if _supports_field(Property, "is_active"):
		filters["is_active"] = True
	return (
		Property.objects.filter(**filters)
		.select_related("owner", "city", "locality")
		.prefetch_related("images", "amenities", "policies", "offers")
		.annotate(
			min_room_price=Min("room_types__base_price"),
		)
	)



def get_property_detail(identifier):
	filters = {
		"status": "approved",
		"agreement_signed": True,
	}
	if _supports_field(Property, "is_active"):
		filters["is_active"] = True
	lookup = Q(slug=str(identifier))
	try:
		lookup |= Q(pk=int(identifier))
	except (TypeError, ValueError):
		pass
	queryset = (
		Property.objects.filter(lookup, **filters)
		.select_related("owner")
		.prefetch_related(
			"images",
			"amenities",
			"policies",
			"offers",
			"room_types",
		)
	)
	property_obj = queryset.first()
	if property_obj or not settings.DEBUG:
		return property_obj
	# In DEBUG, if not found with new system, fallback to checking any property
	fallback_qs = Property.objects.filter(lookup)
	if _supports_field(Property, "is_active"):
		fallback_qs = fallback_qs.filter(is_active=True)
	property_obj = (
		fallback_qs
		.select_related("owner")
		.prefetch_related(
			"images",
			"amenities",
			"policies",
			"offers",
			"room_types",
		)
		.first()
	)
	return property_obj


def _get_list_param(params, key: str):
	if hasattr(params, "getlist"):
		values = params.getlist(key)
	else:
		value = params.get(key)
		values = value if isinstance(value, list) else [value] if value is not None else []
	flattened = []
	for value in values:
		if value is None:
			continue
		parts = [item.strip() for item in str(value).split(",") if item.strip()]
		flattened.extend(parts)
	return flattened


def parse_filters(params):
	search_query = (params.get("q") or params.get("location") or "").strip()
	selected_cities = _get_list_param(params, "city")
	selected_areas = _get_list_param(params, "area")
	selected_ratings = _get_list_param(params, "rating")
	selected_amenities = _get_list_param(params, "amenities")
	selected_property_types = _get_list_param(params, "property_type")
	selected_meals = _get_list_param(params, "meals")
	selected_cancellation = (params.get("cancellation") or "").strip().lower()
	min_price = (params.get("min_price") or "").strip()
	max_price = (params.get("max_price") or "").strip()
	selected_category = (params.get("category") or "").strip()
	return {
		"search_query": search_query,
		"selected_cities": selected_cities,
		"selected_areas": selected_areas,
		"selected_ratings": selected_ratings,
		"selected_amenities": selected_amenities,
		"selected_property_types": selected_property_types,
		"selected_meals": selected_meals,
		"selected_cancellation": selected_cancellation,
		"min_price": min_price,
		"max_price": max_price,
		"selected_category": selected_category,
		"guests": (params.get("guests") or "").strip(),
		"rooms": (params.get("rooms") or params.get("quantity") or "").strip(),
		"checkin": (params.get("checkin") or params.get("check_in") or "").strip(),
		"checkout": (params.get("checkout") or params.get("check_out") or "").strip(),
	}


def apply_hotel_filters(queryset, params, exclude_price: bool = False):
	filters = parse_filters(params)
	search_query = filters["search_query"]
	selected_cities = filters["selected_cities"]
	selected_areas = filters["selected_areas"]
	selected_ratings = filters["selected_ratings"]
	selected_amenities = filters["selected_amenities"]
	selected_property_types = filters["selected_property_types"]
	selected_meals = filters["selected_meals"]
	selected_cancellation = filters["selected_cancellation"]
	min_price = filters["min_price"]
	max_price = filters["max_price"]
	selected_category = filters["selected_category"]
	guests = filters.get("guests")
	rooms = filters.get("rooms")

	if search_query:
		queryset = queryset.filter(
			Q(name__icontains=search_query)
			| Q(city__name__icontains=search_query)
			| Q(city__display_name__icontains=search_query)
			| Q(city_text__icontains=search_query)
			| Q(area__icontains=search_query)
			| Q(locality__name__icontains=search_query)
			| Q(landmark__icontains=search_query)
			| Q(slug__icontains=search_query)
		)

	if selected_cities:
		city_query = Q()
		for city in selected_cities:
			city_query |= Q(city__name__iexact=city)
			city_query |= Q(city__display_name__iexact=city)
			city_query |= Q(city_text__iexact=city)
		queryset = queryset.filter(city_query)

	if selected_areas:
		area_query = Q()
		for area in selected_areas:
			area_query |= Q(area__iexact=area)
			area_query |= Q(locality__name__iexact=area)
		queryset = queryset.filter(area_query)

	if selected_ratings:
		try:
			rating_thresholds = [float(value) for value in selected_ratings]
			min_rating = min(rating_thresholds)
			queryset = queryset.filter(rating__gte=min_rating)
		except (ValueError, TypeError):
			pass

	if min_price and not exclude_price:
		try:
			from decimal import Decimal, InvalidOperation
			min_price_decimal = Decimal(str(min_price).strip())
			queryset = queryset.filter(room_types__base_price__gte=min_price_decimal)
		except (ValueError, TypeError, InvalidOperation):
			pass

	if max_price and not exclude_price:
		try:
			from decimal import Decimal, InvalidOperation
			max_price_decimal = Decimal(str(max_price).strip())
			queryset = queryset.filter(room_types__base_price__lte=max_price_decimal)
		except (ValueError, TypeError, InvalidOperation):
			pass

	if selected_amenities:
		amenity_map = {
			"wifi": "Free WiFi",
			"breakfast": "Breakfast Included",
			"pool": "Swimming Pool",
			"parking": "Parking",
		}
		amenity_names = []
		for value in selected_amenities:
			key = value.lower()
			amenity_names.append(amenity_map.get(key, value))
		queryset = queryset.filter(amenities__name__in=amenity_names).distinct()

	if selected_property_types:
		queryset = queryset.filter(property_type__in=selected_property_types)

	if selected_meals and _supports_relation(queryset.model, "meal_plans"):
		queryset = queryset.filter(meal_plans__name__in=selected_meals).distinct()

	if selected_cancellation == "free":
		queryset = queryset.filter(has_free_cancellation=True)
	elif selected_cancellation == "non_refundable":
		queryset = queryset.filter(has_free_cancellation=False)

	if guests:
		try:
			guest_count = int(guests)
			queryset = queryset.filter(room_types__max_guests__gte=guest_count)
		except (ValueError, TypeError):
			pass

	if rooms:
		try:
			room_count = int(rooms)
			queryset = queryset.filter(room_types__available_count__gte=room_count)
		except (ValueError, TypeError):
			pass

	if selected_category:
		queryset = queryset.filter(categories__category__slug=selected_category)

	filters.update({
		"queryset": queryset,
		"selected_category": selected_category,
	})
	return filters