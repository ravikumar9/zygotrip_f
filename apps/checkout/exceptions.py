"""Checkout domain exceptions."""


class CheckoutException(Exception):
    """Base exception for checkout domain."""
    pass


class SessionExpiredException(CheckoutException):
    """Checkout session has expired."""
    pass


class SessionStateError(CheckoutException):
    """Invalid session state transition."""
    pass


class PriceChangedException(CheckoutException):
    """Price changed during revalidation."""

    def __init__(self, old_price, new_price, message=None):
        self.old_price = old_price
        self.new_price = new_price
        super().__init__(message or f"Price changed: ₹{old_price} → ₹{new_price}")


class InventoryTokenExpiredError(CheckoutException):
    """Inventory token has expired or is not active."""
    pass


class PaymentIntentError(CheckoutException):
    """Error creating or processing payment intent."""
    pass


class RiskBlockedException(CheckoutException):
    """Booking blocked by fraud risk assessment."""

    def __init__(self, risk_score, risk_level, message=None):
        self.risk_score = risk_score
        self.risk_level = risk_level
        super().__init__(message or f"Blocked: risk {risk_score} ({risk_level})")
