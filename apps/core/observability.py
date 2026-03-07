"""
Observability Dashboard System
Real metrics collection: error rates, bookings/min, failures/min, inventory mismatches.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import models
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.apps import apps
from django.utils.module_loading import import_string
from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip')


class SystemMetrics(TimeStampedModel):
    """Store system-wide metrics snapshots"""
    
    # Booking metrics
    total_bookings = models.PositiveIntegerField(default=0)
    confirmed_bookings = models.PositiveIntegerField(default=0)
    failed_bookings = models.PositiveIntegerField(default=0)
    pending_bookings = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    bookings_per_minute = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    failures_per_minute = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    error_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Inventory metrics
    inventory_mismatches = models.PositiveIntegerField(default=0)
    rooms_available = models.PositiveIntegerField(default=0)
    hotels_with_issues = models.PositiveIntegerField(default=0)
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    revenue_per_booking = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # System health
    average_response_time_ms = models.PositiveIntegerField(default=0)
    cache_hit_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Timestamp
    snapshot_time = models.DateTimeField(db_index=True, auto_now_add=True)
    
    class Meta:
        ordering = ['-snapshot_time']
        indexes = [models.Index(fields=['-snapshot_time'])]
    
    def __str__(self):
        return f"Metrics @ {self.snapshot_time.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def collect_metrics(cls) -> Dict:
        """Collect current system metrics"""
        from apps.core.models import OperationLog
        Booking = apps.get_model('booking', 'Booking')
        InventorySource = import_string('apps.hotels.inventory.InventorySource')
        
        # Booking metrics
        all_bookings = Booking.objects.all()
        total_bookings = all_bookings.count()
        confirmed = all_bookings.filter(status='confirmed').count()
        failed = all_bookings.filter(status='failed').count()
        pending = all_bookings.filter(status='pending').count()
        
        # Revenue
        total_revenue = all_bookings.aggregate(Sum('total_price'))['total_price__sum'] or 0
        avg_revenue = total_revenue / total_bookings if total_bookings > 0 else 0
        
        # Failure rate (last hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_ops = OperationLog.objects.filter(timestamp__gte=one_hour_ago)
        total_ops = recent_ops.count()
        failed_ops = recent_ops.filter(status='failed').count()
        error_rate = (failed_ops / total_ops * 100) if total_ops > 0 else 0
        
        bookings_per_min = (confirmed / 60) if confirmed > 0 else 0
        failures_per_min = (failed / 60) if failed > 0 else 0
        
        # Inventory metrics
        mismatches = InventorySource.objects.filter(sync_status='failed').count()
        total_rooms = InventorySource.objects.aggregate(Sum('available_rooms'))['available_rooms__sum'] or 0
        hotels_failed = InventorySource.objects.filter(sync_status='failed').count()
        
        metrics = {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed,
            'failed_bookings': failed,
            'pending_bookings': pending,
            'bookings_per_minute': Decimal(str(round(bookings_per_min, 2))),
            'failures_per_minute': Decimal(str(round(failures_per_min, 2))),
            'error_rate_percent': Decimal(str(round(error_rate, 2))),
            'inventory_mismatches': mismatches,
            'rooms_available': total_rooms,
            'hotels_with_issues': hotels_failed,
            'total_revenue': Decimal(str(total_revenue)),
            'revenue_per_booking': Decimal(str(round(float(avg_revenue), 2))),
        }
        
        return metrics
    
    @classmethod
    def create_snapshot(cls) -> 'SystemMetrics':
        """Create a metrics snapshot"""
        metrics = cls.collect_metrics()
        return cls.objects.create(**metrics)
    
    @classmethod
    def get_latest(cls) -> Optional['SystemMetrics']:
        """Get latest metrics snapshot"""
        return cls.objects.first()
    
    @classmethod
    def get_trend(cls, hours: int = 24) -> List[Dict]:
        """Get metrics trend over time"""
        cutoff = timezone.now() - timedelta(hours=hours)
        snapshots = cls.objects.filter(snapshot_time__gte=cutoff).order_by('snapshot_time').values(
            'snapshot_time',
            'bookings_per_minute',
            'failures_per_minute',
            'error_rate_percent',
            'total_bookings',
        )
        return list(snapshots)


class InventoryHealthCheck(TimeStampedModel):
    """Track inventory health issues"""
    
    ISSUE_TYPES = [
        ('mismatch', 'Inventory Mismatch'),
        ('sync_failed', 'Sync Failed'),
        ('price_anomaly', 'Price Anomaly'),
        ('availability_zero', 'Zero Availability'),
        ('stale_data', 'Stale Data'),
    ]
    
    hotel_id = models.PositiveIntegerField(db_index=True)
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPES)
    
    description = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium'
    )
    
    # Resolution tracking
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['hotel_id', 'is_resolved']),
            models.Index(fields=['severity', 'is_resolved']),
        ]
        ordering = ['-detected_at']
    
    def __str__(self):
        return f"{self.get_issue_type_display()} - Hotel {self.hotel_id} ({self.get_severity_display()})"
    
    def resolve(self):
        """Mark issue as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        
        if self.detected_at:
            delta = self.resolved_at - self.detected_at
            self.resolution_time_minutes = int(delta.total_seconds() / 60)
        
        self.save(update_fields=['is_resolved', 'resolved_at', 'resolution_time_minutes'])
        logger.info(f"Inventory issue resolved: {self}")


class PerformanceLog(TimeStampedModel):
    """Log performance metrics for operations"""
    
    OPERATION_TYPES = [
        ('booking_create', 'Booking Creation'),
        ('search', 'Search'),
        ('payment', 'Payment'),
        ('inventory_sync', 'Inventory Sync'),
        ('price_calculation', 'Price Calculation'),
        ('inventory_lock', 'Inventory Lock'),
    ]
    
    operation_type = models.CharField(max_length=50, choices=OPERATION_TYPES, db_index=True)
    
    # Timing
    duration_ms = models.PositiveIntegerField()  # Milliseconds
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('success', 'Success'), ('timeout', 'Timeout'), ('error', 'Error')],
        default='success'
    )
    
    error_message = models.TextField(blank=True)
    
    # Context
    user_id = models.PositiveIntegerField(null=True, blank=True)
    resource_id = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['operation_type', 'start_time']),
            models.Index(fields=['status', 'start_time']),
        ]
        ordering = ['-start_time']
    
    def __str__(self):
        status_emoji = '✓' if self.status == 'success' else '✗'
        return f"{status_emoji} {self.get_operation_type_display()} - {self.duration_ms}ms"
    
    @classmethod
    def get_performance_stats(cls, operation_type: str, hours: int = 1) -> Dict:
        """Get performance statistics for operation"""
        cutoff = timezone.now() - timedelta(hours=hours)
        
        stats = cls.objects.filter(
            operation_type=operation_type,
            start_time__gte=cutoff
        ).aggregate(
            count=Count('id'),
            avg_duration=Avg('duration_ms'),
            max_duration=Count('duration_ms'),
            error_count=Count('id', filter=Q(status='error')),
            timeout_count=Count('id', filter=Q(status='timeout')),
        )
        
        total = stats['count'] or 1
        error_rate = ((stats['error_count'] or 0) / total * 100)
        
        return {
            'operation': operation_type,
            'total_operations': stats['count'],
            'average_duration_ms': stats['avg_duration'],
            'max_duration_ms': stats['max_duration'],
            'error_count': stats['error_count'],
            'error_rate_percent': round(error_rate, 2),
            'timeout_count': stats['timeout_count'],
        }


class MetricsCollector:
    """Real-time metrics collection service"""
    
    def __init__(self):
        self.logger = logging.getLogger('zygotrip')
    
    def start_operation_timer(self, operation_type: str) -> Dict:
        """Start timing an operation"""
        return {
            'operation_type': operation_type,
            'start_time': timezone.now(),
            'start_ms': timezone.now().timestamp() * 1000,
        }
    
    def end_operation_timer(self, timer: Dict, status: str = 'success', error_message: str = '') -> int:
        """End operation timer and log metrics"""
        end_time = timezone.now()
        duration_ms = int((end_time.timestamp() * 1000) - timer['start_ms'])
        
        try:
            PerformanceLog.objects.create(
                operation_type=timer['operation_type'],
                duration_ms=duration_ms,
                start_time=timer['start_time'],
                end_time=end_time,
                status=status,
                error_message=error_message[:500],
            )
        except Exception as e:
            self.logger.warning(f"Failed to log performance metric: {str(e)}")
        
        return duration_ms
    
    def log_operation(self, operation_type: str, duration_ms: int, status: str = 'success'):
        """Log operation performance"""
        try:
            PerformanceLog.objects.create(
                operation_type=operation_type,
                duration_ms=duration_ms,
                start_time=timezone.now() - timedelta(milliseconds=duration_ms),
                end_time=timezone.now(),
                status=status,
            )
        except Exception as e:
            self.logger.warning(f"Failed to log metric: {str(e)}")
    
    def check_inventory_health(self) -> List[Dict]:
        """Check health of all inventory sources"""
        InventorySource = import_string('apps.hotels.inventory.InventorySource')
        
        issues = []
        
        for inv in InventorySource.objects.all():
            # Check for sync failures
            if inv.sync_status == 'failed':
                try:
                    InventoryHealthCheck.objects.get_or_create(
                        hotel_id=inv.property_id,
                        issue_type='sync_failed',
                        is_resolved=False,
                        defaults={
                            'description': f"Failed to sync inventory from {inv.source_type}",
                            'severity': 'high',
                        }
                    )
                except:
                    pass
            
            # Check for zero availability
            if inv.available_rooms == 0 and inv.supplier_inventory > 0:
                issues.append({
                    'hotel_id': inv.property_id,
                    'type': 'availability_zero',
                    'description': f'Zero availability despite supplier having {inv.supplier_inventory} rooms',
                })
            
            # Check for stale data (not synced in 24 hours)
            if inv.last_synced_at:
                age = timezone.now() - inv.last_synced_at
                if age > timedelta(hours=24):
                    issues.append({
                        'hotel_id': inv.property_id,
                        'type': 'stale_data',
                        'description': f'Data not synced in {int(age.total_seconds() / 3600)} hours',
                    })
        
        return issues


@method_decorator(staff_member_required, name='dispatch')
class DashboardView(TemplateView):
    """Admin dashboard view"""
    
    template_name = 'admin/metrics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get latest metrics
        latest_metrics = SystemMetrics.get_latest()
        context['metrics'] = latest_metrics
        
        # Get trend data
        context['trend'] = SystemMetrics.get_trend(hours=24)
        
        # Get unresolved inventory issues
        context['inventory_issues'] = InventoryHealthCheck.objects.filter(
            is_resolved=False
        ).order_by('-detected_at')[:10]
        
        # Get performance stats
        context['performance'] = {
            'booking_create': PerformanceLog.get_performance_stats('booking_create', hours=1),
            'search': PerformanceLog.get_performance_stats('search', hours=1),
            'payment': PerformanceLog.get_performance_stats('payment', hours=1),
        }
        
        # Get recent errors
        from apps.core.models import OperationLog
        context['recent_errors'] = OperationLog.objects.filter(
            status='failed'
        ).order_by('-timestamp')[:10]
        
        return context