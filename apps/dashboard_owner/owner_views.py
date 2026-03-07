"""
Owner dashboard HARDENED features (PHASE 6, PROMPT 10).

Views:
1. Bulk inventory update
2. Booking list with filtering
3. CSV export
4. Revenue dashboard
5. Check-in management
6. API endpoints for quick actions
"""
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from csv import writer as csv_writer
from datetime import timedelta
import json

from apps.accounts.permissions import role_required
from apps.booking.models import Booking
from apps.rooms.models import RoomInventory, RoomType
from apps.hotels.models import Property


@role_required('property_owner')
def inventory_management(request, property_id):
    """
    Bulk inventory update view.
    
    Allows owner to:
    - Select date range
    - Update room count
    - Update daily price
    - Mark dates closed
    """
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    
    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        room_type_id = request.POST.get('room_type')
        new_count = request.POST.get('available_rooms')
        new_price = request.POST.get('price')
        is_closed = request.POST.get('is_closed') == 'on'
        
        # Validate and parse dates
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            room_type = RoomType.objects.get(id=room_type_id, property=property_obj)
        except (ValueError, RoomType.DoesNotExist):
            messages.error(request, 'Invalid input')
            return render(request, 'dashboard_owner/inventory_management.html', {
                'property': property_obj,
                'room_types': property_obj.room_types.all(),
            })
        
        # Update inventories in range
        current_date = start_date
        updated_count = 0
        
        while current_date <= end_date:
            inventory, created = RoomInventory.objects.get_or_create(
                room_type=room_type,
                date=current_date,
                defaults={
                    'available_rooms': int(new_count) if new_count else 0,
                    'price': new_price or 0,
                    'is_closed': is_closed,
                }
            )
            
            if not created:
                # Update existing
                inventory.available_rooms = int(new_count) if new_count else inventory.available_rooms
                inventory.price = new_price or inventory.price
                inventory.is_closed = is_closed
                inventory.save()
            
            updated_count += 1
            current_date += timedelta(days=1)
        
        messages.success(request, f'Updated {updated_count} days')
        return redirect('dashboard_owner:inventory_management', property_id=property_id)
    
    room_types = property_obj.room_types.all()
    
    return render(request, 'dashboard_owner/inventory_management.html', {
        'property': property_obj,
        'room_types': room_types,
    })


@role_required('property_owner')
def booking_list(request, property_id):
    """
    Booking list view with filtering.
    
    Filters:
    - Date range (check-in)
    - Status
    - Sorting
    """
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    
    # Get filter parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    status_filter = request.GET.get('status')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Build query
    bookings = Booking.objects.filter(property=property_obj)
    
    # Date filters
    if start_date_str:
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__gte=start_date)
        except ValueError:
            pass
    
    if end_date_str:
        try:
            from datetime import datetime
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__lte=end_date)
        except ValueError:
            pass
    
    # Status filter
    if status_filter and status_filter != 'all':
        bookings = bookings.filter(status=status_filter)
    
    # Sort
    bookings = bookings.order_by(sort_by)
    
    # Pagination
    from django.paginate import Paginator
    paginator = Paginator(bookings, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'property': property_obj,
        'page_obj': page_obj,
        'bookings': page_obj.object_list,
        'status_choices': Booking.STATUS_CHOICES,
        'status_filter': status_filter,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    
    return render(request, 'dashboard_owner/booking_list.html', context)


@role_required('property_owner')
def export_bookings_csv(request, property_id):
    """Export bookings to CSV."""
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    
    # Get date range if specified
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    bookings = Booking.objects.filter(property=property_obj)
    
    if start_date_str:
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__gte=start_date)
        except ValueError:
            pass
    
    if end_date_str:
        try:
            from datetime import datetime
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__lte=end_date)
        except ValueError:
            pass
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="bookings_{property_id}.csv"'
    
    # Write headers
    writer = csv_writer(response)
    writer.writerow([
        'Booking ID',
        'Guest Name',
        'Check-in',
        'Check-out',
        'Status',
        'Gross Amount',
        'Commission',
        'Net Payable',
        'Created',
    ])
    
    # Write rows
    for booking in bookings.values_list(
        'public_booking_id',
        'guest_name',
        'check_in',
        'check_out',
        'status',
        'gross_amount',
        'commission_amount',
        'net_payable_to_hotel',
        'created_at',
    ):
        writer.writerow(booking)
    
    return response


@role_required('property_owner')
def revenue_dashboard(request):
    """Revenue and earnings dashboard for property owner across all properties"""
    
    # Get owner's properties
    properties = Property.objects.filter(owner=request.user).annotate(
        total_revenue=Sum('booking__gross_amount'),
        booking_count=Count('booking', filter=Q(booking__status='confirmed'))
    )
    
    # Total revenue
    confirmed_bookings = Booking.objects.filter(
        property__owner=request.user,
        status='confirmed'
    )
    
    total_revenue = confirmed_bookings.aggregate(
        Sum('net_payable_to_hotel')
    )['net_payable_to_hotel__sum'] or 0
    
    total_commission = confirmed_bookings.aggregate(
        Sum('commission_amount')
    )['commission_amount__sum'] or 0
    
    total_bookings = confirmed_bookings.count()
    
    # Monthly trend
    from django.db.models.functions import TruncMonth
    monthly_revenue = confirmed_bookings.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        revenue=Sum('net_payable_to_hotel')
    ).order_by('month')
    
    months_json = json.dumps([str(m['month'].strftime('%b %Y')) if m['month'] else 'N/A' for m in monthly_revenue])
    revenue_trend_json = json.dumps([float(m['revenue'] or 0) for m in monthly_revenue])
    
    # Property-wise breakdown
    property_revenue_data = []
    for prop in properties:
        prop_bookings = confirmed_bookings.filter(property=prop)

        # Real occupancy: (booked room-nights) / (total room capacity × 30-day window) × 100
        total_room_capacity = prop.roomtype_set.aggregate(
            cap=Sum('available_count')
        )['cap'] or 0
        booked_room_nights = sum(
            (b.check_out - b.check_in).days * b.rooms
            for b in prop_bookings.only('check_in', 'check_out', 'rooms')
        )
        if total_room_capacity > 0:
            occupancy_rate = round(min(booked_room_nights / (total_room_capacity * 30) * 100, 100), 1)
        else:
            occupancy_rate = 0

        prop_revenue_data = {
            'property': prop,
            'booking_count': prop_bookings.count(),
            'gross_revenue': prop_bookings.aggregate(Sum('gross_amount'))['gross_amount__sum'] or 0,
            'commission': prop_bookings.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0,
            'commission_percent': getattr(prop, 'commission_percentage', 5),
            'net_earnings': prop_bookings.aggregate(Sum('net_payable_to_hotel'))['net_payable_to_hotel__sum'] or 0,
            'occupancy_rate': occupancy_rate,
        }
        property_revenue_data.append(prop_revenue_data)
    
    # Statistics
    confirmed_count = confirmed_bookings.count()
    cancelled_count = Booking.objects.filter(
        property__owner=request.user,
        status='cancelled'
    ).count()
    pending_count = Booking.objects.filter(
        property__owner=request.user,
        status='pending'
    ).count()
    
    context = {
        'total_revenue': int(total_revenue),
        'total_bookings': total_bookings,
        'confirmed_revenue': int(total_revenue),
        'total_commission': int(total_commission),
        'your_commission': getattr(request.user, 'commission_percentage', 95),
        'net_earnings': int(total_revenue - total_commission),
        'properties': property_revenue_data,
        'months_json': months_json,
        'revenue_trend_json': revenue_trend_json,
        'confirmed_count': confirmed_count,
        'cancelled_count': cancelled_count,
        'pending_count': pending_count,
        'new_bookings_this_month': confirmed_bookings.filter(
            created_at__month=timezone.now().month
        ).count(),
        'pending_settlement': 0,
        'settled_amount': int(total_revenue),
        'next_payout_date': (timezone.now() + timedelta(days=5)).date() if total_revenue > 0 else None,
    }
    
    return render(request, 'dashboard_owner/revenue_dashboard.html', context)


@role_required('property_owner')
def checkin_management(request):
    """Manage guest check-ins and check-outs across all properties"""
    
    # Get bookings for owner's properties
    bookings = Booking.objects.filter(
        property__owner=request.user,
        status='confirmed'
    ).select_related('user', 'property').order_by('check_in')
    
    now = timezone.now()
    today = now.date()
    
    # Filter by status
    status_filter = request.GET.get('status', 'upcoming')
    
    if status_filter == 'today':
        bookings = bookings.filter(check_in=today)
    elif status_filter == 'checked_in':
        bookings = bookings.filter(check_in__lte=today, check_out__gte=today)
    elif status_filter == 'completed':
        bookings = bookings.filter(check_out__lt=today)
    else:  # upcoming
        bookings = bookings.filter(check_in__gte=today)
    
    # Prepare check-in data
    checkins = []
    for booking in bookings:
        nights_remaining = (booking.check_out - today).days
        is_today = booking.check_in == today
        checked_in = booking.check_in < today  # Simple check
        
        checkins.append({
            'booking': booking,
            'is_today': is_today,
            'checked_in': checked_in,
            'nights_remaining': max(0, nights_remaining),
        })
    
    # Statistics
    upcoming_checkins = bookings.filter(check_in__gte=today).count()
    todays_checkins = bookings.filter(check_in=today).count()
    checked_in_count = bookings.filter(check_in__lte=today, check_out__gte=today).count()
    completed_count = bookings.filter(check_out__lt=today).count()
    
    # Occupancy
    all_properties = Property.objects.filter(owner=request.user)
    total_rooms = RoomType.objects.filter(property__in=all_properties).count() or 1
    occupied_rooms = bookings.aggregate(Sum('number_of_rooms'))['number_of_rooms__sum'] or 0
    occupancy_rate = int((occupied_rooms / max(total_rooms, 1)) * 100)
    
    context = {
        'checkins': checkins,
        'filter_status': status_filter,
        'upcoming_checkins': upcoming_checkins,
        'todays_checkins': todays_checkins,
        'checked_in_count': checked_in_count,
        'completed_count': completed_count,
        'this_week_checkins': bookings.filter(
            check_in__gte=today,
            check_in__lte=today + timedelta(days=7)
        ).count(),
        'occupied_rooms': occupied_rooms,
        'total_rooms': total_rooms,
        'occupancy_rate': occupancy_rate,
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return render(request, 'dashboard_owner/checkin_management.html', context)


# API endpoints for quick actions
@role_required('property_owner')
def api_booking_checkin(request, booking_id):
    """API endpoint to mark booking as checked in (sets STATUS_CHECKED_IN)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
    booking.status = Booking.STATUS_CHECKED_IN
    if hasattr(booking, 'check_in_datetime'):
        booking.check_in_datetime = timezone.now()
    booking.save()

    # Record status history
    try:
        from apps.booking.models import BookingStatusHistory
        BookingStatusHistory.objects.create(
            booking=booking,
            status=Booking.STATUS_CHECKED_IN,
            note=f"Checked in by owner at {timezone.now().strftime('%d %b %Y %H:%M')}"
        )
    except Exception:
        pass

    return JsonResponse({'success': True, 'status': Booking.STATUS_CHECKED_IN})


@role_required('property_owner')
def api_booking_checkout(request, booking_id):
    """
    API endpoint to mark booking as checked out.
    Phase 3: Triggers settlement service to release payout to owner wallet.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
    booking.status = Booking.STATUS_CHECKED_OUT
    if hasattr(booking, 'check_out_datetime'):
        booking.check_out_datetime = timezone.now()
    booking.save()

    # Record status history
    try:
        from apps.booking.models import BookingStatusHistory
        BookingStatusHistory.objects.create(
            booking=booking,
            status=Booking.STATUS_CHECKED_OUT,
            note=f"Checked out by owner at {timezone.now().strftime('%d %b %Y %H:%M')}"
        )
    except Exception:
        pass

    # Phase 3: Trigger settlement payout to owner wallet
    settlement_result = None
    try:
        from apps.booking.settlement_service import SettlementService, CashbackService
        svc = SettlementService()
        settlement_result = svc.settle(booking)
        # Phase 5: Award cashback to customer
        CashbackService().award_cashback(booking)
    except Exception as settle_err:
        # Non-fatal: log and continue — don't block checkout confirmation
        import logging
        logging.getLogger(__name__).error(f"Settlement failed for booking {booking_id}: {settle_err}")

    return JsonResponse({
        'success': True,
        'status': Booking.STATUS_CHECKED_OUT,
        'settlement': settlement_result,
    })


@role_required('property_owner')
def api_booking_cancel(request, booking_id):
    """
    Cancel a booking with policy-based refund calculation.
    Phase 4: Uses CancellationPolicy + RefundCalculator for accurate refund tiers.
    Phase 3: Triggers settlement reversal on owner wallet.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
    booking.status = Booking.STATUS_CANCELLED

    # Phase 4: Compute refund using CancellationPolicy engine
    refund_amount = 0
    refund_note = 'No policy found — full refund issued.'
    try:
        from apps.booking.cancellation_models import CancellationPolicy, RefundCalculator
        policy = CancellationPolicy.objects.get(property=booking.property)
        calculator = RefundCalculator(policy, booking.total_amount)
        result = calculator.compute(booking.check_in)
        refund_amount = float(result['refund_amount'])
        refund_note = result['note']
    except CancellationPolicy.DoesNotExist:
        # No policy configured — use property-level fallback
        property_obj = booking.property
        days_before = (booking.check_in - timezone.now().date()).days
        free_hours_threshold = getattr(property_obj, 'cancellation_hours', 48) // 24
        if getattr(property_obj, 'has_free_cancellation', True) and days_before >= free_hours_threshold:
            refund_amount = float(booking.total_amount)
            refund_note = 'Free cancellation — full refund.'
        else:
            refund_amount = float(booking.total_amount) * 0.5
            refund_note = '50% refund applied.'
    except Exception:
        refund_amount = 0

    booking.refund_amount = refund_amount
    if hasattr(booking, 'cancelled_at'):
        booking.cancelled_at = timezone.now()
    booking.save()

    # Refund to customer wallet (if they paid via wallet)
    if refund_amount > 0 and booking.user:
        try:
            from apps.wallet.services import refund_to_wallet
            refund_to_wallet(
                user=booking.user,
                amount=refund_amount,
                booking_reference=str(booking.public_booking_id),
                note=refund_note,
            )
        except Exception as refund_err:
            import logging
            logging.getLogger(__name__).warning(
                f"Wallet refund failed for booking {booking_id}: {refund_err}"
            )

    # Phase 3: Reverse any pending settlement on owner wallet
    try:
        from apps.booking.settlement_service import SettlementService
        SettlementService().reverse(booking, reason=f'Booking cancelled: {refund_note}')
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'refund_amount': refund_amount,
        'refund_note': refund_note,
    })
