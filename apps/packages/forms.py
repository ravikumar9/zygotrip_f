from django import forms
from django.utils import timezone


class PackageBookingForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    number_of_travellers = forms.IntegerField(min_value=1, max_value=50)
    promo_code = forms.CharField(required=False)
    traveler_full_name = forms.CharField(max_length=120)
    traveler_age = forms.IntegerField(min_value=1, max_value=120)
    traveler_relationship = forms.CharField(required=False, max_length=120)
    traveler_email = forms.EmailField(required=False)
    traveler_phone = forms.CharField(required=False, max_length=20)

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        today = timezone.now().date()

        if start_date and start_date < today:
            self.add_error("start_date", "Start date cannot be in the past.")

        if start_date and end_date and end_date <= start_date:
            self.add_error("end_date", "End date must be after start date.")

        return cleaned
