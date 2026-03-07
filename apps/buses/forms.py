# buses/forms.py - Bus booking forms with date validation

from django import forms
from django.core.exceptions import ValidationError
from apps.core.date_utils import get_date_for_template, validate_booking_date
from .models import BusBooking, Bus, BusType


class BusRegistrationForm(forms.ModelForm):
    """Form for bus operators to register their buses"""
    
    class Meta:
        model = Bus
        fields = ['operator_name', 'from_city', 'to_city', 'departure_time', 'arrival_time', 
                  'journey_date', 'price_per_seat', 'available_seats', 'registration_number', 
                  'bus_type', 'amenities']
        widgets = {
            'operator_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ABC Travels'
            }),
            'from_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Departure city'
            }),
            'to_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Destination city'
            }),
            'departure_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'arrival_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'journey_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'price_per_seat': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '₹',
                'step': '0.01',
                'min': '1'
            }),
            'available_seats': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '60'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., DL-01-AB-1234'
            }),
            'amenities': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Comma-separated: WiFi, AC, Charging Point'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make bus_type optional since view provides default
        self.fields['bus_type'].required = False
    
    def clean_operator_name(self):
        name = self.cleaned_data.get('operator_name', '').strip()
        if not name:
            raise ValidationError("Operator name is required")
        if len(name) < 3:
            raise ValidationError("Operator name must be at least 3 characters")
        return name
    
    def clean_price_per_seat(self):
        price = self.cleaned_data.get('price_per_seat')
        if not price or price <= 0:
            raise ValidationError("Price must be greater than ₹0")
        if price < 50:
            raise ValidationError("Minimum price is ₹50 per seat")
        if price > 10000:
            raise ValidationError("Price exceeds maximum allowed (₹10,000/seat)")
        return price
    
    def clean_available_seats(self):
        seats = self.cleaned_data.get('available_seats')
        if not seats or seats <= 0:
            raise ValidationError("Number of seats must be greater than 0")
        if seats > 60:
            raise ValidationError("Maximum seats allowed is 60")
        return seats


class BusBookingForm(forms.ModelForm):
    """Form for creating bus bookings with date validation"""
    
    class Meta:
        model = BusBooking
        fields = ['journey_date', 'promo_code']
    
    journey_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
        }),
        label='Journey Date'
    )
    promo_code = forms.CharField(
        max_length=30,
        required=False,
        label='Promo Code'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimum date for date field
        today = get_date_for_template()
        self.fields['journey_date'].widget.attrs['min'] = today
    
    def clean_journey_date(self):
        """Backend validation for journey date"""
        journey_date = self.cleaned_data.get('journey_date')
        if journey_date:
            valid, message = validate_booking_date(journey_date, allow_today=True)
            if not valid:
                raise ValidationError(message)
        return journey_date


class BusSeatBookingForm(forms.Form):
    """Booking form with seat selection and passenger details"""

    seat_id = forms.ChoiceField(label='Seat')
    journey_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        }),
        label='Journey Date'
    )
    passenger_full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Passenger Name'
    )
    passenger_age = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Passenger Age'
    )
    passenger_gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Passenger Gender'
    )
    passenger_phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Phone (Optional)'
    )
    promo_code = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Promo Code (Optional)'
    )

    def __init__(self, *args, **kwargs):
        seat_choices = kwargs.pop('seat_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['seat_id'].choices = seat_choices
        today = get_date_for_template()
        self.fields['journey_date'].widget.attrs['min'] = today

    def clean_journey_date(self):
        journey_date = self.cleaned_data.get('journey_date')
        if journey_date:
            valid, message = validate_booking_date(journey_date, allow_today=True)
            if not valid:
                raise ValidationError(message)
        return journey_date