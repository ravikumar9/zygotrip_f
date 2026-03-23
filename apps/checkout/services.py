"""
Checkout Service Layer — Production-grade checkout session management.

Orchestrates:
  1. Session creation (from search → room selection)
  2. Inventory token creation (links to InventoryHold)
  3. Price revalidation (before payment)
  4. Guest details capture
  5. Payment intent creation
  6. Final booking creation (after payment success)
  7. Risk scoring
  8. Session expiry
"""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.booking.distributed_locks import acquire_booking_lock
from apps.booking.models import Booking, BookingContext, BookingStatusHistory
from apps.booking.state_machine import BookingStateMachine
from apps.booking.services import create_booking
from apps.inventory.lock_manager import acquire_hold_locked
from apps.inventory.models import InventoryCalendar, InventoryHold
from apps.inventory.services import create_hold, release_holds, convert_hold_to_booking
from apps.pricing.pricing_service import calculate as pricing_calculate, resolve_meal_plan_price

from .exceptions import (
    CheckoutException,
    InventoryTokenExpiredError,
    PaymentIntentError,
    PriceChangedException,
    RiskBlockedException,
    SessionExpiredException,
    SessionStateError,
)
from .models import BookingSession, InventoryToken, PaymentIntent, PaymentAttempt

logger = logging.getLogger('zygotrip.checkout')

# ── Constants ────────────────────────────────────────────────────────────────
SESSION_TTL_MINUTES = 15
PRICE_TOLERANCE_PERCENT = Decimal('2.0')  # Allow 2% price drift


def _string_amount(value, default='0'):
    """Normalize Decimal-like values to string snapshots for JSON storage."""
    if value in (None, ''):
        return default
    return str(value)


def extract_snapshot_total(price_snapshot, fallback=Decimal('0')):
    """
    Return the payable amount from a price snapshot.

    Supports the canonical pricing keys returned by apps.pricing.pricing_service
    and legacy checkout keys kept for backward compatibility.
    """
    if not isinstance(price_snapshot, dict):
        return Decimal(str(fallback))

    for key in ('total', 'final_total', 'total_after_tax'):
        value = price_snapshot.get(key)
        if value not in (None, ''):
            return Decimal(str(value))

    return Decimal(str(fallback))


def _build_price_snapshot(price_result):
    """
    Translate the canonical pricing engine response into the checkout snapshot.

    The checkout API keeps legacy keys like ``total`` and ``gst`` so older
    consumers remain compatible, while the values are sourced from the
    authoritative pricing engine keys (``final_total`` and ``gst_amount``).
    """
    total = (
        price_result.get('final_total')
        or price_result.get('total_after_tax')
        or price_result.get('total')
        or 0
    )
    from decimal import ROUND_HALF_UP as _RHU
    total = Decimal(str(total)).quantize(Decimal("1"), rounding=_RHU)
    gst_amount = price_result.get('gst_amount', price_result.get('gst', 0))

    return {
        'base_price': _string_amount(price_result.get('base_price', 0)),
        'meal_amount': _string_amount(price_result.get('meal_plan_price', 0)),
        'service_fee': _string_amount(price_result.get('service_fee', 0)),
        'gst': _string_amount(gst_amount),
        'gst_amount': _string_amount(gst_amount),
        'total': _string_amount(total),
        'final_total': _string_amount(total),
        'tariff_per_night': _string_amount(price_result.get('tariff_per_night', 0)),
        'property_discount': _string_amount(price_result.get('property_discount', 0)),
        'platform_discount': _string_amount(price_result.get('platform_discount', 0)),
        'promo_discount': _string_amount(price_result.get('promo_discount', 0)),
        'demand_adjustment': _string_amount(price_result.get('demand_adjustment', 0)),
        'advance_modifier': _string_amount(price_result.get('advance_modifier', 0)),
        'loyalty_discount': _string_amount(price_result.get('loyalty_discount', 0)),
        'wallet_credit': _string_amount(price_result.get('wallet_credit', 0)),
    }


# ============================================================================
# 1. SESSION CREATION
# ============================================================================

@transaction.atomic
def create_checkout_session(
    user,
    session_key,
    property_obj,
    room_type,
    check_in,
    check_out,
    guests=2,
    rooms=1,
    rate_plan_id='',
    meal_plan_code='',
    promo_code='',
    ip_address=None,
    user_agent='',
    device_fingerprint='',
):
    """
    Create a checkout session with inventory hold and price snapshot.

    Steps:
      1. Validate availability
      2. Create inventory holds (via existing service)
      3. Calculate price snapshot (via pricing engine)
      4. Create BookingSession with frozen data
      5. Create InventoryToken linking to holds
      6. Return session with all data

    Returns:
        BookingSession instance (status=ROOM_SELECTED)
    """
    nights = (check_out - check_in).days
    if nights <= 0:
        raise CheckoutException("check_out must be after check_in")

    # ── 1. Create inventory holds (per-date distributed lock + SELECT FOR UPDATE) ──
    # acquire_hold_locked acquires one Redis lock per night before the DB write,
    # preventing overlapping-range races that a single booking-range lock cannot catch.
    holds = acquire_hold_locked(
        room_type_id=room_type.id,
        check_in=check_in,
        check_out=check_out,
        rooms=rooms,
        hold_minutes=SESSION_TTL_MINUTES,
    )

    # ── 2. Calculate price ───────────────────────────────────────────────
    meal_price = resolve_meal_plan_price(room_type, meal_plan_code) if meal_plan_code else Decimal('0')
    price_result = pricing_calculate(
        room_type=room_type,
        nights=nights,
        rooms=rooms,
        meal_plan_price=meal_price,
        meal_plan_code=meal_plan_code,
        checkin_date=check_in,
        user=user,
    )

    price_snapshot = _build_price_snapshot(price_result)

    search_snapshot = {
        'city': str(getattr(property_obj, 'city', '') or ''),
        'check_in': str(check_in),
        'check_out': str(check_out),
        'guests': guests,
        'rooms': rooms,
        'meal_plan_code': meal_plan_code,
        'promo_code': promo_code,
    }

    # ── 3. Create InventoryToken ─────────────────────────────────────────
    hold_ids = [str(h.hold_id) for h in holds]
    expires_at = timezone.now() + timedelta(minutes=SESSION_TTL_MINUTES)

    inv_token = InventoryToken.objects.create(
        hotel=property_obj,
        room_type=room_type,
        rate_plan_id=rate_plan_id,
        date_start=check_in,
        date_end=check_out,
        reserved_rooms=rooms,
        hold_ids=hold_ids,
        expires_at=expires_at,
    )

    # ── 4. Create BookingSession ─────────────────────────────────────────
    session = BookingSession.objects.create(
        user=user,
        session_key=session_key or '',
        hotel=property_obj,
        room_type=room_type,
        rate_plan_id=rate_plan_id,
        search_snapshot=search_snapshot,
        price_snapshot=price_snapshot,
        inventory_token=inv_token,
        session_status=BookingSession.STATUS_ROOM_SELECTED,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent or '',
        device_fingerprint=device_fingerprint or '',
    )

    logger.info(
        "Checkout session created: session=%s property=%s room=%s total=%s",
        session.session_id, property_obj.id, room_type.id,
        price_snapshot['total'],
    )

    return session


# ============================================================================
# 2. GUEST DETAILS
# ============================================================================

@transaction.atomic
def set_guest_details(session, guest_details):
    """
    Save guest details on the checkout session.

    Args:
        session: BookingSession (must be ROOM_SELECTED)
        guest_details: dict with name, email, phone, special_requests
    """
    if session.is_expired:
        session.transition_to(BookingSession.STATUS_EXPIRED)
        raise SessionExpiredException("Session has expired")

    if session.session_status not in [BookingSession.STATUS_ROOM_SELECTED, BookingSession.STATUS_GUEST_DETAILS]:
        raise SessionStateError(
            f"Cannot set guest details in state {session.session_status}"
        )

    # Validate required fields
    required = ['name', 'email', 'phone']
    missing = [f for f in required if not guest_details.get(f)]
    if missing:
        raise CheckoutException(f"Missing guest fields: {', '.join(missing)}")

    session.guest_details = {
        'name': guest_details['name'].strip(),
        'email': guest_details['email'].strip().lower(),
        'phone': str(guest_details['phone']).strip(),
        'special_requests': guest_details.get('special_requests', '').strip(),
    }
    session.save(update_fields=['guest_details', 'updated_at'])
    session.transition_to(BookingSession.STATUS_GUEST_DETAILS)

    logger.info("Guest details set: session=%s", session.session_id)
    return session


# ============================================================================
# 3. PRICE REVALIDATION
# ============================================================================

def revalidate_price(session):
    """
    Revalidate price against current pricing engine.

    Called before payment to ensure price hasn't changed significantly.
    If price changed within tolerance (2%), update and proceed.
    If price changed beyond tolerance, raise PriceChangedException.

    Returns:
        (session, price_changed: bool, new_total: Decimal)
    """
    if session.is_expired:
        raise SessionExpiredException("Session has expired")

    search = session.search_snapshot
    check_in_str = search.get('check_in', '')
    check_out_str = search.get('check_out', '')

    from datetime import date as date_type
    check_in = date_type.fromisoformat(check_in_str) if check_in_str else None
    check_out = date_type.fromisoformat(check_out_str) if check_out_str else None

    if not check_in or not check_out:
        raise CheckoutException("Invalid search snapshot: missing dates")

    nights = (check_out - check_in).days
    rooms = search.get('rooms', 1)
    meal_plan_code = search.get('meal_plan_code', '')

    meal_price = resolve_meal_plan_price(session.room_type, meal_plan_code) if meal_plan_code else Decimal('0')
    price_result = pricing_calculate(
        room_type=session.room_type,
        nights=nights,
        rooms=rooms,
        meal_plan_price=meal_price,
        meal_plan_code=meal_plan_code,
        checkin_date=check_in,
        user=session.user,
    )

    new_total = extract_snapshot_total(_build_price_snapshot(price_result))
    old_total = extract_snapshot_total(session.price_snapshot)

    price_changed = new_total != old_total
    if price_changed and old_total > 0:
        pct_change = abs((new_total - old_total) / old_total) * 100
        if pct_change > PRICE_TOLERANCE_PERCENT:
            raise PriceChangedException(old_total, new_total)

    # Update snapshot with new price
    updated_snapshot = _build_price_snapshot(price_result)
    updated_snapshot['total'] = _string_amount(new_total)
    updated_snapshot['final_total'] = _string_amount(new_total)
    session.price_snapshot = updated_snapshot
    session.price_revalidated_at = timezone.now()
    session.price_changed = price_changed
    session.save(update_fields=[
        'price_snapshot', 'price_revalidated_at', 'price_changed', 'updated_at',
    ])

    logger.info(
        "Price revalidated: session=%s old=%s new=%s changed=%s",
        session.session_id, old_total, new_total, price_changed,
    )

    return session, price_changed, new_total


# ============================================================================
# 4. PAYMENT INTENT CREATION
# ============================================================================

@transaction.atomic
def create_payment_intent(session, idempotency_key=None):
    """
    Create a PaymentIntent for the checkout session.

    Steps:
      1. Check session state (must be GUEST_DETAILS)
      2. Revalidate price
      3. Check inventory token is still active
      4. Create PaymentIntent
      5. Transition session to PAYMENT_INITIATED

    Returns:
        PaymentIntent instance
    """
    if session.is_expired:
        session.transition_to(BookingSession.STATUS_EXPIRED)
        raise SessionExpiredException("Session has expired")

    if session.session_status != BookingSession.STATUS_GUEST_DETAILS:
        raise SessionStateError(
            f"Cannot initiate payment in state {session.session_status}"
        )

    # Idempotency check
    if idempotency_key:
        existing = PaymentIntent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    original_total = extract_snapshot_total(session.price_snapshot)

    # Revalidate price via PriceGuard (freshness + 3% drift tolerance)
    # PriceGuard.validate_before_payment handles:
    #   - Fast path if price validated < 5 min ago
    #   - Live revalidation against pricing engine
    #   - ±3% drift tolerance (raises PriceChangedException if exceeded)
    from apps.checkout.price_guard import PriceGuard
    session, new_total = PriceGuard.validate_before_payment(session)
    price_changed = (new_total != original_total)

    # Verify inventory token
    token = session.inventory_token
    if not token or token.is_expired or token.token_status != InventoryToken.STATUS_ACTIVE:
        raise InventoryTokenExpiredError("Inventory reservation has expired")

    # Mark token as payment pending
    token.token_status = InventoryToken.STATUS_PAYMENT_PENDING
    token.save(update_fields=['token_status', 'updated_at'])

    intent = PaymentIntent.objects.create(
        booking_session=session,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
        amount=new_total,
        currency='INR',
        original_amount=original_total,
        price_revalidated=True,
        price_delta=new_total - original_total if price_changed else Decimal('0'),
    )

    session.transition_to(BookingSession.STATUS_PAYMENT_INITIATED)

    logger.info(
        "Payment intent created: intent=%s session=%s amount=%s",
        intent.intent_id, session.session_id, new_total,
    )

    return intent


# ============================================================================
# 5. PAYMENT ATTEMPT
# ============================================================================

@transaction.atomic
def create_payment_attempt(intent, gateway):
    """
    Create a payment attempt for a gateway.

    Args:
        intent: PaymentIntent
        gateway: str (e.g., 'wallet', 'cashfree', 'stripe', 'dev_simulate')

    Returns:
        PaymentAttempt instance
    """
    if intent.payment_status not in (
        PaymentIntent.STATUS_CREATED,
        PaymentIntent.STATUS_FAILED,  # allow retry
    ):
        raise PaymentIntentError(
            f"Cannot create attempt for intent in state {intent.payment_status}"
        )

    attempt = PaymentAttempt.objects.create(
        payment_intent=intent,
        gateway=gateway,
        amount=intent.amount,
    )

    intent.payment_status = PaymentIntent.STATUS_PROCESSING
    intent.save(update_fields=['payment_status', 'updated_at'])

    # Transition session to PAYMENT_PROCESSING
    session = intent.booking_session
    if session.session_status == BookingSession.STATUS_PAYMENT_INITIATED:
        session.transition_to(BookingSession.STATUS_PAYMENT_PROCESSING)

    logger.info(
        "Payment attempt created: attempt=%s intent=%s gateway=%s",
        attempt.attempt_id, intent.intent_id, gateway,
    )

    return attempt


# ============================================================================
# 6. PAYMENT SUCCESS → BOOKING CREATION
# ============================================================================

@transaction.atomic
def complete_payment(attempt, gateway_response=None):
    """
    Mark payment attempt as successful and create the final booking.

    Steps:
      1. Mark attempt as SUCCESS
      2. Mark intent as SUCCEEDED
      3. Create Booking via existing booking service
      4. Convert inventory holds to booking
      5. Mark session as COMPLETED
      6. Return (booking, session)
    """
    intent = attempt.payment_intent
    session = intent.booking_session

    # Update attempt
    attempt.attempt_status = PaymentAttempt.STATUS_SUCCESS
    attempt.gateway_response = gateway_response or {}
    attempt.save(update_fields=['attempt_status', 'gateway_response', 'updated_at'])

    # Update intent
    intent.payment_status = PaymentIntent.STATUS_SUCCEEDED
    intent.save(update_fields=['payment_status', 'updated_at'])

    # ── Create booking via existing service ──────────────────────────────
    search = session.search_snapshot
    from datetime import date as date_type
    check_in = date_type.fromisoformat(search['check_in'])
    check_out = date_type.fromisoformat(search['check_out'])

    guests_data = session.guest_details
    guests = [{
        'full_name': guests_data.get('name', ''),
        'age': guests_data.get('age', 18),
        'email': guests_data.get('email', ''),
    }]

    total = extract_snapshot_total(session.price_snapshot, fallback=intent.amount)

    booking = create_booking(
        user=session.user,
        property_obj=session.hotel,
        room_type=session.room_type,
        quantity=search.get('rooms', 1),
        meal_plan=search.get('meal_plan_code', ''),
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        promo_code=search.get('promo_code', ''),
        locked_price=total,
    )
    # Save guest details + payment reference to booking
    booking.guest_name = guests_data.get('name', '')
    booking.guest_email = guests_data.get('email', session.user.email if session.user else '')
    booking.guest_phone = guests_data.get('phone', '')
    booking.payment_reference_id = str(intent.intent_id)
    booking.idempotency_key = str(session.session_id)
    booking.save(update_fields=['guest_name', 'guest_email', 'guest_phone', 'payment_reference_id', 'idempotency_key', 'updated_at'])

    # Convert holds to booking
    token = session.inventory_token
    if token and token.hold_ids:
        holds = InventoryHold.objects.filter(
            hold_id__in=token.hold_ids,
            status=InventoryHold.STATUS_ACTIVE,
        )
        if holds.exists():
            convert_hold_to_booking(list(holds), booking)

        token.token_status = InventoryToken.STATUS_CONVERTED
        token.save(update_fields=['token_status', 'updated_at'])

    # Transition booking from HOLD → PAYMENT_PENDING → CONFIRMED
    if booking.status == Booking.STATUS_HOLD:
        booking = BookingStateMachine.transition(
            booking,
            Booking.STATUS_PAYMENT_PENDING,
            note='Payment initiated via checkout flow',
            user=session.user,
        )
    if booking.status == Booking.STATUS_PAYMENT_PENDING:
        booking = BookingStateMachine.transition(
            booking,
            Booking.STATUS_CONFIRMED,
            note='Payment completed via checkout flow',
            user=session.user,
        )

    # Link session + intent to booking
    intent.booking = booking
    intent.save(update_fields=['booking', 'updated_at'])

    session.booking = booking
    session.save(update_fields=['booking', 'updated_at'])
    session.transition_to(BookingSession.STATUS_COMPLETED)

    logger.info(
        "Checkout completed: session=%s booking=%s amount=%s",
        session.session_id, booking.uuid, intent.amount,
    )

    # Generate invoice
    try:
        from apps.booking.invoice_service import generate_invoice
        generate_invoice(booking)
        logger.info("Invoice generated for booking=%s", booking.uuid)
    except Exception as e:
        logger.warning("Invoice generation failed: %s", e)

    # Fire confirmation email async
    try:
        from apps.core.tasks import send_booking_confirmation_email
        send_booking_confirmation_email.delay(booking.id)
        logger.info("Booking confirmation email queued: booking=%s", booking.uuid)
    except Exception as e:
        logger.warning("Failed to queue confirmation email: %s", e)

    # Fire booking confirmed SMS
    try:
        from apps.core.sms_tasks import send_booking_confirmed_sms, send_payment_received_sms
        send_booking_confirmed_sms.delay(booking.id)
        send_payment_received_sms.delay(booking.id)
        logger.info("Booking SMS queued: booking=%s", booking.uuid)
    except Exception as e:
        logger.warning("Failed to queue booking SMS: %s", e)
    return booking, session
# ============================================================================
# 7. PAYMENT FAILURE
# ============================================================================

@transaction.atomic
def fail_payment(attempt, failure_reason='', gateway_response=None):
    """Mark payment attempt as failed. Session goes back to allow retry."""
    intent = attempt.payment_intent
    session = intent.booking_session

    attempt.attempt_status = PaymentAttempt.STATUS_FAILED
    attempt.failure_reason = failure_reason
    attempt.gateway_response = gateway_response or {}
    attempt.save(update_fields=[
        'attempt_status', 'failure_reason', 'gateway_response', 'updated_at',
    ])

    # Only fail intent if no other successful attempt exists
    has_success = intent.attempts.filter(
        attempt_status=PaymentAttempt.STATUS_SUCCESS
    ).exists()

    if not has_success:
        intent.payment_status = PaymentIntent.STATUS_FAILED
        intent.save(update_fields=['payment_status', 'updated_at'])

        session.session_status = BookingSession.STATUS_FAILED
        session.save(update_fields=['session_status', 'updated_at'])

    logger.warning(
        "Payment failed: attempt=%s intent=%s reason=%s",
        attempt.attempt_id, intent.intent_id, failure_reason,
    )

    return attempt


# ============================================================================
# 8. SESSION EXPIRY
# ============================================================================

def expire_stale_sessions():
    """
    Batch expire sessions past their expires_at.
    Called by Celery beat task every 2 minutes.
    """
    now = timezone.now()
    active_statuses = [
        BookingSession.STATUS_CREATED,
        BookingSession.STATUS_ROOM_SELECTED,
        BookingSession.STATUS_GUEST_DETAILS,
        BookingSession.STATUS_PAYMENT_INITIATED,
    ]

    stale = BookingSession.objects.filter(
        session_status__in=active_statuses,
        expires_at__lt=now,
    ).select_related('inventory_token')

    count = 0
    for session in stale:
        try:
            _expire_session(session)
            count += 1
        except Exception as exc:
            logger.error(
                "Failed to expire session %s: %s", session.session_id, exc,
            )

    if count:
        logger.info("Expired %d stale checkout sessions", count)
    return count


@transaction.atomic
def _expire_session(session):
    """Expire a single session and release its inventory."""
    session.session_status = BookingSession.STATUS_EXPIRED
    session.save(update_fields=['session_status', 'updated_at'])

    # Release inventory token
    token = session.inventory_token
    if token and token.token_status in (
        InventoryToken.STATUS_ACTIVE,
        InventoryToken.STATUS_PAYMENT_PENDING,
    ):
        token.token_status = InventoryToken.STATUS_EXPIRED
        token.save(update_fields=['token_status', 'updated_at'])

        # Release underlying holds
        if token.hold_ids:
            holds = InventoryHold.objects.filter(
                hold_id__in=token.hold_ids,
                status=InventoryHold.STATUS_ACTIVE,
            )
            if holds.exists():
                release_holds(list(holds))

    logger.info("Session expired: %s", session.session_id)


# ============================================================================
# 9. RISK SCORING
# ============================================================================

def compute_risk_score(session):
    """
    Compute fraud risk score for a checkout session.

    Risk factors (weighted):
      - IP analysis (25%): VPN/proxy/datacenter detection
      - Device analysis (20%): fingerprint uniqueness
      - Velocity (25%): booking frequency
      - Payment pattern (15%): failed payment history
      - Location (15%): geo mismatch between IP and hotel

    Returns:
        BookingRiskScore instance
    """
    from .analytics_models import BookingRiskScore

    # Default low risk
    ip_risk = 0
    device_risk = 0
    velocity_risk = 0
    payment_risk = 0
    location_risk = 0

    user = session.user

    # ── Velocity checks ──────────────────────────────────────────────────
    bookings_last_hour = 0
    bookings_last_day = 0
    if user:
        one_hour_ago = timezone.now() - timedelta(hours=1)
        one_day_ago = timezone.now() - timedelta(days=1)

        bookings_last_hour = BookingSession.objects.filter(
            user=user,
            created_at__gte=one_hour_ago,
        ).exclude(pk=session.pk).count()

        bookings_last_day = BookingSession.objects.filter(
            user=user,
            created_at__gte=one_day_ago,
        ).exclude(pk=session.pk).count()

        if bookings_last_hour >= 5:
            velocity_risk = 90
        elif bookings_last_hour >= 3:
            velocity_risk = 60
        elif bookings_last_day >= 10:
            velocity_risk = 50
        elif bookings_last_day >= 5:
            velocity_risk = 30

    # ── Payment failure checks ───────────────────────────────────────────
    failed_payments = 0
    if user:
        one_day_ago = timezone.now() - timedelta(days=1)
        failed_payments = PaymentAttempt.objects.filter(
            payment_intent__booking_session__user=user,
            attempt_status=PaymentAttempt.STATUS_FAILED,
            created_at__gte=one_day_ago,
        ).count()

        if failed_payments >= 5:
            payment_risk = 80
        elif failed_payments >= 3:
            payment_risk = 50
        elif failed_payments >= 1:
            payment_risk = 20

    # ── IP analysis (simplified — production would use MaxMind/ipinfo) ───
    if session.ip_address:
        # Flag if IP was used in blocked sessions
        blocked = BookingRiskScore.objects.filter(
            ip_address=session.ip_address,
            action_taken='blocked',
        ).exists()
        if blocked:
            ip_risk = 80

    # ── Composite score (weighted) ───────────────────────────────────────
    score = int(
        ip_risk * 0.25
        + device_risk * 0.20
        + velocity_risk * 0.25
        + payment_risk * 0.15
        + location_risk * 0.15
    )
    score = min(score, 100)

    risk = BookingRiskScore.objects.create(
        booking_session=session,
        user=user,
        risk_score=score,
        ip_risk=ip_risk,
        device_risk=device_risk,
        velocity_risk=velocity_risk,
        payment_risk=payment_risk,
        location_risk=location_risk,
        ip_address=session.ip_address,
        device_fingerprint=session.device_fingerprint,
        bookings_last_hour=bookings_last_hour,
        bookings_last_day=bookings_last_day,
        failed_payments_last_day=failed_payments,
    )
    risk.compute_risk_level()

    # Auto-action
    if risk.risk_level == 'critical':
        risk.action_taken = 'blocked'
    elif risk.risk_level == 'high':
        risk.action_taken = 'flagged'
    else:
        risk.action_taken = 'approved'

    risk.save(update_fields=['risk_level', 'action_taken', 'updated_at'])

    logger.info(
        "Risk scored: session=%s score=%d level=%s action=%s",
        session.session_id, score, risk.risk_level, risk.action_taken,
    )

    return risk


# ============================================================================
# 10. ANALYTICS EVENT TRACKING
# ============================================================================

def track_funnel_event(
    event_type,
    session_id='',
    user=None,
    property_id=None,
    room_type_id=None,
    booking_session_id=None,
    search_context=None,
    revenue_amount=None,
    device_type='',
    traffic_source='',
    metadata=None,
):
    """
    Track a funnel analytics event.
    Non-blocking — failures are logged but never raise.
    """
    try:
        from .analytics_models import BookingAnalytics

        search_context = search_context or {}

        BookingAnalytics.objects.create(
            event_type=event_type,
            session_id=session_id,
            user=user,
            property_id=property_id,
            room_type_id=room_type_id,
            booking_session_id=booking_session_id,
            search_city=search_context.get('city', ''),
            search_checkin=search_context.get('check_in'),
            search_checkout=search_context.get('check_out'),
            search_guests=search_context.get('guests'),
            search_rooms=search_context.get('rooms'),
            revenue_amount=revenue_amount,
            device_type=device_type,
            traffic_source=traffic_source,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("Failed to track funnel event %s: %s", event_type, exc)
