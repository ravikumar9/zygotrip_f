from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from datetime import datetime
from apps.accounts.selectors import user_has_role
from .forms import BookingCreateForm
from apps.payments.services import process_payment
from apps.wallet.services import get_or_create_wallet
from .selectors import get_booking_or_403, get_property_or_404
from .services import create_simple_booking, transition_booking_status


@login_required
def create(request, property_id):
	"""
	Create a new booking and redirect to review.
	GET: Show booking form with hotel details
	POST: Create booking and go to review
	"""
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	
	# Get property
	property_obj = get_property_or_404(property_id)
	
	if request.method == 'POST':
		form = BookingCreateForm(request.POST, property_obj=property_obj)
		if form.is_valid():
			try:
				booking = create_simple_booking(request.user, property_obj, form)
			except ValueError:
				messages.error(request, 'Check-out date must be after check-in date.')
				return render(request, 'booking/create.html', {
					'form': form,
					'property': property_obj,
				})
			messages.success(request, 'Booking created. Please review and confirm.')
			return redirect('booking:review', uuid=booking.uuid)
	else:
		form = BookingCreateForm(property_obj=property_obj)
	
	return render(request, 'booking/create.html', {
		'form': form,
		'property': property_obj
	})


@login_required
def review(request, uuid):
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	booking = get_booking_or_403(request.user, uuid)
	if booking.status not in [booking.STATUS_REVIEW, booking.STATUS_PAYMENT]:
		raise PermissionDenied
	if request.method == 'POST':
		transition_booking_status(booking, booking.STATUS_PAYMENT)
		return redirect('booking:payment', uuid=booking.uuid)
	nights = (booking.check_out - booking.check_in).days
	return render(request, 'booking/review.html', {'booking': booking, 'nights': nights})


@login_required
def payment(request, uuid):
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	booking = get_booking_or_403(request.user, uuid)
	# Accept HOLD (new goibibo-style flow) or PAYMENT (legacy review flow)
	if booking.status not in [booking.STATUS_PAYMENT, booking.STATUS_HOLD]:
		raise PermissionDenied
	if request.method == 'POST':
		use_wallet = request.POST.get('use_wallet') == 'on'
		if use_wallet:
			from apps.wallet.services import use_wallet_for_payment, check_wallet_balance
			can_pay = check_wallet_balance(request.user, booking.total_amount)
			if not can_pay:
				messages.error(request, 'Insufficient wallet balance.')
				wallet = get_or_create_wallet(request.user)
				return render(request, 'booking/payment.html', {'booking': booking, 'wallet': wallet})
			success, err = use_wallet_for_payment(
				user=request.user,
				amount=booking.total_amount,
				booking_reference=booking.public_booking_id or str(booking.uuid)
			)
			if not success:
				messages.error(request, f'Wallet payment failed: {err}')
				wallet = get_or_create_wallet(request.user)
				return render(request, 'booking/payment.html', {'booking': booking, 'wallet': wallet})
		else:
			# Non-wallet: initiate gateway payment via REST API
			# Legacy template view — redirects user to the Next.js payment page
			from django.shortcuts import redirect as _redir
			return _redir(f'/payment/{booking.uuid}/')
		transition_booking_status(booking, booking.STATUS_CONFIRMED)
		messages.success(request, 'Payment successful. Your booking is confirmed!')
		return redirect('booking:success', uuid=booking.uuid)
	wallet = get_or_create_wallet(request.user)
	return render(request, 'booking/payment.html', {'booking': booking, 'wallet': wallet})


@login_required
def success(request, uuid):
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	booking = get_booking_or_403(request.user, uuid)
	if booking.status != booking.STATUS_CONFIRMED:
		raise PermissionDenied
	return render(request, 'booking/success.html', {'booking': booking})


@login_required
@require_http_methods(["POST"])
def cancel(request, uuid):
	"""API endpoint to cancel booking (called when timer expires)"""
	if not user_has_role(request.user, 'customer'):
		return JsonResponse({'error': 'Unauthorized'}, status=403)
	
	try:
		booking = get_booking_or_403(request.user, uuid)
	except PermissionError:
		return JsonResponse({'error': 'Booking not found'}, status=404)
	
	# Only cancel if still in review or payment status
	if booking.status in [booking.STATUS_REVIEW, booking.STATUS_PAYMENT]:
		transition_booking_status(booking, booking.STATUS_CANCELLED, note='Cancelled due to timer expiry')
		return JsonResponse({'success': True, 'message': 'Booking cancelled'})
	
	return JsonResponse({'error': 'Cannot cancel booking'}, status=400)


@login_required
def checkout(request, booking_reference):
	"""PHASE 1: Checkout/Payment page with booking reference
	
	URL: /checkout/<booking_reference>/
	- Validates booking_reference points to valid booking
	- Checks user owns booking (or is guest with access)
	- Shows final pricing breakdown
	- Provides payment method selection (wallet, card, netbanking, etc)
	- On submit: processes payment and goes to success page
	"""
	try:
		from .models import Booking
		# Try to find booking by public_booking_id (BK-YYYYMMDD-HTL-XXXXXXXX)
		booking = Booking.objects.get(public_booking_id=booking_reference)
		
		# Verify user access (either owner or guest user)
		if not request.user.is_authenticated:
			messages.error(request, 'Please login to continue payment.')
			return redirect('account_login')
		
		if booking.user != request.user:
			# Check if user has customer role
			if not user_has_role(request.user, 'customer'):
				raise PermissionDenied
		
		if booking.status != booking.STATUS_PAYMENT:
			raise PermissionDenied(f'Booking must be in payment status, currently: {booking.status}')
		
		if request.method == 'POST':
			use_wallet = request.POST.get('use_wallet') == 'on'
			payment_method = 'wallet' if use_wallet else None
			process_payment(booking=booking, payment_method=payment_method)
			transition_booking_status(booking, booking.STATUS_CONFIRMED)
			messages.success(request, 'Payment successful.')
			return redirect('booking:success', uuid=booking.uuid)
		
		wallet = get_or_create_wallet(request.user)
		nights = (booking.check_out - booking.check_in).days
		
		return render(request, 'booking/checkout.html', {
			'booking': booking,
			'booking_reference': booking_reference,
			'wallet': wallet,
			'nights': nights,
		})
	
	except Exception as e:
		import logging
		logger = logging.getLogger(__name__)
		logger.exception(f"CHECKOUT_VIEW_FAILURE: {str(e)}")
		messages.error(request, 'Unable to load checkout. Please try again.')
		return render(
			request,
			'booking/error.html',
			{'error_message': 'Booking not found or access denied.'},
			status=404,
		)


@login_required
@require_POST
def create_booking_from_form(request):
	"""Create booking from guest form submission and redirect to payment page.
	
	POST /checkout/create-booking/
	
	Creates Booking with UUID and all related records, then redirects to
	/booking/<uuid>/payment/ for payment processing.
	
	Required POST params:
	- property_id
	- room_type_id
	- checkin (YYYY-MM-DD)
	- checkout (YYYY-MM-DD)
	- adults
	- rooms
	- guest_email
	- guest_first_name
	- guest_last_name
	- guest_phone
	
	Optional:
	- children
	- coupon_code
	- special_requests
	"""
	import logging
	logger = logging.getLogger(__name__)
	
	try:
		# Extract form data
		property_id = request.POST.get('property_id')
		room_type_id = request.POST.get('room_type_id')
		checkin_str = request.POST.get('checkin')
		checkout_str = request.POST.get('checkout')
		adults = int(request.POST.get('adults', 1))
		children = int(request.POST.get('children', 0))
		rooms = int(request.POST.get('rooms', 1))
		coupon_code = request.POST.get('coupon_code', '').strip()
		
		# Guest details - matching guest_form.html field names
		guest_email = request.POST.get('email', '').strip()
		guest_first_name = request.POST.get('first_name', '').strip()
		guest_last_name = request.POST.get('last_name', '').strip()
		guest_phone = request.POST.get('phone', '').strip()
		special_requests = request.POST.get('special_requests', '').strip()
		
		# Validate required fields
		if not all([property_id, room_type_id, checkin_str, checkout_str, guest_email, guest_first_name, guest_phone]):
			messages.error(request, 'Please fill all required fields.')
			return redirect(request.META.get('HTTP_REFERER', '/'))
		
		# Parse dates
		from datetime import datetime as dt
		checkin_date = dt.strptime(checkin_str, '%Y-%m-%d').date()
		checkout_date = dt.strptime(checkout_str, '%Y-%m-%d').date()
		
		# Validate dates
		if checkout_date <= checkin_date:
			messages.error(request, 'Check-out must be after check-in.')
			return redirect(request.META.get('HTTP_REFERER', '/'))
		
		# Get property and room type
		from apps.hotels.models import Property
		from apps.rooms.models import RoomType
		
		try:
			property_obj = Property.objects.get(id=property_id)
		except Property.DoesNotExist:
			messages.error(request, 'Property not found.')
			return redirect('hotels:listing')
		
		try:
			room_type = RoomType.objects.get(id=room_type_id, property=property_obj)
		except RoomType.DoesNotExist:
			messages.error(request, 'Room type not available.')
			return redirect('hotels:details', property=property_obj.slug)
		
		# Calculate pricing with PriceEngine
		from apps.pricing.price_engine import PriceEngine
		from apps.offers.models import Offer, PropertyOffer
		from django.utils import timezone
		
		nights = (checkout_date - checkin_date).days
		
		# Get active offers
		now = timezone.now()
		property_offers = PropertyOffer.objects.filter(
			property=property_obj,
			offer__is_active=True,
			offer__start_datetime__lte=now,
			offer__end_datetime__gte=now
		).select_related('offer')
		
		global_offers = Offer.objects.filter(
			is_global=True,
			is_active=True,
			start_datetime__lte=now,
			end_datetime__gte=now
		)
		
		# Calculate discounts
		property_discount_percent = 0
		if property_offers.exists():
			property_discount_percent = float(property_offers.first().offer.discount_percentage)
		
		platform_discount_percent = 0
		if global_offers.exists():
			platform_discount_percent = float(global_offers.first().discount_percentage)
		
		# Apply coupon
		coupon_discount_percent = 0
		applied_coupon = None
		if coupon_code:
			for offer in global_offers:
				if offer.coupon_code and offer.coupon_code.lower() == coupon_code.lower():
					applied_coupon = offer
					coupon_discount_percent = float(offer.discount_percentage)
					break
			if not applied_coupon:
				for prop_offer in property_offers:
					if prop_offer.offer.coupon_code and prop_offer.offer.coupon_code.lower() == coupon_code.lower():
						applied_coupon = prop_offer.offer
						coupon_discount_percent = float(prop_offer.offer.discount_percentage)
						break
		
		# Calculate final pricing
		price_breakdown = PriceEngine.calculate(
			room_type=room_type,
			nights=nights,
			rooms=rooms,
			property_discount_percent=property_discount_percent,
			platform_discount_percent=platform_discount_percent,
			coupon_discount_percent=coupon_discount_percent
		)
		
		# Create booking with HOLD status
		# PriceEngine.calculate() returns a dict — use dict key access
		from .models import Booking, BookingRoom, BookingGuest, BookingPriceBreakdown, BookingStatusHistory
		from decimal import Decimal
		
		# Extract all values from PriceEngine dict (fixes ₹0.00 bug)
		final_price = price_breakdown['final_price']
		base_price_val = price_breakdown['base_price']
		gst_val = price_breakdown['gst']
		service_fee_val = price_breakdown['service_fee']
		coupon_discount_val = price_breakdown['coupon_discount']
		property_discount_val = price_breakdown['property_discount']
		platform_discount_val = price_breakdown['platform_discount']
		
		booking = Booking.objects.create(
			user=request.user,
			property=property_obj,
			check_in=checkin_date,
			check_out=checkout_date,
			status=Booking.STATUS_HOLD,
			total_amount=final_price,
			gross_amount=final_price,
			promo_code=coupon_code if applied_coupon else '',
			guest_name=f"{guest_first_name} {guest_last_name}",
			guest_email=guest_email,
			guest_phone=guest_phone,
		)
		
		# Create booking room
		BookingRoom.objects.create(
			booking=booking,
			room_type=room_type
		)
		
		# Create primary guest
		BookingGuest.objects.create(
			booking=booking,
			full_name=f"{guest_first_name} {guest_last_name}",
			email=guest_email
		)
		
		# Create price breakdown (all values already Decimal from PriceEngine)
		BookingPriceBreakdown.objects.create(
			booking=booking,
			base_amount=base_price_val,
			gst=gst_val,
			service_fee=service_fee_val,
			promo_discount=coupon_discount_val,
			total_amount=final_price
		)
		
		# Create status history
		BookingStatusHistory.objects.create(
			booking=booking,
			status=Booking.STATUS_HOLD,
			note='Booking created from guest form'
		)
		
		# Wire BookingContext: mark funnel as converted, link to booking
		try:
			from .models import BookingContext
			session_key = request.session.session_key or ''
			# Find the active context for this session/property/room combo
			ctx_qs = BookingContext.objects.filter(
				session_key=session_key,
				property=property_obj,
				room_type=room_type,
				context_status=BookingContext.STATUS_ACTIVE,
			).order_by('-created_at')
			if ctx_qs.exists():
				ctx = ctx_qs.first()
				ctx.booking = booking
				ctx.user = request.user
				ctx.base_price = base_price_val
				ctx.property_discount = property_discount_val
				ctx.platform_discount = platform_discount_val
				ctx.promo_discount = coupon_discount_val
				ctx.tax = gst_val
				ctx.service_fee = service_fee_val
				ctx.final_price = final_price
				ctx.context_status = BookingContext.STATUS_CONVERTED
				ctx.save(update_fields=[
					'booking', 'user', 'base_price', 'property_discount',
					'platform_discount', 'promo_discount', 'tax', 'service_fee',
					'final_price', 'context_status',
				])
			else:
				# No prior context (e.g., session was cleared) — create retroactive record
				from django.utils import timezone as _tz
				BookingContext.objects.create(
					session_key=session_key,
					user=request.user,
					property=property_obj,
					room_type=room_type,
					checkin=checkin_date,
					checkout=checkout_date,
					adults=adults,
					children=children,
					rooms=rooms,
					base_price=base_price_val,
					property_discount=property_discount_val,
					platform_discount=platform_discount_val,
					promo_discount=coupon_discount_val,
					tax=gst_val,
					service_fee=service_fee_val,
					final_price=final_price,
					promo_code=coupon_code if applied_coupon else '',
					booking=booking,
					context_status=BookingContext.STATUS_CONVERTED,
				)
		except Exception as _ctx_err:
			logger.warning(f"BookingContext wiring failed (non-fatal): {_ctx_err}")
		
		# Log success
		logger.info(f"BOOKING_CREATED: UUID={booking.uuid}, PUBLIC_ID={booking.public_booking_id}, USER={request.user.id}")
		
		messages.success(request, f'Booking created: {booking.public_booking_id}')
		
		# Redirect to payment page using UUID
		return redirect('booking:payment', uuid=booking.uuid)
	
	except Exception as e:
		logger.exception(f"BOOKING_CREATION_FAILURE: {str(e)}")
		messages.error(request, f'Unable to create booking: {str(e)}')
		return redirect(request.META.get('HTTP_REFERER', '/'))


# Create your views here.