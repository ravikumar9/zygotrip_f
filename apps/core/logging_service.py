# core/logging_service.py - Structured logging for critical operations

import json
import logging
from django.utils import timezone
from datetime import datetime


# Get logger for critical operations
logger = logging.getLogger('zygotrip.critical')


class OperationLogger:
    """Log critical operations with full context"""
    
    # Operation types
    OP_BOOKING_CREATED = 'booking_created'
    OP_BOOKING_FAILED = 'booking_failed'
    OP_PAYMENT_INITIATED = 'payment_initiated'
    OP_PAYMENT_FAILED = 'payment_failed'
    OP_COUPON_APPLIED = 'coupon_applied'
    OP_COUPON_REJECTED = 'coupon_rejected'
    OP_INVENTORY_SYNC = 'inventory_sync'
    OP_PRICE_CALCULATED = 'price_calculated'
    
    @staticmethod
    def log_booking_failure(user_id, service_type, reason, details=None):
        """
        Log booking failure with full context.
        
        Args:
            user_id: User ID
            service_type: 'hotel', 'bus', 'cab', 'package'
            reason: Failure reason (string)
            details: Additional details (dict)
        """
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_BOOKING_FAILED,
            'user_id': user_id,
            'service_type': service_type,
            'reason': reason,
            'details': details or {},
        }
        
        logger.error(
            f"BOOKING_FAILED: {service_type}",
            extra=log_entry,
            exc_info=True
        )
        
        # Store in database for auditing
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_booking_success(user_id, booking_id, service_type, total_amount):
        """Log successful booking creation"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_BOOKING_CREATED,
            'user_id': user_id,
            'booking_id': booking_id,
            'service_type': service_type,
            'amount': str(total_amount),
        }
        
        logger.info(
            f"BOOKING_CREATED: {service_type}",
            extra=log_entry
        )
        
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_payment_failure(user_id, booking_id, reason, error_code=None):
        """Log payment failure"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_PAYMENT_FAILED,
            'user_id': user_id,
            'booking_id': booking_id,
            'reason': reason,
            'error_code': error_code,
        }
        
        logger.error(
            f"PAYMENT_FAILED: Booking {booking_id}",
            extra=log_entry,
            exc_info=True
        )
        
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_payment_success(user_id, booking_id, amount, gateway='razorpay'):
        """Log successful payment"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_PAYMENT_INITIATED,
            'user_id': user_id,
            'booking_id': booking_id,
            'amount': str(amount),
            'gateway': gateway,
        }
        
        logger.info(
            f"PAYMENT_SUCCESS: Booking {booking_id}",
            extra=log_entry
        )
        
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_coupon_rejection(user_id, coupon_code, reason):
        """Log rejected coupon application"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_COUPON_REJECTED,
            'user_id': user_id,
            'coupon_code': coupon_code,
            'reason': reason,
        }
        
        logger.warning(
            f"COUPON_REJECTED: {coupon_code}",
            extra=log_entry
        )
        
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_coupon_applied(user_id, booking_id, coupon_code, discount_amount):
        """Log successful coupon application"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_COUPON_APPLIED,
            'user_id': user_id,
            'booking_id': booking_id,
            'coupon_code': coupon_code,
            'discount': str(discount_amount),
        }
        
        logger.info(
            f"COUPON_APPLIED: {coupon_code}",
            extra=log_entry
        )
        
        _store_operation_log(log_entry)
    
    @staticmethod
    def log_inventory_sync(supplier_name, status, synced_count, error=None):
        """Log inventory sync operation"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'operation': OperationLogger.OP_INVENTORY_SYNC,
            'supplier': supplier_name,
            'status': status,  # 'success' or 'failed'
            'synced_count': synced_count,
            'error': error,
        }
        
        level = logging.INFO if status == 'success' else logging.ERROR
        logger.log(
            level,
            f"INVENTORY_SYNC: {supplier_name}",
            extra=log_entry
        )
        
        _store_operation_log(log_entry)


def _store_operation_log(log_entry):
    """Store operation log in database for audit trail"""
    try:
        from apps.core.models import OperationLog
        OperationLog.objects.create(
            operation_type=log_entry['operation'],
            status='success' if 'failed' not in log_entry['operation'] else 'failed',
            details=json.dumps(log_entry),
            timestamp=timezone.now(),
        )
    except Exception as e:
        # Fail silently - don't let logging errors break the application
        logger.exception(f"Failed to store operation log: {e}")