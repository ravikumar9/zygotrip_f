from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.promos.models import Promo
from .models import CabAvailability, Cab


def get_best_coupon():
    try:
        now = timezone.now().date()
        coupons = Promo.objects.filter(
            is_active=True,
            applicable_module__in=['cabs', 'all'],
            starts_at__lte=now,
            ends_at__gte=now,
        ).order_by('-value')[:1]
        return coupons.first()
    except Exception:
        return None


def apply_promo_to_booking(booking, promo_code):
    if not promo_code:
        return None
    try:
        promo = Promo.objects.get(
            code=promo_code,
            is_active=True,
            applicable_module__in=['cabs', 'all'],
        )
    except Promo.DoesNotExist:
        return None

    now = timezone.now().date()
    if promo.starts_at and promo.starts_at > now:
        return None
    if promo.ends_at and promo.ends_at < now:
        return None

    if promo.discount_type == 'percent':
        discount = (booking.total_price * Decimal(promo.value)) / Decimal(100)
    else:
        discount = Decimal(promo.value)

    if promo.max_discount:
        discount = min(discount, Decimal(promo.max_discount))

    booking.discount_amount = discount
    booking.promo_code = promo_code
    booking.final_price = booking.total_price - discount
    return promo


def create_cab_booking(user, cab, form, promo_code):
    with transaction.atomic():
        booking = form.save(commit=False)
        booking.cab = cab
        booking.user = user
        booking.booking_date = form.cleaned_data['booking_date']
        booking.price_per_km = cab.system_price_per_km
        booking.base_fare = Decimal('50')

        availability, _ = CabAvailability.objects.select_for_update().get_or_create(
            cab=cab,
            date=booking.booking_date,
            defaults={'is_available': True},
        )
        if not availability.is_available:
            return None, 'Cab is not available for the selected date.'

        booking.calculate_total()
        applied_promo = apply_promo_to_booking(booking, promo_code)

        booking.save()
        availability.is_available = False
        availability.save(update_fields=['is_available', 'updated_at'])

        return booking, applied_promo


def set_system_price(cab):
    margin = getattr(settings, 'PLATFORM_CAB_MARGIN', 3)
    cab.system_price_per_km = cab.base_price_per_km + Decimal(margin)
    return cab


def update_cab_details(cab_id, user, form):
    with transaction.atomic():
        cab = Cab.objects.select_for_update().get(id=cab_id, owner=user)
        cab = form.save(commit=False)
        set_system_price(cab)
        cab.save()
        return cab


def deactivate_cab(cab_id, user):
    with transaction.atomic():
        cab = Cab.objects.select_for_update().get(id=cab_id, owner=user)
        cab.is_active = False
        cab.save(update_fields=['is_active', 'updated_at'])
        return cab
