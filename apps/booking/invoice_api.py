"""
Booking Invoice API — retrieve and generate GST-compliant invoices.

Endpoints:
  GET  /api/v1/booking/<uuid>/invoice/   — Get or generate invoice for a booking
  POST /api/v1/booking/<uuid>/invoice/   — (Re-)generate invoice
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.invoice.api')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def booking_invoice_api(request, booking_uuid):
    """
    GET  /api/v1/booking/<uuid>/invoice/  — Retrieve existing invoice
    POST /api/v1/booking/<uuid>/invoice/  — Generate/re-generate invoice
    """
    from apps.booking.models import Booking

    try:
        booking = Booking.objects.select_related(
            'property__owner', 'user', 'property__city'
        ).get(uuid=booking_uuid)
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found'}},
            status=404,
        )

    # Authorization: owner of the booking or admin
    if not (request.user.is_staff or booking.user == request.user):
        return Response(
            {'success': False, 'error': {'code': 'access_denied', 'message': 'Access denied'}},
            status=403,
        )

    if request.method == 'GET':
        try:
            invoice = booking.invoice
            from apps.booking.invoice_service import get_invoice_summary
            return Response({'success': True, 'data': get_invoice_summary(invoice)})
        except Exception:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'invoice_not_ready',
                        'message': 'Invoice not yet generated for this booking',
                    },
                },
                status=404,
            )

    # POST — generate or regenerate
    if booking.status not in ('confirmed', 'checked_in', 'checked_out', 'settled', 'settlement_pending'):
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'invalid_status',
                    'message': f'Cannot generate invoice for booking in status: {booking.status}',
                },
            },
            status=400,
        )

    try:
        from apps.booking.invoice_service import generate_invoice, get_invoice_summary
        invoice = generate_invoice(booking)
        return Response({'success': True, 'data': get_invoice_summary(invoice)}, status=201)
    except Exception as exc:
        logger.error('invoice generation failed for %s: %s', booking_uuid, exc, exc_info=True)
        return Response(
            {'success': False, 'error': {'code': 'invoice_generation_failed', 'message': 'Failed to generate invoice'}},
            status=500,
        )
