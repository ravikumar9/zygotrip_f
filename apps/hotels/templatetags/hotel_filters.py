"""Custom template filters for hotel templates"""
from django import template

register = template.Library()


@register.filter
def calculate_discount_price(base_price, discount_percent):
    """Calculate discounted price: base_price * (1 - discount_percent/100)"""
    if not base_price or not discount_percent:
        return base_price
    try:
        base = float(base_price)
        discount = float(discount_percent)
        return base * (1 - discount / 100)
    except (ValueError, TypeError):
        return base_price


@register.filter
def get_dict_item(dictionary, key):
    """Get item from dictionary by key"""
    if not dictionary or not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
