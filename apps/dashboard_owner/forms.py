from django import forms
from django.core.exceptions import ValidationError
from apps.hotels.validators import validate_https_image_url
from apps.hotels.models import Property, PropertyImage, RatingAggregate, Category, PropertyCategory
from apps.meals.models import MealPlan
from apps.rooms.models import RoomType, RoomImage
# PropertyOffer moved to apps.offers.models


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'name', 'property_type', 'city', 'area', 'landmark',
            'country', 'address', 'description', 'rating',
            'latitude', 'longitude', 'place_id', 'formatted_address',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'place_id': forms.TextInput(attrs={'placeholder': 'Google Maps Place ID (optional)'}),
            'formatted_address': forms.TextInput(attrs={'placeholder': 'Full formatted address from Google Places (optional)'}),
        }


class PropertyImageForm(forms.ModelForm):
    """Form for uploading property images with validation"""
    class Meta:
        model = PropertyImage
        fields = ['image', 'image_url', 'caption', 'is_featured', 'display_order']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Optional: Describe this image'}),
            'display_order': forms.NumberInput(attrs={'min': 0, 'value': 0}),
        }
    
    def clean_image_url(self):
        url = self.cleaned_data.get('image_url')
        if url:
            validate_https_image_url(url)
        return url
    
    def clean(self):
        cleaned_data = super().clean()
        image_file = cleaned_data.get('image')
        image_url = cleaned_data.get('image_url')
        if not image_file and not image_url:
            raise ValidationError('Provide an image upload or image URL')
        # Auto-unset other featured images when is_featured is True
        if cleaned_data.get('is_featured'):
            property_obj = getattr(self.instance, 'property', None)
            if property_obj:
                PropertyImage.objects.filter(property=property_obj, is_featured=True).update(is_featured=False)
        return cleaned_data


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['name', 'description', 'base_price', 'max_guests', 'available_count', 'bed_type', 'room_size_sqm']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class RoomImageForm(forms.ModelForm):
    """Form for uploading room images"""
    class Meta:
        model = RoomImage
        fields = ['image_url', 'is_featured', 'display_order']
    
    def clean_image_url(self):
        url = self.cleaned_data.get('image_url')
        if url:
            validate_https_image_url(url)
        return url


class MealPlanForm(forms.ModelForm):
    class Meta:
        model = MealPlan
        fields = ['code', 'name', 'display_name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'icon': forms.TextInput(attrs={'placeholder': 'e.g., 🍳 or fa-utensils'}),
        }


# PropertyOffer form moved to apps.offers
# from apps.offers.models import PropertyOffer
# class PropertyOfferForm(forms.ModelForm):
#     """Form for creating promotional offers"""
#     class Meta:
#         model = PropertyOffer
#         fields = ['title', 'description', 'discount_percentage', 'discount_amount', 'valid_from', 'valid_until', 'is_active', 'code']
#         widgets = {
#             'description': forms.Textarea(attrs={'rows': 3}),
#             'valid_from': forms.DateInput(attrs={'type': 'date'}),
#             'valid_until': forms.DateInput(attrs={'type': 'date'}),
#             'code': forms.TextInput(attrs={'placeholder': 'e.g., SUMMER2024'}),
#         }
#     
#     def clean(self):
#         cleaned_data = super().clean()
#         discount_pct = cleaned_data.get('discount_percentage')
#         discount_amt = cleaned_data.get('discount_amount')
#         
#         if not discount_pct and not discount_amt:
#             raise ValidationError('Either discount percentage or discount amount must be provided')
#
#         if discount_pct and discount_pct > 90:
#             raise ValidationError('Discount percentage must be 90 or less')
#         
#         valid_from = cleaned_data.get('valid_from')
#         valid_until = cleaned_data.get('valid_until')
#         
#         if valid_from and valid_until and valid_from >= valid_until:
#             raise ValidationError('Valid from date must be before valid until date')
#         
#         return cleaned_data


class RatingAggregateForm(forms.ModelForm):
    """Form for updating rating breakdowns"""
    class Meta:
        model = RatingAggregate
        fields = ['cleanliness', 'service', 'location', 'amenities', 'value_for_money', 'total_reviews']
        widgets = {
            'cleanliness': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'max': '5'}),
            'service': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'max': '5'}),
            'location': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'max': '5'}),
            'amenities': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'max': '5'}),
            'value_for_money': forms.NumberInput(attrs={'step': '0.1', 'min': '0', 'max': '5'}),
        }

class PriceForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['base_price']


class PropertyOfferForm(forms.Form):
    """Form for creating property-specific offers"""
    title = forms.CharField(
        max_length=200, 
        help_text="Offer title (e.g., 'Summer Special 2024')"
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Optional description of the offer"
    )
    discount_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=90,
        required=False,
        help_text="Percentage discount (e.g., 15 for 15% off)"
    )
    discount_flat = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Flat discount amount (e.g., 500 for ₹500 off)"
    )
    coupon_code = forms.CharField(
        max_length=50,
        required=False,
        help_text="Optional coupon code (e.g., SUMMER2024)"
    )
    start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Offer starts from this date/time"
    )
    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Offer ends at this date/time"
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Check to activate the offer immediately"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        discount_pct = cleaned_data.get('discount_percentage')
        discount_flat = cleaned_data.get('discount_flat')
        
        if not discount_pct and not discount_flat:
            raise ValidationError('Either discount percentage or flat discount amount must be provided')
        
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        
        if start and end and start >= end:
            raise ValidationError('Start date/time must be before end date/time')
        
        return cleaned_data


class RoomAmenityForm(forms.Form):
    """Form for managing room-specific amenities"""
    name = forms.CharField(
        max_length=120,
        help_text="Amenity name (e.g., 'Jacuzzi', 'Balcony', 'City View')"
    )
    icon = forms.CharField(
        max_length=40,
        required=False,
        help_text="Optional icon class (e.g., 'fa-hot-tub')"
    )