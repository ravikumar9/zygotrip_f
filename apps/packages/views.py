"""Packages views - production-ready listing and detail pages."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Package
from .forms import PackageBookingForm
from .ota_selectors import get_ota_context


def _split_list(raw_text):
    if not raw_text:
        return []
    return [item.strip() for item in raw_text.split(',') if item.strip()]


def package_list(request):
    """Display available travel packages with OTA filtering"""
    context = get_ota_context(request)
    context.setdefault('empty_state', True)
    context.setdefault('total_count', 0)
    context.setdefault('filter_options', {})
    context.setdefault('selected_filters', {})
    context.setdefault('current_sort', 'popular')
    context.setdefault('page_title', 'Travel Packages')
    
    return render(request, 'packages/list.html', context)


@login_required
def package_detail(request, package_id):
    """Display single package detail"""
    package = get_object_or_404(Package, id=package_id, is_active=True)
    itinerary = package.itinerary.filter(is_active=True).order_by('day_number')
    context = {
        'package': package,
        'itinerary': itinerary,
        'inclusions': _split_list(package.inclusions),
        'exclusions': _split_list(package.exclusions),
        'page_title': 'Package Details',
    }
    return render(request, 'packages/detail.html', context)


@login_required
def package_booking(request, package_id):
    """Handle package booking request"""
    package = get_object_or_404(Package, id=package_id, is_active=True)
    if request.method == 'POST':
        form = PackageBookingForm(request.POST)
        if form.is_valid():
            messages.success(request, 'Package booking request received.')
            return redirect('packages:detail', package_id=package.id)
    else:
        form = PackageBookingForm()
    context = {
        'package': package,
        'form': form,
        'page_title': 'Book Package',
    }
    return render(request, 'packages/booking.html', context)