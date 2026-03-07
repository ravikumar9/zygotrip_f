from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.permissions import provider_required
from django.utils import timezone
from decimal import Decimal
from .forms import CabRegistrationForm, CabFilterForm, CabBookingForm
from .serializers import CabRenderReadySerializer
from .selectors import (
	get_cab_queryset,
	paginate_cabs,
	get_cab_or_404,
	get_owner_cab_or_404,
	get_owner_cabs,
	get_cab_booking_or_404,
	get_cab_availability,
)
from .services import get_best_coupon, create_cab_booking, set_system_price, update_cab_details, deactivate_cab
from .ota_selectors import get_ota_context


def cab_list(request):
	"""LIST CABS: Backend-driven OTA listing
	
	Uses get_ota_context() from ota_selectors.py
	Enforces all 8 OTA rules for consistent filtering
	"""
	context = get_ota_context(request)
	
	# Ensure all required context fields are present
	context.setdefault('empty_state', True)
	context.setdefault('total_count', 0)
	context.setdefault('filter_options', {})
	context.setdefault('selected_filters', {})
	context.setdefault('current_sort', 'popular')
	context.setdefault('page_title', 'Cabs - Zygotrip')
	
	return render(request, 'cabs/list.html', context)


def cab_detail(request, cab_id):
	"""
	Cab detail page with availability and booking
	"""
	cab = get_cab_or_404(cab_id)
	images = cab.images.all()
	availability = get_cab_availability(cab)
	
	context = {
		'cab': cab,
		'images': images,
		'availability': availability,
	}
	return render(request, 'cabs/detail.html', context)


@login_required
def cab_booking(request, cab_id):
	"""
	Cab booking with pricing calculation and coupon application
	"""
	cab = get_cab_or_404(cab_id)
	best_coupon = None
	
	if request.method == 'POST':
		form = CabBookingForm(request.POST)
		if form.is_valid():
			promo_code = form.cleaned_data.get('promo_code', '').strip().upper()
			booking, applied_promo = create_cab_booking(request.user, cab, form, promo_code)
			if booking is None:
				messages.error(request, 'Cab is not available for the selected date.')
				return redirect('cabs:booking', cab_id=cab.id)
			if promo_code and applied_promo is None:
				messages.warning(request, f'Promo code "{promo_code}" not found or invalid for cabs')
			messages.success(request, 'Booking confirmed! Check your bookings.')
			return redirect('cabs:booking-success', booking_id=booking.id)
		best_coupon = get_best_coupon()
	else:
		form = CabBookingForm()
		# Auto-suggest best coupon for cabs
		best_coupon = get_best_coupon()
	
	context = {
		'cab': cab,
		'form': form,
		'best_coupon': best_coupon,
	}
	return render(request, 'cabs/booking.html', context)


def booking_success(request, booking_id):
	"""Booking confirmation page"""
	booking = get_cab_booking_or_404(booking_id)
	if booking.user != request.user:
		messages.error(request, 'Unauthorized')
		return redirect('cabs:list')
	
	context = {'booking': booking}
	return render(request, 'cabs/booking_success.html', context)


@provider_required
def owner_cab_add(request):
	"""
	Owner registration form for adding new cabs
	"""
	# Check if user is owner (has owner role or permission)
	if request.method == 'POST':
		form = CabRegistrationForm(request.POST)
		if form.is_valid():
			cab = form.save(commit=False)
			cab.owner = request.user
			set_system_price(cab)
			cab.save()
			messages.success(request, 'Cab registered successfully!')
			return redirect('cabs:owner-list')
	else:
		form = CabRegistrationForm()
	
	context = {'form': form}
	return render(request, 'cabs/owner_registration.html', context)


@login_required
def owner_cab_list(request):
	"""
	Owner dashboard - list own cabs
	"""
	cabs = get_owner_cabs(request.user)
	
	context = {'cabs': cabs}
	return render(request, 'cabs/owner_list.html', context)


@login_required
def owner_cab_edit(request, cab_id):
	"""
	Owner edit cab details
	"""
	cab = get_owner_cab_or_404(cab_id, request.user)
	
	if request.method == 'POST':
		form = CabRegistrationForm(request.POST, instance=cab)
		if form.is_valid():
			update_cab_details(cab_id, request.user, form)
			messages.success(request, 'Cab updated successfully!')
			return redirect('cabs:owner-list')
	else:
		form = CabRegistrationForm(instance=cab)
	
	context = {'form': form, 'cab': cab}
	return render(request, 'cabs/owner_edit.html', context)


@login_required
def owner_cab_delete(request, cab_id):
	"""
	Owner delete cab (soft delete via is_active flag)
	"""
	cab = get_owner_cab_or_404(cab_id, request.user)
	
	if request.method == 'POST':
		deactivate_cab(cab_id, request.user)
		messages.success(request, 'Cab deleted successfully!')
		return redirect('cabs:owner-list')
	
	context = {'cab': cab}
	return render(request, 'cabs/owner_delete.html', context)


def coming_soon(request):
	context = {'module_name': 'Cabs'}
	return render(request, 'coming_soon.html', context)