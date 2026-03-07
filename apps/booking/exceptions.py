"""Custom exceptions for booking domain."""


class BookingException(Exception):
    """Base exception for booking domain."""
    pass


class InventoryUnavailableException(BookingException):
    """Raised when inventory is insufficient for booking."""
    pass


class BookingStateTransitionError(BookingException):
    """Raised when attempting illegal booking status transition."""
    pass


class HoldExpiredException(BookingException):
    """Raised when attempting operation on expired hold."""
    pass


class RefundCalculationError(BookingException):
    """Raised when refund calculation fails."""
    pass
