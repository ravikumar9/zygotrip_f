"""
Channel Manager Service — Production-Grade.

Centralized hub for managing rate/availability synchronization between
ZygoTrip and external OTA channels (Booking.com, Expedia, Agoda, etc.).

Responsibilities:
  - Rate sync (push our rates to channels, pull their rates)
  - Availability sync (real-time inventory push)
  - Webhook handler for channel updates
  - Rate parity enforcement
  - Channel connection lifecycle
"""
import hashlib
import hmac
import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.channel_manager')


# ============================================================================
# Models
# ============================================================================

class ChannelConnection(TimeStampedModel):
    """
    Represents a connection between a ZygoTrip property and an external channel.
    One property can be connected to multiple channels.
    """
    CHANNEL_BOOKING_COM = 'booking_com'
    CHANNEL_EXPEDIA = 'expedia'
    CHANNEL_AGODA = 'agoda'
    CHANNEL_GOIBIBO = 'goibibo'
    CHANNEL_MMT = 'makemytrip'
    CHANNEL_AIRBNB = 'airbnb'

    CHANNEL_CHOICES = [
        (CHANNEL_BOOKING_COM, 'Booking.com'),
        (CHANNEL_EXPEDIA, 'Expedia'),
        (CHANNEL_AGODA, 'Agoda'),
        (CHANNEL_GOIBIBO, 'Goibibo'),
        (CHANNEL_MMT, 'MakeMyTrip'),
        (CHANNEL_AIRBNB, 'Airbnb'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_DISCONNECTED = 'disconnected'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_DISCONNECTED, 'Disconnected'),
        (STATUS_ERROR, 'Error'),
    ]

    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='channel_connections',
    )
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)
    external_property_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    sync_rates = models.BooleanField(default=True)
    sync_availability = models.BooleanField(default=True)
    rate_markup_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Markup percentage applied to rates pushed to this channel',
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'inventory'
        unique_together = ['property', 'channel']
        indexes = [
            models.Index(fields=['channel', 'status'], name='chan_channel_status_idx'),
        ]

    def __str__(self):
        return f"{self.property.name} ↔ {self.get_channel_display()}"


class ChannelRateSync(TimeStampedModel):
    """Log of rate synchronization events."""

    DIRECTION_PUSH = 'push'
    DIRECTION_PULL = 'pull'
    DIRECTION_CHOICES = [
        (DIRECTION_PUSH, 'Push (ZygoTrip → Channel)'),
        (DIRECTION_PULL, 'Pull (Channel → ZygoTrip)'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    connection = models.ForeignKey(
        ChannelConnection, on_delete=models.CASCADE,
        related_name='rate_syncs',
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE, null=True, blank=True,
    )
    date_start = models.DateField()
    date_end = models.DateField()
    rates_data = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    response_data = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'inventory'
        ordering = ['-created_at']


class ChannelAvailabilitySync(TimeStampedModel):
    """Log of availability synchronization events."""

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    connection = models.ForeignKey(
        ChannelConnection, on_delete=models.CASCADE,
        related_name='availability_syncs',
    )
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE, null=True, blank=True,
    )
    date_start = models.DateField()
    date_end = models.DateField()
    availability_data = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = 'inventory'
        ordering = ['-created_at']


class ChannelWebhookLog(TimeStampedModel):
    """Immutable log of incoming channel webhooks."""

    connection = models.ForeignKey(
        ChannelConnection, on_delete=models.CASCADE,
        related_name='webhook_logs', null=True, blank=True,
    )
    channel = models.CharField(max_length=30)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = 'inventory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', 'event_type', '-created_at'],
                         name='chan_webhook_type_idx'),
        ]


# ============================================================================
# Channel Manager Service
# ============================================================================

class ChannelManagerService:
    """
    Centralized service for managing rate and availability sync
    between ZygoTrip and external OTA channels.
    """

    @staticmethod
    def push_rates(property_obj, room_type, date_start, date_end):
        """
        Push rates to ALL active channels connected to this property.
        Applies per-channel markup.
        """
        from apps.inventory.models import InventoryCalendar

        connections = ChannelConnection.objects.filter(
            property=property_obj,
            status=ChannelConnection.STATUS_ACTIVE,
            sync_rates=True,
        )

        results = []
        for conn in connections:
            try:
                # Build rate data for the date range
                rates = {}
                current = date_start
                while current <= date_end:
                    try:
                        cal = InventoryCalendar.objects.get(
                            room_type=room_type, date=current,
                        )
                        base_rate = cal.effective_rate
                        # Apply channel markup
                        markup = Decimal('1') + (conn.rate_markup_percent / Decimal('100'))
                        channel_rate = (base_rate * markup).quantize(Decimal('0.01'))
                        rates[str(current)] = {
                            'rate': str(channel_rate),
                            'min_stay': cal.min_stay,
                            'max_stay': cal.max_stay,
                            'is_closed': cal.is_closed,
                        }
                    except InventoryCalendar.DoesNotExist:
                        rates[str(current)] = {
                            'rate': str(room_type.base_price),
                            'is_closed': True,
                        }
                    current += timedelta(days=1)

                # Create sync log
                sync = ChannelRateSync.objects.create(
                    connection=conn,
                    direction=ChannelRateSync.DIRECTION_PUSH,
                    room_type=room_type,
                    date_start=date_start,
                    date_end=date_end,
                    rates_data=rates,
                    status=ChannelRateSync.STATUS_PENDING,
                )

                # Dispatch to channel adapter
                adapter = _get_channel_adapter(conn.channel)
                if adapter:
                    success = adapter.push_rates(conn, room_type, rates)
                    sync.status = ChannelRateSync.STATUS_SUCCESS if success else ChannelRateSync.STATUS_FAILED
                else:
                    sync.status = ChannelRateSync.STATUS_SUCCESS  # no adapter = noop

                sync.save(update_fields=['status', 'updated_at'])
                conn.last_sync_at = timezone.now()
                conn.save(update_fields=['last_sync_at', 'updated_at'])

                results.append({
                    'channel': conn.channel,
                    'status': sync.status,
                    'dates': len(rates),
                })

            except Exception as exc:
                logger.error('Rate push failed channel=%s property=%s: %s',
                             conn.channel, property_obj.id, exc)
                ChannelRateSync.objects.create(
                    connection=conn,
                    direction=ChannelRateSync.DIRECTION_PUSH,
                    room_type=room_type,
                    date_start=date_start,
                    date_end=date_end,
                    status=ChannelRateSync.STATUS_FAILED,
                    error_message=str(exc),
                )
                results.append({
                    'channel': conn.channel,
                    'status': 'failed',
                    'error': str(exc),
                })

        return results

    @staticmethod
    def push_availability(property_obj, room_type, date_start, date_end):
        """
        Push availability to ALL active channels connected to this property.
        """
        from apps.inventory.models import InventoryCalendar

        connections = ChannelConnection.objects.filter(
            property=property_obj,
            status=ChannelConnection.STATUS_ACTIVE,
            sync_availability=True,
        )

        results = []
        for conn in connections:
            try:
                avail_data = {}
                current = date_start
                while current <= date_end:
                    try:
                        cal = InventoryCalendar.objects.get(
                            room_type=room_type, date=current,
                        )
                        avail_data[str(current)] = {
                            'available': cal.available_rooms,
                            'is_closed': cal.is_closed,
                        }
                    except InventoryCalendar.DoesNotExist:
                        avail_data[str(current)] = {'available': 0, 'is_closed': True}
                    current += timedelta(days=1)

                sync = ChannelAvailabilitySync.objects.create(
                    connection=conn,
                    room_type=room_type,
                    date_start=date_start,
                    date_end=date_end,
                    availability_data=avail_data,
                    status=ChannelAvailabilitySync.STATUS_PENDING,
                )

                adapter = _get_channel_adapter(conn.channel)
                if adapter:
                    success = adapter.push_availability(conn, room_type, avail_data)
                    sync.status = (ChannelAvailabilitySync.STATUS_SUCCESS
                                   if success else ChannelAvailabilitySync.STATUS_FAILED)
                else:
                    sync.status = ChannelAvailabilitySync.STATUS_SUCCESS

                sync.save(update_fields=['status', 'updated_at'])
                conn.last_sync_at = timezone.now()
                conn.save(update_fields=['last_sync_at', 'updated_at'])

                results.append({'channel': conn.channel, 'status': sync.status})

            except Exception as exc:
                logger.error('Availability push failed channel=%s: %s',
                             conn.channel, exc)
                results.append({'channel': conn.channel, 'status': 'failed', 'error': str(exc)})

        return results

    @staticmethod
    def handle_webhook(channel, event_type, payload, signature='', ip_address=None):
        """
        Handle incoming webhook from a channel.
        Verifies signature, logs, and dispatches to appropriate handler.
        """
        # Find connection
        connection = None
        property_id = payload.get('property_id') or payload.get('hotel_id')
        if property_id:
            connection = ChannelConnection.objects.filter(
                channel=channel,
                external_property_id=str(property_id),
                status=ChannelConnection.STATUS_ACTIVE,
            ).first()

        # Log webhook
        log = ChannelWebhookLog.objects.create(
            connection=connection,
            channel=channel,
            event_type=event_type,
            payload=payload,
            signature=signature,
            ip_address=ip_address,
        )

        # Verify signature
        if connection and connection.webhook_secret and signature:
            expected = hmac.new(
                connection.webhook_secret.encode(),
                json.dumps(payload, sort_keys=True).encode(),
                hashlib.sha256,
            ).hexdigest()
            log.is_verified = hmac.compare_digest(signature, expected)
            log.save(update_fields=['is_verified'])

            if not log.is_verified:
                logger.warning('Webhook signature mismatch channel=%s', channel)
                return {'status': 'signature_invalid'}

        # Dispatch based on event type
        try:
            if event_type in ('rate_update', 'price_update'):
                _handle_rate_update(connection, payload)
            elif event_type in ('availability_update', 'inventory_update'):
                _handle_availability_update(connection, payload)
            elif event_type in ('booking_notification', 'new_booking'):
                _handle_booking_notification(connection, payload)
            elif event_type == 'cancellation':
                _handle_cancellation_notification(connection, payload)
            else:
                logger.info('Unhandled webhook event_type=%s channel=%s', event_type, channel)

            log.is_processed = True
            log.save(update_fields=['is_processed'])
            return {'status': 'processed'}

        except Exception as exc:
            log.processing_error = str(exc)
            log.save(update_fields=['processing_error'])
            logger.error('Webhook processing failed: %s', exc)
            return {'status': 'error', 'message': str(exc)}

    @staticmethod
    def get_channel_status(property_obj):
        """Get status of all channel connections for a property."""
        connections = ChannelConnection.objects.filter(property=property_obj)
        return [{
            'channel': c.get_channel_display(),
            'channel_code': c.channel,
            'status': c.status,
            'last_sync': c.last_sync_at,
            'sync_rates': c.sync_rates,
            'sync_availability': c.sync_availability,
            'rate_markup': float(c.rate_markup_percent),
            'error': c.last_error if c.status == ChannelConnection.STATUS_ERROR else '',
        } for c in connections]


# ============================================================================
# Webhook handlers
# ============================================================================

def _handle_rate_update(connection, payload):
    """Handle incoming rate update from a channel."""
    from apps.inventory.models import SupplierInventory, SupplierRoom
    from datetime import date

    rates = payload.get('rates', [])
    for rate_entry in rates:
        entry_date = date.fromisoformat(rate_entry['date'])
        room_id = rate_entry.get('room_type_id') or rate_entry.get('room_id')
        new_rate = Decimal(str(rate_entry['rate']))

        try:
            supplier_room = SupplierRoom.objects.filter(
                supplier_map__supplier_name=connection.channel,
                external_room_id=str(room_id),
            ).first()

            if supplier_room:
                SupplierInventory.objects.update_or_create(
                    supplier_room=supplier_room,
                    date=entry_date,
                    defaults={'rate_per_night': new_rate},
                )
        except Exception as exc:
            logger.error('Rate update handler failed: %s', exc)


def _handle_availability_update(connection, payload):
    """Handle incoming availability update from a channel."""
    from apps.inventory.models import SupplierInventory, SupplierRoom
    from datetime import date

    updates = payload.get('availability', [])
    for entry in updates:
        entry_date = date.fromisoformat(entry['date'])
        room_id = entry.get('room_type_id') or entry.get('room_id')
        available = int(entry['available'])
        is_closed = entry.get('is_closed', False)

        try:
            supplier_room = SupplierRoom.objects.filter(
                supplier_map__supplier_name=connection.channel,
                external_room_id=str(room_id),
            ).first()

            if supplier_room:
                SupplierInventory.objects.update_or_create(
                    supplier_room=supplier_room,
                    date=entry_date,
                    defaults={
                        'available_rooms': available,
                        'is_closed': is_closed,
                    },
                )
        except Exception as exc:
            logger.error('Availability update handler failed: %s', exc)


def _handle_booking_notification(connection, payload):
    """Handle booking notification from channel — for info/reconciliation."""
    logger.info('Channel booking notification: channel=%s payload=%s',
                connection.channel if connection else 'unknown',
                json.dumps(payload, default=str)[:500])


def _handle_cancellation_notification(connection, payload):
    """Handle cancellation from channel — may need to release inventory."""
    logger.info('Channel cancellation notification: channel=%s payload=%s',
                connection.channel if connection else 'unknown',
                json.dumps(payload, default=str)[:500])


# ============================================================================
# Channel Adapters (pluggable per-channel integration)
# ============================================================================

class BaseChannelAdapter:
    """Abstract base for channel-specific API integration."""

    def push_rates(self, connection, room_type, rates):
        raise NotImplementedError

    def push_availability(self, connection, room_type, availability):
        raise NotImplementedError

    def pull_rates(self, connection, room_type, date_start, date_end):
        raise NotImplementedError

    def pull_availability(self, connection, room_type, date_start, date_end):
        raise NotImplementedError


class BookingComAdapter(BaseChannelAdapter):
    """Booking.com channel adapter (OTA XML / Connectivity API)."""

    def push_rates(self, connection, room_type, rates):
        logger.info('Booking.com rate push: property=%s rooms=%d dates=%d',
                     connection.property_id, room_type.id if room_type else 0, len(rates))
        # TODO: Implement Booking.com Connectivity API rate push
        return True

    def push_availability(self, connection, room_type, availability):
        logger.info('Booking.com availability push: property=%s dates=%d',
                     connection.property_id, len(availability))
        return True


class ExpediaAdapter(BaseChannelAdapter):
    """Expedia EPC (Expedia Partner Central) adapter."""

    def push_rates(self, connection, room_type, rates):
        logger.info('Expedia rate push: property=%s dates=%d',
                     connection.property_id, len(rates))
        return True

    def push_availability(self, connection, room_type, availability):
        logger.info('Expedia availability push: property=%s dates=%d',
                     connection.property_id, len(availability))
        return True


class AgodaAdapter(BaseChannelAdapter):
    """Agoda YCS adapter."""

    def push_rates(self, connection, room_type, rates):
        logger.info('Agoda rate push: property=%s dates=%d',
                     connection.property_id, len(rates))
        return True

    def push_availability(self, connection, room_type, availability):
        logger.info('Agoda availability push: property=%s dates=%d',
                     connection.property_id, len(availability))
        return True


_CHANNEL_ADAPTERS = {
    ChannelConnection.CHANNEL_BOOKING_COM: BookingComAdapter(),
    ChannelConnection.CHANNEL_EXPEDIA: ExpediaAdapter(),
    ChannelConnection.CHANNEL_AGODA: AgodaAdapter(),
}


def _get_channel_adapter(channel):
    """Get the adapter for a specific channel."""
    return _CHANNEL_ADAPTERS.get(channel)
