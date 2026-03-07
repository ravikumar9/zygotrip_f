from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.cabs.models import Cab, CabAvailability, CabBooking


def get_cab_queryset(filters):
	queryset = Cab.objects.filter(is_active=True)
	search_query = (filters.get('search_query') or '').strip()
	selected_cities = filters.get('selected_cities') or []
	selected_seats = filters.get('selected_seats') or []
	selected_fuels = filters.get('selected_fuels') or []
	max_price_val = filters.get('max_price_val')
	min_price_val = filters.get('min_price_val')

	if search_query:
		queryset = queryset.filter(Q(name__icontains=search_query))
	if selected_cities:
		queryset = queryset.filter(city__in=selected_cities)
	if selected_seats:
		try:
			selected_seats = [int(seats) for seats in selected_seats]
			queryset = queryset.filter(seats__in=selected_seats)
		except (ValueError, TypeError):
			pass
	if selected_fuels:
		queryset = queryset.filter(fuel_type__in=selected_fuels)
	if max_price_val is not None:
		try:
			queryset = queryset.filter(system_price_per_km__lte=Decimal(max_price_val))
		except (ValueError, TypeError):
			pass
	if min_price_val is not None:
		try:
			queryset = queryset.filter(system_price_per_km__gte=Decimal(min_price_val))
		except (ValueError, TypeError):
			pass

	sort_by = (filters.get('sort_by') or '').strip()
	if sort_by == 'price_low':
		queryset = queryset.order_by('system_price_per_km')
	elif sort_by == 'price_high':
		queryset = queryset.order_by('-system_price_per_km')
	else:
		queryset = queryset.order_by('-created_at')

	return queryset


def paginate_cabs(queryset, page, per_page=12):
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
	return Cab.objects.filter(owner=user).order_by('-created_at')


def get_cab_booking_or_404(booking_uuid, user):
	return get_object_or_404(CabBooking, uuid=booking_uuid, user=user)


def get_cab_availability(cab, booking_date):
	return CabAvailability.objects.filter(cab=cab, date=booking_date).first()
