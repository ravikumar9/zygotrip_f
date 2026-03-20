from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.core.models import TimeStampedModel

# ==========================================================================
# PHASE 1: USER MODEL RESTRUCTURE - CORE FOUNDATION
# ==========================================================================

ROLE_CHOICES = [
    ('traveler', 'Traveler'),
    ('property_owner', 'Property Owner'),
    ('cab_owner', 'Cab Owner'),
    ('bus_operator', 'Bus Operator'),
    ('package_provider', 'Package Provider'),
    ('admin', 'Admin'),
]


class UserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError('Email is required')
		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('is_active', True)
		extra_fields.setdefault('role', 'admin')
		return self.create_user(email, password, **extra_fields)


class User(TimeStampedModel, AbstractBaseUser, PermissionsMixin):
	email = models.EmailField(unique=True)
	full_name = models.CharField(max_length=120)
	phone = models.CharField(max_length=20, blank=True, null=True, unique=True,
		help_text="Phone number must be unique. Blank stored as NULL for uniqueness.")
	google_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
	apple_sub = models.CharField(max_length=255, blank=True, null=True, db_index=True)
	is_staff = models.BooleanField(default=False)
	
	# ==========================================
	# PHASE 1: Role-based identifier (NEW)
	# ==========================================
	role = models.CharField(
		max_length=30,
		choices=ROLE_CHOICES,
		default='traveler',
		help_text="User's primary role in the marketplace"
	)
	
	# Vendor verification flag
	is_verified_vendor = models.BooleanField(
		default=False,
		help_text="Whether this vendor has been verified by admin"
	)
	
	# Legacy support for ManyToMany roles (will be deprecated)
	roles = models.ManyToManyField('Role', through='UserRole', related_name='users', blank=True)

	objects = UserManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = ['full_name']

	def __str__(self):
		return f"{self.email} ({self.get_role_display()})"

	def save(self, *args, **kwargs):
		# Ensure blank phone is stored as NULL for unique constraint
		if not self.phone:
			self.phone = None
		super().save(*args, **kwargs)

	def is_vendor(self):
		"""Check if user is a vendor (non-traveler/non-admin role)"""
		return self.role in ['property_owner', 'cab_owner', 'bus_operator', 'package_provider']
	
	def is_property_owner(self):
		return self.role == 'property_owner'
	
	def is_cab_owner(self):
		return self.role == 'cab_owner'
	
	def is_bus_operator(self):
		return self.role == 'bus_operator'
	
	def is_package_provider(self):
		return self.role == 'package_provider'
	
	def is_admin(self):
		return self.role == 'admin' or self.is_staff


class Role(TimeStampedModel):
	code = models.CharField(max_length=50, unique=True)
	name = models.CharField(max_length=80)
	description = models.TextField(blank=True)
	permissions = models.ManyToManyField('Permission', through='RolePermission', related_name='roles')

	def __str__(self):
		return self.name


class Permission(TimeStampedModel):
	code = models.CharField(max_length=80, unique=True)
	name = models.CharField(max_length=120)
	description = models.TextField(blank=True)

	def __str__(self):
		return self.code


class RolePermission(TimeStampedModel):
	role = models.ForeignKey(Role, on_delete=models.CASCADE)
	permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

	class Meta:
		unique_together = ('role', 'permission')


class UserRole(TimeStampedModel):
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	role = models.ForeignKey(Role, on_delete=models.CASCADE)

	class Meta:
		unique_together = ('user', 'role')