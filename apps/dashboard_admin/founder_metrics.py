"""
Founder metrics dashboard (PHASE 8, PROMPT 12).

Admin-only dashboard showing:
- Today's GMV (Gross Merchandise Value)
- Today's confirmed bookings
- Today's refund amount
- Pending settlement amount
- Available inventory summary
- Payment failures count
"""
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta

from apps.booking.models import Booking, Settlement
from apps.hotels.models import Property
from apps.rooms.models import RoomInventory


@staff_member_required
def founder_dashboard(request):
    """
    Founder/founder metrics dashboard.
    
    Shows real-time KPIs for business monitoring.
    """
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # Today's bookings
    today_bookings = Booking.objects.filter(
        created_at__date=today
    ).select_related('property', 'user')
    
    confirmed_today = today_bookings.filter(
        status=Booking.STATUS_CONFIRMED
    )
    
    # TODAY'S GMV (Gross Merchandise Value)
    today_gmv = confirmed_today.aggregate(
        total=Sum('gross_amount')
    )['total'] or 0
    
    # TODAY'S CONFIRMED BOOKINGS
    confirmed_count = confirmed_today.count()
    
    # TODAY'S REFUNDS
    refunded_today = Booking.objects.filter(
        status=Booking.STATUS_REFUNDED,
        updated_at__date=today
    ).aggregate(
        total=Sum('refund_amount')
    )['total'] or 0
    
    # PENDING SETTLEMENT AMOUNT
    pending_settlement = Booking.objects.filter(
        status=Booking.STATUS_SETTLEMENT_PENDING
    ).aggregate(
        total=Sum('net_payable_to_hotel')
    )['total'] or 0
    
    # UNSETTLED SETTLEMENTS
    unsettled_amount = Settlement.objects.filter(
        status__in=['draft', 'pending']
    ).aggregate(
        total=Sum('total_payable')
    )['total'] or 0
    
    # AVAILABLE INVENTORY
    available_inventory = RoomInventory.objects.filter(
        date__gte=today,
        is_closed=False
    ).aggregate(
        total=Sum('available_rooms')
    )['total'] or 0
    
    # PAYMENT FAILURES (last 24 hours)
    payment_failures = Booking.objects.filter(
        status=Booking.STATUS_FAILED,
        updated_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    # HOLDS EXPIRING (next hour)
    hour_from_now = timezone.now() + timedelta(hours=1)
    expiring_holds = Booking.objects.filter(
        status=Booking.STATUS_HOLD,
        hold_expires_at__lte=hour_from_now,
        hold_expires_at__gt=timezone.now()
    ).count()
    
    # 7-day metrics
    week_gmv = Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        created_at__date__gte=week_ago
    ).aggregate(
        total=Sum('gross_amount')
    )['total'] or 0
    
    week_bookings = Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        created_at__date__gte=week_ago
    ).count()
    
    # Top properties by bookings
    top_properties = Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        created_at__date__gte=week_ago
    ).values('property__name', 'property__id').annotate(
        booking_count=Count('id'),
        total_amount=Sum('gross_amount')
    ).order_by('-booking_count')[:5]
    
    # Status distribution
    status_distribution = Booking.objects.filter(
        created_at__date=today
    ).values('status').annotate(
        count=Count('id')
    )
    
    context = {
        'today': today,
        'today_gmv': today_gmv,
        'confirmed_count': confirmed_count,
        'refunded_today': refunded_today,
        'pending_settlement': pending_settlement,
        'unsettled_amount': unsettled_amount,
        'available_inventory': available_inventory,
        'payment_failures': payment_failures,
        'expiring_holds': expiring_holds,
        'week_gmv': week_gmv,
        'week_bookings': week_bookings,
        'top_properties': list(top_properties),
        'status_distribution': list(status_distribution),
    }
    
    return render(request, 'dashboard_admin/founder_metrics.html', context)


@staff_member_required
def system_health(request):
    """System health and monitoring dashboard."""
    today = timezone.now().date()
    
    # Database health
    booking_count = Booking.objects.count()
    hold_count = Booking.objects.filter(status=Booking.STATUS_HOLD).count()
    
    # Inventory health
    inventory_count = RoomInventory.objects.filter(date__gte=today).count()
    closed_dates = RoomInventory.objects.filter(
        is_closed=True,
        date__gte=today
    ).count()
    
    # Settlement health
    draft_settlements = Settlement.objects.filter(status=Settlement.STATUS_DRAFT).count()
    pending_settlements = Settlement.objects.filter(status=Settlement.STATUS_PENDING).count()
    
    # Booking pipeline
    payment_pending = Booking.objects.filter(
        status=Booking.STATUS_PAYMENT_PENDING
    ).count()
    refund_pending = Booking.objects.filter(
        status=Booking.STATUS_REFUND_PENDING
    ).count()
    
    context = {
        'database': {
            'total_bookings': booking_count,
            'holds_count': hold_count,
        },
        'inventory': {
            'inventory_records': inventory_count,
            'closed_dates': closed_dates,
        },
        'settlement': {
            'draft_settlements': draft_settlements,
            'pending_settlements': pending_settlements,
        },
        'pipeline': {
            'payment_pending': payment_pending,
            'refund_pending': refund_pending,
        },
    }
    
    return render(request, 'dashboard_admin/system_health.html', context)
