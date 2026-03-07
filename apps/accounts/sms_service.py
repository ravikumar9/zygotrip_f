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
    """Abstract SMS backend."""

    def send(self, phone: str, message: str) -> bool:
        raise NotImplementedError


class ConsoleSMSBackend(SMSBackend):
    """Dev backend — logs OTP to console."""

    def send(self, phone: str, message: str) -> bool:
        logger.info('[SMS-CONSOLE] To: %s | Message: %s', phone, message)
        print(f'\n======== OTP SMS ========')
        print(f'  To: {phone}')
        print(f'  Message: {message}')
        print(f'=========================\n')
        return True


class TwilioSMSBackend(SMSBackend):
    """Twilio SMS backend for production."""

    def send(self, phone: str, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            msg = client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_NUMBER,
                to=phone,
            )
            logger.info('Twilio SMS sent to %s: SID=%s', phone, msg.sid)
            return True
        except Exception as e:
            logger.error('Twilio SMS failed to %s: %s', phone, e)
            return False


class MSG91SMSBackend(SMSBackend):
    """MSG91 SMS backend — popular for Indian phone numbers."""

    def send(self, phone: str, message: str) -> bool:
        try:
            import requests
            url = 'https://api.msg91.com/api/v5/flow/'
            headers = {
                'authkey': settings.MSG91_AUTH_KEY,
                'Content-Type': 'application/json',
            }
            payload = {
                'template_id': settings.MSG91_TEMPLATE_ID,
                'recipients': [
                    {
                        'mobiles': phone,
                        'otp': message.split()[-1] if message else '',
                    },
                ],
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info('MSG91 SMS sent to %s', phone)
            return True
        except Exception as e:
            logger.error('MSG91 SMS failed to %s: %s', phone, e)
            return False


# Backend registry
_BACKENDS = {
    'console': ConsoleSMSBackend,
    'twilio': TwilioSMSBackend,
    'msg91': MSG91SMSBackend,
}


def get_sms_backend() -> SMSBackend:
    """Get configured SMS backend instance."""
    backend_name = getattr(settings, 'SMS_BACKEND', 'console')
    backend_cls = _BACKENDS.get(backend_name, ConsoleSMSBackend)
    return backend_cls()


def send_otp(phone: str, code: str) -> bool:
    """Send an OTP code via the configured SMS backend."""
    message = f'Your ZygoTrip verification code is: {code}. Valid for 5 minutes. Do not share.'
    backend = get_sms_backend()
    return backend.send(phone, message)
