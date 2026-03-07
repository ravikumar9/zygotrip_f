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

from apps.booking.models import Booking, BookingContext, BookingRoom, GuestBookingContext
from apps.hotels.models import Property
from apps.rooms.models import RoomType
from apps.pricing.pricing_service import calculate as calculate_price
from apps.booking.services import create_booking, transition_booking_status
from apps.booking.exceptions import InventoryUnavailableException
from apps.booking.cancellation_models import CancellationPolicy, RefundCalculator
from apps.inventory.services import release_inventory, create_hold, release_booking_inventory

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
    Guest users provide ?email=x for verification.
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
            # Guest access: require email match
            email = request.query_params.get('email', '').strip()
            if not email:
                return Response(
                    {'success': False, 'error': {'code': 'auth_required', 'message': 'Provide email for guest booking lookup.'}},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            booking = qs.get(uuid=booking_uuid, is_guest_booking=True, guest_email__iexact=email)
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
        }
    return Response({'success': True, 'data': response_data})
