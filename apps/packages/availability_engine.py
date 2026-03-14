"""
Package Availability Calendar & Itinerary Builder.

Implements:
- Date-based package availability with capacity tracking
- Dynamic pricing based on season, group size, and availability
- Itinerary customization (add-ons, hotel upgrades, activity swaps)
- Departure slot management
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.packages')


def get_package_availability(package, start_date, end_date=None):
    """
    Get availability calendar for a package over a date range.
    Uses PackageDeparture model for slot-based availability.
    
    Returns list of {date, available_slots, total_slots, price, season, is_sold_out}.
    """
    from apps.packages.models import PackageDeparture, PackageSeasonalPrice

    if not end_date:
        end_date = start_date + timedelta(days=90)

    departures = PackageDeparture.objects.filter(
        package=package,
        departure_date__gte=start_date,
        departure_date__lte=end_date,
        is_active=True,
    ).order_by('departure_date')

    # Get seasonal pricing
    seasonal = PackageSeasonalPrice.objects.filter(
        package=package,
    )

    calendar = []
    for dep in departures:
        available = dep.available_slots
        season = _get_season(dep.departure_date, seasonal)
        price = _calculate_departure_price(package, dep, season)

        calendar.append({
            'date': dep.departure_date,
            'departure_id': dep.id,
            'available_slots': max(0, available),
            'total_slots': dep.total_slots,
            'price_adult': price['adult'],
            'price_child': price['child'],
            'season': season['name'] if season else 'regular',
            'season_multiplier': float(season['multiplier']) if season else 1.0,
            'is_sold_out': available <= 0,
            'is_guaranteed': dep.is_guaranteed,
        })

    return calendar


def _get_season(departure_date, seasonal_prices):
    """Determine which season a date falls in."""
    for sp in seasonal_prices:
        if sp.is_active and sp.start_date <= departure_date <= sp.end_date:
            return {
                'name': sp.season_name,
                'multiplier': Decimal('1'),
                'adult_price': sp.adult_price,
                'child_price': sp.child_price,
            }
    return None


def _calculate_departure_price(package, departure, season):
    """Calculate price for a specific departure considering season and capacity."""
    base_adult = package.base_price
    base_child = package.base_price * Decimal('0.7')

    if season:
        if season.get('adult_price') and season['adult_price'] > 0:
            base_adult = season['adult_price']
        elif season.get('multiplier'):
            base_adult = base_adult * season['multiplier']
        if season.get('child_price') and season['child_price'] > 0:
            base_child = season['child_price']
        elif season.get('multiplier'):
            base_child = base_child * season['multiplier']

    # Early bird discount: > 60 days out → 5% off
    days_ahead = (departure.departure_date - date.today()).days
    if days_ahead > 60:
        base_adult *= Decimal('0.95')
        base_child *= Decimal('0.95')

    # Last-minute premium: < 7 days out → 10% surcharge
    if 0 < days_ahead < 7:
        base_adult *= Decimal('1.10')
        base_child *= Decimal('1.10')

    return {
        'adult': round(base_adult, 2),
        'child': round(base_child, 2),
    }


def build_custom_itinerary(package, customizations=None):
    """
    Build a customized itinerary from base package.
    
    customizations: {
        'hotel_upgrade': 'premium',  # standard/premium/luxury
        'add_activities': [activity_id, ...],
        'remove_days': [day_number, ...],
        'meal_upgrade': 'all_meals',
    }
    """
    from apps.packages.models import PackageItinerary, PackageAddon

    customizations = customizations or {}
    base_itinerary = PackageItinerary.objects.filter(
        package=package, is_active=True,
    ).order_by('day_number')

    days = []
    total_addon_cost = Decimal('0')
    remove_days = set(customizations.get('remove_days', []))

    for item in base_itinerary:
        if item.day_number in remove_days:
            continue
        day = {
            'day': item.day_number,
            'title': item.title,
            'description': item.description,
            'accommodation': item.accommodation,
            'meals': item.meals_included,
            'activities': [],
            'addons': [],
        }

        # Hotel upgrade
        if customizations.get('hotel_upgrade') == 'premium':
            day['accommodation'] = f"{day['accommodation']} (Upgraded to Premium)"
            total_addon_cost += Decimal('1500')  # Per night premium
        elif customizations.get('hotel_upgrade') == 'luxury':
            day['accommodation'] = f"{day['accommodation']} (Upgraded to Luxury)"
            total_addon_cost += Decimal('3500')  # Per night luxury

        # Meal upgrade
        if customizations.get('meal_upgrade') == 'all_meals':
            day['meals'] = 'ALL'
            total_addon_cost += Decimal('500')  # Per day meal upgrade

        days.append(day)

    # Add-on activities
    addon_activities = customizations.get('add_activities', [])
    if addon_activities:
        addons = PackageAddon.objects.filter(
            package=package, id__in=addon_activities, is_active=True,
        )
        for addon in addons:
            total_addon_cost += addon.price
            days.append({
                'day': len(days) + 1,
                'title': f'Add-on: {addon.name}',
                'description': addon.description,
                'accommodation': days[-1]['accommodation'] if days else '',
                'meals': 'NONE',
                'is_addon': True,
                'addon_price': str(addon.price),
            })

    return {
        'days': days,
        'total_days': len(days),
        'base_price': str(package.base_price),
        'addon_cost': str(total_addon_cost),
        'total_price': str(package.base_price + total_addon_cost),
        'customizations_applied': customizations,
    }


@transaction.atomic
def book_package_slot(package_id, departure_id, adults, children, user, addons=None):
    """
    Book a package departure slot with capacity check.
    
    Returns: (success, result_dict)
    """
    from apps.packages.models import Package, PackageDeparture, PackageBooking

    departure = PackageDeparture.objects.select_for_update().get(
        id=departure_id, package_id=package_id, is_active=True,
    )

    total_pax = adults + children
    available = departure.available_slots

    if total_pax > available:
        return False, {'error': f'Only {available} slots available, requested {total_pax}'}

    # Calculate pricing
    season = None
    from apps.packages.models import PackageSeasonalPrice
    seasonal = PackageSeasonalPrice.objects.filter(package_id=package_id)
    season = _get_season(departure.departure_date, seasonal)
    prices = _calculate_departure_price(departure.package, departure, season)

    traveler_subtotal = prices['adult'] * adults + prices['child'] * children

    # Apply add-on costs
    addon_total = Decimal('0')
    if addons:
        from apps.packages.models import PackageAddon
        for addon_id in addons:
            try:
                addon = PackageAddon.objects.get(id=addon_id, package_id=package_id, is_active=True)
                if addon.pricing_type == 'per_person':
                    addon_total += addon.price * total_pax
                else:
                    addon_total += addon.price
            except PackageAddon.DoesNotExist:
                continue

    group_discount = Decimal('0')
    if total_pax >= 10:
        group_discount = (traveler_subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
    elif total_pax >= 5:
        group_discount = (traveler_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))

    discounted_subtotal = (traveler_subtotal - group_discount).quantize(Decimal('0.01'))
    taxable_subtotal = (discounted_subtotal + addon_total).quantize(Decimal('0.01'))
    gst = (taxable_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
    total = (taxable_subtotal + gst).quantize(Decimal('0.01'))

    # Create booking
    booking = PackageBooking.objects.create(
        package_id=package_id,
        departure=departure,
        user=user,
        adults=adults,
        children=children,
        adult_price=prices['adult'],
        child_price=prices['child'],
        subtotal=taxable_subtotal,
        group_discount=group_discount,
        gst=gst,
        total_amount=total,
        status='confirmed',
        special_requests=(
            f"Addon IDs: {','.join(str(addon_id) for addon_id in addons)}"
            if addons else ''
        ),
    )

    # Decrement capacity
    departure.booked_slots += total_pax
    departure.save(update_fields=['booked_slots', 'updated_at'])

    logger.info(
        'Package booking created: package=%d, departure=%s, pax=%d, total=%s',
        package_id, departure.departure_date, total_pax, total,
    )

    return True, {
        'booking_id': booking.id,
        'total_amount': str(total),
        'departure_date': str(departure.departure_date),
        'adults': adults,
        'children': children,
    }
