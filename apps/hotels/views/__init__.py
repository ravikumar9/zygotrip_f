import logging
from django.conf import settings
from django.core.management import call_command
from apps.hotels.models import Property
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from ..services import HotelDetailService
from ..ota_selectors import get_ota_context
from ..url_validator import URLParamValidator

logger = logging.getLogger(__name__)


def _ensure_seed_data():
	if not settings.DEBUG:
		return
	if Property.objects.exists():
		return
	call_command("seed_ota_data", verbosity=0)


def hotel_home(request):
	"""LANDING PAGE: Shows search form, recent searches, offers, daily deals
	
	Purpose: User entry point with personalized content
	Serves: landing.html with search form + dynamic sections
	Behavior: Routes to /hotels/hotel-listing/ on form submit
	"""
	try:
		
		from apps.hotels.models import RecentSearch, Category
		from apps.offers.models import Offer, PropertyOffer
		from django.utils import timezone
		
		context = {}
		
		# Recent Searches (user or session based)
		if request.user.is_authenticated:
			recent_searches = RecentSearch.objects.filter(
				user=request.user
			).order_by('-created_at')[:3]
		else:
			session_key = request.session.session_key
			if session_key:
				recent_searches = RecentSearch.objects.filter(
					session_key=session_key
				).order_by('-created_at')[:3]
			else:
				recent_searches = []
		
		context['recent_searches'] = recent_searches
		
		# Active Offers (global + property-specific)
		now = timezone.now()
		active_offers = Offer.objects.filter(
			is_active=True,
			is_global=True,
			start_datetime__lte=now,
			end_datetime__gte=now
		).order_by('-discount_percentage')[:6]
		
		context['offers'] = active_offers
		
		# Daily Deals (properties with active offers today)
		daily_deal_properties = Property.objects.filter(
			status='approved',
			agreement_signed=True,
			offers__offer__is_active=True,
			offers__offer__start_datetime__lte=now,
			offers__offer__end_datetime__gte=now
		).select_related('city').prefetch_related('images', 'offers__offer').distinct()[:6]
		
		context['daily_deals'] = daily_deal_properties
		
		# Destination Categories (Beach Vacations, Mountains, etc.)
		destination_categories = Category.objects.filter(
			is_active=True
		).order_by('display_order', 'name')[:6]
		
		context['destination_categories'] = destination_categories

		return render(request, "hotels/landing.html", context)
	except Exception as e:
		logger.exception(f"HOTEL_HOME_VIEW_FAILURE: {str(e)}")
		return render(request, "hotels/landing.html", {}, status=500)


def hotel_listing(request):
	"""SEARCH RESULTS PAGE: /hotels/hotel-listing/?location=...&checkin=...
	
	Shows filters + hotel listings
	- All params: location, checkin, checkout, rooms, adults, children, min_price, max_price, star, rating, property_type, sort, page
	- URL reproducible: copy-paste URL works identically
	- All 8 Rules enforced:
	  1. ZERO hardcoded counts - all from database
	  2. URL-stateful search with request.GET binding
	  3. Sort pills modify queryset with order_by()
	  4. Hotel card data from database, no placeholders
	  5. Filter counts dynamic from filtered queryset
	  6. Empty state checked against actual result count
	  7. All GET parameters persisted for stateful URLs
	  8. Real data ONLY - no seeding fake values
	"""
	try:
		# Normalize URL parameters to canonical form
		normalized_params = URLParamValidator.normalize_listing_params(request.GET)
		
		# Save recent search for personalization
		location = normalized_params.get('location', '')
		checkin = normalized_params.get('checkin')
		checkout = normalized_params.get('checkout')
		if location and checkin and checkout:
			try:
				from apps.hotels.models import RecentSearch
				from datetime import datetime
				
				# Parse dates
				checkin_date = datetime.strptime(checkin, '%Y-%m-%d').date() if isinstance(checkin, str) else checkin
				checkout_date = datetime.strptime(checkout, '%Y-%m-%d').date() if isinstance(checkout, str) else checkout
				
				# Create recent search entry
				search_data = {
					'search_text': location,
					'checkin': checkin_date,
					'checkout': checkout_date,
					'adults': normalized_params.get('adults', 1),
					'children': normalized_params.get('children', 0),
					'rooms': normalized_params.get('rooms', 1),
				}
				
				if request.user.is_authenticated:
					search_data['user'] = request.user
				else:
					# Create session if doesn't exist
					if not request.session.session_key:
						request.session.create()
					search_data['session_key'] = request.session.session_key
				
				RecentSearch.objects.create(**search_data)
			except Exception as search_save_error:
				# Don't fail the whole request if search save fails
				logger.warning(f"RECENT_SEARCH_SAVE_FAILED: {str(search_save_error)}")
		
		# Build OTA context with strict backend logic
		context = get_ota_context(request)
		
		# Add normalized params to context for template use
		context['normalized_params'] = normalized_params
		context['current_url_params'] = request.GET.urlencode()
		
		# Ensure template gets all required fields
		context['empty_state'] = context.get('empty_state', True)
		context['total_count'] = context.get('total_count', 0)
		context['filter_options'] = context.get('filter_options', {})
		context['selected_filters'] = context.get('selected_filters', {})
		context['current_sort'] = normalized_params.get('sort', 'popular')
		context['current_query'] = normalized_params
		
		return render(request, "hotels/list.html", context)
	
	except Exception as e:
		logger.exception(f"HOTEL_SEARCH_VIEW_FAILURE: {str(e)}")
		# Return empty but valid context on error
		return render(
			request,
			"hotels/list.html",
			{
				'hotels': [],
				'empty_state': True,
				'total_count': 0,
				'filter_options': {},
				'selected_filters': {},
				'current_sort': 'popular',
				'current_query': {},
				'error_message': 'We hit a snag loading hotels. Please try again.',
			},
			status=500
		)


def hotel_details(request):
	"""DETAIL PAGE: /hotels/hotel-details/?property=<slug>
	
	Shows single property with selectable room types
	- Accepts date params: checkin, checkout, adults, children, rooms
	- All params validated and normalized (ISO dates, integers)
	- Detail page DISPLAYS selected dates for room selection
	- Booking form PREPOPULATED with dates and guest breakdown
	- If dates invalid/missing, defaults applied
	
	Query Params:
	  ?property=<slug> (required)
	  &checkin=YYYY-MM-DD (optional)
	  &checkout=YYYY-MM-DD (optional)
	  &adults=N (optional)
	  &children=N (optional)
	  &rooms=N (optional)
	"""
	try:
		# Get property slug from query param
		slug = request.GET.get('property')
		if not slug:
			return render(
				request,
				"hotels/not_found.html",
				{"error_message": "Property not specified."},
				status=400,
			)
		
		# Validate and normalize date params from search flow
		try:
			detail_params = URLParamValidator.normalize_detail_params(request.GET)
		except Exception as param_error:
			logger.warning(f"INVALID_DETAIL_PARAMS: {str(param_error)} - using defaults")
			# Default params if validation fails
			detail_params = {
				'checkin': None,
				'checkout': None,
				'adults': 1,
				'children': 0,
				'rooms': 1
			}
		
		# Call detail service (passes through slug + validated params)
		response = HotelDetailService(request, slug, detail_params=detail_params).execute()
		
		if isinstance(response, dict) and response.get("redirect_to"):
			return redirect(response["redirect_to"], **response.get("redirect_kwargs", {}))
		
		# Add canonical params to context for template
		response["context"]["detail_params"] = detail_params
		response["context"]["canonical_dates"] = {
			'checkin': detail_params.get('checkin'),
			'checkout': detail_params.get('checkout'),
			'adults': detail_params.get('adults'),
			'children': detail_params.get('children'),
			'rooms': detail_params.get('rooms')
		}
		
		# Use OTA-grade detail template
		response["template"] = "hotels/detail_goibibo.html"
		return render(request, response["template"], response["context"], status=response["status"])
	except Exception:
		logger.exception("HOTEL_DETAILS_VIEW_FAILURE")
		return render(
			request,
			"hotels/not_found.html",
			{"error_message": "We could not load this property right now."},
			status=500,
		)


def legacy_property_booking(request, property_id):
	"""Legacy booking entry point used by E2E tests.

	Renders the booking form at /hotels/<property_id>/ with the standard
	booking/create flow while keeping the legacy URL stable.
	"""
	from apps.booking.views import create as booking_create
	try:
		property_obj = Property.objects.get(id=property_id)
		if hasattr(property_obj, "status") and (
			property_obj.status != "approved" or not property_obj.agreement_signed
		):
			return render(
				request,
				"hotels/not_found.html",
				{"error_message": "Property not available."},
				status=404,
			)
	except Property.DoesNotExist:
		return render(
			request,
			"hotels/not_found.html",
			{"error_message": "Property not available."},
			status=404,
		)

	return booking_create(request, property_id)


def hotel_booking(request):
	"""BOOKING PAGE: /hotels/nhotel-booking/?property=<slug>&room_type=<id>...
	
	Shows room selection + guest details form
	- URL: ?property=<slug>&room_type=<id>&checkin=...&checkout=...&adults=...&rooms=...
	- Validates room_type exists for property + inventory available
	- Validates dates and guest counts
	- Displays room details + pricing for selected dates
	- Form collects: guest email, names, contact info
	- On submit: creates Booking record, redirects to /checkout/<booking_reference>/
	
	All params required or validation error.
	"""
	try:
		# Get property slug from query param
		slug = request.GET.get('property')
		if not slug:
			return render(
				request,
				"hotels/not_found.html",
				{"error_message": "Property not specified."},
				status=400,
			)
		
		# Validate strict booking params
		try:
			booking_params = URLParamValidator.normalize_booking_params(request.GET, slug)
		except Exception as param_error:
			logger.warning(f"INVALID_BOOKING_PARAMS for {slug}: {str(param_error)}")
			# Redirect back to detail page if params missing
			detail_url = f"{reverse('hotels:details')}?property={slug}"
			return redirect(detail_url)
		
		# Get property object
		try:
			property_obj = Property.objects.get(slug=slug)
		except Property.DoesNotExist:
			return render(
				request,
				"hotels/not_found.html",
				{"error_message": "Property not found."},
				status=404,
			)
		
		# Get room type object
		from apps.rooms.models import RoomType
		try:
			room_type = RoomType.objects.get(
				id=booking_params['room_type'],
				property=property_obj
			)
		except RoomType.DoesNotExist:
			return render(
				request,
				"hotels/not_found.html",
				{"error_message": "Room type not available."},
				status=404,
			)
		
		# Check inventory availability
		from apps.rooms.models import RoomInventory
		try:
			from datetime import datetime as dt
			checkin_date = dt.strptime(booking_params['checkin'], '%Y-%m-%d').date()
			checkout_date = dt.strptime(booking_params['checkout'], '%Y-%m-%d').date()
			
			# Verify at least 1 room available for entire stay
			inventory_records = RoomInventory.objects.filter(
				room_type=room_type,
				date__gte=checkin_date,
				date__lt=checkout_date
			)
			# Graceful mode: if no inventory records exist, treat as available (owner hasn't configured inventory)
			if not inventory_records.exists():
				min_available = 9999  # Bookable
			else:
				min_available = min((inv.available_rooms for inv in inventory_records), default=0)
			
			if min_available < 1:
				return render(
					request,
					"hotels/not_found.html",
					{"error_message": "Rooms not available for selected dates."},
					status=409,
				)
		except Exception as inv_error:
			logger.error(f"INVENTORY_CHECK_FAILURE: {str(inv_error)}")
			# Don't fail - just continue without full inventory check
			pass
		
		# Wire PriceEngine: Calculate comprehensive pricing
		from apps.pricing.price_engine import PriceEngine
		from apps.offers.models import Offer, PropertyOffer
		from django.utils import timezone
		from datetime import datetime as dt
		checkin_date = dt.strptime(booking_params['checkin'], '%Y-%m-%d').date()
		checkout_date = dt.strptime(booking_params['checkout'], '%Y-%m-%d').date()
		nights = (checkout_date - checkin_date).days
		
		# Get active property offers
		now = timezone.now()
		property_offers = PropertyOffer.objects.filter(
			property=property_obj,
			offer__is_active=True,
			offer__start_datetime__lte=now,
			offer__end_datetime__gte=now
		).select_related('offer')
		
		# Calculate property discount (owner-controlled)
		property_discount_percent = 0
		if property_offers.exists():
			property_discount_percent = float(property_offers.first().offer.discount_percentage)
		
		# Get global offers (admin-controlled)
		global_offers = Offer.objects.filter(
			is_global=True,
			is_active=True,
			start_datetime__lte=now,
			end_datetime__gte=now
		)
		platform_discount_percent = 0
		if global_offers.exists():
			platform_discount_percent = float(global_offers.first().discount_percentage)
		
		# Apply coupon if provided
		coupon_code = (request.GET.get('coupon_code') or request.GET.get('coupon') or '').strip()
		coupon_discount_percent = 0
		applied_coupon = None
		if coupon_code:
			matched_coupon = None
			for offer in global_offers:
				if offer.coupon_code.lower() == coupon_code.lower():
					matched_coupon = offer
					break
			if not matched_coupon:
				for prop_offer in property_offers:
					if prop_offer.offer.coupon_code.lower() == coupon_code.lower():
						matched_coupon = prop_offer.offer
						break
			if matched_coupon:
				coupon_discount_percent = float(matched_coupon.discount_percentage)
				applied_coupon = matched_coupon
		
		price_breakdown = PriceEngine.calculate(
			room_type=room_type,
			nights=nights,
			rooms=booking_params['rooms'],
			property_discount_percent=property_discount_percent,
			platform_discount_percent=platform_discount_percent,
			coupon_discount_percent=coupon_discount_percent
		)
		
		# Get available coupons for display
		available_coupons = []
		for offer in global_offers:
			available_coupons.append({
				'id': offer.id,
				'code': offer.coupon_code,
				'title': offer.title,
				'description': offer.description,
				'discount_percent': float(offer.discount_percentage),
				'max_discount': float(offer.discount_flat) if offer.discount_flat else None,
			})
		for prop_offer in property_offers:
			available_coupons.append({
				'id': prop_offer.offer.id,
				'code': prop_offer.offer.coupon_code,
				'title': prop_offer.offer.title,
				'description': prop_offer.offer.description,
				'discount_percent': float(prop_offer.offer.discount_percentage),
				'max_discount': float(prop_offer.offer.discount_flat) if prop_offer.offer.discount_flat else None,
			})
		
		# Build context for booking page
		# Convert checkin/checkout strings to date objects for template date filters
		from datetime import datetime as _dt
		try:
			checkin_date_obj = _dt.strptime(booking_params['checkin'], '%Y-%m-%d').date()
			checkout_date_obj = _dt.strptime(booking_params['checkout'], '%Y-%m-%d').date()
		except Exception:
			checkin_date_obj = booking_params['checkin']
			checkout_date_obj = booking_params['checkout']

		context = {
			'property': property_obj,
			'room_type': room_type,
			'booking_params': booking_params,
			'checkin': checkin_date_obj,
			'checkout': checkout_date_obj,
			'adults': booking_params['adults'],
			'children': booking_params.get('children', 0),
			'rooms': booking_params['rooms'],
			'num_nights': nights,  # Total nights for stay summary
			'price_breakdown': price_breakdown,  # Wire pricing
			'coupons': available_coupons,  # Wire coupons
			'applied_coupon_code': coupon_code,
			'applied_coupon': applied_coupon,
		}
		
		# Wire BookingContext: persist funnel state for session recovery + analytics
		try:
			from apps.booking.models import BookingContext
			from django.utils import timezone as _tz
			from datetime import timedelta as _td
			session_key = request.session.session_key
			if not session_key:
				request.session.create()
				session_key = request.session.session_key
			booking_user = request.user if request.user.is_authenticated else None
			BookingContext.objects.update_or_create(
				session_key=session_key,
				property=property_obj,
				room_type=room_type,
				context_status=BookingContext.STATUS_ACTIVE,
				defaults={
					'user': booking_user,
					'checkin': checkin_date,
					'checkout': checkout_date,
					'adults': booking_params['adults'],
					'children': booking_params.get('children', 0),
					'rooms': booking_params['rooms'],
					'base_price': price_breakdown['base_price'],
					'property_discount': price_breakdown['property_discount'],
					'platform_discount': price_breakdown['platform_discount'],
					'promo_discount': price_breakdown['coupon_discount'],
					'tax': price_breakdown['gst'],
					'service_fee': price_breakdown['service_fee'],
					'final_price': price_breakdown['final_price'],
					'promo_code': coupon_code if applied_coupon else '',
					'expires_at': _tz.now() + _td(hours=1),
				}
			)
		except Exception as _ctx_err:
			logger.warning(f"BookingContext creation skipped (non-fatal): {_ctx_err}")
		
		# Use OTA-grade booking template
		return render(request, "hotels/booking_goibibo.html", context)
	
	except Exception:
		import traceback
		error_details = traceback.format_exc()
		logger.error(f"HOTEL_BOOKING_VIEW_FAILURE:\n{error_details}")
		print(error_details)  # Also print to console for debugging
		return render(
			request,
			"hotels/error.html",
			{"error_message": "Unable to process booking."},
			status=500,
		)