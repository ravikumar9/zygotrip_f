"""
Operations Dashboard API — Comprehensive real-time KPIs for admin/ops team.

Endpoints:
  - Platform overview (GMV, bookings, users, revenue)
  - Revenue breakdown by vertical/city/property
  - Booking funnel metrics
  - Fraud & moderation dashboard
  - Supplier health & reconciliation
  - Top properties / user growth
  - Export-ready data
"""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

logger = logging.getLogger('zygotrip.ops_dashboard')


def _staff_json(view_func):
    """Decorator: staff-only + JSON response."""
    from functools import wraps

    @wraps(view_func)
    @staff_member_required
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


@require_GET
@_staff_json
def platform_overview(request):
    """
    Real-time platform KPIs.
    ?range=today|7d|30d|90d
    """
    from apps.booking.models import Booking
    from apps.accounts.models import User
    from apps.hotels.models import Property

    range_key = request.GET.get('range', '7d')
    range_map = {'today': 0, '7d': 7, '30d': 30, '90d': 90}
    days = range_map.get(range_key, 7)

    now = timezone.now()
    start = now - timedelta(days=days) if days > 0 else now.replace(hour=0, minute=0, second=0)

    bookings = Booking.objects.filter(created_at__gte=start)
    confirmed = bookings.filter(status__in=['confirmed', 'checked_in', 'checked_out', 'settled'])

    gmv = confirmed.aggregate(total=Sum('gross_amount'))['total'] or 0
    revenue = confirmed.aggregate(total=Sum('commission_amount'))['total'] or 0

    # Previous period for comparison
    prev_start = start - timedelta(days=max(days, 1))
    prev_bookings = Booking.objects.filter(
        created_at__gte=prev_start, created_at__lt=start,
    ).filter(status__in=['confirmed', 'checked_in', 'checked_out', 'settled'])
    prev_gmv = prev_bookings.aggregate(total=Sum('gross_amount'))['total'] or 0

    return JsonResponse({
        'period': range_key,
        'gmv': float(gmv),
        'gmv_change_pct': _pct_change(prev_gmv, gmv),
        'revenue': float(revenue),
        'total_bookings': bookings.count(),
        'confirmed_bookings': confirmed.count(),
        'cancelled': bookings.filter(status='cancelled').count(),
        'failed': bookings.filter(status='failed').count(),
        'avg_booking_value': float(confirmed.aggregate(avg=Avg('gross_amount'))['avg'] or 0),
        'active_properties': Property.objects.filter(is_active=True).count(),
        'total_users': User.objects.filter(is_active=True).count(),
        'new_users': User.objects.filter(date_joined__gte=start).count(),
    })


@require_GET
@_staff_json
def revenue_breakdown(request):
    """
    Revenue breakdown by vertical and city.
    ?range=7d|30d|90d
    """
    from apps.booking.models import Booking

    days = int(request.GET.get('days', 30))
    start = timezone.now() - timedelta(days=days)

    confirmed = Booking.objects.filter(
        created_at__gte=start,
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    )

    # By city
    by_city = list(
        confirmed.values('property__city')
        .annotate(
            total_gmv=Sum('gross_amount'),
            booking_count=Count('id'),
        )
        .order_by('-total_gmv')[:15]
    )

    # Daily trend
    daily = list(
        confirmed.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(gmv=Sum('gross_amount'), count=Count('id'))
        .order_by('date')
    )

    return JsonResponse({
        'by_city': [{
            'city': r['property__city'] or 'Unknown',
            'gmv': float(r['total_gmv'] or 0),
            'bookings': r['booking_count'],
        } for r in by_city],
        'daily_trend': [{
            'date': r['date'].isoformat() if r['date'] else None,
            'gmv': float(r['gmv'] or 0),
            'bookings': r['count'],
        } for r in daily],
    })


@require_GET
@_staff_json
def booking_funnel(request):
    """
    Booking funnel: searches → holds → confirmed → completed.
    ?days=7
    """
    from apps.booking.models import Booking
    from apps.core.analytics import AnalyticsEvent

    days = int(request.GET.get('days', 7))
    start = timezone.now() - timedelta(days=days)

    # Search events
    searches = AnalyticsEvent.objects.filter(
        event_type='search',
        created_at__gte=start,
    ).count()

    bookings = Booking.objects.filter(created_at__gte=start)
    holds = bookings.filter(status__in=['hold', 'payment_pending', 'confirmed', 'checked_in', 'checked_out']).count()
    payment_attempted = bookings.exclude(status__in=['hold', 'draft']).count()
    confirmed = bookings.filter(status__in=['confirmed', 'checked_in', 'checked_out', 'settled']).count()
    completed = bookings.filter(status__in=['checked_out', 'settled']).count()

    return JsonResponse({
        'funnel': [
            {'stage': 'searches', 'count': searches},
            {'stage': 'holds_created', 'count': holds},
            {'stage': 'payment_attempted', 'count': payment_attempted},
            {'stage': 'confirmed', 'count': confirmed},
            {'stage': 'completed', 'count': completed},
        ],
        'conversion_rates': {
            'search_to_hold': _pct(holds, searches),
            'hold_to_payment': _pct(payment_attempted, holds),
            'payment_to_confirmed': _pct(confirmed, payment_attempted),
            'overall': _pct(confirmed, searches),
        },
    })


@require_GET
@_staff_json
def fraud_dashboard(request):
    """Fraud & moderation overview."""
    from apps.core.fraud_engine import FraudAlert
    from apps.hotels.review_models import Review
    from apps.hotels.review_fraud import ReviewFraudFlag

    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    # Fraud alerts
    open_alerts = FraudAlert.objects.filter(is_resolved=False).count()
    alerts_this_week = FraudAlert.objects.filter(created_at__gte=week_ago).count()
    high_risk_alerts = FraudAlert.objects.filter(
        is_resolved=False, risk_score__gte=80,
    ).count()

    # Review moderation
    pending_reviews = Review.objects.filter(status='pending').count()
    unresolved_flags = ReviewFraudFlag.objects.filter(is_resolved=False).count()
    auto_rejected = Review.objects.filter(
        status='rejected', created_at__gte=week_ago,
    ).count()

    return JsonResponse({
        'fraud_alerts': {
            'open': open_alerts,
            'this_week': alerts_this_week,
            'high_risk': high_risk_alerts,
        },
        'review_moderation': {
            'pending': pending_reviews,
            'unresolved_flags': unresolved_flags,
            'auto_rejected_this_week': auto_rejected,
        },
    })


@require_GET
@_staff_json
def supplier_health(request):
    """Supplier health status and reconciliation summary."""
    from apps.inventory.models import SupplierHealth

    suppliers = SupplierHealth.objects.all().order_by('supplier_name')

    health_data = [{
        'name': s.supplier_name,
        'status': s.status,
        'last_check': s.last_checked.isoformat() if s.last_checked else None,
        'success_rate': float(s.success_rate) if hasattr(s, 'success_rate') else None,
        'avg_response_ms': s.avg_response_ms if hasattr(s, 'avg_response_ms') else None,
    } for s in suppliers]

    # Reconciliation summary
    try:
        from apps.booking.supplier_reconciliation import SupplierReconciliationEngine
        recon_summary = SupplierReconciliationEngine.get_recon_summary(days=7)
    except Exception:
        recon_summary = []

    return JsonResponse({
        'suppliers': health_data,
        'reconciliation': [{
            'date': r['date'].isoformat(),
            'vertical': r['vertical'],
            'total': r['total'],
            'matched': r['matched'],
            'mismatched': r['mismatched'],
            'match_rate': r['match_rate'],
        } for r in recon_summary],
    })


@require_GET
@_staff_json
def top_properties(request):
    """Top properties by revenue, bookings, and rating."""
    from apps.booking.models import Booking
    from apps.hotels.models import Property

    days = int(request.GET.get('days', 30))
    start = timezone.now() - timedelta(days=days)

    top_by_revenue = list(
        Booking.objects.filter(
            created_at__gte=start,
            status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
        )
        .values('property__id', 'property__name', 'property__city')
        .annotate(
            total_revenue=Sum('gross_amount'),
            booking_count=Count('id'),
            avg_value=Avg('gross_amount'),
        )
        .order_by('-total_revenue')[:20]
    )

    top_by_rating = list(
        Property.objects.filter(
            is_active=True, review_count__gte=5,
        )
        .values('id', 'name', 'city', 'rating', 'review_count')
        .order_by('-rating', '-review_count')[:20]
    )

    return JsonResponse({
        'by_revenue': [{
            'id': r['property__id'],
            'name': r['property__name'],
            'city': r['property__city'],
            'revenue': float(r['total_revenue'] or 0),
            'bookings': r['booking_count'],
            'avg_value': float(r['avg_value'] or 0),
        } for r in top_by_revenue],
        'by_rating': [{
            'id': r['id'],
            'name': r['name'],
            'city': r['city'],
            'rating': float(r['rating']),
            'reviews': r['review_count'],
        } for r in top_by_rating],
    })


@require_GET
@_staff_json
def user_growth(request):
    """User registration trends."""
    from apps.accounts.models import User

    days = int(request.GET.get('days', 30))
    start = timezone.now() - timedelta(days=days)

    daily = list(
        User.objects.filter(date_joined__gte=start)
        .annotate(date=TruncDate('date_joined'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    total_active = User.objects.filter(is_active=True).count()
    with_bookings = User.objects.filter(
        bookings__status__in=['confirmed', 'checked_in', 'checked_out'],
    ).distinct().count()

    return JsonResponse({
        'daily_registrations': [{
            'date': r['date'].isoformat() if r['date'] else None,
            'count': r['count'],
        } for r in daily],
        'total_active_users': total_active,
        'users_with_bookings': with_bookings,
        'booking_rate': _pct(with_bookings, total_active),
    })


@require_GET
@_staff_json
def settlement_overview(request):
    """Settlement & payout status for finance team."""
    from apps.booking.models import Settlement
    from apps.wallet.models import OwnerPayout

    pending = Settlement.objects.filter(status__in=['draft', 'pending'])
    pending_amount = pending.aggregate(total=Sum('total_payable'))['total'] or 0

    recent_payouts = OwnerPayout.objects.order_by('-created_at')[:20]
    failed_payouts = OwnerPayout.objects.filter(status='failed').count()

    return JsonResponse({
        'pending_settlements': pending.count(),
        'pending_amount': float(pending_amount),
        'failed_payouts': failed_payouts,
        'recent_payouts': [{
            'id': p.id,
            'owner_id': p.owner_wallet_id,
            'amount': float(p.amount),
            'method': p.payout_method,
            'status': p.status,
            'created': p.created_at.isoformat(),
        } for p in recent_payouts],
    })


# ── URL Configuration ──

def get_urls():
    """Return URL patterns for ops dashboard API."""
    from django.urls import path
    return [
        path('overview/', platform_overview, name='ops_overview'),
        path('revenue/', revenue_breakdown, name='ops_revenue'),
        path('funnel/', booking_funnel, name='ops_funnel'),
        path('fraud/', fraud_dashboard, name='ops_fraud'),
        path('suppliers/', supplier_health, name='ops_suppliers'),
        path('properties/', top_properties, name='ops_properties'),
        path('users/', user_growth, name='ops_users'),
        path('settlements/', settlement_overview, name='ops_settlements'),
    ]


# ── Helpers ──

def _pct(numerator, denominator):
    if not denominator:
        return 0
    return round(numerator / denominator * 100, 1)


def _pct_change(old_val, new_val):
    if not old_val:
        return 100.0 if new_val else 0
    return round((float(new_val) - float(old_val)) / float(old_val) * 100, 1)
