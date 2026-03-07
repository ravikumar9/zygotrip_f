"""Forms for property owners to manage hotel features and details"""
from django import forms
from apps.hotels.models import Property


class PropertyFeaturesForm(forms.ModelForm):
    """Form for property owners to update hotel features and details"""
    
    class Meta:
        model = Property
        fields = [
            'name',
            'address',
            'description',
            'property_type',
            'star_category',
            'has_free_cancellation',
            'cancellation_hours',
            'latitude',
            'longitude',
            'place_id',
            'formatted_address',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hotel Name'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Address'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your property - highlight unique features, nearby attractions, and what makes your property special...'
            }),
            'property_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hotel, Resort, Guesthouse, etc.'
            }),
            'star_category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'has_free_cancellation': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'cancellation_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 72,
                'placeholder': 'Hours before check-in'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g. 19.075984'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g. 72.877656'
            }),
            'place_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Google Maps Place ID (auto-filled)'
            }),
            'formatted_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full formatted address from Google Places (auto-filled)'
            }),
        }
        labels = {
            'name': 'Property Name',
            'address': 'Full Address',
            'description': 'Property Description',
            'property_type': 'Property Type',
            'star_category': 'Star Category',
            'has_free_cancellation': 'Offer Free Cancellation',
            'cancellation_hours': 'Free Cancellation Window (hours)',
        }
