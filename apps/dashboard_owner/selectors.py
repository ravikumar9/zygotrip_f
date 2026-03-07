from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import get_object_or_404


def get_owner_properties(user):
    property_model = apps.get_model('hotels', 'Property')
    filters = {"owner": user}
    try:
        property_model._meta.get_field('is_active')
        filters["is_active"] = True
    except FieldDoesNotExist:
        pass
    return property_model.objects.filter(**filters).prefetch_related('room_types', 'images', 'offers')


def get_property_or_404(property_id, user):
    property_model = apps.get_model('hotels', 'Property')
    return get_object_or_404(property_model, id=property_id, owner=user)


def get_room_or_404(room_id, user):
    room_model = apps.get_model('rooms', 'RoomType')
    return get_object_or_404(room_model, id=room_id, property__owner=user)


def get_or_create_rating(property_obj):
    rating_model = apps.get_model('hotels', 'RatingAggregate')
    return rating_model.objects.get_or_create(property=property_obj)
