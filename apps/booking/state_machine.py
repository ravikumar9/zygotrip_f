"""
Booking state machine service - HARDENED enforcement.

PHASE 1, PROMPT 3: Prevent uncontrolled state mutations.

Rules:
1. All status transitions must go through transition_booking_status()
2. No direct .save() of status field
3. Only valid transitions allowed
4. Logged in status history
"""
from django.db import transaction, models
from django.utils import timezone
from .models import Booking, BookingStatusHistory
from .exceptions import BookingStateTransitionError


class BookingStateMachine:
    """Central state machine enforcement."""
    
    @staticmethod
    def transition(booking, new_status, note='', user=None):
        """
        Transition booking with full validation and audit trail.
        
        Args:
            booking: Booking model instance
            new_status: Target status code from Booking.STATUS_CHOICES
            note: Human-readable reason for transition (logged)
            user: User performing transition (for audit)
        
        Returns:
            Updated Booking instance
            
        Raises:
            BookingStateTransitionError: If transition is invalid
        """
        if not _is_valid_status(new_status):
            raise BookingStateTransitionError(
                f'Invalid status: {new_status}'
            )
        
        current_status = booking.status
        valid_next_states = Booking.VALID_TRANSITIONS.get(current_status, [])
        
        if new_status not in valid_next_states:
            raise BookingStateTransitionError(
                f'Cannot transition {current_status} → {new_status}. '
                f'Valid: {valid_next_states}'
            )
        
        with transaction.atomic():
            # Refresh with row lock to prevent concurrent transitions
            booking = Booking.objects.select_for_update().get(pk=booking.pk)
            
            # Final check (in case another process changed it)
            if booking.status != current_status:
                raise BookingStateTransitionError(
                    f'Booking status changed by another process. '
                    f'Expected: {current_status}, Got: {booking.status}'
                )
            
            # Perform transition
            booking.status = new_status
            booking.save(update_fields=['status', 'updated_at'])
            
            # Record audit trail
            BookingStatusHistory.objects.create(
                booking=booking,
                status=new_status,
                note=note,
            )
        
        return booking
    
    @staticmethod
    def can_transition(booking, target_status):
        """Check if transition is allowed without performing it."""
        if not _is_valid_status(target_status):
            return False
        
        valid_next = Booking.VALID_TRANSITIONS.get(booking.status, [])
        return target_status in valid_next


def _is_valid_status(status):
    """Validate status against choices."""
    valid_statuses = [choice[0] for choice in Booking.STATUS_CHOICES]
    return status in valid_statuses
