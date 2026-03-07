from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from apps.dashboard_admin.models import PropertyApproval
from apps.hotels.models import Property
from apps.core.services import user_has_role, get_dashboard_data, get_home_data


def home(request):
	properties, categories = get_home_data(limit=6)
	return render(request, 'core/home.html', {
		'properties': properties,
		'categories': categories,
	})


def component_library_preview(request):
	"""Component library preview page for design system showcase"""
	return render(request, 'component-library-preview.html')


def permission_denied(request, exception):
	return render(request, '403.html', status=403)


def seed_test_data(request):
	if not settings.DEBUG:
		return JsonResponse({"status": "disabled"}, status=403)
	
	User = get_user_model()
	needs_seed = (
		not Property.objects.exists()
		or not Property.objects.filter(room_types__isnull=False).exists()
		or not User.objects.filter(email="property_owner@test.com").exists()
		or not User.objects.filter(email="bus_operator_1@test.com").exists()
		or not Property.objects.filter(name__iexact="Aurora Bay Hotel").exists()
	)
	if needs_seed:
		call_command("seed_ota_data", verbosity=0)
	
	property_qs = Property.objects.all()
	if hasattr(Property, "is_active"):
		property_qs = property_qs.filter(is_active=True)
	property_qs = property_qs.filter(room_types__isnull=False).distinct()
	# Use new clean approval system: status='approved' AND agreement_signed=True
	approved_qs = property_qs.filter(status='approved', agreement_signed=True)
	property_obj = approved_qs.order_by("id").first()
	if not property_obj:
		property_obj = property_qs.order_by("id").first()
		if property_obj:
			# Update to new system
			property_obj.status = 'approved'
			property_obj.agreement_signed = True
			property_obj.save(update_fields=['status', 'agreement_signed', 'updated_at'])
	return JsonResponse({
		"status": "ok",
		"properties": Property.objects.count(),
		"property_id": property_obj.id if property_obj else None,
		"property_slug": property_obj.slug if property_obj else None,
	})


@login_required
def dashboard(request):
	if user_has_role(request.user, 'property_owner'):
		return redirect('dashboard_owner:dashboard')
	if user_has_role(request.user, 'cab_owner'):
		return redirect('cabs:dashboard')
	if user_has_role(request.user, 'bus_operator'):
		return redirect('buses:dashboard')

	context = get_dashboard_data(request.user)
	return render(request, 'dashboard/dashboard.html', context)


# PHASE 9: Health check endpoint
def health_check(request):
	"""
	Health check endpoint for deployment monitoring.
	Returns database connection status and service health.
	"""
	try:
		from django.db import connection
		# Test database connection
		with connection.cursor() as cursor:
			cursor.execute("SELECT 1")
		db_status = "connected"
	except Exception as e:
		db_status = f"disconnected: {str(e)}"
	
	return JsonResponse({
		"status": "ok",
		"database": db_status,
		"debug": settings.DEBUG,
		"timestamp": timezone.now().isoformat(),
	})

# Create your views here.