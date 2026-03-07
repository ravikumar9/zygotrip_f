from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Cab, CabAvailability, CabBooking


def get_cab_queryset(filters):
    queryset = Cab.objects.filter(is_active=True).select_related('owner').prefetch_related('images').order_by('-created_at')

    search_query = filters.get('search_query') or ''
    if search_query:
        queryset = queryset.filter(Q(name__icontains=search_query))

    selected_cities = filters.get('selected_cities') or []
    if selected_cities:
        queryset = queryset.filter(city__in=selected_cities)

    selected_seats = filters.get('selected_seats') or []
    if selected_seats:
        queryset = queryset.filter(seats__in=selected_seats)

    selected_fuels = filters.get('selected_fuels') or []
    if selected_fuels:
        queryset = queryset.filter(fuel_type__in=selected_fuels)

    max_price_val = filters.get('max_price_val')
    min_price_val = filters.get('min_price_val')
    if max_price_val is not None:
        queryset = queryset.filter(system_price_per_km__lte=max_price_val)
    if min_price_val is not None:
        queryset = queryset.filter(system_price_per_km__gte=min_price_val)

    sort_by = filters.get('sort_by', '')
    if sort_by == 'price_low':
        queryset = queryset.order_by('system_price_per_km')
    elif sort_by == 'price_high':
        queryset = queryset.order_by('-system_price_per_km')
    elif sort_by == 'seats':
        queryset = queryset.order_by('-seats')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset


def paginate_cabs(queryset, page, per_page=20):
    paginator = Paginator(queryset, per_page)
    try:
        page_num = int(page)
        if page_num < 1:
            page_num = 1
        return paginator.get_page(page_num)
    except (ValueError, TypeError):
        return paginator.get_page(1)


def get_cab_or_404(cab_id):
    return get_object_or_404(Cab, id=cab_id, is_active=True)


def get_owner_cab_or_404(cab_id, user):
    return get_object_or_404(Cab, id=cab_id, owner=user)


def get_owner_cabs(user):
    return Cab.objects.filter(owner=user).prefetch_related('images', 'bookings')


def get_cab_booking_or_404(booking_id):
    return get_object_or_404(CabBooking, id=booking_id)


def get_cab_availability(cab):
    return cab.availability.filter(date__gte=timezone.now().date()).order_by('date')[:30]
