"""REMOVED — Use apps.pricing.pricing_service.calculate() for ALL pricing."""
import warnings
warnings.warn('core_engine removed. Use apps.pricing.pricing_service.calculate.', DeprecationWarning, stacklevel=2)
from apps.pricing.pricing_service import calculate as calculate_price  # noqa: F401
