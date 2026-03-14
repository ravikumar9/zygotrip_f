"""
Voucher & Ticket Generation Service.

Generates booking confirmation documents for all verticals:
- Hotel booking vouchers
- Bus tickets with seat info
- Cab ride confirmations
- Flight e-tickets
- Activity vouchers
- Package itinerary documents

Supports PDF generation and QR code encoding.
"""
import hashlib
import json
import logging
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.voucher')


class BookingVoucher(TimeStampedModel):
    """Generated voucher/ticket for a confirmed booking."""

    VOUCHER_HOTEL = 'hotel'
    VOUCHER_BUS = 'bus'
    VOUCHER_CAB = 'cab'
    VOUCHER_FLIGHT = 'flight'
    VOUCHER_ACTIVITY = 'activity'
    VOUCHER_PACKAGE = 'package'

    VOUCHER_TYPE_CHOICES = [
        (VOUCHER_HOTEL, 'Hotel Voucher'),
        (VOUCHER_BUS, 'Bus Ticket'),
        (VOUCHER_CAB, 'Cab Confirmation'),
        (VOUCHER_FLIGHT, 'E-Ticket'),
        (VOUCHER_ACTIVITY, 'Activity Voucher'),
        (VOUCHER_PACKAGE, 'Package Itinerary'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_USED = 'used'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_USED, 'Used'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    voucher_id = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True,
        help_text='Human-readable voucher ID e.g. ZV-20260311-A1B2C3',
    )
    voucher_type = models.CharField(max_length=20, choices=VOUCHER_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    # Polymorphic link to any booking type
    booking_uuid = models.UUIDField(db_index=True, help_text='UUID of the source booking')
    booking_ref = models.CharField(max_length=50, help_text='Public booking ID or PNR')

    # Guest info
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)

    # Voucher data (vertical-specific details as JSON)
    voucher_data = models.JSONField(
        default=dict,
        help_text='Structured voucher content: dates, venue, seat info etc.',
    )

    # QR code payload (hashed for verification)
    qr_payload = models.CharField(max_length=500, blank=True)
    qr_hash = models.CharField(max_length=64, blank=True, help_text='SHA-256 of qr_payload')

    # Timestamps
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_uuid'], name='voucher_booking_idx'),
            models.Index(fields=['voucher_type', 'status'], name='voucher_type_status_idx'),
            models.Index(fields=['guest_email'], name='voucher_guest_email_idx'),
        ]

    def __str__(self):
        return f"{self.voucher_id} ({self.get_voucher_type_display()})"

    def save(self, *args, **kwargs):
        if not self.voucher_id:
            date_str = timezone.now().strftime('%Y%m%d')
            short = uuid_lib.uuid4().hex[:6].upper()
            self.voucher_id = f"ZV-{date_str}-{short}"
        if self.qr_payload and not self.qr_hash:
            self.qr_hash = hashlib.sha256(self.qr_payload.encode()).hexdigest()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.status == self.STATUS_ACTIVE
            and self.valid_from <= now <= self.valid_until
        )

    def mark_used(self):
        self.status = self.STATUS_USED
        self.used_at = timezone.now()
        self.save(update_fields=['status', 'used_at', 'updated_at'])

    def mark_cancelled(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'updated_at'])


def generate_hotel_voucher(booking):
    """Generate hotel booking voucher."""
    from apps.booking.models import Booking
    qr_data = json.dumps({
        'type': 'hotel', 'booking': str(booking.uuid),
        'checkin': str(booking.check_in), 'checkout': str(booking.check_out),
    })
    voucher_data = {
        'property_name': booking.property.name if booking.property else '',
        'property_address': booking.property.address if booking.property else '',
        'check_in': str(booking.check_in),
        'check_out': str(booking.check_out),
        'guest_name': booking.guest_name,
        'total_amount': str(booking.total_amount),
        'rooms': [],
    }
    for br in booking.rooms.select_related('room_type').all():
        voucher_data['rooms'].append({
            'room_type': br.room_type.name if br.room_type else '',
            'quantity': br.quantity,
        })

    return BookingVoucher.objects.create(
        voucher_type=BookingVoucher.VOUCHER_HOTEL,
        booking_uuid=booking.uuid,
        booking_ref=booking.public_booking_id or str(booking.uuid),
        guest_name=booking.guest_name,
        guest_email=booking.guest_email,
        guest_phone=booking.guest_phone,
        voucher_data=voucher_data,
        qr_payload=qr_data,
        valid_from=timezone.now(),
        valid_until=timezone.make_aware(
            datetime.combine(booking.check_out, datetime.max.time())
        ) if booking.check_out else timezone.now(),
    )


def generate_bus_voucher(bus_booking):
    """Generate bus ticket voucher."""
    qr_data = json.dumps({
        'type': 'bus', 'pnr': getattr(bus_booking, 'pnr', ''),
        'booking_id': str(bus_booking.uuid) if hasattr(bus_booking, 'uuid') else str(bus_booking.pk),
    })
    voucher_data = {
        'operator': bus_booking.bus.operator if hasattr(bus_booking, 'bus') else '',
        'from_city': bus_booking.bus.from_city if hasattr(bus_booking, 'bus') else '',
        'to_city': bus_booking.bus.to_city if hasattr(bus_booking, 'bus') else '',
        'journey_date': str(bus_booking.journey_date) if hasattr(bus_booking, 'journey_date') else '',
        'departure_time': str(bus_booking.bus.departure_time) if hasattr(bus_booking, 'bus') else '',
        'pnr': getattr(bus_booking, 'pnr', ''),
        'seats': list(bus_booking.seats.values_list('seat_number', flat=True)) if hasattr(bus_booking, 'seats') else [],
        'total_amount': str(bus_booking.total_amount) if hasattr(bus_booking, 'total_amount') else '0',
    }
    return BookingVoucher.objects.create(
        voucher_type=BookingVoucher.VOUCHER_BUS,
        booking_uuid=getattr(bus_booking, 'uuid', uuid_lib.uuid4()),
        booking_ref=getattr(bus_booking, 'pnr', str(bus_booking.pk)),
        guest_name=getattr(bus_booking, 'passenger_name', ''),
        guest_email=getattr(bus_booking, 'contact_email', ''),
        guest_phone=getattr(bus_booking, 'contact_phone', ''),
        voucher_data=voucher_data,
        qr_payload=qr_data,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=1),
    )


def generate_flight_voucher(flight_booking):
    """Generate flight e-ticket voucher."""
    qr_data = json.dumps({
        'type': 'flight', 'pnr': flight_booking.pnr,
        'booking_id': str(flight_booking.uuid),
    })
    passengers = []
    if hasattr(flight_booking, 'passengers'):
        for p in flight_booking.passengers.all():
            passengers.append({
                'name': f"{p.first_name} {p.last_name}",
                'type': p.passenger_type,
                'seat': getattr(p, 'seat_number', ''),
            })
    voucher_data = {
        'pnr': flight_booking.pnr,
        'airline': str(flight_booking.fare_class.flight.airline) if flight_booking.fare_class else '',
        'flight_number': flight_booking.fare_class.flight.flight_number if flight_booking.fare_class else '',
        'origin': str(flight_booking.fare_class.flight.origin) if flight_booking.fare_class else '',
        'destination': str(flight_booking.fare_class.flight.destination) if flight_booking.fare_class else '',
        'departure': str(flight_booking.fare_class.flight.departure_datetime) if flight_booking.fare_class else '',
        'passengers': passengers,
        'total_amount': str(flight_booking.total_amount),
    }
    return BookingVoucher.objects.create(
        voucher_type=BookingVoucher.VOUCHER_FLIGHT,
        booking_uuid=flight_booking.uuid,
        booking_ref=flight_booking.pnr,
        guest_name=passengers[0]['name'] if passengers else '',
        guest_email=getattr(flight_booking, 'contact_email', ''),
        guest_phone=getattr(flight_booking, 'contact_phone', ''),
        voucher_data=voucher_data,
        qr_payload=qr_data,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=1),
    )


def generate_activity_voucher(activity_booking):
    """Generate activity voucher."""
    qr_data = json.dumps({
        'type': 'activity',
        'ref': activity_booking.booking_ref,
        'booking_id': str(activity_booking.uuid),
    })
    voucher_data = {
        'activity_name': activity_booking.activity.title if activity_booking.activity else '',
        'date': str(activity_booking.booking_date),
        'time_slot': str(activity_booking.time_slot) if activity_booking.time_slot else '',
        'participants': activity_booking.total_participants,
        'booking_ref': activity_booking.booking_ref,
        'total_amount': str(activity_booking.total_amount),
    }
    return BookingVoucher.objects.create(
        voucher_type=BookingVoucher.VOUCHER_ACTIVITY,
        booking_uuid=activity_booking.uuid,
        booking_ref=activity_booking.booking_ref,
        guest_name=activity_booking.user.full_name if activity_booking.user else '',
        guest_email=activity_booking.user.email if activity_booking.user else '',
        voucher_data=voucher_data,
        qr_payload=qr_data,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=1),
    )


def verify_voucher(voucher_id, qr_hash=None):
    """Verify a voucher is valid and optionally check QR integrity."""
    try:
        voucher = BookingVoucher.objects.get(voucher_id=voucher_id)
    except BookingVoucher.DoesNotExist:
        return {'valid': False, 'error': 'Voucher not found'}

    if not voucher.is_valid:
        return {'valid': False, 'error': f'Voucher status: {voucher.status}'}

    if qr_hash and voucher.qr_hash != qr_hash:
        return {'valid': False, 'error': 'QR verification failed'}

    return {
        'valid': True,
        'voucher_id': voucher.voucher_id,
        'voucher_type': voucher.voucher_type,
        'guest_name': voucher.guest_name,
        'booking_ref': voucher.booking_ref,
        'valid_until': voucher.valid_until.isoformat(),
    }
