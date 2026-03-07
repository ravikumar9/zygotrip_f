from django import forms
from django.core.exceptions import ValidationError
from apps.core.date_utils import get_date_for_template, validate_booking_date
from .models import Cab, CabImage, CabBooking, FUEL_TYPE_CHOICES, SEAT_CHOICES, CITY_CHOICES


class CabRegistrationForm(forms.ModelForm):
	"""Owner cab registration form"""
	fuel_type = forms.ChoiceField(choices=FUEL_TYPE_CHOICES)
	city = forms.ChoiceField(choices=CITY_CHOICES)
	seats = forms.ChoiceField(choices=SEAT_CHOICES)

	class Meta:
		model = Cab
		fields = ['name', 'city', 'seats', 'fuel_type', 'base_price_per_km']
		widgets = {
			'name': forms.TextInput(attrs={
				'class': 'form-control',
				'placeholder': 'e.g., Uber Black Premium'
			}),
			'base_price_per_km': forms.NumberInput(attrs={
				'class': 'form-control',
				'placeholder': '₹',
				'step': '0.01',
				'min': '1'
			}),
		}

	def clean_name(self):
		name = self.cleaned_data.get('name', '').strip()
		if not name:
			raise ValidationError("Cab name is required")
		if len(name) < 3:
			raise ValidationError("Cab name must be at least 3 characters")
		return name

	def clean_base_price_per_km(self):
		price = self.cleaned_data.get('base_price_per_km')
		if not price or price <= 0:
			raise ValidationError("Price must be greater than ₹0")
		if price < 5:
			raise ValidationError("Minimum price is ₹5 per km")
		if price > 10000:
			raise ValidationError("Price exceeds maximum allowed (₹10,000/km)")
		return price

	def clean_seats(self):
		seats = self.cleaned_data.get('seats')
		try:
			seats = int(seats)
			if seats < 2 or seats > 12:
				raise ValidationError("Seats must be between 2 and 12")
		except (ValueError, TypeError):
			raise ValidationError("Invalid seat count")
		return seats


class CabFilterForm(forms.Form):
	"""Server-side filtering form for cab listings"""
	city = forms.MultipleChoiceField(
		choices=CITY_CHOICES,
		required=False,
		widget=forms.CheckboxSelectMultiple
	)
	seats = forms.MultipleChoiceField(
		choices=SEAT_CHOICES,
		required=False,
		widget=forms.CheckboxSelectMultiple
	)
	fuel_type = forms.MultipleChoiceField(
		choices=FUEL_TYPE_CHOICES,
		required=False,
		widget=forms.CheckboxSelectMultiple
	)
	max_price = forms.DecimalField(
		required=False,
		min_value=0,
		decimal_places=2,
		widget=forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '500'})
	)
	min_price = forms.DecimalField(
		required=False,
		min_value=0,
		decimal_places=2,
		widget=forms.HiddenInput()
	)
	search = forms.CharField(required=False, max_length=100)


class CabBookingForm(forms.ModelForm):
	"""Cab booking form for customers"""
	booking_date = forms.DateField(
		required=False,
		widget=forms.DateInput(attrs={
			'type': 'date',
			'class': 'form-control'
		}),
		label='Booking Date'
	)
	distance_km = forms.DecimalField(
		required=True,
		min_value=1,
		decimal_places=1,
		widget=forms.NumberInput(attrs={
			'class': 'form-control',
			'placeholder': 'Distance in km',
			'step': '0.1',
			'min': '1'
		})
	)
	promo_code = forms.CharField(
		required=False,
		max_length=50,
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': 'Enter coupon code (optional)'
		})
	)

	class Meta:
		model = CabBooking
		fields = ['booking_date', 'distance_km', 'promo_code']
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Set minimum date for booking_date field
		today = get_date_for_template()
		self.fields['booking_date'].widget.attrs['min'] = today

	def clean_booking_date(self):
		"""Backend validation for booking date"""
		booking_date = self.cleaned_data.get('booking_date')
		if not booking_date:
			from django.utils import timezone
			return timezone.now().date()
		valid, message = validate_booking_date(booking_date, allow_today=True)
		if not valid:
			raise ValidationError(message)
		return booking_date

	def clean_distance_km(self):
		distance = self.cleaned_data.get('distance_km')
		if not distance or distance < 1:
			raise ValidationError("Distance must be at least 1 km")
		if distance > 5000:
			raise ValidationError("Distance exceeds maximum (5000 km)")
		return distance

	def clean_promo_code(self):
		code = self.cleaned_data.get('promo_code', '').strip().upper()
		return code  # Validation happens during booking process