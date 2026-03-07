# core/date_utils.py - Date utilities for booking forms

from django.utils import timezone
from datetime import datetime, timedelta


def get_today():
    """Get today's date in the configured timezone (timezone-aware)"""
    return timezone.localdate()


def get_min_date():
    """Get the minimum allowed booking date (today)"""
    return get_today()


def get_date_for_template():
    """Get today's date in ISO format for HTML min attribute: YYYY-MM-DD"""
    return get_today().isoformat()


def validate_booking_date(date_value, allow_today=True):
    """
    Validates a booking date against min/max constraints.
    
    Args:
        date_value: datetime.date or datetime.datetime object
        allow_today: If True, today is allowed. If False, tomorrow+ required.
    
    Returns:
        tuple: (valid: bool, message: str)
    """
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    
    today = get_today()
    
    if allow_today:
        if date_value < today:
            return False, f"Date cannot be in the past. Minimum date is {today.strftime('%Y-%m-%d')}"
    else:
        if date_value <= today:
            return False, f"Date must be tomorrow or later. Minimum date is {(today + timedelta(days=1)).strftime('%Y-%m-%d')}"
    
    # Max date validation (2 years from now)
    max_date = today + timedelta(days=730)
    if date_value > max_date:
        return False, f"Date is too far in the future. Maximum date is {max_date.strftime('%Y-%m-%d')}"
    
    return True, ""


def get_date_range_for_filter(days_ahead=30):
    """Get date range for filtering (today to N days ahead)"""
    today = get_today()
    end_date = today + timedelta(days=days_ahead)
    return today, end_date