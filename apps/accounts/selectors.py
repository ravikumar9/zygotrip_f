from django.db.models import Q
from django.apps import apps
from .models import Permission, RolePermission, UserRole


def user_has_role(user, role_code):
    if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False
    return UserRole.objects.filter(user=user, role__code=role_code, is_active=True, role__is_active=True).exists()


def user_has_permission(user, permission_code):
    if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False
    return RolePermission.objects.filter(
        role__userrole__user=user,
        permission__code=permission_code,
        is_active=True,
        role__is_active=True,
        permission__is_active=True,
    ).exists()


def get_customer_bookings(user):
    """Return bookings for a customer without direct app imports."""
    booking_model = apps.get_model("booking", "Booking")
    return booking_model.objects.filter(user=user).select_related("property").order_by("-created_at")


def get_booking_stats(bookings_queryset):
    """Aggregate booking stats from a queryset."""
    booking_model = apps.get_model("booking", "Booking")
    total_bookings = bookings_queryset.count()
    confirmed_bookings = bookings_queryset.filter(
        status__in=[booking_model.STATUS_CONFIRMED, booking_model.STATUS_PAYMENT]
    ).count()
    cancelled_bookings = bookings_queryset.filter(status=booking_model.STATUS_CANCELLED).count()
    return total_bookings, confirmed_bookings, cancelled_bookings