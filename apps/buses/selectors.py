from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Bus, BusBooking, BusSeat


def get_bus_queryset(filters):
    queryset = Bus.objects.filter(is_active=True)
    search_query = filters.get('search_query', '')
    if search_query:
        queryset = queryset.filter(
            Q(operator_name__icontains=search_query)
            | Q(from_city__icontains=search_query)
            | Q(to_city__icontains=search_query)
        )

    from_city = filters.get('from_city')
    to_city = filters.get('to_city')
    journey_date = filters.get('journey_date')

    if from_city:
        queryset = queryset.filter(from_city__icontains=from_city)
    if to_city:
        queryset = queryset.filter(to_city__icontains=to_city)
    if journey_date:
        queryset = queryset.filter(journey_date=journey_date)

    sort_by = filters.get('sort_by', '')
    if sort_by == 'price_low':
        queryset = queryset.order_by('price_per_seat')
    elif sort_by == 'price_high':
        queryset = queryset.order_by('-price_per_seat')
    elif sort_by == 'departure':
        queryset = queryset.order_by('departure_time')
    else:
        queryset = queryset.order_by('departure_time')

    return queryset


def paginate_buses(queryset, page, per_page=20):
    paginator = Paginator(queryset, per_page)
    try:
        page_num = int(page)
        if page_num < 1:
            page_num = 1
        return paginator.get_page(page_num)
    except (ValueError, TypeError):
        return paginator.get_page(1)


def get_bus_or_404(bus_id):
    return get_object_or_404(Bus, id=bus_id, is_active=True)


def get_booking_or_404(booking_uuid, user):
    return get_object_or_404(BusBooking, uuid=booking_uuid, user=user)


def get_available_seats(bus):
    return bus.seats.filter(state=BusSeat.AVAILABLE).order_by('row', 'column')
