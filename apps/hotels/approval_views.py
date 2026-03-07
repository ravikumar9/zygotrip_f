"""
Admin views for property approval workflow
Provides approval queue for admins to review pending property changes
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from apps.hotels.approval_models import PendingPropertyChange, AutoApprovalSettings


@staff_member_required
def approval_queue(request):
	"""
	Admin view to review and approve/reject pending property changes
	URL: /admin/approval-queue/
	"""
	
	# Filter options
	status_filter = request.GET.get('status', 'pending')
	property_filter = request.GET.get('property', '')
	
	# Base queryset
	queryset = PendingPropertyChange.objects.select_related(
		'property', 'reviewed_by'
	).all()
	
	# Apply filters
	if status_filter and status_filter != 'all':
		queryset = queryset.filter(status=status_filter)
	
	if property_filter:
		queryset = queryset.filter(
			Q(property__name__icontains=property_filter) |
			Q(property__owner__email__icontains=property_filter)
		)
	
	# Get statistics
	stats = {
		'pending_count': PendingPropertyChange.objects.filter(status='pending').count(),
		'approved_count': PendingPropertyChange.objects.filter(status='approved').count(),
		'rejected_count': PendingPropertyChange.objects.filter(status='rejected').count(),
		'auto_approved_count': PendingPropertyChange.objects.filter(status='auto_approved').count(),
	}
	
	# Get settings
	settings = AutoApprovalSettings.get_settings()
	
	context = {
		'changes': queryset[:100],  # Limit to 100 for performance
		'stats': stats,
		'settings': settings,
		'status_filter': status_filter,
		'property_filter': property_filter,
		'title': 'Property Change Approval Queue',
	}
	
	return render(request, 'admin/hotels/approval_queue.html', context)


@staff_member_required
def approve_change(request, change_id):
	"""
	Approve a pending property change
	URL: /admin/approval-queue/approve/<change_id>/
	"""
	change = get_object_or_404(PendingPropertyChange, id=change_id)
	
	if request.method == 'POST':
		notes = request.POST.get('notes', '')
		change.approve(admin_user=request.user, notes=notes)
		
		messages.success(
			request, 
			f"Approved change to {change.property.name} - {change.field_label}"
		)
		
		return redirect('admin:approval_queue')
	
	context = {
		'change': change,
		'title': f'Approve Change - {change.property.name}',
	}
	
	return render(request, 'admin/hotels/approve_change.html', context)


@staff_member_required
def reject_change(request, change_id):
	"""
	Reject a pending property change
	URL: /admin/approval-queue/reject/<change_id>/
	"""
	change = get_object_or_404(PendingPropertyChange, id=change_id)
	
	if request.method == 'POST':
		notes = request.POST.get('notes', '')
		if not notes:
			messages.error(request, "Rejection reason is required")
			return redirect('admin:approval_queue')
		
		change.reject(admin_user=request.user, notes=notes)
		
		messages.success(
			request, 
			f"Rejected change to {change.property.name} - {change.field_label}"
		)
		
		return redirect('admin:approval_queue')
	
	context = {
		'change': change,
		'title': f'Reject Change - {change.property.name}',
	}
	
	return render(request, 'admin/hotels/reject_change.html', context)


@staff_member_required
def update_approval_settings(request):
	"""
	Update auto-approval settings
	URL: /admin/approval-queue/settings/
	"""
	settings = AutoApprovalSettings.get_settings()
	
	if request.method == 'POST':
		settings.auto_approve_enabled = request.POST.get('auto_approve_enabled') == 'on'
		settings.auto_approve_hours = int(request.POST.get('auto_approve_hours', 6))
		settings.notify_admins = request.POST.get('notify_admins') == 'on'
		settings.notify_owners = request.POST.get('notify_owners') == 'on'
		settings.save()
		
		messages.success(request, "Auto-approval settings updated successfully")
		return redirect('admin:approval_queue')
	
	context = {
		'settings': settings,
		'title': 'Auto-Approval Settings',
	}
	
	return render(request, 'admin/hotels/approval_settings.html', context)
