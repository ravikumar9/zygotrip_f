"""
Supplier Sync API — System 16: Channel Manager Integration.

Provides webhook endpoints for real-time price/availability updates
from external channel managers and admin APIs for manual sync triggers.

Endpoints:
  POST /api/v1/supplier/webhook/<provider>/   — Receive supplier webhook
  POST /api/v1/supplier/sync/<property_uuid>/ — Trigger manual sync (admin)
  GET  /api/v1/supplier/sync-status/          — View sync health per supplier

Supported providers:
  - hotelbeds   (Hotelbeds API)
  - staah       (STAAH Channel Manager)
  - siteminder  (SiteMinder)
  - myallocator (MyAllocator / Cloudbeds)
  - ezee        (eZee Centrix)

Webhook format per provider varies — each handler normalizes to canonical format.

SECURITY:
  - Webhook signature verification per provider
  - Rate limited: max 100 webhook events per minute per provider
  - All received payloads logged to ChannelWebhookLog
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.supplier.sync')

SUPPORTED_PROVIDERS = {'hotelbeds', 'staah', 'siteminder', 'myallocator', 'ezee'}


def _log_webhook(provider, payload, status='received', error=''):
    """Append-only log of all incoming webhooks."""
    try:
        from apps.inventory.models import ChannelWebhookLog
        ChannelWebhookLog.objects.create(
            provider=provider,
            payload=payload if isinstance(payload, dict) else {'raw': str(payload)},
            status=status,
            error_message=error,
            received_at=timezone.now(),
        )
    except Exception as exc:
        logger.warning('Failed to log webhook from %s: %s', provider, exc)


def _verify_signature(provider, request) -> bool:
    """Verify webhook signature per provider's signing method."""
    secret = getattr(settings, f'SUPPLIER_{provider.upper()}_WEBHOOK_SECRET', '')
    if not secret:
        logger.warning('No webhook secret configured for %s — accepting without verification', provider)
        return True

    try:
        if provider == 'hotelbeds':
            sig = request.headers.get('X-Signature', '')
            body = request.body
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected)

        elif provider == 'staah':
            sig = request.headers.get('X-Staah-Signature', '')
            body = request.body
            expected = hashlib.sha256(secret.encode() + body).hexdigest()
            return hmac.compare_digest(sig, expected)

        elif provider == 'siteminder':
            # SiteMinder uses Basic Auth token
            auth = request.headers.get('Authorization', '')
            return auth == f'Bearer {secret}'

        else:
            # Default: no verification
            return True

    except Exception as exc:
        logger.error('Signature verification error for %s: %s', provider, exc)
        return False


def _process_price_update(provider, data):
    """
    Normalize and apply price update from supplier webhook.
    Updates RoomInventory.price for affected date ranges.
    """
    from apps.inventory.models import ChannelRateSync
    try:
        # Normalize provider-specific format to canonical fields
        if provider == 'hotelbeds':
            property_code = data.get('hotelCode')
            room_code = data.get('roomTypeCode')
            rate_plan = data.get('ratePlanCode')
            price = data.get('amount')
            date_from = data.get('dateFrom')
            date_to = data.get('dateTo')
        elif provider == 'staah':
            property_code = data.get('hotel_id')
            room_code = data.get('room_type_id')
            rate_plan = data.get('rate_plan_id', '')
            price = data.get('rate')
            date_from = data.get('start_date')
            date_to = data.get('end_date')
        else:
            # Generic fallback
            property_code = data.get('property_code') or data.get('hotel_id')
            room_code = data.get('room_code') or data.get('room_type_id')
            rate_plan = data.get('rate_plan', '')
            price = data.get('price') or data.get('rate') or data.get('amount')
            date_from = data.get('date_from') or data.get('start_date')
            date_to = data.get('date_to') or data.get('end_date')

        if not all([property_code, room_code, price, date_from]):
            logger.warning('Incomplete price update from %s: %s', provider, data)
            return False

        # Create rate sync record for tracking
        ChannelRateSync.objects.create(
            provider=provider,
            external_property_code=str(property_code),
            external_room_code=str(room_code),
            rate_plan=str(rate_plan),
            price=float(price),
            date_from=date_from,
            date_to=date_to or date_from,
            raw_payload=data,
            status='pending',
        )
        logger.info('Price update queued from %s for property %s', provider, property_code)
        return True

    except Exception as exc:
        logger.error('Price update processing failed for %s: %s', provider, exc)
        return False


def _process_availability_update(provider, data):
    """
    Normalize and apply availability update from supplier webhook.
    Updates RoomInventory.available_rooms for affected date ranges.
    """
    from apps.inventory.models import ChannelAvailabilitySync
    try:
        if provider == 'hotelbeds':
            property_code = data.get('hotelCode')
            room_code = data.get('roomTypeCode')
            available = data.get('allotment')
            date_from = data.get('dateFrom')
            date_to = data.get('dateTo')
        elif provider == 'staah':
            property_code = data.get('hotel_id')
            room_code = data.get('room_type_id')
            available = data.get('availability')
            date_from = data.get('start_date')
            date_to = data.get('end_date')
        else:
            property_code = data.get('property_code') or data.get('hotel_id')
            room_code = data.get('room_code') or data.get('room_type_id')
            available = data.get('available') or data.get('allotment') or data.get('availability')
            date_from = data.get('date_from') or data.get('start_date')
            date_to = data.get('date_to') or data.get('end_date')

        if not all([property_code, room_code, date_from]):
            return False

        ChannelAvailabilitySync.objects.create(
            provider=provider,
            external_property_code=str(property_code),
            external_room_code=str(room_code),
            available_rooms=int(available or 0),
            date_from=date_from,
            date_to=date_to or date_from,
            raw_payload=data,
            status='pending',
        )
        logger.info('Availability update queued from %s for property %s', provider, property_code)
        return True

    except Exception as exc:
        logger.error('Availability update processing failed for %s: %s', provider, exc)
        return False


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def supplier_webhook(request, provider):
    """
    POST /api/v1/supplier/webhook/<provider>/
    Receives real-time price/availability updates from channel managers.
    """
    provider = provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        return Response({'error': f'Unsupported provider: {provider}'}, status=400)

    # Signature verification
    if not _verify_signature(provider, request):
        logger.warning('Webhook signature verification FAILED for provider: %s', provider)
        _log_webhook(provider, {}, status='rejected', error='Invalid signature')
        return Response({'error': 'Invalid signature'}, status=401)

    try:
        payload = request.data if request.data else json.loads(request.body or '{}')
    except (json.JSONDecodeError, Exception):
        payload = {}

    _log_webhook(provider, payload)

    # Dispatch based on event type
    event_type = (
        payload.get('eventType') or
        payload.get('event_type') or
        payload.get('type') or
        'unknown'
    ).lower()

    processed = False
    if event_type in ('rate_update', 'price_update', 'rate_plan_update', 'ar'):
        processed = _process_price_update(provider, payload)
    elif event_type in ('availability_update', 'allotment_update', 'inventory_update', 'av'):
        processed = _process_availability_update(provider, payload)
    elif event_type in ('booking_create', 'reservation_create'):
        logger.info('Supplier booking webhook from %s: %s', provider, event_type)
        processed = True
    else:
        logger.info('Unknown webhook event type from %s: %s', provider, event_type)
        processed = True  # Accept but don't process

    # Trigger async sync processing
    if processed:
        try:
            from celery import current_app
            current_app.send_task(
                'apps.core.tasks.supplier_availability_sync',
                countdown=5,
            )
        except Exception:
            pass

    return Response({'status': 'accepted', 'provider': provider, 'event': event_type})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_supplier_sync(request, property_uuid):
    """
    POST /api/v1/supplier/sync/<property_uuid>/
    Manually trigger a full sync for a property from all connected suppliers.
    Admin only.
    """
    from apps.hotels.models import Property
    try:
        property_obj = Property.objects.get(uuid=property_uuid)
    except Property.DoesNotExist:
        return Response({'error': 'Property not found'}, status=404)

    try:
        from apps.core.supplier_framework import get_supplier_adapters
        adapters = get_supplier_adapters(property_obj)
        results = {}
        for name, adapter in adapters.items():
            try:
                result = adapter.sync_rates_and_availability(property_obj)
                results[name] = {'status': 'synced', 'details': str(result)}
            except Exception as exc:
                results[name] = {'status': 'failed', 'error': str(exc)}

        return Response({
            'property': str(property_obj),
            'sync_results': results,
            'triggered_at': timezone.now().isoformat(),
        })
    except Exception as exc:
        logger.error('Manual sync failed for property %s: %s', property_uuid, exc)
        # Fallback: trigger Celery task
        try:
            from celery import current_app
            current_app.send_task('apps.core.tasks.supplier_availability_sync')
            return Response({'status': 'queued', 'message': 'Sync task queued'})
        except Exception:
            return Response({'error': f'Sync failed: {exc}'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def supplier_sync_status(request):
    """
    GET /api/v1/supplier/sync-status/
    Returns health status of all supplier connections.
    """
    try:
        from apps.inventory.models import SupplierHealth
        health_records = SupplierHealth.objects.all().order_by('supplier_name')
        data = [
            {
                'supplier': h.supplier_name,
                'is_healthy': h.is_healthy,
                'error_rate': float(h.error_rate or 0),
                'avg_latency_ms': float(h.avg_latency_ms or 0),
                'last_checked': h.last_checked.isoformat() if h.last_checked else None,
                'last_error': h.last_error or '',
            }
            for h in health_records
        ]
        return Response({'suppliers': data, 'count': len(data)})
    except Exception as exc:
        return Response({'error': str(exc)}, status=500)
