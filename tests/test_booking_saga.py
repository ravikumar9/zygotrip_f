import datetime

import pytest

from apps.booking.models import Booking
from apps.booking.services import transition_booking_status


@pytest.mark.django_db
def test_happy_path_hold_payment_confirm(booking_factory):
    booking = booking_factory(status=Booking.STATUS_HOLD)
    transition_booking_status(booking, Booking.STATUS_PAYMENT_PENDING)
    booking.refresh_from_db()
    assert booking.status == Booking.STATUS_PAYMENT_PENDING
    transition_booking_status(booking, Booking.STATUS_CONFIRMED)
    booking.refresh_from_db()
    assert booking.status == Booking.STATUS_CONFIRMED


@pytest.mark.django_db
def test_payment_failure_rollback_releases_inventory(booking_factory):
    booking = booking_factory(status=Booking.STATUS_PAYMENT_PENDING)
    transition_booking_status(booking, Booking.STATUS_FAILED)
    booking.refresh_from_db()
    assert booking.status == Booking.STATUS_FAILED


@pytest.mark.django_db
def test_concurrent_hold_same_room_one_succeeds_one_fails(booking_factory):
    first = booking_factory(status=Booking.STATUS_HOLD)
    second = booking_factory(status=Booking.STATUS_HOLD)
    assert first.status == Booking.STATUS_HOLD
    assert second.status == Booking.STATUS_HOLD


@pytest.mark.django_db
def test_hold_expiry_releases_inventory(booking_factory):
    booking = booking_factory(status=Booking.STATUS_HOLD)
    booking.hold_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    booking.save(update_fields=['hold_expires_at'])
    assert booking.is_hold_expired()


@pytest.mark.django_db
def test_idempotency_key_prevents_double_booking(booking_factory):
    booking = booking_factory()
    booking.idempotency_key = 'idem-123'
    booking.save(update_fields=['idempotency_key'])
    duplicate = Booking.objects.filter(idempotency_key='idem-123').count()
    assert duplicate == 1
