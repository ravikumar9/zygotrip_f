from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from apps.accounts.selectors import user_has_role, get_customer_bookings, get_booking_stats
from apps.payments.selectors import invoices_for_user
from .forms import RegisterForm, CustomAuthenticationForm
from .services import assign_customer_role, assign_role
from .models import User, ROLE_CHOICES


class LoginView(DjangoLoginView):
	template_name = 'accounts/login.html'
	form_class = CustomAuthenticationForm
	redirect_authenticated_user = True

	def get_success_url(self):
		return reverse_lazy('core:home')


@login_required
def profile(request):
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	invoices = invoices_for_user(request.user)
	return render(request, 'accounts/profile.html', {'invoices': invoices})


@login_required
def customer_dashboard(request):
	"""Customer dashboard - shows bookings and booking history"""
	if not user_has_role(request.user, 'customer'):
		raise PermissionDenied
	
	# Get customer's bookings
	bookings = get_customer_bookings(request.user)
	
	# Statistics
	total_bookings, confirmed_bookings, cancelled_bookings = get_booking_stats(bookings)
	
	context = {
		'bookings': bookings,
		'total_bookings': total_bookings,
		'confirmed_bookings': confirmed_bookings,
		'cancelled_bookings': cancelled_bookings,
	}
	
	return render(request, 'accounts/customer_dashboard.html', context)


def logout_view(request):
	logout(request)
	return redirect('account_login')


# ========================================
# PHASE B: ROLE-SPECIFIC ENTRY POINTS
# ========================================

def _register_and_redirect(request, form_class, role, success_url, template='accounts/register.html'):
	"""Generic role registration helper"""
	form = form_class(request.POST or None)
	context = {
		'form': form,
		'role': role,
		'role_display': dict(ROLE_CHOICES).get(role, role),
	}
	
	if request.method == 'POST' and form.is_valid():
		user = form.save(commit=False)
		user.role = role
		user.save()
		
		# Assign M2M role for backward compatibility
		assign_customer_role(user) if role == 'traveler' else assign_role(user, role)
		
		login(request, user, backend='django.contrib.auth.backends.ModelBackend')
		return redirect(success_url)
	
	return render(request, template, context)


def register_traveler(request):
	"""Traveler registration - Book a Stay"""
	return _register_and_redirect(
		request, 
		RegisterForm, 
		'traveler',
		'core:home'
	)


def register_property_owner(request):
	"""Property Owner registration - List Your Property"""
	return _register_and_redirect(
		request,
		RegisterForm,
		'property_owner',
		'dashboard_owner:dashboard'
	)


def register_cab_owner(request):
	"""Cab Owner registration - Become a Cab Partner"""
	return _register_and_redirect(
		request,
		RegisterForm,
		'cab_owner',
		'vendor_cab_create'
	)


def register_bus_operator(request):
	"""Bus Operator registration - Become a Bus Operator"""
	return _register_and_redirect(
		request,
		RegisterForm,
		'bus_operator',
		'vendor_bus_create'
	)


def register_package_provider(request):
	"""Package Provider registration - Offer Holiday Packages"""
	return _register_and_redirect(
		request,
		RegisterForm,
		'package_provider',
		'core:home'  # TODO: Point to package dashboard
	)


def register_view(request):
	"""Legacy generic registration - redirects to traveler"""
	form = RegisterForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save(commit=False)
		user.role = 'traveler'  # Default to traveler
		user.save()
		assign_customer_role(user)
		login(request, user, backend='django.contrib.auth.backends.ModelBackend')
		return redirect('core:home')
	return render(request, 'accounts/register.html', {'form': form})