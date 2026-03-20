"""FCM push notification service using firebase-admin SDK."""
import logging

from apps.notifications.models import DeviceToken, NotificationLog

logger = logging.getLogger(__name__)


class FCMService:
    def send_to_user(self, user, title, body, data=None):
        data = data or {}
        tokens_qs = DeviceToken.objects.filter(user=user, is_active=True)
        tokens = list(tokens_qs.values_list('token', flat=True))
        if not tokens:
            return {'success': True, 'sent_count': 0}

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in data.items()},
                tokens=tokens,
            )
            response = messaging.send_each_for_multicast(message)

            # Deactivate unregistered tokens to avoid repeated failures.
            for index, result in enumerate(response.responses):
                if result.success:
                    continue
                exc = result.exception
                if exc and ('UnregisteredError' in exc.__class__.__name__ or 'unregistered' in str(exc).lower()):
                    DeviceToken.objects.filter(token=tokens[index]).update(is_active=False)

            NotificationLog.objects.create(
                user=user,
                title=title,
                body=body,
                data=data,
                status=NotificationLog.STATUS_SENT if response.success_count > 0 else NotificationLog.STATUS_FAILED,
            )
            return {'success': response.success_count > 0, 'sent_count': response.success_count}
        except Exception as exc:
            logger.exception('send_to_user failed for user=%s: %s', getattr(user, 'id', None), exc)
            NotificationLog.objects.create(
                user=user,
                title=title,
                body=body,
                data=data,
                status=NotificationLog.STATUS_FAILED,
            )
            return {'success': False, 'sent_count': 0}

    def booking_confirmed(self, booking):
        return self.send_to_user(
            user=booking.user,
            title='Booking Confirmed!',
            body=f'Your stay at {booking.property.name} is confirmed',
            data={'type': 'booking_confirmed', 'booking_uuid': str(booking.public_booking_id)},
        )

    def payment_received(self, booking):
        return self.send_to_user(
            user=booking.user,
            title='Payment Received',
            body=f'Payment received for booking {booking.public_booking_id}',
            data={'type': 'payment_received', 'booking_uuid': str(booking.public_booking_id)},
        )

    def check_in_reminder(self, booking):
        return self.send_to_user(
            user=booking.user,
            title='Check-in Reminder',
            body=f'Your check-in at {booking.property.name} is in 24 hours',
            data={'type': 'check_in_reminder', 'booking_uuid': str(booking.public_booking_id)},
        )

    def refund_processed(self, booking):
        return self.send_to_user(
            user=booking.user,
            title='Refund Processed',
            body=f'Refund for booking {booking.public_booking_id} has been processed',
            data={'type': 'refund_processed', 'booking_uuid': str(booking.public_booking_id)},
        )

    def price_drop_alert(self, user, property_name, old_price, new_price):
        return self.send_to_user(
            user=user,
            title='Price Drop Alert',
            body=f'{property_name} dropped from Rs.{old_price} to Rs.{new_price}',
            data={'type': 'price_drop_alert'},
        )

    def wallet_credited(self, user, amount):
        return self.send_to_user(
            user=user,
            title='Wallet Credited',
            body=f'Rs.{amount} has been credited to your wallet',
            data={'type': 'wallet_credited', 'amount': str(amount)},
        )


fcm_service = FCMService()
