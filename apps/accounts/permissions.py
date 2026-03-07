from functools import wraps
from django.core.exceptions import PermissionDenied
from .selectors import user_has_role


def login_required_403(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


def role_required(role_code):
    def decorator(view_func):
        @login_required_403
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not user_has_role(request.user, role_code):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def provider_required(view_func):
    """
    Decorator for provider creation routes
    Allows users with any of these roles: property_owner, bus_operator, cab_provider, package_provider
    """
    @login_required_403
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        allowed_roles = ['property_owner', 'bus_operator', 'cab_provider', 'package_provider']
        has_provider_role = any(user_has_role(request.user, role) for role in allowed_roles)
        if not has_provider_role:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


class RoleRequiredMixin:
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_role and not user_has_role(request.user, self.required_role):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ==========================================
# PHASE 10: PERMISSION CHECKING UTILITIES (NEW)
# ==========================================

def has_role(user, *roles):
	"""Check if user has any of the given roles"""
	return user.is_authenticated and user.role in roles


def is_traveler(user):
	"""Check if user is a traveler"""
	return user.is_authenticated and user.role == 'traveler'


def is_vendor(user):
	"""Check if user is any type of vendor"""
	vendor_roles = {'property_owner', 'cab_owner', 'bus_operator', 'package_provider'}
	return user.is_authenticated and user.role in vendor_roles


def is_property_owner(user):
	"""Check if user is a property owner"""
	return user.is_authenticated and user.role == 'property_owner'


def is_cab_owner(user):
	"""Check if user is a cab owner"""
	return user.is_authenticated and user.role == 'cab_owner'


def is_bus_operator(user):
	"""Check if user is a bus operator"""
	return user.is_authenticated and user.role == 'bus_operator'


def is_package_provider(user):
	"""Check if user is a package provider"""
	return user.is_authenticated and user.role == 'package_provider'


def is_admin(user):
	"""Check if user is admin or staff"""
	return user.is_authenticated and (user.is_admin() or user.is_staff)


def can_modify_property(user, property_obj):
	"""Check if user can modify a property (must be owner)"""
	if not user.is_authenticated:
		return False
	return property_obj.owner_id == user.id


def can_view_analytics(user, property_obj):
	"""Check if user can view property analytics (owner or admin)"""
	if not user.is_authenticated:
		return False
	return property_obj.owner_id == user.id or user.is_admin()