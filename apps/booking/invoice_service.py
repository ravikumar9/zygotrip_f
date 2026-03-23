"""
GST-Compliant Invoice Generation Service — System 14.

Invoice number format: ZT-YYYYMMDD-NNNNNN (sequential per day)

GST rules:
  - Accommodation: 0% (<₹1000/night), 5% (₹1000–₹7500/night), 18% (>₹7500/night)
  - OTA Commission GST: 18% (B2B service)
"""
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.invoice')

_COMMISSION_GST_RATE = Decimal('0.18')
_DEFAULT_COMMISSION_PCT = Decimal('15.00')


def _q(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _generate_invoice_number(booking_date=None):
    """Generate unique invoice number: ZT-YYYYMMDD-NNNNNN"""
    from apps.booking.models import BookingInvoice
    target_date = booking_date or date.today()
    date_str = target_date.strftime('%Y%m%d')
    prefix = f'ZT-{date_str}-'
    count = BookingInvoice.objects.filter(invoice_number__startswith=prefix).count()
    seq = str(count + 1).zfill(6)
    return f'{prefix}{seq}'


def generate_invoice(booking):
    """
    Create or update a BookingInvoice for a confirmed booking.

    Args:
        booking: Booking instance (must be confirmed or later)

    Returns:
        BookingInvoice instance (status=issued)
    """
    from apps.booking.models import BookingInvoice
    from apps.pricing.pricing_service import get_gst_percentage

    billable = ('confirmed', 'checked_in', 'checked_out', 'settled', 'settlement_pending')
    if booking.status not in billable:
        raise ValueError(f'Cannot generate invoice for booking in status={booking.status!r}')

    with transaction.atomic():
        try:
            existing = BookingInvoice.objects.select_for_update().get(booking=booking)
            if existing.status == BookingInvoice.INVOICE_ISSUED:
                return existing
        except BookingInvoice.DoesNotExist:
            existing = None

        # ── Financial values ───────────────────────────────────────────────
        base_amount  = _q(booking.gross_amount or 0)
        discount     = _q(booking.discount_amount or 0) if hasattr(booking, 'discount_amount') and booking.discount_amount else _q(0)
        gst          = _q(booking.gst_amount or 0) if hasattr(booking, 'gst_amount') and booking.gst_amount else _q(0)
        svc_fee      = _q(0)
        try:
            bd = booking.price_breakdown
            svc_fee  = _q(bd.service_fee or 0)
            gst      = _q(bd.gst or 0)
            discount = _q(bd.promo_discount or 0)
        except Exception:
            pass
        final_price  = _q(booking.net_payable_to_hotel or base_amount)

        # ── Commission ─────────────────────────────────────────────────────
        commission_pct = _q(
            getattr(booking.property, 'commission_percentage', _DEFAULT_COMMISSION_PCT)
            if booking.property else _DEFAULT_COMMISSION_PCT
        )
        commission_amt = _q(base_amount * commission_pct / Decimal('100'))
        commission_gst = _q(commission_amt * _COMMISSION_GST_RATE)
        owner_payout   = _q(base_amount - commission_amt)

        # ── GST slab ──────────────────────────────────────────────────────
        nights = max(1, (booking.check_out - booking.check_in).days) if (booking.check_in and booking.check_out) else 1
        room_count = 1
        try:
            room_count = max(1, booking.rooms.count())
        except Exception:
            pass
        nightly_rate = _q(base_amount / (nights * room_count))
        gst_rate_pct = Decimal(get_gst_percentage(nightly_rate))

        # ── Parties ────────────────────────────────────────────────────────
        customer_name  = ''
        customer_email = ''
        customer_phone = ''
        if hasattr(booking, 'guest_name') and booking.guest_name:
            customer_name = booking.guest_name
        elif booking.user:
            customer_name = getattr(booking.user, 'full_name', '') or getattr(booking.user, 'email', '')
        if hasattr(booking, 'guest_email') and booking.guest_email:
            customer_email = booking.guest_email
        elif booking.user:
            customer_email = booking.user.email or ''
        if hasattr(booking, 'guest_phone') and booking.guest_phone:
            customer_phone = booking.guest_phone
        elif booking.user and hasattr(booking.user, 'phone'):
            customer_phone = booking.user.phone or ''

        prop = booking.property
        supplier_name = prop.name if prop else ''
        supplier_addr = ''
        if prop:
            parts = [getattr(prop, 'address', ''), str(getattr(prop, 'city', '') or '')]
            supplier_addr = ', '.join(p for p in parts if p)

        room_type_name = ''
        try:
            first_room = booking.rooms.select_related('room_type').first()
            if first_room:
                room_type_name = first_room.room_type.name
        except Exception:
            pass

        # ── Build / update ────────────────────────────────────────────────
        invoice_number = existing.invoice_number if existing else _generate_invoice_number(
            booking.created_at.date() if booking.created_at else None
        )

        fields = dict(
            invoice_number       = invoice_number,
            customer_name        = customer_name,
            customer_email       = customer_email,
            customer_phone       = customer_phone,
            supplier_name        = supplier_name,
            supplier_address     = supplier_addr,
            hotel_amount         = base_amount,
            discount_amount      = discount,
            commission_percentage= commission_pct,
            commission_amount    = commission_amt,
            commission_gst       = commission_gst,
            gst_amount           = gst,
            gst_rate             = gst_rate_pct,
            service_fee          = svc_fee,
            final_customer_price = final_price,
            owner_payout_amount  = owner_payout,
            status               = BookingInvoice.INVOICE_ISSUED,
            issued_at            = timezone.now(),
            booking_date         = booking.created_at.date() if booking.created_at else None,
            check_in_date        = booking.check_in,
            check_out_date       = booking.check_out,
            nights               = nights,
            rooms                = room_count,
            property_name        = supplier_name,
            room_type_name       = room_type_name,
        )

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.save()
            invoice = existing
        else:
            from apps.booking.models import BookingInvoice as BI
            invoice = BI.objects.create(booking=booking, **fields)

        logger.info('Invoice %s issued for booking %s', invoice.invoice_number,
                    booking.public_booking_id)
        return invoice


def get_invoice_summary(invoice) -> dict:
    """Return a serialization-ready dict for API or PDF."""
    return {
        'invoice_number':   invoice.invoice_number,
        'status':           invoice.status,
        'issued_at':        invoice.issued_at.isoformat() if invoice.issued_at else None,
        'booking_ref':      invoice.booking.public_booking_id,
        'customer': {
            'name':     invoice.customer_name,
            'email':    invoice.customer_email,
            'phone':    invoice.customer_phone,
            'gstin':    invoice.customer_gstin,
            'address':  invoice.customer_address,
        },
        'supplier': {
            'name':     invoice.supplier_name,
            'gstin':    invoice.supplier_gstin,
            'address':  invoice.supplier_address,
        },
        'stay': {
            'property':   invoice.property_name,
            'room_type':  invoice.room_type_name,
            'check_in':   str(invoice.check_in_date),
            'check_out':  str(invoice.check_out_date),
            'nights':     invoice.nights,
            'rooms':      invoice.rooms,
        },
        'financials': {
            'room_charge':         str(invoice.hotel_amount),
            'discount':            str(invoice.discount_amount),
            'service_fee':         str(invoice.service_fee),
            'gst_rate_pct':        str(invoice.gst_rate),
            'gst_amount':          str(invoice.gst_amount),
            'total_customer_pays': str(invoice.final_customer_price),
        },
        'ota_commission': {
            'commission_pct':       str(invoice.commission_percentage),
            'commission_amount':    str(invoice.commission_amount),
            'commission_gst_18pct': str(invoice.commission_gst),
            'owner_payout':         str(invoice.owner_payout_amount),
        },
    }
