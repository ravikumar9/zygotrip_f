from django import forms
from apps.hotels.models import Property
from apps.core.location_models import City


class PropertyRegistrationForm(forms.ModelForm):
	"""Simple property registration form for owners"""
	
	class Meta:
		model = Property
		fields = [
			'name', 'property_type', 'city', 'locality',
			'address', 'description',
			'latitude', 'longitude',
			'rating', 'has_free_cancellation', 'cancellation_hours'
		]
		widgets = {
			'name': forms.TextInput(attrs={'placeholder': 'Hotel/Resort Name', 'class': 'form-control'}),
			'property_type': forms.Select(attrs={'class': 'form-control'}),
			'city': forms.Select(attrs={'class': 'form-control'}),
			'locality': forms.Select(attrs={'class': 'form-control'}),
			'address': forms.Textarea(attrs={'placeholder': 'Full address', 'rows': 3, 'class': 'form-control'}),
			'description': forms.Textarea(attrs={'placeholder': 'Description', 'rows': 5, 'class': 'form-control'}),
			'latitude': forms.NumberInput(attrs={'placeholder': '28.6139', 'step': '0.000001', 'class': 'form-control'}),
			'longitude': forms.NumberInput(attrs={'placeholder': '77.2090', 'step': '0.000001', 'class': 'form-control'}),
			'rating': forms.NumberInput(attrs={'placeholder': '4.5', 'min': '0', 'max': '5', 'step': '0.1', 'class': 'form-control'}),
			'has_free_cancellation': forms.CheckboxInput(),
			'cancellation_hours': forms.NumberInput(attrs={'placeholder': '24', 'class': 'form-control'}),
		}
	
	def clean_rating(self):
		rating = self.cleaned_data.get('rating')
		if rating and (rating < 0 or rating > 5):
			raise forms.ValidationError("Rating must be between 0 and 5.")
		return rating


class BusRegistrationForm(forms.Form):
	"""Simple bus registration form for operators"""
	operator_name = forms.CharField(max_length=120, label="Bus Operator Name")
	bus_name = forms.CharField(max_length=120, label="Bus Name")
	registration_number = forms.CharField(max_length=50, label="Bus Registration Number")
	capacity = forms.IntegerField(min_value=1, label="Passenger Capacity")
	route_from = forms.CharField(max_length=120, label="Route From (City)")
	route_to = forms.CharField(max_length=120, label="Route To (City)")
	base_fare = forms.DecimalField(max_digits=10, decimal_places=2, label="Base Fare (per passenger)")
	
	def clean_capacity(self):
		capacity = self.cleaned_data.get('capacity')
		if capacity and capacity > 100:
			raise forms.ValidationError("Bus capacity cannot exceed 100.")
		return capacity


class CabRegistrationForm(forms.Form):
	"""Simple cab registration form for operators"""
	operator_name = forms.CharField(max_length=120, label="Cab Operator Name")
	vehicle_type = forms.ChoiceField(
		choices = [
			('sedan', 'Sedan'),
			('suv', 'SUV'),
			('hatchback', 'Hatchback'),
		],
		label="Vehicle Type"
	)
	registration_number = forms.CharField(max_length=50, label="Vehicle Registration Number")
	city_coverage = forms.CharField(max_length=120, label="City Coverage")
	base_fare = forms.DecimalField(max_digits=10, decimal_places=2, label="Base Fare per KM")
	
	def clean_base_fare(self):
		fare = self.cleaned_data.get('base_fare')
		if fare and fare < 0:
			raise forms.ValidationError("Fare must be a positive number.")
		return fare