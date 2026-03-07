from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.date_utils import get_date_for_template, validate_booking_date
from apps.meals.models import MealPlan
from apps.rooms.models import RoomType


class BookingCreateForm(forms.Form):
    room_type = forms.ModelChoiceField(queryset=RoomType.objects.none())
    meal_plan = forms.ModelChoiceField(queryset=MealPlan.objects.none(), required=False)
    check_in = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    check_out = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    quantity = forms.IntegerField(min_value=1, initial=1)
    guest_full_name = forms.CharField(max_length=120)
    guest_age = forms.IntegerField(min_value=1, initial=25)
    guest_email = forms.EmailField(required=False)
    guest_phone = forms.CharField(max_length=20, required=False)
    promo_code = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        property_obj = kwargs.pop('property_obj', None)
        super().__init__(*args, **kwargs)
        
        # Set minimum date for date fields
        today = get_date_for_template()
        self.fields['check_in'].widget.attrs['min'] = today
        self.fields['check_out'].widget.attrs['min'] = today
        
        # Add frontend validation
        self.fields['check_in'].widget.attrs['required'] = 'required'
        self.fields['check_out'].widget.attrs['required'] = 'required'
        
        if property_obj:
            room_types = property_obj.room_types.all()
            if hasattr(RoomType, 'is_active'):
                room_types = room_types.filter(is_active=True)
            self.fields['room_type'].queryset = room_types

            if hasattr(property_obj, 'meal_plans'):
                meal_plans = property_obj.meal_plans.all()
                if meal_plans.model and hasattr(meal_plans.model, 'is_active'):
                    meal_plans = meal_plans.filter(is_active=True)
                self.fields['meal_plan'].queryset = meal_plans
    
    def clean_check_in(self):
        """Backend validation for check-in date"""
        check_in = self.cleaned_data.get('check_in')
        if check_in:
            valid, message = validate_booking_date(check_in, allow_today=True)
            if not valid:
                raise ValidationError(message)
        return check_in
    
    def clean_check_out(self):
        """Backend validation for check-out date"""
        check_out = self.cleaned_data.get('check_out')
        if check_out:
            valid, message = validate_booking_date(check_out, allow_today=True)
            if not valid:
                raise ValidationError(message)
        return check_out
    
    def clean(self):
        """Cross-field validation - STRICT: checkout MUST be > checkin"""
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        
        if check_in and check_out:
            if check_out <= check_in:
                raise ValidationError("Checkout date must be AFTER checkin date, not same day.")
        
        return cleaned_data