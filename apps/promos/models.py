from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.core.models import TimeStampedModel


class Promo(TimeStampedModel):
	TYPE_PERCENT = 'percent'
	TYPE_AMOUNT = 'amount'

	TYPE_CHOICES = [
		(TYPE_PERCENT, 'Percent'),
		(TYPE_AMOUNT, 'Amount'),
	]

	MODULE_CHOICES = [
		('hotels', 'Hotels'),
		('buses', 'Buses'),
		('cabs', 'Cabs'),
		('packages', 'Packages'),
		('flights', 'Flights'),
		('trains', 'Trains'),
		('all', 'All Modules'),
	]

	code = models.CharField(max_length=20, unique=True)
	discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERCENT)
	value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Discount value (% or amount)")
	max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Max discount cap")
	max_uses = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
	starts_at = models.DateField(null=True, blank=True)
	ends_at = models.DateField(null=True, blank=True)
	applicable_module = models.CharField(max_length=50, choices=MODULE_CHOICES, default='all')
	is_active = models.BooleanField(default=True)

	class Meta:
		indexes = [
			models.Index(fields=['code', 'is_active']),
			models.Index(fields=['applicable_module', 'is_active']),
			models.Index(fields=['ends_at']),
		]

	def __str__(self):
		return self.code

	def is_valid(self):
		"""Check if coupon is valid"""
		if not self.is_active:
			return False
		now = timezone.now().date()
		if self.starts_at and self.starts_at > now:
			return False
		if self.ends_at and self.ends_at < now:
			return False
		return True


class PromoUsage(TimeStampedModel):
	promo = models.ForeignKey(Promo, on_delete=models.CASCADE, related_name='usages')
	booking = models.ForeignKey('booking.Booking', on_delete=models.PROTECT, related_name='promo_usages')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

	class Meta:
		verbose_name_plural = "Promo Usage"
		indexes = [models.Index(fields=['promo', 'user'])]

	def __str__(self):
		return f"{self.promo.code} - {self.user.email}"


class CashbackCampaign(TimeStampedModel):
	"""
	Phase 5: Admin-configurable cashback campaigns.
	Cashback is credited to customer wallet AFTER stay completes (checked_out status).
	This prevents refund abuse — cashback only earned on genuine stays.
	"""

	STATUS_ACTIVE = 'active'
	STATUS_PAUSED = 'paused'
	STATUS_EXPIRED = 'expired'
	STATUS_CHOICES = [
		(STATUS_ACTIVE, 'Active'),
		(STATUS_PAUSED, 'Paused'),
		(STATUS_EXPIRED, 'Expired'),
	]

	TYPE_PERCENT = 'percent'    # e.g. "10% cashback on booking value"
	TYPE_FLAT = 'flat'          # e.g. "Rs.500 cashback per booking"
	TYPE_CHOICES = [
		(TYPE_PERCENT, 'Percentage of Booking'),
		(TYPE_FLAT, 'Flat Amount'),
	]

	name = models.CharField(max_length=120)
	slug = models.SlugField(unique=True)
	description = models.TextField(blank=True)
	cashback_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_PERCENT)
	cashback_value = models.DecimalField(
		max_digits=8, decimal_places=2,
		help_text="Percentage (0-100) or flat amount in INR."
	)
	max_cashback_per_booking = models.DecimalField(
		max_digits=10, decimal_places=2, default=0,
		help_text="Cap per booking. 0 = no cap."
	)
	max_cashback_per_user = models.DecimalField(
		max_digits=10, decimal_places=2, default=0,
		help_text="Lifetime cap per user. 0 = no cap."
	)
	min_booking_value = models.DecimalField(
		max_digits=10, decimal_places=2, default=0,
		help_text="Minimum booking amount to qualify. 0 = no minimum."
	)
	cashback_expiry_days = models.PositiveIntegerField(
		default=365,
		help_text="Days before credited cashback expires from wallet."
	)
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
	start_date = models.DateField(null=True, blank=True)
	end_date = models.DateField(null=True, blank=True)
	# Optional: restrict to specific properties or cities
	applicable_properties = models.ManyToManyField(
		'hotels.Property', blank=True, related_name='cashback_campaigns',
		help_text="Leave empty to apply to all properties."
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
		null=True, blank=True, related_name='created_campaigns'
	)

	class Meta:
		app_label = 'promos'
		verbose_name = 'Cashback Campaign'
		verbose_name_plural = 'Cashback Campaigns'

	def __str__(self):
		return self.name

	def compute_cashback(self, booking_total):
		"""Compute cashback amount for a given booking total."""
		from decimal import Decimal as D
		total = D(str(booking_total))
		if self.min_booking_value and total < D(str(self.min_booking_value)):
			return D('0.00')

		if self.cashback_type == self.TYPE_PERCENT:
			amount = (total * D(str(self.cashback_value)) / 100).quantize(D('0.01'))
		else:
			amount = D(str(self.cashback_value))

		if self.max_cashback_per_booking:
			amount = min(amount, D(str(self.max_cashback_per_booking)))

		return amount


class CashbackCredit(TimeStampedModel):
	"""
	Record of cashback credited to a user's wallet after a completed stay.
	"""
	campaign = models.ForeignKey(CashbackCampaign, on_delete=models.SET_NULL, null=True, related_name='credits')
	booking = models.ForeignKey('booking.Booking', on_delete=models.PROTECT, related_name='cashback_credits')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cashback_credits')
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	wallet_txn_reference = models.CharField(max_length=100, blank=True)
	expires_at = models.DateTimeField(null=True, blank=True)
	is_expired = models.BooleanField(default=False)

	class Meta:
		app_label = 'promos'

	def __str__(self):
		return f"Cashback Rs.{self.amount} to {self.user} for {self.booking}"