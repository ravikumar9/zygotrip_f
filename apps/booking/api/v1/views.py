"""
Booking REST API v1.

Endpoints:
  POST /api/v1/booking/context/          — Create price-locked BookingContext
  GET  /api/v1/booking/context/<id>/     — Retrieve BookingContext
  POST /api/v1/booking/                  — Create Booking from context
  GET  /api/v1/booking/my/               — List current user's bookings
  GET  /api/v1/booking/<uuid>/           — Get booking detail
  POST /api/v1/booking/<uuid>/cancel/    — Cancel a booking

All responses use: { "success": true/false, "data": {...} }
"""
import logging
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from decimal import Decimal

from apps.booking.models import Booking, BookingContext, BookingRoom, GuestBookingContext
from apps.hotels.models import Property
from apps.rooms.models import RoomType
from apps.pricing.pricing_service import calculate as calculate_price, calculate_from_amounts
from apps.booking.services import create_booking, transition_booking_status
from apps.booking.exceptions import InventoryUnavailableException
from apps.booking.cancellation_models import CancellationPolicy, RefundCalculator
from apps.inventory.services import release_inventory, create_hold, release_booking_inventory
from apps.promos.selectors import get_active_promo
from apps.promos.services import calculate_promo_discount
from apps.promos.models import PromoUsage

from .serializers import (
    BookingContextCreateSerializer,
    BookingContextSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingListSerializer,
)

logger = logging.getLogger('zygotrip.api.booking')

BOOKING_CONTEXT_TTL_MINUTES = 15


@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking_context(request):
    """
    POST /api/v1/booking/context/

    Creates a price-locked BookingContext. This snapshots the price at time
    of request and gives the user a 30-minute window to complete booking.

    Authenticated users are linked to the context.
    Anonymous users are tracked by session key.
    """
    serializer = BookingContextCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Fetch property
    try:
        property_obj = Property.objects.select_related('city').get(
            id=data['property_id'], status='approved', agreement_signed=True
        )
    except Property.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Property not found or unavailable.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Fetch room type (optional) — MUST belong to the resolved property
    room_type = None
    if data.get('room_type_id'):
        try:
            room_type = RoomType.objects.get(id=data['room_type_id'], property=property_obj)
        except RoomType.DoesNotExist:
            return Response(
                {'success': False, 'error': {'code': 'invalid_room', 'message': 'Room type not found or does not belong to this property.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Validate room is active/bookable
        if hasattr(room_type, 'is_active') and not room_type.is_active:
            return Response(
                {'success': False, 'error': {'code': 'room_unavailable', 'message': 'This room type is currently unavailable.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Validate meal plan is available for this room type (if both provided)
    meal_plan_code = data.get('meal_plan', '')
    if room_type and meal_plan_code and meal_plan_code not in ('', 'none', 'room_only', 'R'):
        try:
            from apps.rooms.models import RoomMealPlan
            from apps.pricing.pricing_service import resolve_meal_plan_price
            resolved_price = resolve_meal_plan_price(room_type, meal_plan_code)
            if resolved_price <= 0:
                logger.warning('Meal plan %r not found for room %s — treating as room-only',
                               meal_plan_code, room_type.id)
        except Exception:
            pass  # Non-blocking — pricing_service will handle gracefully

    # Calculate price snapshot
    nights = (data['checkout'] - data['checkin']).days
    if nights <= 0:
        return Response(
            {'success': False, 'error': {'code': 'invalid_dates', 'message': 'Checkout must be after checkin.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Pre-flight availability check (non-blocking — only blocks when
    # InventoryCalendar is actively provisioned for this room type)
    if room_type:
        try:
            from apps.inventory.models import InventoryCalendar
            calendar_exists = InventoryCalendar.objects.filter(room_type=room_type).exists()
            if calendar_exists:
                from apps.inventory.services import check_availability
                is_avail, unavail_dates = check_availability(
                    room_type, data['checkin'], data['checkout'], data.get('rooms', 1),
                )
                if not is_avail:
                    date_strs = ', '.join(str(d) for d in unavail_dates[:5])
                    return Response(
                        {'success': False, 'error': {
                            'code': 'inventory_unavailable',
                            'message': f'Rooms unavailable on: {date_strs}.',
                        }},
                        status=status.HTTP_409_CONFLICT,
                    )
        except Exception as avail_err:
            logger.debug('Availability pre-check skipped: %s', avail_err)

    price_snapshot = {'base_price': 0, 'meal_amount': 0, 'property_discount': 0,
                      'platform_discount': 0, 'promo_discount': 0, 'tax': 0,
                      'service_fee': 0, 'final_price': 0, 'price_locked': False, 'locked_price': 0}

    if room_type:
        calc = calculate_price(
            room_type=room_type,
            nights=nights,
            rooms=data.get('rooms', 1),
            meal_plan_code=data.get('meal_plan', ''),
            checkin_date=data['checkin'],
        )
        price_snapshot = {
            'base_price': calc['base_price'],
            'meal_amount': calc['meal_plan_price'],
            'property_discount': calc['property_discount'],
            'platform_discount': calc['platform_discount'],
            'promo_discount': calc['promo_discount'],
            'tax': calc['gst_amount'],
            'service_fee': calc['service_fee'],
            'final_price': calc['final_total'],
            'price_locked': True,
            'locked_price': calc['final_total'],
        }

    # Create context
    context = BookingContext.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        property=property_obj,
        room_type=room_type,
        checkin=data['checkin'],
        checkout=data['checkout'],
        adults=data.get('adults', 1),
        children=data.get('children', 0),
        rooms=data.get('rooms', 1),
        meal_plan=data.get('meal_plan', ''),
        promo_code=data.get('promo_code', ''),
        expires_at=timezone.now() + timedelta(minutes=BOOKING_CONTEXT_TTL_MINUTES),
        price_expires_at=timezone.now() + timedelta(minutes=BOOKING_CONTEXT_TTL_MINUTES),
        **price_snapshot,
    )

    # Create inventory hold (prevents double-booking during checkout)
    if room_type:
        try:
            create_hold(
                room_type=room_type,
                check_in=data['checkin'],
                check_out=data['checkout'],
                quantity=data.get('rooms', 1),
                booking_context=context,
            )
        except (ValueError, Exception) as hold_err:
            logger.warning('Inventory hold failed (non-blocking): %s', hold_err)
            # Non-blocking: if InventoryCalendar rows don't exist yet,
            # the legacy RoomInventory path in create_booking will handle it

    logger.info('BookingContext created: id=%s property=%s', context.id, property_obj.name)

    return Response(
        {'success': True, 'data': BookingContextSerializer(context).data},
        status=status.HTTP_201_CREATED,
    )


def _get_context_or_error(context):
    """Check expiry and return (context_obj, None) or (None, Response)."""
    if context.expires_at and timezone.now() > context.expires_at:
        context.context_status = BookingContext.STATUS_EXPIRED
        context.save(update_fields=['context_status'])
        return None, Response(
            {'success': False, 'error': {'code': 'context_expired', 'message': 'This price lock has expired. Please start again.'}},
            status=status.HTTP_410_GONE,
        )
    return context, None


@api_view(['GET'])
@permission_classes([AllowAny])
def get_booking_context(request, context_uuid):
    """GET /api/v1/booking/context/<uuid>/ — UUID-based lookup (canonical)."""
    try:
        context = BookingContext.objects.select_related('property', 'room_type').get(
            uuid=context_uuid
        )
    except BookingContext.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking context not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )
    context, err = _get_context_or_error(context)
    if err:
        return err
    return Response({'success': True, 'data': BookingContextSerializer(context).data})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_booking_context_by_id(request, context_id):
    """GET /api/v1/booking/context/<int>/ — legacy numeric ID lookup (deprecated)."""
    try:
        context = BookingContext.objects.select_related('property', 'room_type').get(
            id=context_id
        )
    except BookingContext.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking context not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )
    context, err = _get_context_or_error(context)
    if err:
        return err
    return Response({'success': True, 'data': BookingContextSerializer(context).data})


@api_view(['POST'])
@permission_classes([AllowAny])
def apply_promo_to_context(request, context_uuid):
    """
    POST /api/v1/booking/context/<uuid>/apply-promo/

    Applies (or removes) a promo code on an existing BookingContext.
    Recalculates service_fee, tax, final_price, locked_price server-side
    so the frontend NEVER computes discounts locally.

    To remove a promo, send {"promo_code": ""}.
    """
    try:
        ctx = BookingContext.objects.select_related('property', 'room_type').get(
            uuid=context_uuid,
            context_status=BookingContext.STATUS_ACTIVE,
        )
    except BookingContext.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking context not found or expired.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    ctx, err = _get_context_or_error(ctx)
    if err:
        return err

    promo_code = (request.data.get('promo_code') or '').strip()

    # ── Remove promo ────────────────────────────────────────────────
    if not promo_code:
        ctx.promo_code = ''
        ctx.promo_discount = Decimal('0')

        nights = max(1, (ctx.checkout - ctx.checkin).days)
        rooms = max(1, ctx.rooms or 1)
        tariff_per_night = ctx.base_price / Decimal(str(nights * rooms))

        breakdown = calculate_from_amounts(
            base_amount=ctx.base_price,
            meal_amount=ctx.meal_amount,
            promo_discount=Decimal('0'),
            tariff_per_night=tariff_per_night,
        )
        ctx.service_fee = breakdown['service_fee']
        ctx.tax = breakdown['gst']
        ctx.final_price = breakdown['total_amount']
        ctx.locked_price = breakdown['total_amount']
        ctx.save(update_fields=[
            'promo_code', 'promo_discount', 'service_fee', 'tax',
            'final_price', 'locked_price',
        ])
        logger.info('Promo removed from context %s', context_uuid)
        return Response({'success': True, 'data': BookingContextSerializer(ctx).data})

    # ── Validate promo ──────────────────────────────────────────────
    promo = get_active_promo(promo_code)
    if not promo:
        return Response(
            {'success': False, 'error': {'code': 'invalid_promo', 'message': 'Promo code is invalid or has expired.'}},
            status=status.HTTP_200_OK,
        )

    # Max global uses
    if promo.max_uses and promo.max_uses > 0:
        usage_count = PromoUsage.objects.filter(promo=promo).count()
        if usage_count >= promo.max_uses:
            return Response(
                {'success': False, 'error': {'code': 'promo_exhausted', 'message': 'This promo code has reached its usage limit.'}},
                status=status.HTTP_200_OK,
            )

    # Per-user guard
    if request.user.is_authenticated:
        already_used = PromoUsage.objects.filter(promo=promo, user=request.user).exists()
        if already_used:
            return Response(
                {'success': False, 'error': {'code': 'already_used', 'message': 'You have already used this promo code.'}},
                status=status.HTTP_200_OK,
            )

    # ── Calculate discount & recalculate breakdown ──────────────────
    subtotal = ctx.base_price + ctx.meal_amount
    discount_amount = calculate_promo_discount(promo, subtotal)
    if promo.max_discount and discount_amount > promo.max_discount:
        discount_amount = Decimal(str(promo.max_discount))

    nights = max(1, (ctx.checkout - ctx.checkin).days)
    rooms = max(1, ctx.rooms or 1)
    tariff_per_night = ctx.base_price / Decimal(str(nights * rooms))

    breakdown = calculate_from_amounts(
        base_amount=ctx.base_price,
        meal_amount=ctx.meal_amount,
        promo_discount=discount_amount,
        tariff_per_night=tariff_per_night,
    )

    ctx.promo_code = promo.code
    ctx.promo_discount = discount_amount
    ctx.service_fee = breakdown['service_fee']
    ctx.tax = breakdown['gst']
    ctx.final_price = breakdown['total_amount']
    ctx.locked_price = breakdown['total_amount']
    ctx.save(update_fields=[
        'promo_code', 'promo_discount', 'service_fee', 'tax',
        'final_price', 'locked_price',
    ])

    logger.info(
        'Promo %s applied to context %s — discount=%s new_total=%s',
        promo.code, context_uuid, discount_amount, breakdown['total_amount'],
    )

    return Response({'success': True, 'data': BookingContextSerializer(ctx).data})


@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking_view(request):
    """
    POST /api/v1/booking/

    Creates a Booking (status=HOLD) from a valid BookingContext.
    Supports both authenticated and guest (anonymous) checkout.
    Guest bookings require email, phone, and undergo device fingerprint
    fraud scoring before acceptance.
    """
    serializer = BookingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    is_authenticated = request.user and request.user.is_authenticated
    is_guest = not is_authenticated

    # --- Device fingerprint fraud gate (especially for guests) ---
    fingerprint = None
    fraud_score = 0
    try:
        from apps.core.device_fingerprint import FingerprintService
        fingerprint = FingerprintService.collect_from_request(request)
        fraud_score = fingerprint.fraud_score
        if fraud_score >= 80:
            logger.warning(
                'Booking blocked: high fraud score %d (fp=%s)',
                fraud_score, fingerprint.fingerprint_hash[:12],
            )
            return Response(
                {'success': False, 'error': {'code': 'fraud_blocked', 'message': 'Booking could not be processed. Please contact support.'}},
                status=status.HTTP_403_FORBIDDEN,
            )
    except Exception as fp_err:
        logger.warning('Fingerprint collection failed (non-blocking): %s', fp_err)

    # Resolve context — prefer UUID lookup, fall back to numeric ID
    try:
        if data.get('context_uuid'):
            context = BookingContext.objects.select_related('property', 'room_type').get(
                uuid=data['context_uuid'],
                context_status=BookingContext.STATUS_ACTIVE,
            )
        else:
            context = BookingContext.objects.select_related('property', 'room_type').get(
                id=data['context_id'],
                context_status=BookingContext.STATUS_ACTIVE,
            )
    except BookingContext.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'invalid_context', 'message': 'Invalid or expired booking context.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if context.expires_at and timezone.now() > context.expires_at:
        context.context_status = BookingContext.STATUS_EXPIRED
        context.save(update_fields=['context_status'])
        return Response(
            {'success': False, 'error': {'code': 'context_expired', 'message': 'Price lock expired. Please restart booking.'}},
            status=status.HTTP_410_GONE,
        )

    # Idempotency: if context already converted, return the existing booking
    if context.context_status == BookingContext.STATUS_CONVERTED and context.booking_id:
        try:
            existing = Booking.objects.prefetch_related('rooms__room_type').select_related('property').get(
                pk=context.booking_id,
            )
            return Response(
                {'success': True, 'data': BookingDetailSerializer(existing).data},
                status=status.HTTP_200_OK,
            )
        except Booking.DoesNotExist:
            pass

    if not context.room_type:
        return Response(
            {'success': False, 'error': {'code': 'missing_room', 'message': 'A room type must be selected to confirm booking.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Wallet balance check (before creating booking) ────────────────
    payment_method = data.get('payment_method', 'wallet')
    if payment_method == 'wallet' and is_authenticated:
        try:
            from apps.wallet.services import check_wallet_balance
            booking_amount = context.locked_price if context.price_locked else context.final_price
            if not check_wallet_balance(request.user, booking_amount):
                return Response(
                    {'success': False, 'error': {
                        'code': 'insufficient_balance',
                        'message': f'Insufficient wallet balance. You need ₹{booking_amount} but your wallet balance is too low. Please add funds or choose a different payment method.',
                    }},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        except Exception as wb_err:
            logger.warning('Wallet balance check failed (non-blocking): %s', wb_err)

    # Determine booking user
    booking_user = request.user if is_authenticated else None

    try:
        booking = create_booking(
            user=booking_user,
            property_obj=context.property,
            room_type=context.room_type,
            quantity=context.rooms,
            meal_plan=context.meal_plan,
            check_in=context.checkin,
            check_out=context.checkout,
            guests=[{
                'full_name': data['guest_name'],
                'email': data['guest_email'],
                'age': data.get('guest_age', 0),
            }],
            promo_code=context.promo_code,
            locked_price=context.locked_price if context.price_locked else None,
        )
    except InventoryUnavailableException as e:
        return Response(
            {'success': False, 'error': {'code': 'inventory_unavailable', 'message': str(e)}},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        logger.exception('Booking creation failed: %s', e)
        return Response(
            {'success': False, 'error': {'code': 'booking_failed', 'message': 'Booking could not be created. Please try again.'}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Update guest contact details + guest flag
    booking.guest_name = data['guest_name']
    booking.guest_email = data['guest_email']
    booking.guest_phone = data['guest_phone']
    booking.is_guest_booking = is_guest
    booking.save(update_fields=['guest_name', 'guest_email', 'guest_phone', 'is_guest_booking'])

    # Create GuestBookingContext for anonymous bookings
    if is_guest:
        GuestBookingContext.objects.create(
            booking=booking,
            booking_context=context,
            email=data['guest_email'],
            phone=data['guest_phone'],
            full_name=data['guest_name'],
            ip_address=_get_client_ip(request),
            session_key=request.session.session_key or '',
            device_fingerprint=fingerprint,
            fraud_score=fraud_score,
        )

    # Link context to booking
    context.booking = booking
    context.context_status = BookingContext.STATUS_CONVERTED
    context.save(update_fields=['booking', 'context_status'])

    # Track conversion event
    try:
        from apps.core.analytics import track_event
        track_event(
            event_type='booking_created',
            user=booking_user,
            property_obj=context.property,
            metadata={
                'booking_id': str(booking.uuid),
                'is_guest': is_guest,
                'fraud_score': fraud_score,
                'amount': str(booking.total_amount),
            },
        )
    except Exception:
        pass  # Analytics non-blocking

    user_label = request.user.email if is_authenticated else f'guest:{data["guest_email"]}'
    logger.info('Booking created: %s for %s (guest=%s)', booking.public_booking_id, user_label, is_guest)

    # ── Wallet payment: auto-process for authenticated wallet payments ──
    # This handles HOLD → PAYMENT_PENDING → CONFIRMED in one shot
    payment_processed = False
    if payment_method == 'wallet' and is_authenticated:
        booking_amount = Decimal(str(booking.total_amount))
        try:
            from apps.wallet.services import use_wallet_for_payment
            from apps.booking.state_machine import BookingStateMachine

            with transaction.atomic():
                # Step 1: HOLD → PAYMENT_PENDING
                booking = BookingStateMachine.transition(
                    booking, Booking.STATUS_PAYMENT_PENDING,
                    note='Wallet payment initiated',
                    user=request.user,
                )

                # Step 2: Debit wallet
                success, err = use_wallet_for_payment(
                    user=request.user,
                    amount=booking_amount,
                    booking_reference=str(booking.uuid),
                )
                if not success:
                    raise ValueError(err or 'Wallet payment failed')

                # Step 3: PAYMENT_PENDING → CONFIRMED
                booking = BookingStateMachine.transition(
                    booking, Booking.STATUS_CONFIRMED,
                    note=f'Wallet payment confirmed (₹{booking_amount})',
                    user=request.user,
                )

            payment_processed = True
            logger.info(
                'Wallet payment processed: %s amount=₹%s user=%s',
                booking.public_booking_id, booking_amount, user_label,
            )
            # Invalidate wallet balance cache after debit
            try:
                from django.core.cache import cache
                cache.delete(f'wallet_balance_{request.user.id}')
            except Exception:
                pass
        except Exception as pay_err:
            # Payment failed — booking stays in HOLD, user can retry
            logger.warning(
                'Wallet auto-payment failed for %s: %s',
                booking.public_booking_id, pay_err,
            )
            # Don't fail the entire booking — just return it in HOLD status

    booking_detail = Booking.objects.prefetch_related('rooms__room_type').select_related('property').get(pk=booking.pk)
    return Response(
        {'success': True, 'data': BookingDetailSerializer(booking_detail).data},
        status=status.HTTP_201_CREATED,
    )


def _get_client_ip(request):
    """Extract client IP from request."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """
    GET /api/v1/booking/my/

    Paginated list of the authenticated user's bookings, newest first.
    """
    qs = (
        Booking.objects
        .filter(user=request.user)
        .select_related('property')
        .order_by('-created_at')
    )

    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)
    serializer = BookingListSerializer(page, many=True)

    return Response({
        'success': True,
        'data': {
            'results': serializer.data,
            'pagination': {
                'count': qs.count(),
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def booking_detail(request, booking_uuid):
    """
    GET /api/v1/booking/<uuid>/

    Authenticated users see their own bookings.
    Guest bookings can be accessed by UUID alone (UUID is the secret token).
    """
    try:
        qs = (
            Booking.objects
            .select_related('property')
            .prefetch_related('rooms__room_type', 'price_breakdown')
        )
        if request.user and request.user.is_authenticated:
            booking = qs.get(uuid=booking_uuid, user=request.user)
        else:
            # Guest access: UUID is the authentication token for guest bookings
            booking = qs.get(uuid=booking_uuid, is_guest_booking=True)
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({'success': True, 'data': BookingDetailSerializer(booking).data})


@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_booking(request, booking_uuid):
    """
    POST /api/v1/booking/<uuid>/cancel/

    Cancels a booking that is in HOLD, PAYMENT_PENDING, or CONFIRMED status.
    Authenticated users cancel their own bookings.
    Guest users must provide guest_email in the request body.
    Triggers refund processing if payment was made.
    """
    try:
        if request.user and request.user.is_authenticated:
            booking = Booking.objects.get(uuid=booking_uuid, user=request.user)
        else:
            guest_email = request.data.get('guest_email', '').strip()
            if not guest_email:
                return Response(
                    {'success': False, 'error': {'code': 'auth_required', 'message': 'Provide guest_email for guest booking cancellation.'}},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            booking = Booking.objects.get(uuid=booking_uuid, is_guest_booking=True, guest_email__iexact=guest_email)
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    cancellable_statuses = {
        Booking.STATUS_HOLD,
        Booking.STATUS_PAYMENT_PENDING,
        Booking.STATUS_CONFIRMED,
    }
    if booking.status not in cancellable_statuses:
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'invalid_status',
                    'message': f'Booking in status "{booking.status}" cannot be cancelled.',
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    try:
        with transaction.atomic():
            # 1. Transition status
            transition_booking_status(
                booking=booking,
                new_status=Booking.STATUS_CANCELLED,
                note='Cancelled by customer via API',
            )

            # 2. Release inventory for each booked room (both legacy + calendar)
            booking_rooms = BookingRoom.objects.filter(booking=booking).select_related('room_type')
            for br in booking_rooms:
                try:
                    release_inventory(
                        room_type=br.room_type,
                        start_date=booking.check_in,
                        end_date=booking.check_out,
                        quantity=br.quantity,
                    )
                except Exception as inv_err:
                    logger.error('Legacy inventory release failed for room %s: %s', br.room_type_id, inv_err)
                try:
                    release_booking_inventory(
                        room_type=br.room_type,
                        check_in=booking.check_in,
                        check_out=booking.check_out,
                        quantity=br.quantity,
                        booking_uuid=str(booking.uuid),
                    )
                except Exception as cal_err:
                    logger.error('Calendar inventory release failed for room %s: %s', br.room_type_id, cal_err)

            # 3. Calculate refund if booking was confirmed (payment was made)
            refund_data = None
            if booking.total_amount and booking.total_amount > 0:
                try:
                    policy = CancellationPolicy.objects.get(property=booking.property)
                except CancellationPolicy.DoesNotExist:
                    # Default flexible policy: create an in-memory one
                    policy = CancellationPolicy(
                        property=booking.property,
                        policy_type=CancellationPolicy.POLICY_TYPE_FLEXIBLE,
                    )
                calculator = RefundCalculator(policy, booking.total_amount)
                refund_data = calculator.compute(booking.check_in)

                # Persist refund amount on booking
                booking.refund_amount = refund_data['refund_amount']
                booking.save(update_fields=['refund_amount', 'updated_at'])

                # 4. Process wallet refund if payment was via wallet
                refund_amount = Decimal(str(refund_data['refund_amount']))
                if refund_amount > 0 and booking.user:
                    try:
                        from apps.wallet.services import refund_to_wallet
                        wallet_refunded = refund_to_wallet(
                            user=booking.user,
                            amount=refund_amount,
                            booking_reference=str(booking.uuid),
                            note=f'Refund for cancelled booking {booking.public_booking_id} ({refund_data["tier"]})',
                        )
                        if wallet_refunded:
                            logger.info(
                                'Wallet refund processed: %s amount=₹%s user=%s',
                                booking.public_booking_id, refund_amount, booking.user.email,
                            )
                            if refund_data:
                                refund_data['wallet_credited'] = True
                            # Invalidate wallet balance cache after refund
                            try:
                                from django.core.cache import cache
                                cache.delete(f'wallet_balance_{booking.user.id}')
                            except Exception:
                                pass
                    except Exception as refund_err:
                        logger.error('Wallet refund failed for %s: %s', booking.public_booking_id, refund_err)
                        if refund_data:
                            refund_data['wallet_credited'] = False

    except Exception as e:
        logger.exception('Booking cancellation failed: %s', e)
        return Response(
            {'success': False, 'error': {'code': 'cancellation_failed', 'message': str(e)}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    user_label = request.user.email if (request.user and request.user.is_authenticated) else f'guest:{booking.guest_email}'
    logger.info('Booking cancelled: %s by %s refund=%s',
                booking.public_booking_id, user_label,
                refund_data['refund_amount'] if refund_data else '0')
    response_data = {
        'message': 'Booking cancelled successfully.',
        'status': booking.status,
    }
    if refund_data:
        response_data['refund'] = {
            'amount': str(refund_data['refund_amount']),
            'tier': refund_data['tier'],
            'note': refund_data['note'],
            'wallet_credited': refund_data.get('wallet_credited', False),
        }
    return Response({'success': True, 'data': response_data})


@api_view(['GET'])
@permission_classes([AllowAny])
def refund_preview(request, booking_uuid):
    """
    GET /api/v1/booking/<uuid>/refund-preview/

    Preview the refund amount WITHOUT cancelling.
    Used by frontend cancellation modal to show the user what they'll get back.
    """
    from apps.booking.models import Booking, CancellationPolicy
    from django.utils import timezone

    # Auth: authenticated users see own bookings; guest uuid acts as token
    try:
        if request.user.is_authenticated:
            booking = Booking.objects.select_related('property').get(
                uuid=booking_uuid, user=request.user
            )
        else:
            booking = Booking.objects.select_related('property').get(uuid=booking_uuid)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=404)

    # Not cancellable statuses
    if booking.status not in ('hold', 'payment_pending', 'confirmed'):
        return Response({
            'amount': 0,
            'tier': 'not_cancellable',
            'note': f'Booking is {booking.status} and cannot be cancelled.',
        })

    # If booking was unpaid (HOLD/PAYMENT_PENDING) → full refund trivially
    if booking.status in ('hold', 'payment_pending'):
        return Response({
            'amount': 0,          # No money was charged
            'tier': 'free',
            'note': 'No charge — booking was not yet paid.',
        })

    # For confirmed bookings: apply CancellationPolicy tiers
    try:
        policy = (
            CancellationPolicy.objects
            .filter(property=booking.property, is_active=True)
            .first()
        )
        if policy:
            try:
                from apps.booking.refund_calculator import RefundCalculator
                refund_data = RefundCalculator.calculate(
                    booking, policy, cancelled_at=timezone.now()
                )
                return Response({
                    'amount': float(refund_data.get('refund_amount', 0)),
                    'tier':   refund_data.get('tier', 'custom'),
                    'note':   refund_data.get('note', ''),
                })
            except ImportError:
                pass

        # Fallback: check cancellation_hours on property
        prop = booking.property
        cancellation_hours = getattr(prop, 'cancellation_hours', 48) or 48
        now = timezone.now()
        check_in_dt = timezone.datetime.combine(booking.check_in, timezone.datetime.min.time())
        check_in_dt = timezone.make_aware(check_in_dt) if timezone.is_naive(check_in_dt) else check_in_dt
        hours_until_checkin = (check_in_dt - now).total_seconds() / 3600

        if hours_until_checkin >= cancellation_hours:
            return Response({
                'amount': float(booking.gross_amount or 0),
                'tier':   'free',
                'note':   f'Free cancellation — more than {cancellation_hours}h before check-in.',
            })
        else:
            return Response({
                'amount': 0,
                'tier':   'non_refundable',
                'note':   f'Non-refundable — less than {cancellation_hours}h before check-in.',
            })

    except Exception as exc:
        logger.warning('refund_preview error booking=%s: %s', booking_uuid, exc)
        return Response({
            'amount': float(booking.gross_amount or 0),
            'tier':   'unknown',
            'note':   'Refund amount to be confirmed after cancellation.',
        })
