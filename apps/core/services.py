from django.apps import apps


def user_has_role(user, role_code):
    """Check user role without direct app imports."""
    if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False
    user_role_model = apps.get_model('accounts', 'UserRole')
    return user_role_model.objects.filter(
        user=user,
        role__code=role_code,
        is_active=True,
        role__is_active=True,
    ).exists()


def get_dashboard_data(user):
    """Return dashboard datasets using app registry lookups."""
    booking_model = apps.get_model('booking', 'Booking')
    property_model = apps.get_model('hotels', 'Property')
    cab_model = apps.get_model('cabs', 'Cab')
    bus_model = apps.get_model('buses', 'Bus')

    bookings = booking_model.objects.filter(user=user).order_by('-created_at')
    properties = property_model.objects.filter(owner=user).order_by('-created_at')
    cabs = cab_model.objects.filter(owner=user).order_by('-created_at')
    buses = bus_model.objects.filter(operator=user).order_by('-created_at')

    return {
        'bookings': bookings,
        'properties': properties,
        'cabs': cabs,
        'buses': buses,
    }


def get_home_data(limit=6):
    """Return featured properties and categories without direct app imports."""
    property_model = apps.get_model('hotels', 'Property')
    category_model = apps.get_model('hotels', 'Category')

    properties = property_model.objects.filter(is_active=True).order_by('-rating')[:limit]
    categories = category_model.objects.filter(is_active=True).order_by('name')

    return properties, categories
