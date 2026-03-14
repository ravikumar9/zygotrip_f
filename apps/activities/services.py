"""
Activities search & booking services.

Functions:
  search_activities       — city + date search with category/price filters
  get_activity_detail     — full detail with slots, images, reviews
  create_activity_booking — atomic booking with capacity decrement
  cancel_activity_booking — cancellation with refund calculation
"""
import logging
from decimal import Decimal
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    Activity, ActivityTimeSlot, ActivityBooking,
    ActivityBookingParticipant, ActivityPriceBreakdown,
    ActivityCancellationPolicy,
)

logger = logging.getLogger('zygotrip.activities')

SERVICE_FEE_PERCENT = Decimal('5')
GST_PERCENT = Decimal('18')


def search_activities(city, date=None, category_slug=None, min_price=None,
                      max_price=None, difficulty=None, sort_by='rating',
                      max_results=40):
    """Search activities by city with optional filters."""
    qs = Activity.objects.filter(city__iexact=city, is_active=True)

    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    if min_price is not None:
        qs = qs.filter(adult_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(adult_price__lte=max_price)

    # If date, filter only those with available slots
    if date:
        from django.db.models import F
        qs = qs.filter(
            time_slots__date=date,
            time_slots__is_active=True,
            time_slots__booked_count__lt=F('time_slots__max_capacity')
        ).distinct()

    SORT_MAP = {
        'rating': ['-avg_rating', '-review_count'],
        'price_low': ['adult_price'],
        'price_high': ['-adult_price'],
        'popular': ['-review_count', '-avg_rating'],
    }
    qs = qs.order_by(*SORT_MAP.get(sort_by, ['-avg_rating']))

    activities = qs.select_related('category').prefetch_related('images')[:max_results]

    results = []
    for act in activities:
        primary_img = act.images.filter(is_primary=True).first()
        results.append({
            'id': act.id,
            'uuid': str(act.uuid),
            'title': act.title,
            'slug': act.slug,
            'category': act.category.name if act.category else None,
            'city': act.city,
            'duration_display': act.duration_display,
            'adult_price': str(act.adult_price),
            'child_price': str(act.child_price),
            'avg_rating': str(act.avg_rating),
            'review_count': act.review_count,
            'is_instant_confirmation': act.is_instant_confirmation,
            'is_free_cancellation': act.is_free_cancellation,
            'image_url': primary_img.image.url if primary_img else None,
            'short_description': act.short_description,
        })
    return results


def get_available_slots(activity_id, date):
    """Get available time slots for an activity on a date."""
    from django.db.models import F
    return ActivityTimeSlot.objects.filter(
        activity_id=activity_id, date=date, is_active=True,
    ).exclude(
        booked_count__gte=F('max_capacity')
    )


@transaction.atomic
def create_activity_booking(user, activity_id, time_slot_id, adults, children,
                            participants_data, contact_name, contact_email,
                            contact_phone, special_requests='', promo_code=''):
    """Create an activity booking with capacity check."""
    slot = ActivityTimeSlot.objects.select_for_update().get(pk=time_slot_id)
    activity = slot.activity

    total_pax = adults + children
    if slot.available_spots < total_pax:
        raise ValueError(
            f"Only {slot.available_spots} spots available, {total_pax} requested")

    # Calculate pricing
    unit_price = slot.effective_price
    adult_subtotal = unit_price * adults
    child_subtotal = activity.child_price * children
    subtotal = adult_subtotal + child_subtotal

    # Group discount
    group_discount = Decimal('0')
    if total_pax >= activity.min_group_size and activity.group_discount_percent > 0:
        group_discount = (subtotal * activity.group_discount_percent / 100).quantize(Decimal('0.01'))

    after_discount = subtotal - group_discount
    service_fee = (after_discount * SERVICE_FEE_PERCENT / 100).quantize(Decimal('0.01'))
    gst = (after_discount * GST_PERCENT / 100).quantize(Decimal('0.01'))
    total_amount = (after_discount + service_fee + gst).quantize(Decimal('0.01'))

    # Promo not implemented here — plug into promos app
    promo_discount = Decimal('0')
    final_amount = total_amount - promo_discount

    booking = ActivityBooking.objects.create(
        user=user, activity=activity, time_slot=slot,
        adults=adults, children=children,
        total_amount=total_amount, discount_amount=promo_discount,
        final_amount=final_amount, promo_code=promo_code,
        contact_name=contact_name, contact_email=contact_email,
        contact_phone=contact_phone, special_requests=special_requests,
        status='confirmed' if activity.is_instant_confirmation else 'initiated',
    )

    # Create participants
    for p in participants_data:
        ActivityBookingParticipant.objects.create(
            booking=booking, name=p['name'],
            pax_type=p.get('pax_type', 'adult'),
            age=p.get('age'), phone=p.get('phone', ''))

    # Price breakdown
    ActivityPriceBreakdown.objects.create(
        booking=booking, adult_subtotal=adult_subtotal,
        child_subtotal=child_subtotal, group_discount=group_discount,
        service_fee=service_fee, gst=gst,
        promo_discount=promo_discount, total_amount=final_amount)

    # Decrement capacity
    slot.booked_count += total_pax
    slot.save(update_fields=['booked_count', 'updated_at'])

    logger.info("Activity booking %s created for %s (slot=%s, pax=%d)",
                booking.booking_ref, user.id, slot.id, total_pax)
    return booking


@transaction.atomic
def cancel_activity_booking(booking_id):
    """Cancel an activity booking with refund calculation."""
    booking = ActivityBooking.objects.select_for_update().get(pk=booking_id)
    if booking.status not in ('initiated', 'confirmed'):
        raise ValueError(f"Cannot cancel booking in '{booking.status}' status")

    # Calculate refund from cancellation policies
    slot = booking.time_slot
    slot_start = timezone.make_aware(
        timezone.datetime.combine(slot.date, slot.start_time),
        timezone.get_current_timezone())
    hours_left = max(0, (slot_start - timezone.now()).total_seconds() / 3600)

    policies = ActivityCancellationPolicy.objects.filter(
        activity=booking.activity
    ).order_by('hours_before')

    refund_pct = Decimal('0')
    cancel_fee = Decimal('0')
    for policy in policies:
        if hours_left >= policy.hours_before:
            refund_pct = policy.refund_percentage
            cancel_fee = policy.cancellation_fee
            break

    refund_amount = (booking.final_amount * refund_pct / 100 - cancel_fee).quantize(Decimal('0.01'))
    refund_amount = max(Decimal('0'), refund_amount)

    booking.transition_to('cancelled')

    # Release capacity
    total_pax = booking.adults + booking.children
    slot.booked_count = max(0, slot.booked_count - total_pax)
    slot.save(update_fields=['booked_count', 'updated_at'])

    logger.info("Activity booking %s cancelled, refund=%.2f",
                booking.booking_ref, refund_amount)

    return {
        'booking_ref': booking.booking_ref,
        'status': 'cancelled',
        'refund_amount': str(refund_amount),
        'cancellation_fee': str(cancel_fee),
    }
