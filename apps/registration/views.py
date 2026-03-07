from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from apps.accounts.selectors import user_has_role
from .forms import PropertyRegistrationForm, BusRegistrationForm, CabRegistrationForm
from .services import ensure_role, create_property_from_form, create_bus_from_form, create_cab_from_form


@login_required
def register_property(request):
	"""Property registration for owners"""
	if not user_has_role(request.user, 'property_owner'):
		ensure_role(request.user, 'property_owner', 'Property Owner')
	
	if request.method == 'POST':
		form = PropertyRegistrationForm(request.POST)
		if form.is_valid():
			property_obj = create_property_from_form(form, request.user)
			messages.success(request, f'Property "{property_obj.name}" registered successfully!')
			return redirect('dashboard_owner:dashboard')
	else:
		form = PropertyRegistrationForm()
	
	return render(request, 'registration/property_register.html', {'form': form})


@login_required
def register_bus(request):
	"""Bus registration for operators"""
	if not user_has_role(request.user, 'bus_owner'):
		ensure_role(request.user, 'bus_owner', 'Bus Owner')
	
	if request.method == 'POST':
		form = BusRegistrationForm(request.POST)
		if form.is_valid():
			bus = create_bus_from_form(form, request.user)
			messages.success(request, f'Bus "{bus.name}" registered successfully!')
			return redirect('buses:dashboard')
	else:
		form = BusRegistrationForm()
	
	return render(request, 'registration/bus_register.html', {'form': form})


@login_required
def register_cab(request):
	"""Cab registration for operators"""
	if not user_has_role(request.user, 'cab_owner'):
		ensure_role(request.user, 'cab_owner', 'Cab Owner')
	
	if request.method == 'POST':
		form = CabRegistrationForm(request.POST)
		if form.is_valid():
			cab = create_cab_from_form(form, request.user)
			messages.success(request, f'Cab registered successfully!')
			return redirect('cabs:dashboard')
	else:
		form = CabRegistrationForm()
	
	return render(request, 'registration/cab_register.html', {'form': form})