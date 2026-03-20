"""Pre-built notification templates for common ZygoTrip events."""
from apps.notifications.fcm_service import fcm_service


def booking_confirmed(booking):
    """Notify guest that booking is confirmed."""
    if not booking.user:
        return
    fcm_service.send_to_user(
        user=booking.user,
        title='Booking Confirmed! 🎉',
        body=f'Your booking at {booking.property.name} is confirmed. Check-in: {booking.check_in}',
        data={
            'type': 'booking_confirmed',
            'booking_uuid': str(booking.uuid),
            'property_name': booking.property.name,
            'check_in': str(booking.check_in),
        },
    )


def payment_received(payment):
    """Notify user of successful payment."""
    booking = payment.booking if hasattr(payment, 'booking') else None
    user = getattr(booking, 'user', None) or getattr(payment, 'user', None)
    if not user:
        return
    fcm_service.send_to_user(
        user=user,
        title='Payment Received ✅',
        body=f'Payment of ₹{payment.amount} received successfully.',
        data={
            'type': 'payment_received',
            'amount': str(payment.amount),
            'transaction_id': str(getattr(payment, 'transaction_id', '')),
        },
    )


def check_in_reminder(booking):
    """Remind guest to check in tomorrow."""
    if not booking.user:
        return
    fcm_service.send_to_user(
        user=booking.user,
        title='Check-in Tomorrow 🏨',
        body=f'Reminder: You check in at {booking.property.name} tomorrow ({booking.check_in}).',
        data={
            'type': 'check_in_reminder',
            'booking_uuid': str(booking.uuid),
            'property_name': booking.property.name,
            'check_in': str(booking.check_in),
        },
    )


def checkout_reminder(booking):
    """Remind guest to check out today."""
    if not booking.user:
        return
    fcm_service.send_to_user(
        user=booking.user,
        title='Check-out Today 🧳',
        body=f'Your check-out at {booking.property.name} is today ({booking.check_out}). Safe travels!',
        data={
            'type': 'checkout_reminder',
            'booking_uuid': str(booking.uuid),
            'property_name': booking.property.name,
            'check_out': str(booking.check_out),
        },
    )


def price_drop_alert(property_obj, old_price, new_price):
    """Alert users who wishlisted this property of a price drop."""
    # Sends to topic: property_{id}_watchers
    savings = float(old_price) - float(new_price)
    fcm_service.send_to_topic(
        topic=f'property_{property_obj.id}_watchers',
        title=f'Price Drop! Save ₹{savings:.0f} 🎯',
        body=f'{property_obj.name} dropped from ₹{old_price:.0f} to ₹{new_price:.0f}',
        data={
            'type': 'price_drop',
            'property_id': str(property_obj.id),
            'property_slug': property_obj.slug,
            'old_price': str(old_price),
            'new_price': str(new_price),
        },
    )


def refund_processed(booking, amount):
    """Notify user that their refund has been processed."""
    if not booking.user:
        return
    fcm_service.send_to_user(
        user=booking.user,
        title='Refund Processed 💸',
        body=f'₹{amount} refund for booking {booking.public_booking_id} has been initiated.',
        data={
            'type': 'refund_processed',
            'booking_uuid': str(booking.uuid),
            'amount': str(amount),
        },
    )


def wallet_credited(wallet, amount):
    """Notify user their wallet was credited."""
    fcm_service.send_to_user(
        user=wallet.user,
        title='Wallet Credited 💰',
        body=f'₹{amount} has been added to your ZygoTrip wallet.',
        data={
            'type': 'wallet_credited',
            'amount': str(amount),
            'balance': str(wallet.balance),
        },
    )
