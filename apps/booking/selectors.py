from django.apps import apps
from django.shortcuts import get_object_or_404


def get_booking_or_403(user, uuid):
    booking_model = apps.get_model('booking', 'Booking')
    booking = get_object_or_404(booking_model, uuid=uuid, is_active=True)
    if booking.user != user:
        raise PermissionError
    return booking


def get_property_or_404(property_id):
    property_model = apps.get_model('hotels', 'Property')
    return get_object_or_404(property_model, id=property_id)
