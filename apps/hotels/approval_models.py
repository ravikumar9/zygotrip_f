"""
Admin Approval Settings Models
Owner-Controlled Property Change Workflow
"""

import builtins
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel


class AutoApprovalSettings(models.Model):
	"""Global settings for auto-approving property changes"""
	
	auto_approve_enabled = models.BooleanField(
		default=True,
		help_text="Enable automatic approval of pending changes after X hours"
	)
	
	auto_approve_hours = models.IntegerField(
		default=6,
		choices=[
			(3, '3 hours'),
			(6, '6 hours'),
			(12, '12 hours'),
			(24, '24 hours'),
		],
		help_text="Hours to wait before auto-approving pending changes"
	)
	
	# Who gets notified
	notify_admins = models.BooleanField(default=True, help_text="Email admins when changes are pending")
	notify_owners = models.BooleanField(default=True, help_text="Email owners when changes are approved/rejected")
	
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	class Meta:
		verbose_name = "Auto Approval Settings"
		verbose_name_plural = "Auto Approval Settings"
	
	def __str__(self):
		status = "Enabled" if self.auto_approve_enabled else "Disabled"
		return f"Auto-Approval: {status} ({self.auto_approve_hours}h)"
	
	@classmethod
	def get_settings(cls):
		"""Get or create singleton settings instance"""
		obj, created = cls.objects.get_or_create(pk=1)
		return obj


class PendingPropertyChange(TimeStampedModel):
	"""Track pending changes to property data that require admin approval"""
	
	property = models.ForeignKey(
		'Property', 
		on_delete=models.CASCADE, 
		related_name='pending_changes'
	)
	
	# Which field was changed
	field_name = models.CharField(
		max_length=100,
		help_text="Name of the field that was changed (e.g., 'name', 'description', 'address')"
	)
	
	field_label = models.CharField(
		max_length=200,
		blank=True,
		help_text="Human-readable field label for display"
	)
	
	# Old and new values (stored as JSON strings for flexibility)
	old_value = models.TextField(blank=True, help_text="Previous value before change")
	new_value = models.TextField(help_text="New value requested by owner")
	
	# Status tracking
	status = models.CharField(
		max_length=20,
		choices=[
			('pending', 'Pending Review'),
			('approved', 'Approved'),
			('rejected', 'Rejected'),
			('auto_approved', 'Auto-Approved'),
		],
		default='pending'
	)
	
	# Timestamps
	requested_at = models.DateTimeField(auto_now_add=True)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	
	# Admin who reviewed
	reviewed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='reviewed_changes'
	)
	
	# Admin notes
	admin_notes = models.TextField(
		blank=True,
		help_text="Optional notes from admin about approval/rejection"
	)
	
	class Meta:
		ordering = ['-requested_at']
		verbose_name = "Pending Property Change"
		verbose_name_plural = "Pending Property Changes"
		indexes = [
			models.Index(fields=['property', 'status']),
			models.Index(fields=['status', 'requested_at']),
		]
	
	def __str__(self):
		return f"{self.property.name} - {self.field_label or self.field_name} ({self.status})"
	
	def approve(self, admin_user=None, notes=''):
		"""Approve and apply the pending change"""
		from django.utils import timezone
		
		# Update the actual property field
		setattr(self.property, self.field_name, self.new_value)
		self.property.save(update_fields=[self.field_name])
		
		# Update pending change record
		self.status = 'approved'
		self.reviewed_at = timezone.now()
		self.reviewed_by = admin_user
		self.admin_notes = notes
		self.save()
	
	def reject(self, admin_user=None, notes=''):
		"""Reject the pending change"""
		from django.utils import timezone
		
		self.status = 'rejected'
		self.reviewed_at = timezone.now()
		self.reviewed_by = admin_user
		self.admin_notes = notes
		self.save()
	
	def auto_approve(self):
		"""Auto-approve the change (called by Celery task)"""
		from django.utils import timezone
		
		# Update the actual property field
		setattr(self.property, self.field_name, self.new_value)
		self.property.save(update_fields=[self.field_name])
		
		# Update pending change record
		self.status = 'auto_approved'
		self.reviewed_at = timezone.now()
		self.admin_notes = f"Auto-approved after {AutoApprovalSettings.get_settings().auto_approve_hours} hours"
		self.save()
	
	@builtins.property
	def is_ready_for_auto_approval(self):
		"""Check if this change is ready for auto-approval"""
		from django.utils import timezone
		from datetime import timedelta
		
		if self.status != 'pending':
			return False
		
		settings = AutoApprovalSettings.get_settings()
		if not settings.auto_approve_enabled:
			return False
		
		hours_passed = (timezone.now() - self.requested_at).total_seconds() / 3600
		return hours_passed >= settings.auto_approve_hours
