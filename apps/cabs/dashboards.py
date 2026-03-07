"""
Cab Owner Dashboard Views
Production-grade views with atomic transactions and RBAC enforcement
"""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from apps.accounts.permissions import role_required
from apps.accounts.selectors import user_has_role
from .models import Cab
from .forms import CabRegistrationForm


@login_required
@role_required('cab_owner')
def cab_dashboard(request):
    """
    Cab owner dashboard showing all their cabs.
    RBAC: cab_owner role required
    """
    owner = request.user
    cabs = Cab.objects.filter(owner=owner, is_active=True)
    
    stats = {
        'total_cabs': cabs.count(),
        'active_cabs': cabs.count(),
        'total_earnings': 0,  # Would calculate from CabBooking if it exists
    }
    
    context = {
        'cabs': cabs,
        'stats': stats,
    }
    return render(request, 'cab_dashboard/dashboard.html', context)


@login_required
@role_required('cab_owner')
@require_http_methods(["GET", "POST"])
def cab_create(request):
    """
    Create new cab for owner.
    POST creates cab with atomic transaction.
    RBAC: cab_owner role required
    """
    form = CabRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                cab = form.save(commit=False)
                cab.owner = request.user
                cab.save()
            messages.success(request, 'Cab added successfully!')
            return redirect('cabs:dashboard')
        except Exception as e:
            messages.error(request, f'Error creating cab: {str(e)}')

    return render(request, 'cab_dashboard/cab_form.html', {'form': form})


@login_required
@role_required('cab_owner')
def cab_detail(request, cab_id):
    """
    View cab details.
    RBAC: Owner can only view their own cabs
    """
    cab = get_object_or_404(Cab, id=cab_id, owner=request.user)
    
    context = {
        'cab': cab,
    }
    return render(request, 'cab_dashboard/cab_detail.html', context)


@login_required
@role_required('cab_owner')
@require_http_methods(["POST"])
def cab_update_availability(request):
    """
    Update cab availability via AJAX with atomic lock.
    RBAC: cab_owner role required
    Returns JSON response
    """
    try:
        cab_id = request.POST.get('cab_id')
        available = request.POST.get('available') == 'true'
        
        # Atomic update with lock
        with transaction.atomic():
            cab = Cab.objects.select_for_update().get(
                id=cab_id,
                owner=request.user
            )
            cab.available = available
            cab.save(update_fields=['available', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Availability updated',
            'available': cab.available,
        })
    except Cab.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cab not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@role_required('cab_owner')
@require_http_methods(["POST"])
def cab_deactivate(request):
    """
    Deactivate cab (soft delete).
    RBAC: cab_owner role required
    """
    try:
        cab_id = request.POST.get('cab_id')
        
        with transaction.atomic():
            cab = Cab.objects.select_for_update().get(
                id=cab_id,
                owner=request.user
            )
            cab.is_active = False
            cab.save(update_fields=['is_active', 'updated_at'])
        
        messages.success(request, 'Cab deactivated successfully')
        return redirect('cabs:dashboard')
    except Cab.DoesNotExist:
        messages.error(request, 'Cab not found')
        return redirect('cabs:dashboard')


@login_required
@role_required('cab_owner')
def cab_list(request):
    """
    List all cabs for owner with filtering.
    Supports filtering by availability status.
    """
    owner = request.user
    cabs = Cab.objects.filter(owner=owner).order_by('-created_at')
    
    # Filter options
    available_filter = request.GET.get('available') or ''
    if available_filter == 'true':
        cabs = cabs.filter(available=True)
    elif available_filter == 'false':
        cabs = cabs.filter(available=False)
    
    context = {
        'cabs': cabs,
        'available_filter': available_filter,
    }
    return render(request, 'cab_dashboard/cabs_list.html', context)