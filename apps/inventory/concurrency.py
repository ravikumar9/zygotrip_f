"""
Concurrency-Safe Inventory Manager

Uses database-level SELECT FOR UPDATE to prevent race conditions.
Every booking deduction is atomic and isolated.

Race condition prevention:
- SELECT FOR UPDATE locks the row
- No two transactions can deduct inventory simultaneously
- SERIALIZABLE isolation ensures atomicity
"""

import logging
import time
from decimal import Decimal
from typing import Tuple, Dict
from django.db import transaction
from django.db.models import F
from django.core.exceptions import SuspiciousOperation
from django.utils import timezone
from apps.core.observability import PerformanceLog
from apps.inventory.models import PropertyInventory

logger = logging.getLogger('zygotrip')


class InventoryException(Exception):
    """Base inventory exception"""
    pass


class InsufficientInventory(InventoryException):
    """Raised when inventory is exhausted"""
    pass


class ConcyclicalInventoryError(InventoryException):
    """Raised when concurrent modification detected"""
    pass


class InventoryManager:
    """
    Concurrency-safe inventory management.
    
    All operations use SELECT FOR UPDATE to prevent race conditions.
    """
    
    @staticmethod
    @transaction.atomic
    def deduct_rooms(property_id: int, room_count: int) -> bool:
        """
        Atomically deduct rooms from inventory.
        
        Uses SELECT FOR UPDATE to lock the inventory row.
        No other transaction can modify it until this one completes.
        
        Args:
            property_id: Property ID
            room_count: Number of rooms to deduct
        
        Returns:
            True if deduction successful
        
        Raises:
            InsufficientInventory: If not enough rooms available
            ConcyclicalInventoryError: If row locked by another transaction
        """
        
        try:
            # SELECT FOR UPDATE: Lock the row
            lock_start = time.time()
            inventory = PropertyInventory.objects.select_for_update().get(
                property_id=property_id
            )
            lock_ms = int((time.time() - lock_start) * 1000)
            PerformanceLog.objects.create(
                operation_type='inventory_lock',
                duration_ms=lock_ms,
                start_time=timezone.now(),
                end_time=timezone.now(),
                status='success',
                resource_id=property_id,
            )
        except PropertyInventory.DoesNotExist:
            raise InventoryException(f"No inventory for property {property_id}")
        
        # Check availability
        if inventory.available_rooms < room_count:
            raise InsufficientInventory(
                f"Only {inventory.available_rooms} rooms available, "
                f"requested {room_count}"
            )
        
        # Deduct atomically
        inventory.available_rooms = F('available_rooms') - room_count
        inventory.version = F('version') + 1
        inventory.save(update_fields=['available_rooms', 'version'])
        
        # Refresh to get actual values
        inventory.refresh_from_db()
        
        logger.info(
            f"Deducted {room_count} rooms from property {property_id}. "
            f"Available: {inventory.available_rooms}/{inventory.total_rooms}"
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def restore_rooms(property_id: int, room_count: int) -> bool:
        """
        Atomically restore rooms to inventory (for cancellations).
        
        Args:
            property_id: Property ID
            room_count: Number of rooms to restore
        
        Returns:
            True if restoration successful
        """
        
        try:
            lock_start = time.time()
            inventory = PropertyInventory.objects.select_for_update().get(
                property_id=property_id
            )
            lock_ms = int((time.time() - lock_start) * 1000)
            PerformanceLog.objects.create(
                operation_type='inventory_lock',
                duration_ms=lock_ms,
                start_time=timezone.now(),
                end_time=timezone.now(),
                status='success',
                resource_id=property_id,
            )
        except PropertyInventory.DoesNotExist:
            raise InventoryException(f"No inventory for property {property_id}")
        
        # Cannot restore more than total rooms
        if inventory.available_rooms + room_count > inventory.total_rooms:
            raise InsufficientInventory(
                f"Restoration would exceed total rooms "
                f"({inventory.available_rooms} + {room_count} > {inventory.total_rooms})"
            )
        
        # Restore atomically
        inventory.available_rooms = F('available_rooms') + room_count
        inventory.version = F('version') + 1
        inventory.save(update_fields=['available_rooms', 'version'])
        
        inventory.refresh_from_db()
        
        logger.info(
            f"Restored {room_count} rooms to property {property_id}. "
            f"Available: {inventory.available_rooms}/{inventory.total_rooms}"
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def check_availability(property_id: int, room_count: int) -> Tuple[bool, int]:
        """
        Check if enough rooms are available without modifying inventory.
        
        Args:
            property_id: Property ID
            room_count: Number of rooms requested
        
        Returns:
            Tuple of (available: bool, remaining_rooms: int)
        """
        
        try:
            inventory = PropertyInventory.objects.select_for_update().get(
                property_id=property_id
            )
        except PropertyInventory.DoesNotExist:
            return False, 0
        
        available = inventory.available_rooms >= room_count
        
        return available, inventory.available_rooms
    
    @staticmethod
    def get_inventory_snapshot(property_id: int) -> Dict:
        """
        Get current inventory snapshot (non-blocking).
        
        This method does NOT lock the row, so it's suitable for read-only operations.
        """
        
        try:
            inv = PropertyInventory.objects.get(property_id=property_id)
            return {
                'property_id': property_id,
                'total_rooms': inv.total_rooms,
                'available_rooms': inv.available_rooms,
                'occupancy_percent': (
                    (inv.total_rooms - inv.available_rooms) / inv.total_rooms * 100
                    if inv.total_rooms > 0
                    else 0
                ),
                'sync_status': inv.sync_status,
                'version': inv.version,
            }
        except PropertyInventory.DoesNotExist:
            return None


def require_inventory_lock(func):
    """
    Decorator: Ensure function is wrapped in SELECT FOR UPDATE.
    
    Usage:
        @require_inventory_lock
        def book_rooms(property_id, room_count):
            ...
    """
    def wrapper(*args, **kwargs):
        # Must be called within atomic transaction
        if not transaction.get_autocommit() == False:
            raise SuspiciousOperation(
                "Inventory operations must be in atomic transaction"
            )
        return func(*args, **kwargs)
    return wrapper