from django.db import models
import json

# Import location models for registration
from .location_models import Country, State, City, Locality, LocationSearchIndex, RegionGroup


class TimeStampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		abstract = True


class OperationLog(TimeStampedModel):
	"""Audit log for critical operations"""
	
	OPERATION_CHOICES = [
		('booking_failed', 'Booking Failed'),
		('booking_created', 'Booking Created'),
		('payment_failed', 'Payment Failed'),
		('payment_initiated', 'Payment Initiated'),
		('coupon_applied', 'Coupon Applied'),
		('coupon_rejected', 'Coupon Rejected'),
		('inventory_sync', 'Inventory Sync'),
		('price_calculated', 'Price Calculated'),
		('mapping_decision', 'Mapping Decision'),
		('fraud_triggered', 'Fraud Triggered'),
	]
	
	STATUS_CHOICES = [
		('success', 'Success'),
		('failed', 'Failed'),
		('pending', 'Pending'),
	]
	
	operation_type = models.CharField(max_length=50, choices=OPERATION_CHOICES)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	details = models.TextField()  # JSON string with operation details
	timestamp = models.DateTimeField(db_index=True)
	
	class Meta:
		ordering = ['-timestamp']
		indexes = [
			models.Index(fields=['operation_type', 'status', '-timestamp']),
			models.Index(fields=['timestamp']),
		]
		verbose_name_plural = "Operation Logs"
	
	def get_details(self):
		"""Parse JSON details"""
		try:
			return json.loads(self.details)
		except:
			return {}
	
	def __str__(self):
		return f"{self.get_operation_type_display()} - {self.get_status_display()} @ {self.timestamp}"


# ==========================================
# PHASE 5: PLATFORM SETTINGS FOR COMMISSIONS (NEW)
# ==========================================
class PlatformSettings(TimeStampedModel):
	"""
	Admin-configurable platform settings for commissions and policies
	This model should have at most one instance (enforced via migrations)
	"""
	
	# Default commission percentages for each vendor type
	default_property_commission = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=10.00,
		help_text="Default commission % for hotel/property owners"
	)
	
	default_cab_commission = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=15.00,
		help_text="Default commission % for cab owners"
	)
	
	default_bus_commission = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=12.00,
		help_text="Default commission % for bus operators"
	)
	
	default_package_commission = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=20.00,
		help_text="Default commission % for package providers"
	)
	
	# Global settings
	require_agreement_signature = models.BooleanField(
		default=True,
		help_text="Require vendor to sign agreement before listing is public"
	)
	
	platform_name = models.CharField(
		max_length=100,
		default='Zygotrip',
		help_text="Platform name for agreements and communications"
	)
	
	support_email = models.EmailField(
		default='support@zygotrip.com',
		help_text="Support email for vendor communications"
	)
	
	# Platform fees
	service_fee_percent = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=10.00,
		help_text="Service fee % applied to bookings (e.g., 10.00 for 10%)"
	)
	
	class Meta:
		verbose_name_plural = "Platform Settings"
	
	def __str__(self):
		return f"{self.platform_name} Settings"
	
	@classmethod
	def get_settings(cls):
		"""Get or create the singleton settings instance"""
		settings, _ = cls.objects.get_or_create(pk=1)
		return settings


# Import observability models for migration generation
from .observability import SystemMetrics, InventoryHealthCheck, PerformanceLog

# OTA system models — imported at bottom to avoid circular imports
# These use TimeStampedModel from this file, so we must defer the imports.
# Django discovers models by importing all modules in the app's models module.

# S14: Feature flag model (for migration generation)
from .feature_flags import FeatureFlag  # noqa: F401, E402


def _register_ota_models():
    """Late import to break circular dependency."""
    from . import loyalty  # noqa: F401
    from . import referral  # noqa: F401
    from . import fraud_detection  # noqa: F401
    from . import analytics  # noqa: F401
    from . import intelligence  # noqa: F401
    from . import device_fingerprint  # noqa: F401
    # S7: Fraud Engine models
    from . import fraud_engine  # noqa: F401
    # S8: Notification Service models
    from . import notification_service  # noqa: F401
    # S11: Geo Index model
    from . import geo_search  # noqa: F401
    # S14: Security Hardening models
    from . import security_hardening  # noqa: F401
    # S15: Performance models
    from . import performance  # noqa: F401


_register_ota_models()