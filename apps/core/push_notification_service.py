"""
Push Notification Service — System 8: Multi-channel notification delivery.

Channels:
  1. FCM  — mobile push (Firebase Cloud Messaging)
  2. Email — via email_service.py
  3. SMS   — MSG91 / Twilio
  4. WhatsApp — via whatsapp_notifications.py

RULES:
  - All sends are non-blocking (Celery async tasks where possible)
  - Gracefully degrade if any channel is not configured
  - FCM tokens stored in DeviceFingerprint.fcm_token
"""
import logging
from typing import Optional, Dict, Any, List

from django.conf import settings

logger = logging.getLogger('zygotrip.push')


# ── FCM Client ────────────────────────────────────────────────────────────────

class FCMClient:
    """Firebase Cloud Messaging via Legacy HTTP API (or HTTP v1)."""

    LEGACY_URL = 'https://fcm.googleapis.com/fcm/send'

    def __init__(self):
        self.server_key  = getattr(settings, 'FCM_SERVER_KEY', '')
        self.project_id  = getattr(settings, 'FCM_PROJECT_ID', '')
        self.enabled     = bool(self.server_key or self.project_id)

    def _send_legacy(self, token: str, title: str, body: str, data: dict) -> bool:
        import requests
        headers = {
            'Authorization': f'key={self.server_key}',
            'Content-Type':  'application/json',
        }
        payload = {
            'to':           token,
            'notification': {'title': title, 'body': body},
            'data':         {str(k): str(v) for k, v in data.items()},
            'priority':     'high',
        }
        try:
            resp = requests.post(self.LEGACY_URL, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success', 0) > 0:
                    return True
                logger.warning('FCM token rejected: %s', result.get('results', []))
                return False
            logger.warning('FCM HTTP %s: %s', resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.error('FCM send error: %s', exc)
            return False

    def send(self, token: str, title: str, body: str, data: dict = None) -> bool:
        if not self.enabled:
            logger.debug('[FCM disabled] Would send "%s" to ...%s', title, token[-8:] if token else '')
            return False
        if not token:
            return False
        d = data or {}
        if self.server_key:
            return self._send_legacy(token, title, body, d)
        logger.warning('FCM HTTP v1 requires service account — not yet configured')
        return False

    def send_many(self, tokens: List[str], title: str, body: str, data: dict = None) -> dict:
        sent = failed = 0
        for tok in tokens:
            if self.send(tok, title, body, data):
                sent += 1
            else:
                failed += 1
        return {'sent': sent, 'failed': failed}


_fcm = FCMClient()


# ── SMS Client ────────────────────────────────────────────────────────────────

def _send_sms(phone: str, message: str) -> bool:
    """Send SMS via MSG91 (primary) or Twilio (fallback)."""
    provider = getattr(settings, 'SMS_PROVIDER', 'msg91')

    if provider == 'msg91':
        auth_key = getattr(settings, 'MSG91_AUTH_KEY', '')
        if not auth_key:
            logger.debug('[SMS/MSG91 disabled] Would send to %s', phone)
            return False
        import requests
        try:
            resp = requests.post(
                'https://api.msg91.com/api/v5/flow/',
                headers={'authkey': auth_key, 'Content-Type': 'application/json'},
                json={
                    'template_id': getattr(settings, 'MSG91_TEMPLATE_ID', ''),
                    'recipients':  [{'mobiles': phone, 'message': message}],
                },
                timeout=8,
            )
            return resp.status_code == 200
        except Exception as exc:
            logger.error('MSG91 SMS error: %s', exc)
            return False

    elif provider == 'twilio':
        sid   = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_  = getattr(settings, 'TWILIO_FROM_NUMBER', '')
        if not all([sid, token, from_]):
            logger.debug('[SMS/Twilio disabled]')
            return False
        try:
            from twilio.rest import Client
            Client(sid, token).messages.create(body=message, from_=from_, to=phone)
            return True
        except Exception as exc:
            logger.error('Twilio SMS error: %s', exc)
            return False
    return False


# ── Core dispatcher ───────────────────────────────────────────────────────────

def send_push_notification(
    user,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    channels: Optional[List[str]] = None,
) -> dict:
    """
    Dispatch notification to a user across multiple channels.

    Args:
        user      : User instance
        title     : Notification title
        body      : Notification body
        data      : Extra payload (FCM data dict)
        channels  : ['fcm', 'email', 'sms', 'whatsapp']  (None = ['fcm', 'email'])
    Returns:
        dict with per-channel results
    """
    if channels is None:
        channels = ['fcm', 'email']

    results = {}

    # ── FCM ───────────────────────────────────────────────────────────
    if 'fcm' in channels:
        try:
            from apps.core.device_fingerprint import DeviceFingerprint
            tokens = list(
                DeviceFingerprint.objects
                .filter(user=user)
                .exclude(fcm_token='')
                .values_list('fcm_token', flat=True)
            )
            if tokens:
                results['fcm'] = _fcm.send_many(tokens, title, body, data)
            else:
                results['fcm'] = {'sent': 0, 'failed': 0, 'reason': 'no_tokens'}
        except Exception as exc:
            results['fcm'] = {'error': str(exc)}

    # ── Email (async — just mark queued here) ─────────────────────────
    if 'email' in channels and getattr(user, 'email', None):
        results['email'] = {'queued': True}

    # ── SMS ───────────────────────────────────────────────────────────
    if 'sms' in channels:
        phone = getattr(user, 'phone', '') or ''
        if phone:
            ok = _send_sms(phone, f'{title}: {body}')
            results['sms'] = {'sent': ok}
        else:
            results['sms'] = {'sent': False, 'reason': 'no_phone'}

    # ── WhatsApp ──────────────────────────────────────────────────────
    if 'whatsapp' in channels:
        phone = getattr(user, 'phone', '') or ''
        if phone:
            try:
                from apps.core.whatsapp_notifications import WhatsAppClient
                wa = WhatsAppClient()
                r = wa.send_template(phone, 'generic_notification',
                                     components=[{'type': 'body', 'parameters': [
                                         {'type': 'text', 'text': title},
                                         {'type': 'text', 'text': body},
                                     ]}])
                results['whatsapp'] = r
            except Exception as exc:
                results['whatsapp'] = {'error': str(exc)}
        else:
            results['whatsapp'] = {'sent': False, 'reason': 'no_phone'}

    return results


# ── Customer notification helpers ─────────────────────────────────────────────

def notify_booking_confirmation(booking):
    """Async booking confirmation across all channels."""
    if not booking.user:
        return
    send_push_notification(
        booking.user,
        title='Booking Confirmed ✓',
        body=(f'Your booking at {booking.property.name if booking.property else "hotel"} '
              f'({booking.check_in} – {booking.check_out}) is confirmed. '
              f'Ref: {booking.public_booking_id}'),
        data={
            'type':       'booking_confirmed',
            'booking_id': str(booking.uuid),
        },
        channels=['fcm', 'email', 'whatsapp'],
    )


def notify_payment_success(booking, amount):
    if not booking.user:
        return
    send_push_notification(
        booking.user,
        title='Payment Successful ✓',
        body=f'₹{amount} paid for {booking.property.name if booking.property else "booking"}. '
             f'Ref: {booking.public_booking_id}',
        data={
            'type':       'payment_success',
            'booking_id': str(booking.uuid),
            'amount':     str(amount),
        },
    )


def notify_price_drop(user, property_name: str, old_price, new_price, property_uuid):
    drop_pct = round((float(old_price) - float(new_price)) / float(old_price) * 100, 0)
    send_push_notification(
        user,
        title=f'Price Drop! {drop_pct:.0f}% off 🎉',
        body=f'{property_name} is now ₹{new_price}/night (was ₹{old_price})',
        data={
            'type':          'price_drop',
            'property_uuid': str(property_uuid),
            'new_price':     str(new_price),
        },
    )


def notify_limited_availability(user, property_name: str, rooms_left: int, property_uuid):
    send_push_notification(
        user,
        title='⚠️ Only a few rooms left!',
        body=f'Only {rooms_left} room(s) at {property_name}. Book now!',
        data={
            'type':          'limited_availability',
            'property_uuid': str(property_uuid),
            'rooms_left':    str(rooms_left),
        },
    )


# ── Owner notification helpers ────────────────────────────────────────────────

def notify_owner_new_booking(booking):
    if not (booking.property and booking.property.owner):
        return
    send_push_notification(
        booking.property.owner,
        title='🎉 New Booking!',
        body=(f'Booking {booking.public_booking_id} for '
              f'{booking.property.name} '
              f'({booking.check_in} – {booking.check_out})'),
        data={
            'type':        'new_booking',
            'booking_id':  str(booking.uuid),
            'property_id': str(booking.property.id),
        },
        channels=['fcm', 'email', 'whatsapp'],
    )


def notify_owner_competitor_price(owner, property_name: str,
                                   market_avg, current_price, suggestion: str):
    send_push_notification(
        owner,
        title='Market Price Update',
        body=(f'{property_name}: Market avg ₹{market_avg}/night · '
              f'Your price ₹{current_price}/night. {suggestion}'),
        data={
            'type':          'competitor_price_change',
            'market_avg':    str(market_avg),
            'current_price': str(current_price),
        },
    )


def notify_owner_inventory_low(owner, property_name: str, rooms_left: int, date_str: str):
    send_push_notification(
        owner,
        title='Low Inventory Alert',
        body=f'{property_name}: only {rooms_left} room(s) available on {date_str}',
        data={
            'type':       'inventory_low',
            'rooms_left': str(rooms_left),
            'date':       date_str,
        },
    )


def notify_owner_high_demand(owner, property_name: str, date_str: str, multiplier: float):
    send_push_notification(
        owner,
        title='🔥 High Demand Alert',
        body=f'High demand expected for {property_name} on {date_str}. Consider raising prices.',
        data={
            'type':    'high_demand',
            'date':    date_str,
            'multiplier': str(multiplier),
        },
    )


# ── Admin alert ───────────────────────────────────────────────────────────────

def send_admin_alert(alert_type: str, message: str, severity: str = 'warning',
                     details: dict = None):
    """Log and email the admin team on critical platform anomalies."""
    log_level = {'info': 20, 'warning': 30, 'critical': 40}.get(severity, 30)
    logger.log(log_level, '[ADMIN ALERT][%s] %s — %s', severity.upper(), alert_type, message)

    if severity == 'critical':
        admin_email = getattr(settings, 'ADMIN_ALERT_EMAIL', 'admin@zygotrip.com')
        try:
            from apps.core.email_service import _send_template_email
            _send_template_email(
                to_email=admin_email,
                subject=f'[CRITICAL] {alert_type} — ZygoTrip',
                template=None,
                context={},
                fallback_text=(f'CRITICAL ALERT: {alert_type}\n\n{message}'
                               f'\n\nDetails: {details}'),
            )
        except Exception as exc:
            logger.error('Admin alert email failed: %s', exc)
