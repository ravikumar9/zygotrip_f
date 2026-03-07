from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, ROLE_CHOICES


# ==========================================
# PHASE 2: ROLE-BASED REGISTRATION FORMS (NEW)
# ==========================================

class RoleSelectionForm(forms.Form):
	"""Step 1: User selects their role in the marketplace"""
	role = forms.ChoiceField(
		choices=ROLE_CHOICES,
		widget=forms.RadioSelect(attrs={'class': 'role-input'}),
		label="What is your role?",
		help_text="Choose how you will use Zygotrip"
	)


class TravelerRegistrationForm(UserCreationForm):
	"""Registration form for travelers (buyers)"""
	email = forms.EmailField(
		widget=forms.EmailInput(attrs={
			'placeholder': 'Email',
			'class': 'form-control'
		})
	)
	full_name = forms.CharField(
		max_length=120,
		widget=forms.TextInput(attrs={
			'placeholder': 'Full Name',
			'class': 'form-control'
		})
	)
	phone = forms.CharField(
		max_length=20,
		required=False,
		widget=forms.TextInput(attrs={
			'placeholder': 'Phone (optional)',
			'class': 'form-control'
		})
	)
	password1 = forms.CharField(
		widget=forms.PasswordInput(attrs={
			'placeholder': 'Password',
			'class': 'form-control'
		})
	)
	password2 = forms.CharField(
		widget=forms.PasswordInput(attrs={
			'placeholder': 'Confirm Password',
			'class': 'form-control'
		})
	)

	class Meta:
		model = User
		fields = ['email', 'full_name', 'phone', 'password1', 'password2']

	def clean_email(self):
		email = self.cleaned_data['email'].strip().lower()
		if User.objects.filter(email=email).exists():
			raise forms.ValidationError('An account with this email already exists.')
		return email

	def save(self, commit=True):
		user = super().save(commit=False)
		user.role = 'traveler'
		if commit:
			user.save()
		return user


class VendorRegistrationForm(UserCreationForm):
	"""Registration form for vendors (property owners, cab owners, etc.)"""
	email = forms.EmailField(
		widget=forms.EmailInput(attrs={
			'placeholder': 'Email',
			'class': 'form-control'
		})
	)
	full_name = forms.CharField(
		max_length=120,
		widget=forms.TextInput(attrs={
			'placeholder': 'Full Name / Business Name',
			'class': 'form-control'
		})
	)
	phone = forms.CharField(
		max_length=20,
		required=True,
		widget=forms.TextInput(attrs={
			'placeholder': 'Phone',
			'class': 'form-control'
		}),
		help_text='We will verify your phone number'
	)
	password1 = forms.CharField(
		widget=forms.PasswordInput(attrs={
			'placeholder': 'Password',
			'class': 'form-control'
		})
	)
	password2 = forms.CharField(
		widget=forms.PasswordInput(attrs={
			'placeholder': 'Confirm Password',
			'class': 'form-control'
		})
	)

	class Meta:
		model = User
		fields = ['email', 'full_name', 'phone', 'password1', 'password2']

	def clean_email(self):
		email = self.cleaned_data['email'].strip().lower()
		if User.objects.filter(email=email).exists():
			raise forms.ValidationError('An account with this email already exists.')
		return email

	def clean_phone(self):
		phone = self.cleaned_data.get('phone', '').strip()
		if not phone:
			raise forms.ValidationError('Phone number is required for vendors.')
		return phone

	def save(self, commit=True, role='property_owner'):
		user = super().save(commit=False)
		user.role = role  # Set by subclass
		user.is_verified_vendor = False  # Must be verified by admin
		if commit:
			user.save()
		return user


class PropertyOwnerRegistrationForm(VendorRegistrationForm):
	"""Registration form specifically for property owners"""
	
	def save(self, commit=True):
		return super().save(commit=commit, role='property_owner')


class CabOwnerRegistrationForm(VendorRegistrationForm):
	"""Registration form specifically for cab owners"""
	
	def save(self, commit=True):
		return super().save(commit=commit, role='cab_owner')


class BusOperatorRegistrationForm(VendorRegistrationForm):
	"""Registration form specifically for bus operators"""
	
	def save(self, commit=True):
		return super().save(commit=commit, role='bus_operator')


class PackageProviderRegistrationForm(VendorRegistrationForm):
	"""Registration form specifically for package providers"""
	
	def save(self, commit=True):
		return super().save(commit=commit, role='package_provider')


class RegisterForm(UserCreationForm):
	"""Legacy registration form for backward compatibility"""
	class Meta:
		model = User
		fields = ['email', 'full_name', 'password1', 'password2']

	email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
	full_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'placeholder': 'Full name'}))

	def clean_email(self):
		email = self.cleaned_data['email'].strip().lower()
		if User.objects.filter(email=email).exists():
			raise forms.ValidationError('An account with this email already exists.')
		return email


class CustomAuthenticationForm(AuthenticationForm):
	"""Authentication form for custom User model with email as primary field"""
	username = forms.EmailField(
		label='Email Address',
		widget=forms.EmailInput(attrs={
			'class': 'form-control',
			'placeholder': 'Email address',
			'autofocus': True,
			'required': True
		})
	)
	password = forms.CharField(
		label='Password',
		strip=False,
		widget=forms.PasswordInput(attrs={
			'class': 'form-control',
			'placeholder': 'Password',
			'required': True
		})
	)
	
	def clean_username(self):
		"""Normalize email on login"""
		username = self.cleaned_data.get('username', '').strip().lower()
		return username