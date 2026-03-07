# ==========================================
# PHASE 10: ROLE-BASED ACCESS CONTROL (NEW)
# ==========================================

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse


def role_required(*allowed_roles):
	"""
	Decorator to restrict view access to users with specific roles.
	
	Usage:
		@role_required('property_owner', 'admin')
		def owner_dashboard(request):
			...
	
	Behavior:
	- Redirects unauthenticated users to login
	- Redirects unauthorized users to their appropriate role dashboard
	- Allows access if user.role in allowed_roles
	"""
	def decorator(view_func):
		@wraps(view_func)
		@login_required(login_url='login')
		def wrapper(request, *args, **kwargs):
			user = request.user
			
			# Check if user has allowed role
			if user.role not in allowed_roles:
				# Role-based redirect
				role_redirects = {
					'traveler': 'traveler_dashboard',
					'property_owner': 'owner_dashboard',
					'cab_owner': 'cab_dashboard',
					'bus_operator': 'bus_dashboard',
					'package_provider': 'package_dashboard',
					'admin': 'admin:index',
				}
				
				redirect_url = reverse(role_redirects.get(user.role, 'home'))
				return HttpResponseRedirect(redirect_url)
			
			return view_func(request, *args, **kwargs)
		
		return wrapper
	return decorator


def vendor_required(view_func):
	"""
	Decorator to restrict access to vendors only (non-traveler, non-admin).
	
	Usage:
		@vendor_required
		def vendor_dashboard(request):
			...
	"""
	allowed_vendor_roles = ['property_owner', 'cab_owner', 'bus_operator', 'package_provider']
	return role_required(*allowed_vendor_roles)(view_func)


def property_owner_required(view_func):
	"""Restrict to property owners only"""
	return role_required('property_owner')(view_func)


def cab_owner_required(view_func):
	"""Restrict to cab owners only"""
	return role_required('cab_owner')(view_func)


def bus_operator_required(view_func):
	"""Restrict to bus operators only"""
	return role_required('bus_operator')(view_func)


def package_provider_required(view_func):
	"""Restrict to package providers only"""
	return role_required('package_provider')(view_func)


def admin_required(view_func):
	"""Restrict to admin/staff only"""
	@wraps(view_func)
	@login_required(login_url='login')
	def wrapper(request, *args, **kwargs):
		if not (request.user.is_admin() or request.user.is_staff):
			return HttpResponseRedirect(reverse('home'))
		return view_func(request, *args, **kwargs)
	return wrapper


def traveler_only(view_func):
	"""Restrict to travelers only (no vendors, no admin)"""
	return role_required('traveler')(view_func)
