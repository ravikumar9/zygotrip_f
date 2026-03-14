"""
Multi-currency exchange rate service.

Provides:
  1. Fetch exchange rates from external API
  2. Cache rates with configurable TTL
  3. Convert amounts between currencies
  4. Detect user's preferred currency from IP/locale

Supported API providers:
  - ExchangeRate-API (v6) — default
  - Fallback to static rates when API unavailable
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("zygotrip")

CACHE_KEY_RATES = "currency:rates:{base}"
CACHE_KEY_USER_CURRENCY = "currency:user:{identifier}"

# Static fallback rates (INR-based, approximate)
FALLBACK_RATES = {
    "INR": Decimal("1.0"),
    "USD": Decimal("0.0119"),
    "EUR": Decimal("0.0109"),
    "GBP": Decimal("0.0094"),
    "AED": Decimal("0.0438"),
    "SGD": Decimal("0.0160"),
    "THB": Decimal("0.4100"),
    "MYR": Decimal("0.0530"),
    "AUD": Decimal("0.0184"),
    "CAD": Decimal("0.0163"),
    "JPY": Decimal("1.7900"),
    "KRW": Decimal("16.30"),
    "SAR": Decimal("0.0448"),
    "QAR": Decimal("0.0435"),
    "BDT": Decimal("1.4300"),
    "LKR": Decimal("3.5600"),
    "NPR": Decimal("1.6000"),
}

CURRENCY_SYMBOLS = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "د.إ",
    "SGD": "S$", "THB": "฿", "MYR": "RM", "AUD": "A$", "CAD": "C$",
    "JPY": "¥", "KRW": "₩", "SAR": "﷼", "QAR": "﷼", "BDT": "৳",
    "LKR": "Rs", "NPR": "रू",
}

CURRENCY_NAMES = {
    "INR": "Indian Rupee", "USD": "US Dollar", "EUR": "Euro",
    "GBP": "British Pound", "AED": "UAE Dirham", "SGD": "Singapore Dollar",
    "THB": "Thai Baht", "MYR": "Malaysian Ringgit", "AUD": "Australian Dollar",
    "CAD": "Canadian Dollar", "JPY": "Japanese Yen", "KRW": "Korean Won",
    "SAR": "Saudi Riyal", "QAR": "Qatari Riyal", "BDT": "Bangladeshi Taka",
    "LKR": "Sri Lankan Rupee", "NPR": "Nepalese Rupee",
}

# Locale → currency mapping
LOCALE_CURRENCY_MAP = {
    "en-US": "USD", "en-GB": "GBP", "en-AU": "AUD", "en-CA": "CAD",
    "en-SG": "SGD", "en-IN": "INR", "ja-JP": "JPY", "ko-KR": "KRW",
    "th-TH": "THB", "ms-MY": "MYR", "ar-AE": "AED", "ar-SA": "SAR",
    "ar-QA": "QAR", "bn-BD": "BDT", "si-LK": "LKR", "ne-NP": "NPR",
    "fr-FR": "EUR", "de-DE": "EUR", "it-IT": "EUR", "es-ES": "EUR",
    "pt-PT": "EUR", "nl-NL": "EUR",
}

# Country code → currency
COUNTRY_CURRENCY_MAP = {
    "IN": "INR", "US": "USD", "GB": "GBP", "AU": "AUD", "CA": "CAD",
    "SG": "SGD", "JP": "JPY", "KR": "KRW", "TH": "THB", "MY": "MYR",
    "AE": "AED", "SA": "SAR", "QA": "QAR", "BD": "BDT", "LK": "LKR",
    "NP": "NPR", "FR": "EUR", "DE": "EUR", "IT": "EUR", "ES": "EUR",
}


def get_exchange_rates(base: str = "INR") -> dict[str, Decimal]:
    """
    Fetch exchange rates from API, with caching and fallback.

    Args:
        base: Base currency code (default: INR)

    Returns:
        Dict mapping target currency → rate (1 base = X target)
    """
    cache_key = CACHE_KEY_RATES.format(base=base)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = getattr(settings, "EXCHANGE_RATE_API_KEY", "")
    api_url = getattr(settings, "EXCHANGE_RATE_API_URL", "")
    ttl = getattr(settings, "EXCHANGE_RATE_CACHE_TTL", 3600)

    if api_key and api_url:
        try:
            url = f"{api_url}/{api_key}/latest/{base}"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            if data.get("result") == "success":
                raw_rates = data.get("conversion_rates", {})
                supported = getattr(settings, "SUPPORTED_CURRENCIES", list(FALLBACK_RATES.keys()))
                rates = {
                    code: Decimal(str(rate))
                    for code, rate in raw_rates.items()
                    if code in supported
                }
                if rates:
                    cache.set(cache_key, rates, ttl)
                    logger.info("Fetched %d exchange rates from API (base=%s)", len(rates), base)
                    return rates
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.warning("Exchange rate API error: %s — using fallback rates", e)

    # Fallback to static rates
    if base == "INR":
        rates = dict(FALLBACK_RATES)
    else:
        # Convert fallback INR rates to the requested base
        inr_to_base = FALLBACK_RATES.get(base, Decimal("1"))
        if inr_to_base == 0:
            inr_to_base = Decimal("1")
        rates = {
            code: (rate / inr_to_base).quantize(Decimal("0.000001"))
            for code, rate in FALLBACK_RATES.items()
        }

    cache.set(cache_key, rates, ttl)
    return rates


def convert_amount(
    amount: Decimal | float | int,
    from_currency: str = "INR",
    to_currency: str = "USD",
) -> Decimal:
    """
    Convert an amount from one currency to another.

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Converted amount (Decimal)
    """
    if from_currency == to_currency:
        return Decimal(str(amount))

    rates = get_exchange_rates(from_currency)
    rate = rates.get(to_currency)

    if rate is None:
        logger.warning("No rate found for %s→%s, returning original amount", from_currency, to_currency)
        return Decimal(str(amount))

    return (Decimal(str(amount)) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_currency(amount: Decimal | float | int, currency: str = "INR") -> str:
    """
    Format amount with currency symbol.

    Returns e.g.: '₹9,960', '$120.00', '€108.50'
    """
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    num = Decimal(str(amount))

    # No decimals for currencies where it's not customary
    no_decimal = currency in {"INR", "JPY", "KRW"}
    if no_decimal:
        formatted = f"{int(num):,}"
    else:
        formatted = f"{num:,.2f}"

    return f"{symbol}{formatted}"


def detect_user_currency(
    ip_country: Optional[str] = None,
    browser_locale: Optional[str] = None,
    user_preference: Optional[str] = None,
) -> str:
    """
    Detect user's preferred currency.

    Priority: user_preference > ip_country > browser_locale > default INR

    Args:
        ip_country: Two-letter country code from IP geolocation
        browser_locale: Browser Accept-Language (e.g. 'en-US')
        user_preference: Explicitly stored preference

    Returns:
        Currency code (e.g. 'USD')
    """
    supported = getattr(settings, "SUPPORTED_CURRENCIES", list(FALLBACK_RATES.keys()))

    # 1. User explicit preference
    if user_preference and user_preference.upper() in supported:
        return user_preference.upper()

    # 2. IP-based country
    if ip_country:
        cc = ip_country.upper()
        currency = COUNTRY_CURRENCY_MAP.get(cc)
        if currency and currency in supported:
            return currency

    # 3. Browser locale
    if browser_locale:
        # Handle 'en-US,en;q=0.9' format — take first
        primary = browser_locale.split(",")[0].strip()
        currency = LOCALE_CURRENCY_MAP.get(primary)
        if currency and currency in supported:
            return currency
        # Try just the language part with common country
        lang = primary.split("-")[0].lower()
        for locale, cur in LOCALE_CURRENCY_MAP.items():
            if locale.lower().startswith(lang) and cur in supported:
                return cur

    # 4. Default
    return getattr(settings, "BASE_CURRENCY", "INR")


def get_supported_currencies() -> list[dict]:
    """
    Return list of supported currencies for frontend dropdown.

    Returns: [{'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'}, ...]
    """
    supported = getattr(settings, "SUPPORTED_CURRENCIES", list(FALLBACK_RATES.keys()))
    return [
        {
            "code": code,
            "name": CURRENCY_NAMES.get(code, code),
            "symbol": CURRENCY_SYMBOLS.get(code, code),
        }
        for code in supported
    ]
