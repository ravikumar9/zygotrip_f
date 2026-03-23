"""
Invoice PDF Generator — fpdf2-based booking invoice PDF.

Usage:
    from apps.booking.invoice_pdf import get_invoice_pdf_bytes
    pdf_bytes = get_invoice_pdf_bytes(booking)
"""
import logging

logger = logging.getLogger('zygotrip.invoice')


def generate_booking_invoice_pdf(booking) -> bytes:
    """
    Generate a GST-compliant invoice PDF for a confirmed booking.
    Returns bytes of the PDF file.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        logger.error('fpdf2 not installed. Run: pip install fpdf2')
        raise

    booking_ref = str(getattr(booking, 'public_booking_id', '') or booking.uuid)
    guest_name = getattr(booking, 'guest_name', '') or (
        booking.user.full_name if booking.user else 'Guest'
    )
    guest_email = getattr(booking, 'guest_email', '') or (
        booking.user.email if booking.user else ''
    )
    guest_phone = getattr(booking, 'guest_phone', '') or (
        getattr(booking.user, 'phone', '') if booking.user else ''
    )
    hotel_name = booking.property.name if booking.property else 'N/A'
    city_name = getattr(booking.property, 'city_name', '') if booking.property else ''
    check_in = booking.check_in.strftime('%d %b %Y') if booking.check_in else ''
    check_out = booking.check_out.strftime('%d %b %Y') if booking.check_out else ''
    nights = max(1, (booking.check_out - booking.check_in).days) if (booking.check_in and booking.check_out) else 1

    total_amount = float(getattr(booking, 'total_amount', 0) or 0)
    gst_amount = float(getattr(booking, 'gst_amount', 0) or 0)
    base_amount = float(getattr(booking, 'gross_amount', total_amount - gst_amount) or 0)
    promo_disc = 0.0
    svc_fee = 0.0
    try:
        bd = booking.price_breakdown
        base_amount = float(bd.base_amount or base_amount)
        gst_amount = float(bd.gst or gst_amount)
        promo_disc = float(bd.promo_discount or 0)
        svc_fee = float(bd.service_fee or 0)
    except Exception:
        pass

    from django.utils import timezone
    issued_at = timezone.now().strftime('%d %b %Y, %I:%M %p IST')

    invoice_number = ''
    try:
        invoice_number = booking.invoice.invoice_number
    except Exception:
        invoice_number = f'ZT-{booking_ref}'

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    PRIMARY = (235, 32, 38)
    DARK = (30, 30, 30)
    GRAY = (100, 100, 100)
    LGRAY = (240, 240, 240)
    WHITE = (255, 255, 255)
    GREEN = (22, 163, 74)

    # Header bar
    pdf.set_fill_color(*PRIMARY)
    pdf.rect(0, 0, 210, 28, 'F')
    pdf.set_text_color(*WHITE)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_xy(10, 7)
    pdf.cell(100, 10, 'ZygoTrip')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_xy(10, 17)
    pdf.cell(100, 6, 'Hotels  Buses  Holidays  Cabs')
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_xy(130, 7)
    pdf.cell(70, 8, 'TAX INVOICE', align='R')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_xy(130, 16)
    pdf.cell(70, 6, f'Invoice: {invoice_number}', align='R')

    # Status badge
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(*WHITE)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_xy(155, 30)
    pdf.cell(45, 7, 'BOOKING CONFIRMED', fill=True, align='C', border=1)

    # Booking ref + date
    pdf.set_text_color(*DARK)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_xy(10, 32)
    pdf.cell(0, 7, f'Booking ID: {booking_ref}', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, f'Issued: {issued_at}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(3)

    # Divider
    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Guest + Hotel info (two columns)
    y0 = pdf.get_y()
    col_w = 90

    pdf.set_text_color(*DARK)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_xy(10, y0)
    pdf.cell(col_w, 6, 'GUEST DETAILS', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    for label, val in [('Name', guest_name), ('Email', guest_email), ('Phone', guest_phone)]:
        pdf.set_x(10)
        pdf.cell(30, 5, f'{label}:')
        pdf.set_text_color(*DARK)
        pdf.cell(col_w - 30, 5, str(val), new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(*GRAY)

    pdf.set_xy(110, y0)
    pdf.set_text_color(*DARK)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(90, 6, 'PROPERTY DETAILS', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    for label, val in [
        ('Hotel', hotel_name), ('City', city_name),
        ('Check-in', check_in), ('Check-out', check_out), ('Nights', str(nights))
    ]:
        pdf.set_x(110)
        pdf.cell(30, 5, f'{label}:')
        pdf.set_text_color(*DARK)
        pdf.cell(60, 5, str(val), new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(*GRAY)

    pdf.ln(5)

    # Price breakdown table
    pdf.set_draw_color(*PRIMARY)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, 'PRICE BREAKDOWN', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_fill_color(*LGRAY)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(140, 7, 'Description', border=1, fill=True)
    pdf.cell(50, 7, 'Amount (INR)', border=1, fill=True, align='R', new_x='LMARGIN', new_y='NEXT')

    def row(desc, amount, bold=False, color=None):
        c = color or DARK
        pdf.set_font('Helvetica', 'B' if bold else '', 9)
        pdf.set_text_color(*c)
        pdf.cell(140, 6, desc, border=1)
        label = f'Rs {abs(amount):,.2f}' if amount >= 0 else f'-Rs {abs(amount):,.2f}'
        pdf.cell(50, 6, label, border=1, align='R', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(*DARK)

    row(f'Room charge ({nights} night{"s" if nights > 1 else ""})', base_amount)
    if svc_fee > 0:
        row('Service fee', svc_fee)
    if gst_amount > 0:
        row('GST & taxes', gst_amount)
    if promo_disc > 0:
        row('Promo discount', -promo_disc, color=GREEN)

    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(140, 8, 'TOTAL PAYABLE', border=1, fill=True)
    pdf.cell(50, 8, f'Rs {total_amount:,.2f}', border=1, fill=True, align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(*DARK)
    pdf.ln(5)

    # Footer
    pdf.set_draw_color(*PRIMARY)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5,
        'ZygoTrip Travel Technologies Pvt. Ltd.  |  support@zygotrip.com  |  www.zygotrip.com\n'
        'This is a computer-generated invoice and does not require a physical signature.\n'
        'For cancellations and refunds, please contact support within the cancellation window.'
    )

    return pdf.output()


def get_invoice_pdf_bytes(booking) -> bytes:
    """Public entry point. Returns PDF bytes or None on failure."""
    try:
        return generate_booking_invoice_pdf(booking)
    except Exception as exc:
        logger.error('Invoice PDF failed for booking %s: %s', getattr(booking, 'uuid', '?'), exc)
        return None
