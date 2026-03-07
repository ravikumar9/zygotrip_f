from django.apps import apps
from django.core.exceptions import ValidationError


def create_property_image(property_obj, image_url):
    if not image_url:
        return None
    image_model = apps.get_model('hotels', 'PropertyImage')
    try:
        return image_model.objects.create(property=property_obj, image_url=image_url, is_featured=True)
    except ValidationError:
        return None


def save_property_image(form, property_obj):
    img = form.save(commit=False)
    img.property = property_obj
    img.save()
    return img


def save_room(form, property_obj):
    room = form.save(commit=False)
    room.property = property_obj
    room.save()
    return room


def save_room_image(form, room):
    img = form.save(commit=False)
    img.room_type = room
    img.save()
    return img


def save_meal(form, property_obj):
    meal = form.save(commit=False)
    meal.property = property_obj
    meal.save()
    return meal


def save_offer(form, property_obj):
    offer = form.save(commit=False)
    offer.property = property_obj
    offer.save()
    return offer


def update_rating(property_obj, rating_obj, form):
    form.save()
    avg = (
        rating_obj.cleanliness
        + rating_obj.service
        + rating_obj.location
        + rating_obj.amenities
        + rating_obj.value_for_money
    ) / 5
    property_obj.rating = avg
    property_obj.save(update_fields=['rating', 'updated_at'])
    return rating_obj
