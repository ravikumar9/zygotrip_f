# core/validators.py - Global validation utilities

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from typing import Any, Tuple, Dict
import logging

logger = logging.getLogger('zygotrip')


def validate_future_date(value):
    """
    Validates that a date is not in the past.
    Must be used at model level, not just in forms.
    Allows None values for optional date fields.
    """
    if value is None:
        return  # Skip validation for None/blank values
    if value < timezone.localdate():
        raise ValidationError("Past dates are not allowed. Please select today or a future date.")


# ============================================================================
# PRICING VALIDATION FIREWALL
# ============================================================================

class PricingValidationError(ValidationError):
    """Base pricing validation error"""
    pass


class FraudPrice(PricingValidationError):
    """Price indicates fraudulent data"""
    pass


class SuspiciousPrice(PricingValidationError):
    """Price is unusual but not necessarily fraudulent"""
    pass


class StaleData(PricingValidationError):
    """Data is too old to use"""
    pass


class ValidationConfig:
    """Centralized validation configuration"""
    
    # Price bounds
    MIN_PRICE = Decimal('100')
    MAX_PRICE = Decimal('1000000')
    
    # Data freshness
    MAX_AGE_MINUTES = 60  # 1 hour
    
    # Demand and confidence bounds
    MIN_DEMAND_SCORE = 0
    MAX_DEMAND_SCORE = 100
    MIN_CONFIDENCE = Decimal('0.0')
    MAX_CONFIDENCE = Decimal('1.0')


class InputValidator:
    """Validates all inputs to pricing engine"""
    
    config = ValidationConfig()
    
    @staticmethod
    def validate_price(price: Any, context: str = "price", strict_precision: bool = False) -> Decimal:
        """
        Validate and convert price to Decimal.
        
        Args:
            price: Price value (int, float, Decimal, str)
            context: Context for error message
        
        Returns:
            Validated Decimal price
        
        Raises:
            FraudPrice: If price is invalid
            SuspiciousPrice: If price is unusual
        """
        
        try:
            price = Decimal(str(price))
        except Exception as e:
            raise FraudPrice(f"Invalid price format: {price} ({e})")
        
        # Enforce 2-decimal precision (round or reject)
        quantized = price.quantize(Decimal('0.01'))
        if quantized != price:
            if strict_precision:
                raise SuspiciousPrice(
                    f"{context}: Price has more than 2 decimal places: {price}"
                )
            logger.warning(f"{context}: Price precision rounded: {price} -> {quantized}")
            price = quantized

        # Rule 1: Must be positive
        if price <= 0:
            raise FraudPrice(f"{context}: Price must be positive, got {price}")
        
        # Rule 2: Minimum viable price
        if price < InputValidator.config.MIN_PRICE:
            raise SuspiciousPrice(
                f"{context}: Price ₹{price} below minimum ₹{InputValidator.config.MIN_PRICE} "
                f"(possible data entry error)"
            )
        
        # Rule 3: Maximum sensible price
        if price > InputValidator.config.MAX_PRICE:
            raise SuspiciousPrice(
                f"{context}: Price ₹{price} above maximum ₹{InputValidator.config.MAX_PRICE} "
                f"(possible data entry error)"
            )
        
        return price
    
    @staticmethod
    def validate_demand_score(score: Any) -> int:
        """
        Validate demand score (0-100 scale).
        
        Args:
            score: Demand score value
        
        Returns:
            Validated integer score
        
        Raises:
            ValidationError: If invalid
        """
        
        try:
            score = int(score)
        except Exception as e:
            raise PricingValidationError(f"Invalid demand score format: {score} ({e})")
        
        if not (InputValidator.config.MIN_DEMAND_SCORE <= score <= InputValidator.config.MAX_DEMAND_SCORE):
            raise PricingValidationError(
                f"Demand score must be 0-100, got {score}"
            )
        
        return score
    
    @staticmethod
    def validate_confidence_score(score: Any) -> Decimal:
        """
        Validate confidence score (0.0-1.0 scale).
        
        Args:
            score: Confidence score value
        
        Returns:
            Validated Decimal score
        
        Raises:
            PricingValidationError: If invalid
        """
        
        try:
            score = Decimal(str(score))
        except Exception as e:
            raise PricingValidationError(f"Invalid confidence score format: {score} ({e})")
        
        if not (InputValidator.config.MIN_CONFIDENCE <= score <= InputValidator.config.MAX_CONFIDENCE):
            raise PricingValidationError(
                f"Confidence score must be 0.0-1.0, got {score}"
            )
        
        return score
    
    @staticmethod
    def validate_competitor_price(
        price: Any,
        freshness_minutes: int
    ) -> Tuple[Decimal, bool]:
        """
        Validate competitor price and freshness.
        
        Args:
            price: Competitor price
            freshness_minutes: Age of price in minutes
        
        Returns:
            Tuple of (validated_price, is_fresh)
        
        Raises:
            StaleData: If data is too old
        """
        
        # Validate price
        price = InputValidator.validate_price(
            price,
            context="competitor_price"
        )
        
        # Check freshness
        is_fresh = freshness_minutes <= InputValidator.config.MAX_AGE_MINUTES
        
        if not is_fresh:
            logger.warning(
                f"Competitor price data is {freshness_minutes} minutes old "
                f"(max allowed: {InputValidator.config.MAX_AGE_MINUTES} min). "
                f"Ignoring stale data."
            )
        
        return price, is_fresh
    
    @staticmethod
    def validate_supplier_price(
        base_price: Decimal,
        final_price: Decimal,
        max_change_percent: int = 70
    ) -> bool:
        """
        Validate that price change is within acceptable bounds.
        
        Prevents:
        - Price drops > 70% in 5 minutes (fraud signal)
        - Price rises > 200% in 5 minutes (fraud signal)
        
        Args:
            base_price: Previous price
            final_price: New price
            max_change_percent: Max allowed % change
        
        Returns:
            True if change is valid
        
        Raises:
            SuspiciousPrice: If change exceeds threshold
        """
        
        if base_price <= 0:
            return True  # Cannot calculate change from zero base
        
        change_percent = abs((final_price - base_price) / base_price * 100)
        
        if change_percent > max_change_percent:
            raise SuspiciousPrice(
                f"Price change {change_percent:.1f}% exceeds threshold {max_change_percent}% "
                f"({base_price} → {final_price})"
            )
        
        return True

    @staticmethod
    def validate_currency(currency_code: Any) -> str:
        """
        Validate currency code matches system configuration.
        """
        if not currency_code:
            raise ValidationError("Currency code is required")
        if str(currency_code).upper() != settings.CURRENCY_CODE:
            raise ValidationError(
                f"Currency mismatch: {currency_code} (expected {settings.CURRENCY_CODE})"
            )
        return str(currency_code).upper()

    @staticmethod
    def normalize_timezone(dt_value: Any):
        """
        Normalize datetime to system timezone (timezone-aware).
        """
        if dt_value is None:
            return None
        if timezone.is_naive(dt_value):
            return timezone.make_aware(dt_value, timezone.get_current_timezone())
        return timezone.localtime(dt_value)

    @staticmethod
    def validate_schema(payload: Dict[str, Any], required_fields: Dict[str, type]) -> Dict[str, Any]:
        """
        Validate required fields and data types for payloads.
        """
        missing = [key for key in required_fields.keys() if key not in payload]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")

        for field, expected_type in required_fields.items():
            value = payload.get(field)
            if value is None:
                raise ValidationError(f"Field '{field}' cannot be null")
            if expected_type and not isinstance(value, expected_type):
                raise ValidationError(
                    f"Field '{field}' must be {expected_type.__name__}, got {type(value).__name__}"
                )

        return payload


def validate_before_pricing(**kwargs) -> Dict:
    """
    Validate all inputs before sending to pricing engine.
    
    Usage:
        validated = validate_before_pricing(
            base_price=1000,
            demand_score=75,
            competitor_price=950,
            competitor_age_minutes=30
        )
    """
    
    validated = {}
    
    # Validate base price
    if 'base_price' in kwargs:
        validated['base_price'] = InputValidator.validate_price(
            kwargs['base_price'],
            context="base_price"
        )
    
    # Validate demand score
    if 'demand_score' in kwargs:
        validated['demand_score'] = InputValidator.validate_demand_score(
            kwargs['demand_score']
        )
    
    # Validate competitor price and freshness
    if 'competitor_price' in kwargs and 'competitor_age_minutes' in kwargs:
        price, is_fresh = InputValidator.validate_competitor_price(
            kwargs['competitor_price'],
            kwargs['competitor_age_minutes']
        )
        if is_fresh:
            validated['competitor_price'] = price
        # else: silently ignore stale competitor data

    # Validate currency
    if 'currency_code' in kwargs:
        validated['currency_code'] = InputValidator.validate_currency(
            kwargs['currency_code']
        )
    
    return validated