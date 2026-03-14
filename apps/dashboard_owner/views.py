from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect, render
from apps.accounts.permissions import role_required, provider_required
from apps.hotels.services import create_property, submit_property_for_approval
from .forms import (
    MealPlanForm, PriceForm, PropertyForm, RoomTypeForm,
    PropertyImageForm, RoomImageForm, RatingAggregateForm
)
# PropertyOfferForm moved to apps.offers
from .selectors import get_owner_properties, get_property_or_404, get_room_or_404, get_or_create_rating
from .services import (
	create_property_image,
	save_property_image,
	save_room,
	save_room_image,
	save_meal,
	# save_offer,  # Moved to apps.offers
	update_rating,
)


@role_required('property_owner')
def dashboard(request):
	properties = get_owner_properties(request.user)
	return render(request, 'dashboard_owner/dashboard.html', {'properties': properties})


@role_required('property_owner')
def edit_property_features(request, property_id):
	"""Allow property owners to edit hotel features, amenities, and details"""
	from apps.hotels.models import Property, PropertyAmenity
	from .forms_property_features import PropertyFeaturesForm
	
	property_obj = get_property_or_404(property_id, request.user)
	amenities_list = '\n'.join(
		PropertyAmenity.objects.filter(property=property_obj).values_list('name', flat=True)
	)
	
	if request.method == 'POST':
		form = PropertyFeaturesForm(request.POST, instance=property_obj)
		if form.is_valid():
			property_obj = form.save(commit=False)
			property_obj.save()
			
			# Handle amenities (if provided as comma-separated or line-separated list)
			amenities_text = request.POST.get('amenities_list', '')
			if amenities_text:
				# Clear existing and add new
				PropertyAmenity.objects.filter(property=property_obj).delete()
				for amenity in amenities_text.strip().split('\n'):
					amenity = amenity.strip()
					if amenity:
						PropertyAmenity.objects.create(property=property_obj, name=amenity)
			
			messages.success(request, 'Property features updated successfully!')
			return redirect('dashboard_owner:dashboard')
	else:
		form = PropertyFeaturesForm(instance=property_obj)
	
	return render(request, 'dashboard_owner/edit_property_features.html', {
		'form': form,
		'property': property_obj,
		'amenities_list': amenities_list,
	})


@provider_required
def add_property(request):
	form = PropertyForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		property_obj = create_property(request.user, **form.cleaned_data)
		image_url = request.POST.get('image_url', '').strip()
		create_property_image(property_obj, image_url)
		messages.success(request, 'Property created. Continue with gallery, rooms, and inventory to complete setup.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/add_property.html', {'form': form})


@role_required('property_owner')
def add_property_image(request, property_id):
	"""Upload images for a property"""
	property_obj = get_property_or_404(property_id, request.user)
	form = PropertyImageForm(request.POST or None, request.FILES or None)
	if request.method == 'POST' and form.is_valid():
		save_property_image(form, property_obj)
		messages.success(request, 'Image uploaded successfully.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/add_property_image.html', {'form': form, 'property': property_obj})


@role_required('property_owner')
def add_room(request, property_id):
	property_obj = get_property_or_404(property_id, request.user)
	form = RoomTypeForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		save_room(form, property_obj)
		messages.success(request, 'Room added.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/add_room.html', {'form': form, 'property': property_obj})


@role_required('property_owner')
def add_room_image(request, room_id):
	"""Upload images for a room type"""
	room = get_room_or_404(room_id, request.user)
	form = RoomImageForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		save_room_image(form, room)
		messages.success(request, 'Room image uploaded successfully.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/add_room_image.html', {'form': form, 'room': room})


@role_required('property_owner')
def add_meal(request, property_id):
	property_obj = get_property_or_404(property_id, request.user)
	form = MealPlanForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		save_meal(form, property_obj)
		messages.success(request, 'Meal plan added.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/add_meal.html', {'form': form, 'property': property_obj})


@role_required('property_owner')
def add_offer(request, property_id):
	"""Create promotional offer for a property"""
	from apps.offers.models import Offer, PropertyOffer
	from .forms import PropertyOfferForm
	
	property_obj = get_property_or_404(property_id, request.user)
	form = PropertyOfferForm(request.POST or None)
	
	if request.method == 'POST' and form.is_valid():
		# Create Offer instance
		offer = Offer.objects.create(
			title=form.cleaned_data['title'],
			description=form.cleaned_data.get('description', ''),
			discount_percentage=form.cleaned_data.get('discount_percentage') or 0,
			discount_flat=form.cleaned_data.get('discount_flat') or 0,
			coupon_code=form.cleaned_data.get('coupon_code', ''),
			start_datetime=form.cleaned_data['start_datetime'],
			end_datetime=form.cleaned_data['end_datetime'],
			is_active=form.cleaned_data.get('is_active', True),
			is_global=False,  # Property-specific offer
		)
		
		# Link offer to property via PropertyOffer
		PropertyOffer.objects.create(
			property=property_obj,
			offer=offer
		)
		
		messages.success(request, f'Offer "{offer.title}" created successfully!')
		return redirect('dashboard_owner:dashboard')
	
	return render(request, 'dashboard_owner/add_offer.html', {
		'form': form,
		'property': property_obj
	})


@role_required('property_owner')
def add_room_amenity(request, room_id):
	"""Add amenity to a specific room type"""
	from apps.rooms.models import RoomAmenity
	from .forms import RoomAmenityForm
	
	room = get_room_or_404(room_id, request.user)
	form = RoomAmenityForm(request.POST or None)
	
	if request.method == 'POST' and form.is_valid():
		name = form.cleaned_data['name']
		icon = form.cleaned_data.get('icon', '')
		
		# Create or update room amenity
		RoomAmenity.objects.get_or_create(
			room_type=room,
			name=name,
			defaults={'icon': icon}
		)
		
		messages.success(request, f'Amenity "{name}" added to {room.name}')
		return redirect('dashboard_owner:dashboard')
	
	return render(request, 'dashboard_owner/add_room_amenity.html', {
		'form': form,
		'room': room,
		'existing_amenities': room.amenities.all()
	})


@role_required('property_owner')
def delete_room_amenity(request, amenity_id):
	"""Delete a room-specific amenity"""
	from apps.rooms.models import RoomAmenity
	
	try:
		amenity = RoomAmenity.objects.select_related('room_type__property').get(id=amenity_id)
		# Verify owner has access to this room's property
		if amenity.room_type.property.owner != request.user:
			messages.error(request, 'You do not have permission to delete this amenity.')
			return redirect('dashboard_owner:dashboard')
		
		amenity_name = amenity.name
		room_name = amenity.room_type.name
		amenity.delete()
		messages.success(request, f'Amenity "{amenity_name}" removed from {room_name}')
	except RoomAmenity.DoesNotExist:
		messages.error(request, 'Amenity not found.')
	
	return redirect('dashboard_owner:dashboard')


# @role_required('property_owner')
# def add_offer(request, property_id):
# 	"""Create promotional offer for a property"""
# 	property_obj = get_property_or_404(property_id, request.user)
# 	form = PropertyOfferForm(request.POST or None)
# 	if request.method == 'POST' and form.is_valid():
# 		save_offer(form, property_obj)
# 		messages.success(request, 'Offer created successfully.')
# 		return redirect('dashboard_owner:dashboard')
# 	return render(request, 'dashboard_owner/add_offer.html', {'form': form, 'property': property_obj})
# Offer management moved to apps.offers admin interface


@role_required('property_owner')
def update_ratings(request, property_id):
	"""Update rating breakdown for a property"""
	property_obj = get_property_or_404(property_id, request.user)
	rating_obj, created = get_or_create_rating(property_obj)
	form = RatingAggregateForm(request.POST or None, instance=rating_obj)
	if request.method == 'POST' and form.is_valid():
		update_rating(property_obj, rating_obj, form)
		messages.success(request, 'Rating breakdown updated.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/update_ratings.html', {'form': form, 'property': property_obj})


@role_required('property_owner')
def set_price(request, room_id):
	room = get_room_or_404(room_id, request.user)
	form = PriceForm(request.POST or None, instance=room)
	if request.method == 'POST' and form.is_valid():
		form.save()
		messages.success(request, 'Price updated.')
		return redirect('dashboard_owner:dashboard')
	return render(request, 'dashboard_owner/set_price.html', {'form': form, 'room': room})


@role_required('property_owner')
def submit_approval(request, property_id):
	property_obj = get_property_or_404(property_id, request.user)
	submit_property_for_approval(property_obj)
	messages.success(request, 'Property submitted for approval.')
	return redirect('dashboard_owner:dashboard')


def cancellation_policy(request, property_id):
	"""
	Phase 10: Owner can configure the cancellation policy for their property.
	Creates the policy on first save; updates on subsequent saves.
	"""
	from apps.booking.cancellation_models import CancellationPolicy

	property_obj = get_property_or_404(property_id, request.user)
	policy, created = CancellationPolicy.objects.get_or_create(property=property_obj)

	if request.method == 'POST':
		policy_type = request.POST.get('policy_type', CancellationPolicy.POLICY_TYPE_FLEXIBLE)
		try:
			free_cancel_hours = int(request.POST.get('free_cancel_hours', 48))
			partial_refund_percent = float(request.POST.get('partial_refund_percent', 50))
			partial_cancel_hours = int(request.POST.get('partial_cancel_hours', 24))
			non_refundable_hours = int(request.POST.get('non_refundable_hours', 0))
			platform_fee = float(request.POST.get('platform_fee_always_withheld', 2.0))
		except (ValueError, TypeError):
			messages.error(request, 'Invalid values. Please check your inputs.')
			return render(request, 'dashboard_owner/cancellation_policy.html', {
				'property': property_obj, 'policy': policy,
			})

		policy.policy_type = policy_type
		policy.free_cancel_hours = free_cancel_hours
		policy.partial_refund_percent = partial_refund_percent
		policy.partial_cancel_hours = partial_cancel_hours
		policy.non_refundable_hours = non_refundable_hours
		policy.platform_fee_always_withheld = platform_fee
		policy.display_note = request.POST.get('display_note', '').strip()
		policy.partial_refund_enabled = request.POST.get('partial_refund_enabled') == 'on'
		policy.save()

		messages.success(request, 'Cancellation policy saved successfully.')

	return render(request, 'dashboard_owner/cancellation_policy.html', {
		'property': property_obj,
		'policy': policy,
		'policy_types': CancellationPolicy.POLICY_TYPE_CHOICES,
	})
