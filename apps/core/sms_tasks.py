"""
SMS notification tasks using MSG91 Flow API with verified DLT templates.
"""
import logging
import requests
from celery import shared_task
from django.conf import settings

logger = logging.getLogger('zygotrip.sms')

def _send_msg91_flow(template_id: str, mobile: str, variables: dict) -> bool:
    """Send SMS via MSG91 Flow API."""
    mobile = mobile.replace('+', '').replace(' ', '').replace('-', '')
    if not mobile.startswith('91') and len(mobile) == 10:
        mobile = '91' + mobile

    auth_key = getattr(settings, 'MSG91_AUTH_KEY', '')
    sender = getattr(settings, 'MSG91_SENDER_ID', 'ZYGOIN')

    if not auth_key:
        logger.warning('MSG91_AUTH_KEY not configured')
        return False

    payload = {
        'template_id': template_id,
        'sender': sender,
        'short_url': '0',
        'recipients': [{
            'mobiles': mobile,
            **variables
        }]
    }
    headers = {
        'authkey': auth_key,
        'Content-Type': 'application/json',
        'accept': 'application/json',
    }
    try:
        resp = requests.post(
            'https://control.msg91.com/api/v5/flow/',
            json=payload, headers=headers, timeout=10
        )
        data = resp.json()
        logger.info('MSG91 Flow sent template=%s mobile=%s result=%s', template_id, mobile, data)
        return data.get('type') == 'success'
    except Exception as e:
        logger.error('MSG91 Flow failed template=%s mobile=%s error=%s', template_id, mobile, e)
        return False


@shared_task(bind=True, max_retries=3)
def send_booking_confirmed_sms(self, booking_id: int):
    try:
        from apps.booking.models import Booking
        b = Booking.objects.select_related('user', 'hotel').get(id=booking_id)
        phone = b.guest_phone or (b.user.phone if b.user else None)
        if not phone:
            return {'status': 'skipped', 'reason': 'no_phone'}
        template_id = getattr(settings, 'MSG91_BOOKING_TEMPLATE_ID', '')
        result = _send_msg91_flow(template_id, phone, {
            'alphanumeric': b.public_booking_id,
        })
        return {'status': 'sent' if result else 'failed', 'booking_id': booking_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=3)
def send_payment_received_sms(self, booking_id: int):
    try:
        from apps.booking.models import Booking
        b = Booking.objects.select_related('user', 'hotel').get(id=booking_id)
        phone = b.guest_phone or (b.user.phone if b.user else None)
        if not phone:
            return {'status': 'skipped', 'reason': 'no_phone'}
        template_id = getattr(settings, 'MSG91_PAYMENT_TEMPLATE_ID', '')
        result = _send_msg91_flow(template_id, phone, {
            'number': str(int(b.total_amount)),
            'alphanumeric': b.public_booking_id,
        })
        return {'status': 'sent' if result else 'failed', 'booking_id': booking_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=3)
def send_booking_cancelled_sms(self, booking_id: int):
    try:
        from apps.booking.models import Booking
        b = Booking.objects.select_related('user').get(id=booking_id)
        phone = b.guest_phone or (b.user.phone if b.user else None)
        if not phone:
            return {'status': 'skipped', 'reason': 'no_phone'}
        template_id = getattr(settings, 'MSG91_CANCEL_TEMPLATE_ID', '')
        result = _send_msg91_flow(template_id, phone, {
            'alphanumeric': b.public_booking_id,
        })
        return {'status': 'sent' if result else 'failed', 'booking_id': booking_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
