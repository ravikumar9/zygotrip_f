"""
Celery tasks for hotels app
Handles periodic tasks like auto-approval of property changes
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


@shared_task(name='hotels.auto_approve_pending_changes')
def auto_approve_pending_changes():
	"""
	Automatically approve pending property changes after configured time period
	Runs every hour via Celery beat
	"""
	from apps.hotels.approval_models import PendingPropertyChange, AutoApprovalSettings
	
	settings_obj = AutoApprovalSettings.get_settings()
	
	if not settings_obj.auto_approve_enabled:
		return {
			'status': 'skipped',
			'reason': 'Auto-approval is disabled'
		}
	
	# Find changes ready for auto-approval
	pending_changes = PendingPropertyChange.objects.filter(
		status='pending'
	).select_related('property')
	
	auto_approved_count = 0
	auto_approved_properties = []
	
	for change in pending_changes:
		if change.is_ready_for_auto_approval:
			try:
				change.auto_approve()
				auto_approved_count += 1
				auto_approved_properties.append({
					'property': change.property.name,
					'field': change.field_label or change.field_name,
					'value': change.new_value[:100],  # Truncate long values
				})
			except Exception as e:
				# Log error but continue processing other changes
				print(f"Error auto-approving change {change.id}: {str(e)}")
				continue
	
	# Send notification email to admins if enabled
	if auto_approved_count > 0 and settings_obj.notify_admins:
		send_auto_approval_notification(auto_approved_properties)
	
	return {
		'status': 'success',
		'auto_approved_count': auto_approved_count,
		'changes': auto_approved_properties
	}


def send_auto_approval_notification(changes):
	"""Send email notification about auto-approved changes"""
	
	subject = f"[ZygoTrip] {len(changes)} property changes auto-approved"
	
	message_lines = [
		"The following property changes were automatically approved:",
		"",
	]
	
	for change in changes:
		message_lines.append(
			f"• {change['property']} - {change['field']}: {change['value']}"
		)
	
	message_lines.extend([
		"",
		"You can review these changes in the admin panel.",
		"",
		"ZygoTrip Admin System"
	])
	
	message = "\n".join(message_lines)
	
	# Send to all staff users
	from django.contrib.auth import get_user_model
	User = get_user_model()
	admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
	
	if admin_emails:
		send_mail(
			subject=subject,
			message=message,
			from_email=settings.DEFAULT_FROM_EMAIL,
			recipient_list=list(admin_emails),
			fail_silently=True
		)


@shared_task(name='hotels.notify_pending_changes')
def notify_pending_changes():
	"""
	Send daily digest of pending changes to admins
	Runs once per day via Celery beat
	"""
	from apps.hotels.approval_models import PendingPropertyChange, AutoApprovalSettings
	
	settings_obj = AutoApprovalSettings.get_settings()
	
	if not settings_obj.notify_admins:
		return {'status': 'skipped', 'reason': 'Admin notifications disabled'}
	
	pending_changes = PendingPropertyChange.objects.filter(
		status='pending'
	).select_related('property').order_by('-requested_at')[:50]
	
	if not pending_changes:
		return {'status': 'success', 'pending_count': 0}
	
	subject = f"[ZygoTrip] {pending_changes.count()} pending property changes"
	
	message_lines = [
		f"You have {pending_changes.count()} pending property changes awaiting review:",
		"",
	]
	
	for change in pending_changes:
		hours_ago = (timezone.now() - change.requested_at).total_seconds() / 3600
		message_lines.append(
			f"• {change.property.name} - {change.field_label or change.field_name} "
			f"(requested {hours_ago:.1f}h ago)"
		)
	
	message_lines.extend([
		"",
		"Please review these changes in the admin approval queue:",
		f"{settings.SITE_URL}/admin/approval-queue/",
		"",
		"ZygoTrip Admin System"
	])
	
	message = "\n".join(message_lines)
	
	# Send to all staff users
	from django.contrib.auth import get_user_model
	User = get_user_model()
	admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
	
	if admin_emails:
		send_mail(
			subject=subject,
			message=message,
			from_email=settings.DEFAULT_FROM_EMAIL,
			recipient_list=list(admin_emails),
			fail_silently=True
		)
	
	return {'status': 'success', 'pending_count': pending_changes.count()}


@shared_task(name='hotels.rebuild_hotel_embeddings')
def rebuild_hotel_embeddings(limit=0):
	"""Recompute embeddings for approved hotels."""
	from apps.hotels.models import Property
	from apps.hotels.semantic_search import upsert_hotel_embedding

	qs = Property.objects.filter(status='approved', agreement_signed=True).order_by('id')
	if int(limit or 0) > 0:
		qs = qs[:int(limit)]

	processed = 0
	skipped = 0
	for property_obj in qs:
		if upsert_hotel_embedding(property_obj):
			processed += 1
		else:
			skipped += 1

	return {
		'status': 'success',
		'processed': processed,
		'skipped': skipped,
	}
