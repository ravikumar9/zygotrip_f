"""Selectors for apps.payments module."""

from dataclasses import dataclass

from apps.booking.models import Booking


class InvoiceList(list):
    @property
    def count(self):
        return len(self)


@dataclass
class InvoiceDTO:
    booking: Booking
    status: str
    issued_at: object
	
    @property
    def uuid(self):
        return self.booking.uuid

    @property
    def total_amount(self):
        return self.booking.total_amount


def invoices_for_user(user):
    """
    Get all invoices for a given user
    
    Args:
        user: User instance
        
    Returns:
        QuerySet of invoices
    """
    if not user or not getattr(user, "is_authenticated", False):
        return InvoiceList()
    bookings = (
        Booking.objects.filter(user=user, status=Booking.STATUS_CONFIRMED, is_active=True)
        .select_related("property", "price_breakdown")
        .order_by("-created_at")
    )
    return InvoiceList(
        InvoiceDTO(
            booking=booking,
            status="paid",
            issued_at=booking.updated_at or booking.created_at,
        )
        for booking in bookings
    )
