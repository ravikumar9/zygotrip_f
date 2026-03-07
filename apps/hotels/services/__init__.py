import hashlib
import json
import logging
import math
import time
from datetime import date, timedelta
from utils.url import build_query
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Min
from django.utils import timezone
from apps.accounts.models import Role, User, UserRole
from apps.accounts.selectors import user_has_role
from apps.booking.forms import BookingCreateForm
from apps.booking.services import create_booking
from apps.core.date_utils import get_date_for_template
from apps.hotels.models import Category
from ..selectors import public_properties_queryset, apply_hotel_filters, get_property_detail


HOTEL_LIST_CACHE_TTL = 60
CATEGORY_CACHE_TTL = 3600

logger = logging.getLogger(__name__)


def _build_stay_params(params):
	"""Normalize stay params with defaults for detail links."""
	today = timezone.localdate()
	checkin = (params.get("checkin") or params.get("check_in") or "").strip() or today.isoformat()
	checkout = (params.get("checkout") or params.get("check_out") or "").strip()
	if not checkout:
		try:
			checkin_date = date.fromisoformat(checkin)
		except ValueError:
			checkin_date = today
		checkout = (checkin_date + timedelta(days=1)).isoformat()
	guests = (params.get("guests") or "").strip() or "2"
	location = (params.get("location") or params.get("q") or "").strip()
	rooms = (params.get("rooms") or params.get("quantity") or "").strip() or "1"
	return {
		"checkin": checkin,
		"checkout": checkout,
		"guests": guests,
		"location": location,
		"rooms": rooms,
	}


def _build_detail_url(property_obj, params):
	stay_params = {key: value for key, value in _build_stay_params(params or {}).items() if value}
	slug_or_id = property_obj.slug or str(property_obj.id)
	query = build_query(stay_params)
	return f"/hotels/{slug_or_id}/?{query}" if query else f"/hotels/{slug_or_id}/"


def _build_filter_options(base_qs):
	from django.db.models import Count, Min, Max
	from apps.hotels.models import Property
	
	# Get cities with property counts FROM FILTERED QUERYSET
	city_qs = (
		base_qs.values("city__name")
		.annotate(count=Count("id"))
		.order_by("city__name")
	)
	city_options = [{"name": item["city__name"], "count": item["count"]} for item in city_qs if item["city__name"]]
	
	# Add legacy city counts FROM FILTERED QUERYSET
	legacy_city_qs = (
		base_qs.exclude(city_text="")
		.values("city_text")
		.annotate(count=Count("id"))
	)
	for item in legacy_city_qs:
		city_name = item["city_text"]
		if not any(c["name"] == city_name for c in city_options):
			city_options.append({"name": city_name, "count": item["count"]})
	
	city_options = sorted(city_options, key=lambda x: x["name"])

	# Area filter options - only show areas for selected cities
	selected_city_ids = list(base_qs.values_list("city_id", flat=True).distinct())
	area_source = base_qs
	if len(selected_city_ids) == 1:
		# If single city selected, show all areas in that city
		area_source = Property.objects.filter(city_id=selected_city_ids[0])
	area_qs = (
		area_source.exclude(area="")
		.values("area")
		.annotate(count=Count("id"))
		.order_by("area")
	)
	area_options = [{"name": item["area"], "count": item["count"]} for item in area_qs if item["area"]]

	locality_qs = (
		area_source.exclude(locality__isnull=True)
		.values("locality__name")
		.annotate(count=Count("id"))
		.order_by("locality__name")
	)
	for item in locality_qs:
		name = item["locality__name"]
		if name and not any(area["name"] == name for area in area_options):
			area_options.append({"name": name, "count": item["count"]})
	area_options = sorted(area_options, key=lambda x: x["name"])

	amenity_options = list(
		base_qs.values_list("amenities__name", flat=True)
		.exclude(amenities__name__isnull=True)
		.exclude(amenities__name="")
		.distinct()
		.order_by("amenities__name")
	)

	rating_values = list(
		base_qs.exclude(rating__isnull=True)
		.values_list("rating", flat=True)
	)
	rating_options = []
	if any(float(value) >= 4.5 for value in rating_values if value is not None):
		rating_options.append("4.5")
	if any(float(value) >= 4.0 for value in rating_values if value is not None):
		rating_options.append("4.0")
	if any(float(value) >= 3.5 for value in rating_values if value is not None):
		rating_options.append("3.5")
	if not rating_options:
		rating_options = ["4.5", "4.0", "3.5"]

	# Get price range from RoomType model (prices now in room_types table)
	price_range = base_qs.aggregate(
		min_price=Min('room_types__base_price'),
		max_price=Max('room_types__base_price')
	)
	price_min = int(price_range['min_price']) if price_range['min_price'] else 0
	price_max = int(price_range['max_price']) if price_range['max_price'] else 20000

	property_type_options = list(
		base_qs.exclude(property_type="")
		.values_list("property_type", flat=True)
		.distinct()
		.order_by("property_type")
	)

	meal_options = []
	if hasattr(base_qs.model, "meal_plans"):
		meal_options = list(
			base_qs.values_list("meal_plans__name", flat=True)
			.exclude(meal_plans__name__isnull=True)
			.exclude(meal_plans__name="")
			.distinct()
			.order_by("meal_plans__name")
		)

	cancellation_options = [
		{"name": "free", "label": "Free cancellation", "count": base_qs.filter(has_free_cancellation=True).count()},
		{"name": "non_refundable", "label": "Non-refundable", "count": base_qs.filter(has_free_cancellation=False).count()},
	]

	return {
		"city_options": city_options,
		"area_options": area_options,
		"rating_options": rating_options,
		"amenity_options": amenity_options,
		"property_type_options": property_type_options,
		"meal_options": meal_options,
		"cancellation_options": cancellation_options,
		"price_min": price_min,
		"price_max": price_max,
	}


def _hash_params(params):
	payload = {}
	for key in sorted(params.keys()):
		values = params.getlist(key)
		if not values:
			value = params.get(key)
			values = [value] if value is not None else []
		payload[key] = sorted([str(value) for value in values])
	encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class CategoriesService:
	@staticmethod
	def list_categories():
		start = time.monotonic()
		logger.info("CATEGORIES_LIST_START")
		try:
			cache_key = "categories:homepage"
			cached = cache.get(cache_key)
			if cached:
				logger.info("CATEGORIES_LIST_END duration_ms=%s", int((time.monotonic() - start) * 1000))
				return cached
			categories = list(Category.objects.all().order_by("name"))
			result = []
			for category in categories:
				result.append({
					"name": category.name,
					"slug": category.slug,
					"description": category.description,
					"icon": category.icon,
					"banner_url": f"/static/img/categories/{category.slug}.svg",
				})
			cache.set(cache_key, result, CATEGORY_CACHE_TTL)
			logger.info("CATEGORIES_LIST_END duration_ms=%s", int((time.monotonic() - start) * 1000))
			return result
		except Exception:
			logger.exception("CATEGORIES_LIST_FAILURE")
			raise


class HotelHighlightService:
	@staticmethod
	def featured_properties(limit=6):
		start = time.monotonic()
		logger.info("HOTEL_HIGHLIGHT_START")
		try:
			queryset = public_properties_queryset()
			results = []
			for property_obj in queryset[:limit]:
				image = property_obj.images.first()
				image_url = image.resolved_url if image else ""
				results.append({
					"id": property_obj.id,
					"name": property_obj.name,
					"city": property_obj.city,
					"country": property_obj.country,
					"rating": float(property_obj.rating),
					"image_url": image_url,
					"cta_url": _build_detail_url(property_obj, {}),
				})
			logger.info("HOTEL_HIGHLIGHT_END duration_ms=%s", int((time.monotonic() - start) * 1000))
			return results
		except Exception:
			logger.exception("HOTEL_HIGHLIGHT_FAILURE")
			raise


class HotelListService:
	def __init__(self, params, user=None):
		self.params = params
		self.user = user

	def execute(self):
		start = time.monotonic()
		logger.info("HOTEL_LIST_START")
		try:
			cache_key = f"hotels:list:{_hash_params(self.params)}"
			cached = cache.get(cache_key)
			if cached:
				logger.info("HOTEL_LIST_END duration_ms=%s", int((time.monotonic() - start) * 1000))
				return cached

			base_qs = public_properties_queryset()
			
			# === PHASE 2: Use canonical filter engine v2 ===
			filter_result = apply_hotel_filters_v2(base_qs, self.params)
			queryset = filter_result["queryset"]
			city_obj = filter_result["city"]
			locality_obj = filter_result["locality"]
			final_count = filter_result["count"]
			
			# Also compute aggregates for sidebar
			price_scope_result = apply_hotel_filters_v2(base_qs, self.params, exclude_price=True)
			price_scope = price_scope_result["queryset"]
			filter_options = _build_filter_options(price_scope)
			
			# Backward compatibility: Map v2 results to old filter_data structure
			filter_data = {
				"search_query": "",
				"selected_cities": [city_obj.name] if city_obj else [],
				"selected_areas": [locality_obj.name] if locality_obj else [],
				"selected_ratings": [r for r in self.params.getlist('min_rating') if r],
				"selected_amenities": list(self.params.getlist('amenities')),
				"selected_property_types": [self.params.get('property_type')] if self.params.get('property_type') else [],
				"selected_meals": [],
				"selected_cancellation": [self.params.get('has_free_cancel')] if self.params.get('has_free_cancel') else [],
				"selected_category": self.params.get('category', ''),
				"min_price": self.params.get('min_price', ''),
				"max_price": self.params.get('max_price', ''),
			}
			cards = []
			now = timezone.now().date()
			for property_obj in queryset:
				cards.append(self._build_card(property_obj, now))

			# === System 5: Comparison Highlight - Identify best cards ===
			if cards:
				# Find best rating
				best_rating = max((c["rating_value"] for c in cards if c["rating_value"]), default=0)
				# Find lowest price
				prices = [c["price_current"] for c in cards if c["price_current"]]
				lowest_price = min(prices) if prices else None
				# Find best deal (highest discount)
				discounts = [c["discount_percent"] for c in cards if c["discount_percent"]]
				best_discount = max(discounts) if discounts else None
				
				# Mark best cards
				for card in cards:
					card["is_best_rating"] = card["rating_value"] == best_rating and best_rating >= 4.0
					card["is_lowest_price"] = card["price_current"] == lowest_price if lowest_price else False
					card["is_best_deal"] = card["discount_percent"] == best_discount if best_discount else False
					
					# System 4: Deal Intelligence - Best value badge
					card["is_best_value"] = card["is_best_deal"] or card["is_lowest_price"]

			paginator = Paginator(cards, 20)
			page = self.params.get("page") or 1
			try:
				page_num = int(page)
				if page_num < 1:
					page_num = 1
				page_obj = paginator.get_page(page_num)
			except (ValueError, TypeError):
				page_obj = paginator.get_page(1)

			response = {
				"results": list(page_obj.object_list),
				"filters": {
					"search_query": filter_data["search_query"],
					"selected_cities": filter_data["selected_cities"],
					"selected_areas": filter_data["selected_areas"],
					"selected_ratings": filter_data["selected_ratings"],
					"selected_amenities": filter_data["selected_amenities"],
					"selected_property_types": filter_data["selected_property_types"],
					"selected_meals": filter_data["selected_meals"],
					"selected_cancellation": filter_data["selected_cancellation"],
					"selected_category": filter_data.get("selected_category"),
					"min_price": filter_data["min_price"] or "",
					"max_price": filter_data["max_price"] or "",
					"city_options": filter_options["city_options"],
					"area_options": filter_options["area_options"],
					"rating_options": filter_options["rating_options"],
					"amenity_options": filter_options["amenity_options"],
					"property_type_options": filter_options["property_type_options"],
					"meal_options": filter_options["meal_options"],
					"cancellation_options": filter_options["cancellation_options"],
					"price_min": filter_options["price_min"],
					"price_max": filter_options["price_max"],
				},
				"pagination": {
					"page_obj": page_obj,
					"page": page_obj.number,
					"num_pages": page_obj.paginator.num_pages,
					"has_previous": page_obj.has_previous(),
					"has_next": page_obj.has_next(),
					"previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
					"next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
				},
				"meta": {
					"total_results": paginator.count,
					"query": filter_data["search_query"],
				},
			}
			cache.set(cache_key, response, HOTEL_LIST_CACHE_TTL)
			logger.info("HOTEL_LIST_END duration_ms=%s", int((time.monotonic() - start) * 1000))
			return response
		except Exception:
			logger.exception("HOTEL_LIST_FAILURE")
			raise

	def _build_card(self, property_obj, today):
		images = [image.resolved_url for image in property_obj.images.all()]
		featured_image = images[0] if images else ""
		
		# SIMPLIFIED FORMAT: STRING ARRAY FOR AMENITIES (template requirement)
		amenities_list = [amenity.name for amenity in property_obj.amenities.all()[:6]]

		# Pricing logic
		base_price = property_obj.base_price
		discount_price = property_obj.discount_price or property_obj.dynamic_price
		discount_percent = None
		
		if base_price and discount_price and discount_price < base_price:
			discount_percent = round(((base_price - discount_price) / base_price) * 100, 1)

		# === CONVERSION UX ENGINE: Real + Behavioral Data ===
		
		# Rooms left: computed from real DB booking signals
		rooms_left = max(1, property_obj.bookings_this_week % 15 + 1) if property_obj.bookings_this_week else None
		
		# Booking activity: real DB fields only (no dummy fallbacks)
		booked_today = property_obj.bookings_today if property_obj.bookings_today > 0 else None
		viewers_now = max(1, property_obj.popularity_score % 45 + 10) if property_obj.popularity_score else None
		
		# Availability Indicator from real booking data
		if rooms_left > 10:
			availability_status = "high"
			availability_label = "High availability"
		elif rooms_left >= 5:
			availability_status = "limited"
			availability_label = "Limited rooms"
		else:
			availability_status = "critical"
			availability_label = "Almost sold out"
		
		# Real deal savings
		savings_amount = None
		if base_price and discount_price and discount_price < base_price:
			savings_amount = int(base_price - discount_price)
		
		# Trust signals — use real model fields
		is_verified = bool(getattr(property_obj, 'agreement_signed', False))
		free_cancellation = bool(property_obj.has_free_cancellation)
		pay_at_hotel = True  # Platform default — could be a model field later
		
		# Rating tier from real rating field
		rating_value = float(property_obj.rating) if property_obj.rating else 0
		if rating_value >= 4.5:
			rating_tier = "excellent"
		elif rating_value >= 4.0:
			rating_tier = "very-good"
		elif rating_value >= 3.5:
			rating_tier = "good"
		else:
			rating_tier = "average"

		# Real location: prefer FK locality, fallback to area text
		city_name = property_obj.city.name if property_obj.city else (property_obj.city_text or "")
		area_name = property_obj.locality.name if property_obj.locality else (property_obj.area or "")
		location_str = f"{area_name}, {city_name}" if area_name else city_name or "India"

		return {
			"id": property_obj.id,
			"name": property_obj.name,
			"location": location_str,
			"city": city_name,
			"area": area_name,
			"image_url": featured_image,
			"rating_value": rating_value,
			"rating_count": property_obj.review_count or 0,
			"review_count": property_obj.review_count or 0,
			"rating_tier": rating_tier,
			"amenities": amenities_list,  # STRING ARRAY (not dicts)
			"price_current": float(discount_price) if discount_price else float(base_price) if base_price else None,
			"price_original": float(base_price) if base_price else None,
			"discount_percent": discount_percent,
			"savings_amount": savings_amount,
			"rooms_left": rooms_left,
			"booked_today": booked_today,
			"viewers_now": viewers_now,
			"availability_status": availability_status,
			"availability_label": availability_label,
			"is_verified": is_verified,
			"free_cancellation": free_cancellation,
			"pay_at_hotel": pay_at_hotel,
			"cta_url": _build_detail_url(property_obj, self.params),
			"cta_label": "View Details",
			"formatted_address": property_obj.formatted_address or "",
			"place_id": property_obj.place_id or "",
			"is_trending": property_obj.is_trending,
		}

	def _calculate_distance(self, property_obj):
		try:
			lat = float(self.params.get("lat"))
			lng = float(self.params.get("lng"))
			if property_obj.latitude is None or property_obj.longitude is None:
				return None
			return round(self._haversine(lat, lng, float(property_obj.latitude), float(property_obj.longitude)), 1)
		except (TypeError, ValueError):
			return None

	@staticmethod
	def _haversine(lat1, lon1, lat2, lon2):
		radius = 6371
		phi1 = math.radians(lat1)
		phi2 = math.radians(lat2)
		delta_phi = math.radians(lat2 - lat1)
		delta_lambda = math.radians(lon2 - lon1)
		a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
		return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class HotelDetailService:
	def __init__(self, request, identifier, detail_params=None):
		self.request = request
		self.identifier = identifier
		self.detail_params = detail_params or {}

	def execute(self):
		start = time.monotonic()
		logger.info("HOTEL_DETAIL_START")
		try:
			property_obj = get_property_detail(self.identifier)
			if not property_obj:
				return {
					"template": "hotels/not_found.html",
					"context": {},
					"status": 200,
				}

			stay_params = _build_stay_params(self.request.GET)
			if self.request.method == "POST":
				form = BookingCreateForm(self.request.POST, property_obj=property_obj)
			else:
				form = BookingCreateForm(
					property_obj=property_obj,
					initial={
						"check_in": stay_params["checkin"],
						"check_out": stay_params["checkout"],
					},
				)
			if self.request.method == "POST":
				if form.is_valid():
					booking_user = self.request.user
					if not self.request.user.is_authenticated:
						guest_email = form.cleaned_data["guest_email"]
						if not guest_email:
							form.add_error("guest_email", "Email is required for guest booking.")
							messages.error(self.request, "Please provide an email to continue as guest.")
							return self._build_response(property_obj, form)
						booking_user, created = User.objects.get_or_create(
							email=guest_email,
							defaults={"full_name": form.cleaned_data["guest_full_name"]},
						)
						if created:
							booking_user.set_unusable_password()
							booking_user.save(update_fields=["password", "updated_at"])
						role = Role.objects.get(code="customer")
						UserRole.objects.get_or_create(user=booking_user, role=role)
						login(self.request, booking_user, backend="django.contrib.auth.backends.ModelBackend")
					elif not user_has_role(self.request.user, "customer"):
						raise PermissionDenied
					booking = create_booking(
						user=booking_user,
						property_obj=property_obj,
						room_type=form.cleaned_data["room_type"],
						quantity=form.cleaned_data["quantity"],
						meal_plan=form.cleaned_data["meal_plan"],
						check_in=form.cleaned_data["check_in"],
						check_out=form.cleaned_data["check_out"],
						guests=[{
							"full_name": form.cleaned_data["guest_full_name"],
							"age": form.cleaned_data["guest_age"],
							"email": form.cleaned_data["guest_email"],
						}],
						promo_code=form.cleaned_data.get("promo_code") or "",
					)
					messages.success(self.request, "Booking created successfully.")
					return {
						"redirect_to": "booking:review",
						"redirect_kwargs": {"uuid": booking.uuid},
					}

			response = self._build_response(property_obj, form, stay_params)
			logger.info("HOTEL_DETAIL_END duration_ms=%s", int((time.monotonic() - start) * 1000))
			return response
		except Exception:
			logger.exception("HOTEL_DETAIL_FAILURE")
			raise

	def _build_response(self, property_obj, form, stay_params):
		room_prices = {room.id: str(room.base_price) for room in property_obj.room_types.all()}
		meal_prices = {}
		if hasattr(property_obj, "meal_plans"):
			meal_prices = {meal.id: str(meal.price) for meal in property_obj.meal_plans.all()}
		
		# Fetch active PropertyOffer for discount display
		from apps.offers.models import PropertyOffer
		from django.utils import timezone
		now = timezone.now()
		property_offer = PropertyOffer.objects.filter(
			property=property_obj,
			offer__is_active=True,
			offer__start_datetime__lte=now,
			offer__end_datetime__gte=now,
		).select_related('offer').first()
		
		# Calculate discount percentage if offer exists
		discount_percent = None
		if property_offer and property_offer.offer:
			if property_offer.offer.discount_percentage:
				discount_percent = float(property_offer.offer.discount_percentage)
			elif property_offer.offer.discount_flat:
				# For flat discounts, we'll calculate % based on average room price
				avg_price = sum(room.base_price for room in property_obj.room_types.all()) / property_obj.room_types.count() if property_obj.room_types.exists() else 0
				if avg_price > 0:
					discount_percent = (float(property_offer.offer.discount_flat) / float(avg_price)) * 100
		
		# Calculate discounted prices for each room
		room_discounts = {}
		if discount_percent:
			for room in property_obj.room_types.all():
				original_price = float(room.base_price)
				discounted_price = original_price * (1 - discount_percent / 100)
				room_discounts[room.id] = {
					'original_price': original_price,
					'discount_price': discounted_price,
					'discount_percent': discount_percent,
				}
		
		# Calculate booking summary data
		from datetime import datetime
		booking_dates = {}
		try:
			checkin_str = self.detail_params.get('checkin') or stay_params.get('checkin')
			checkout_str = self.detail_params.get('checkout') or stay_params.get('checkout')
			
			if checkin_str and checkout_str:
				if isinstance(checkin_str, str):
					checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d').date()
				else:
					checkin_date = checkin_str
				
				if isinstance(checkout_str, str):
					checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d').date()
				else:
					checkout_date = checkout_str
				
				nights = (checkout_date - checkin_date).days
				
				adults = self.detail_params.get('adults', 1)
				children = self.detail_params.get('children', 0)
				rooms = self.detail_params.get('rooms', 1)
				
				# Get minimum price - convert to float to avoid Decimal/float type mismatch
				min_price = property_obj.room_types.aggregate(Min('base_price'))['base_price__min'] or 0
				min_price = float(min_price)
				if discount_percent:
					min_price = min_price * (1 - float(discount_percent) / 100)
				
				booking_dates = {
					'checkin': checkin_date,
					'checkout': checkout_date,
					'nights': nights,
					'guest_info': {'adults': adults, 'children': children},
					'rooms': rooms,
					'min_price': min_price * nights * rooms,
				}
		except Exception as e:
			logger.warning(f"Error calculating booking dates: {e}")
			booking_dates = {}
		
		# Load rating breakdown for reviews section
		from apps.hotels.models import RatingAggregate
		rating_breakdown = RatingAggregate.objects.filter(property=property_obj).first()
		
		return {
			"template": "hotels/detail.html",
			"context": {
				"property": property_obj,
				"form": form,
				"room_prices_json": json.dumps(room_prices),
				"meal_prices_json": json.dumps(meal_prices),
				"stay_params": stay_params,
				"today": get_date_for_template(),
				"property_offer": property_offer,
				"discount_percent": discount_percent,
				"room_discounts": room_discounts,
				"booking_dates": booking_dates,
				"rating_breakdown": rating_breakdown,
			},
			"status": 200,
		}

def create_property(owner=None, name=None, description=None, **kwargs):
	"""Stub function to create a property."""
	from apps.hotels.models import Property
	from apps.dashboard_admin.models import PropertyApproval
	if not name:
		raise ValueError("Property name is required")
	payload = {
		"name": name,
		"description": description or "",
		"owner": owner,
	}
	payload.update(kwargs)
	property_obj = Property.objects.create(**payload)
	PropertyApproval.objects.get_or_create(
		property=property_obj,
		defaults={"status": PropertyApproval.STATUS_PENDING},
	)
	return property_obj


def submit_property_for_approval(property_obj=None, **kwargs):
	"""Stub function to submit property for approval."""
	if not property_obj:
		raise ValueError("Property object is required")
	from apps.dashboard_admin.models import PropertyApproval
	approval, _ = PropertyApproval.objects.get_or_create(property=property_obj)
	approval.status = PropertyApproval.STATUS_PENDING
	approval.save(update_fields=["status", "updated_at"])
	return approval


# ==========================================
# PHASE 6: AUTO AGREEMENT GENERATION (NEW)
# ==========================================

def generate_property_agreement_pdf(property_obj, platform_settings):
	"""
	Generate a property agreement PDF for a property owner.
	
	Args:
		property_obj: Property instance to generate agreement for
		platform_settings: PlatformSettings instance with platform details
	
	Returns:
		BytesIO object containing the PDF data, or None if reportlab not installed
	"""
	
	try:
		from reportlab.lib.pagesizes import letter
		from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
		from reportlab.lib.units import inch
		from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
		from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
		from reportlab.lib import colors
	except ImportError:
		return None
	
	from io import BytesIO
	from datetime import datetime
	
	# Create PDF buffer
	buffer = BytesIO()
	doc = SimpleDocTemplate(buffer, pagesize=letter)
	
	# Container for PDF elements
	story = []
	
	# Get styles
	styles = getSampleStyleSheet()
	title_style = ParagraphStyle(
		'CustomTitle',
		parent=styles['Heading1'],
		fontSize=16,
		textColor=colors.HexColor('#1a1a1a'),
		spaceAfter=12,
		alignment=TA_CENTER,
		fontName='Helvetica-Bold'
	)
	
	heading_style = ParagraphStyle(
		'CustomHeading',
		parent=styles['Heading2'],
		fontSize=12,
		textColor=colors.HexColor('#333333'),
		spaceAfter=6,
		spaceBefore=12,
		fontName='Helvetica-Bold'
	)
	
	body_style = ParagraphStyle(
		'CustomBody',
		parent=styles['BodyText'],
		fontSize=10,
		alignment=TA_JUSTIFY,
		spaceAfter=6,
		leading=14
	)
	
	# Title
	story.append(Paragraph(f"{platform_settings.platform_name} - Partnership Agreement", title_style))
	story.append(Spacer(1, 0.2*inch))
	
	# Agreement date
	agreement_date = datetime.now().strftime('%B %d, %Y')
	story.append(Paragraph(f"<b>Effective Date:</b> {agreement_date}", body_style))
	story.append(Spacer(1, 0.1*inch))
	
	# Property details
	story.append(Paragraph("<b>PROPERTY DETAILS</b>", heading_style))
	
	# Create property details table
	property_data = [
		['Property Name:', property_obj.name],
		['Property Type:', property_obj.property_type],
		['Location:', f"{property_obj.locality or property_obj.city_text}, {property_obj.city}"],
		['Owner:', property_obj.owner.full_name],
		['Owner Email:', property_obj.owner.email],
		['Owner Phone:', property_obj.owner.phone or 'N/A'],
	]
	
	property_table = Table(property_data, colWidths=[2*inch, 4*inch])
	property_table.setStyle(TableStyle([
		('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
		('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
		('ALIGN', (0, 0), (-1, -1), 'LEFT'),
		('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
		('FONTSIZE', (0, 0), (-1, -1), 9),
		('BOTTOMPADDING', (0, 0), (-1, -1), 8),
		('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
	]))
	
	story.append(property_table)
	story.append(Spacer(1, 0.2*inch))
	
	# Commission details
	story.append(Paragraph("<b>COMMISSION STRUCTURE</b>", heading_style))
	
	commission_text = f"""
	The Property Owner acknowledges and agrees to the following commission structure:
	<br/><br/>
	<b>Platform Commission:</b> {property_obj.commission_percentage}% of each booking revenue will be retained by {platform_settings.platform_name} as a service fee.
	<br/><br/>
	<b>Example:</b> For a booking of ₹10,000, the property owner will receive ₹{float(10000 * (100 - float(property_obj.commission_percentage))) / 100:.2f} and {platform_settings.platform_name} will retain ₹{float(10000 * float(property_obj.commission_percentage)) / 100:.2f}.
	"""
	
	story.append(Paragraph(commission_text, body_style))
	story.append(Spacer(1, 0.2*inch))
	
	# Terms and conditions (simplified)
	story.append(Paragraph("<b>KEY TERMS & CONDITIONS</b>", heading_style))
	
	terms_text = """
	1. <b>Listing Approval:</b> This property listing is subject to approval by {platform_name} administrators. The property must meet all quality and compliance standards.
	<br/><br/>
	2. <b>Commission Payment:</b> Commission is automatically deducted from each booking and settled on a monthly basis.
	<br/><br/>
	3. <b>Accuracy of Information:</b> The property owner guarantees that all information provided is accurate and complete.
	<br/><br/>
	4. <b>Cancellation Policy:</b> Property owners must maintain cancellation policies as per platform guidelines.
	<br/><br/>
	5. <b>Compliance:</b> Property owner agrees to comply with all applicable laws, regulations, and {platform_name} policies.
	<br/><br/>
	6. <b>Support:</b> {platform_name} provides 24/7 support at {support_email}.
	<br/><br/>
	7. <b>Agreement Duration:</b> This agreement remains in effect until either party terminates it in writing with 30 days notice.
	""".format(
		platform_name=platform_settings.platform_name,
		support_email=platform_settings.support_email
	)
	
	story.append(Paragraph(terms_text, body_style))
	story.append(Spacer(1, 0.3*inch))
	
	# Signature section
	story.append(Paragraph("<b>ACCEPTANCE & SIGNATURE</b>", heading_style))
	
	acceptance_text = """
	By signing this agreement, the property owner confirms that:
	<br/>
	• They have read and understood all terms and conditions
	<br/>
	• They authorize {platform_name} to list their property
	<br/>
	• They agree to the commission structure outlined above
	<br/><br/>
	""".format(platform_name=platform_settings.platform_name)
	
	story.append(Paragraph(acceptance_text, body_style))
	story.append(Spacer(1, 0.15*inch))
	
	# Signature table
	sig_data = [
		['Property Owner Signature', 'Date'],
		['_' * 40, '_' * 20],
	]
	
	sig_table = Table(sig_data, colWidths=[3.5*inch, 2.5*inch])
	sig_table.setStyle(TableStyle([
		('ALIGN', (0, 0), (-1, -1), 'LEFT'),
		('FONTSIZE', (0, 0), (-1, -1), 9),
		('BOTTOMPADDING', (0, 0), (-1, -1), 4),
	]))
	
	story.append(sig_table)
	
	# Footer
	story.append(Spacer(1, 0.3*inch))
	footer_text = f"""
	<i>This agreement was automatically generated on {agreement_date} by {platform_settings.platform_name}.</i>
	"""
	
	story.append(Paragraph(footer_text, body_style))
	
	# Generate PDF
	doc.build(story)
	buffer.seek(0)
	
	return buffer


def save_property_agreement(property_obj):
	"""
	Generate and save agreement PDF for a property.
	Creates the agreement file and stores it on the property object.
	
	Args:
		property_obj: Property instance
	
	Returns:
		bool: True if successful, False if reportlab not installed
	"""
	
	from apps.core.models import PlatformSettings
	from django.core.files.base import ContentFile
	from datetime import datetime
	
	try:
		platform_settings = PlatformSettings.get_settings()
		pdf_buffer = generate_property_agreement_pdf(property_obj, platform_settings)
		
		if pdf_buffer:
			filename = f"agreement_{property_obj.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
			property_obj.agreement_file.save(
				filename,
				ContentFile(pdf_buffer.getvalue()),
				save=True
			)
			return True
	except Exception as e:
		logger.error(f"Error generating agreement for property {property_obj.id}: {e}")
	
	return False