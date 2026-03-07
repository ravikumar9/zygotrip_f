# Channel Manager Inventory System for Hotels and Buses

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel


class InventorySource(TimeStampedModel):
    """Track inventory sources (Internal vs ChannelManager)"""
    
    SOURCE_INTERNAL = 'internal'
    SOURCE_BOOKING_COM = 'booking_com'
    SOURCE_AIRBNB = 'airbnb'
    SOURCE_EXPEDIA = 'expedia'
    SOURCE_AGODA = 'agoda'
    
    SOURCE_CHOICES = [
        (SOURCE_INTERNAL, 'Internal'),
        (SOURCE_BOOKING_COM, 'Booking.com'),
        (SOURCE_AIRBNB, 'Airbnb'),
        (SOURCE_EXPEDIA, 'Expedia'),
        (SOURCE_AGODA, 'Agoda'),
    ]
    
    SYNC_STATUS_PENDING = 'pending'
    SYNC_STATUS_SYNCED = 'synced'
    SYNC_STATUS_FAILED = 'failed'
    
    SYNC_STATUS_CHOICES = [
        (SYNC_STATUS_PENDING, 'Pending'),
        (SYNC_STATUS_SYNCED, 'Synced'),
        (SYNC_STATUS_FAILED, 'Failed'),
    ]
    
    # Property reference
    property = models.OneToOneField(
        'Property',
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    
    # Channel information
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_INTERNAL)
    external_inventory_id = models.CharField(max_length=100, blank=True, help_text="ID from external channel manager")
    external_supplier_id = models.CharField(max_length=100, blank=True)
    
    # Pricing
    supplier_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    internal_price = models.DecimalField(max_digits=12, decimal_places=2)
    margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    
    # Inventory
    supplier_inventory = models.PositiveIntegerField(default=0, help_text="Rooms available from supplier")
    available_rooms = models.PositiveIntegerField(default=0, help_text="Rooms available for booking")
    blocked_rooms = models.PositiveIntegerField(default=0, help_text="Blocked by owner")
    
    # Sync metadata
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default=SYNC_STATUS_PENDING
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, help_text="Last sync error message")
    
    class Meta:
        indexes = [
            models.Index(fields=['source_type', 'sync_status']),
            models.Index(fields=['last_synced_at']),
            models.Index(fields=['next_sync_at']),
        ]
    
    def get_price_to_display(self):
        """Return correct price based on source"""
        if self.source_type != self.SOURCE_INTERNAL and self.supplier_price:
            # Apply margin to supplier price
            margin_multiplier = 1 + (self.margin_percent / Decimal('100'))
            return self.supplier_price * margin_multiplier
        return self.internal_price
    
    def mark_sync_success(self):
        """Mark as successfully synced"""
        self.sync_status = self.SYNC_STATUS_SYNCED
        self.last_synced_at = timezone.now()
        self.last_sync_error = ''
        self.next_sync_at = timezone.now() + timezone.timedelta(minutes=15)
        self.save(update_fields=['sync_status', 'last_synced_at', 'next_sync_at', 'last_sync_error'])
    
    def mark_sync_failed(self, error_message):
        """Mark as failed with error message"""
        self.sync_status = self.SYNC_STATUS_FAILED
        self.last_sync_error = error_message[:500]  # Truncate to 500 chars
        self.next_sync_at = timezone.now() + timezone.timedelta(minutes=5)  # Retry sooner
        self.save(update_fields=['sync_status', 'last_sync_error', 'next_sync_at'])
    
    def needs_sync(self):
        """Check if inventory needs syncing"""
        if self.source_type == self.SOURCE_INTERNAL:
            return False
        
        if not self.next_sync_at:
            return True
        
        return timezone.now() >= self.next_sync_at
    
    def __str__(self):
        return f"{self.property.name} - {self.get_source_type_display()}"


class ExternalInventoryLog(TimeStampedModel):
    """Audit trail for inventory syncs"""
    
    inventory = models.ForeignKey(InventorySource, on_delete=models.CASCADE, related_name='sync_logs')
    
    status = models.CharField(max_length=20, choices=InventorySource.SYNC_STATUS_CHOICES)
    synced_at = models.DateTimeField(auto_now_add=True)
    
    # Sync details
    rooms_synced = models.PositiveIntegerField(default=0)
    prices_synced = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    # Response data (for debugging)
    raw_response = models.TextField(blank=True, help_text="Raw API response (first 2000 chars)")
    
    class Meta:
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['inventory', 'status']),
            models.Index(fields=['synced_at']),
        ]
    
    def __str__(self):
        return f"{self.inventory} - {self.get_status_display()} @ {self.synced_at}"



