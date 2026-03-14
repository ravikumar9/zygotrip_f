"""Forms for property owners to manage hotel features and details"""
from django import forms
from apps.hotels.models import Property


class PropertyFeaturesForm(forms.ModelForm):
    """Form for property owners to update hotel features and details"""

    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Couple Friendly, Mountain View, Pool View (comma-separated)'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tags = self.initial.get('tags')
        if not tags and self.instance and self.instance.pk:
            tags = self.instance.tags
        if isinstance(tags, list):
            self.initial['tags'] = ', '.join(tags)

    def clean_tags(self):
        raw_tags = self.cleaned_data.get('tags', [])
        if isinstance(raw_tags, list):
            return [tag.strip() for tag in raw_tags if str(tag).strip()]
        if isinstance(raw_tags, str):
            return [tag.strip() for tag in raw_tags.replace('\n', ',').split(',') if tag.strip()]
        return []
    
    class Meta:
        model = Property
        fields = [
            'name',
            'city',
            'area',
            'landmark',
            'country',
            'address',
            'description',
            'property_type',
            'star_category',
            'has_free_cancellation',
            'cancellation_hours',
            'pay_at_hotel',
            'tags',
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
            'city': forms.Select(attrs={
                'class': 'form-control'
            }),
            'area': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Madikeri, Baga Beach, MG Road'
            }),
            'landmark': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nearby landmark to help guests find you'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
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
            'pay_at_hotel': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
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
            'city': 'City',
            'area': 'Area / Neighborhood',
            'landmark': 'Landmark',
            'country': 'Country',
            'address': 'Full Address',
            'description': 'Property Description',
            'property_type': 'Property Type',
            'star_category': 'Star Category',
            'has_free_cancellation': 'Offer Free Cancellation',
            'cancellation_hours': 'Free Cancellation Window (hours)',
            'pay_at_hotel': 'Allow Pay at Hotel',
            'tags': 'Property Tags',
        }
