"""
SMS Service — OTP delivery via configured SMS provider.
Supports:
  - Console/log backend (development)
  - Twilio (production)
  - MSG91 (Indian market, production)
Provider is selected by SMS_BACKEND setting.
"""
import logging
from django.conf import settings
logger = logging.getLogger('zygotrip.sms')

class SMSBackend:
    def send(self, phone: str, message: str) -> bool:
        raise NotImplementedError

class ConsoleSMSBackend(SMSBackend):
    def send(self, phone: str, message: str) -> bool:
        logger.info('[SMS-CONSOLE] To: %s | Message: %s', phone, message)
        print(f'\n======== OTP SMS ========\n  To: {phone}\n  Message: {message}\n=========================\n')
        return True

class TwilioSMSBackend(SMSBackend):
    def send(self, phone: str, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(body=message, from_=settings.TWILIO_FROM_NUMBER, to=phone)
            logger.info('Twilio SMS sent to %s: SID=%s', phone, msg.sid)
            return True
        except Exception as e:
            logger.error('Twilio SMS failed to %s: %s', phone, e)
            return False

class MSG91SMSBackend(SMSBackend):
    """MSG91 SMS backend using OTP API v5."""

    def send_otp(self, phone: str, otp: str) -> bool:
        """Send OTP via MSG91 Flow API (same as transactional SMS)."""
        try:
            import requests
            mobile = phone.replace('+', '').replace(' ', '').replace('-', '')
            if not mobile.startswith('91') and len(mobile) == 10:
                mobile = '91' + mobile

            # Use Flow API with OTP template - same approach as booking/payment SMS
            url = 'https://control.msg91.com/api/v5/flow/'
            payload = {
                'template_id': getattr(settings, 'MSG91_OTP_TEMPLATE_ID', ''),
                'sender': getattr(settings, 'MSG91_SENDER_ID', 'ZYGOIN'),
                'short_url': '0',
                'recipients': [{
                    'mobiles': mobile,
                    'number': otp,
                }]
            }
            headers = {
                'authkey': settings.MSG91_AUTH_KEY,
                'Content-Type': 'application/json',
                'accept': 'application/json',
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            logger.info('MSG91 OTP sent to %s: %s', phone, data)
            return data.get('type') == 'success'
        except Exception as e:
            logger.error('MSG91 OTP failed to %s: %s', phone, e)
            return False

    def send(self, phone: str, message: str) -> bool:
        """Send transactional SMS via MSG91 Flow API."""
        try:
            import requests
            mobile = phone.replace('+', '').replace(' ', '').replace('-', '')
            if not mobile.startswith('91') and len(mobile) == 10:
                mobile = '91' + mobile

            url = 'https://control.msg91.com/api/v5/flow/'
            headers = {
                'authkey': settings.MSG91_AUTH_KEY,
                'Content-Type': 'application/json',
            }
            payload = {
                'template_id': getattr(settings, 'MSG91_TEMPLATE_ID', ''),
                'sender': getattr(settings, 'MSG91_SENDER_ID', 'ZYGOIN'),
                'recipients': [{'mobiles': mobile}],
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            logger.info('MSG91 SMS sent to %s: %s', phone, data)
            return data.get('type') == 'success'
        except Exception as e:
            logger.error('MSG91 SMS failed to %s: %s', phone, e)
            return False

_BACKENDS = {
    'console': ConsoleSMSBackend,
    'twilio': TwilioSMSBackend,
    'msg91': MSG91SMSBackend,
}

def get_sms_backend() -> SMSBackend:
    backend_name = getattr(settings, 'SMS_BACKEND', 'console')
    backend_cls = _BACKENDS.get(backend_name, ConsoleSMSBackend)
    return backend_cls()

def send_otp(phone: str, code: str) -> bool:
    """Send OTP via configured backend."""
    backend = get_sms_backend()
    if isinstance(backend, MSG91SMSBackend):
        return backend.send_otp(phone, code)
    message = f'Your ZygoTrip OTP is {code}. Valid for 5 minutes. Do not share.'
    return backend.send(phone, message)
