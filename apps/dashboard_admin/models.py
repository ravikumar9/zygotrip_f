from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel


class PropertyApproval(TimeStampedModel):
	STATUS_PENDING = 'pending'
	STATUS_APPROVED = 'approved'
	STATUS_REJECTED = 'rejected'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_REJECTED, 'Rejected'),
	]

	property = models.OneToOneField('hotels.Property', on_delete=models.CASCADE, related_name='approval')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	decided_at = models.DateTimeField(null=True, blank=True)
	notes = models.TextField(blank=True)


class AuditLog(TimeStampedModel):
	actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	action = models.CharField(max_length=80)
	object_type = models.CharField(max_length=80)
	object_id = models.CharField(max_length=80)
	metadata = models.JSONField(default=dict, blank=True)

# Create your models here.