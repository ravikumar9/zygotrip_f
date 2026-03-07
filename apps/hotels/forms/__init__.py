from django import forms


class HotelFilterForm(forms.Form):
	q = forms.CharField(required=False)
	city = forms.MultipleChoiceField(required=False)
	rating = forms.MultipleChoiceField(required=False)
	amenities = forms.MultipleChoiceField(required=False)
	min_price = forms.DecimalField(required=False, min_value=0)
	max_price = forms.DecimalField(required=False, min_value=0)