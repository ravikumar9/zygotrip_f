"""
Travel Orchestration Service — bundle creation, cart management, checkout.

Functions:
  create_bundle          — Create a new travel bundle
  add_item_to_bundle     — Add a product booking to a bundle
  create_cart            — Create a shopping cart
  add_to_cart            — Add any product to cart
  remove_from_cart       — Remove item
  checkout_cart          — Process multi-product checkout
  suggest_complementary  — Auto-suggest complementary products
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .travel_bundle import TravelBundle, BundleItem, Cart, CartItem

logger = logging.getLogger('zygotrip.orchestration')

CART_TTL_MINUTES = 30


@transaction.atomic
def create_bundle(user, title='', destination_city='', start_date=None, end_date=None):
    """Create a new travel bundle for grouping bookings."""
    bundle = TravelBundle.objects.create(
        user=user, title=title, destination_city=destination_city,
        start_date=start_date, end_date=end_date)
    logger.info("Bundle %s created for user %s", bundle.bundle_ref, user.id)
    return bundle


@transaction.atomic
def add_item_to_bundle(bundle_id, product_type, product_id, product_ref='',
                       description='', amount=Decimal('0'),
                       start_datetime=None, end_datetime=None):
    """Add a product booking to an existing bundle."""
    bundle = TravelBundle.objects.select_for_update().get(pk=bundle_id)
    item = BundleItem.objects.create(
        bundle=bundle, product_type=product_type,
        product_id=product_id, product_ref=product_ref,
        description=description, amount=amount,
        start_datetime=start_datetime, end_datetime=end_datetime,
        status='confirmed')
    bundle.recalculate_totals()
    return item


def get_or_create_cart(user=None, session_key=''):
    """Get active cart or create a new one."""
    qs = Cart.objects.filter(is_active=True, expires_at__gt=timezone.now())
    if user and user.is_authenticated:
        cart = qs.filter(user=user).first()
    elif session_key:
        cart = qs.filter(session_key=session_key).first()
    else:
        cart = None

    if not cart:
        cart = Cart.objects.create(
            user=user if user and user.is_authenticated else None,
            session_key=session_key,
            expires_at=timezone.now() + timedelta(minutes=CART_TTL_MINUTES))
    return cart


@transaction.atomic
def add_to_cart(cart_id, product_type, product_id, unit_price,
                quantity=1, product_snapshot=None):
    """Add an item to the multi-product cart."""
    cart = Cart.objects.select_for_update().get(pk=cart_id)
    if cart.is_expired:
        raise ValueError("Cart has expired")

    # Check for duplicate
    existing = cart.items.filter(
        product_type=product_type, product_id=product_id, is_active=True
    ).first()
    if existing:
        existing.quantity += quantity
        existing.save(update_fields=['quantity', 'subtotal', 'updated_at'])
        return existing

    item = CartItem.objects.create(
        cart=cart, product_type=product_type,
        product_id=product_id, unit_price=Decimal(str(unit_price)),
        quantity=quantity, subtotal=Decimal(str(unit_price)) * quantity,
        product_snapshot=product_snapshot or {},
        hold_expires_at=timezone.now() + timedelta(minutes=CART_TTL_MINUTES))
    return item


@transaction.atomic
def remove_from_cart(cart_id, item_id):
    """Remove an item from the cart."""
    CartItem.objects.filter(cart_id=cart_id, pk=item_id).update(
        is_active=False, updated_at=timezone.now())


def get_cart_summary(cart_id):
    """Get cart with all items and totals."""
    cart = Cart.objects.get(pk=cart_id)
    items = cart.items.filter(is_active=True)
    return {
        'cart_id': str(cart.uuid),
        'items': [
            {
                'id': item.id,
                'product_type': item.product_type,
                'product_id': item.product_id,
                'description': item.product_snapshot.get('title', ''),
                'unit_price': str(item.unit_price),
                'quantity': item.quantity,
                'subtotal': str(item.subtotal),
            }
            for item in items
        ],
        'item_count': items.count(),
        'total_amount': str(cart.total_amount),
        'expires_at': cart.expires_at.isoformat(),
    }


def suggest_complementary(city, start_date=None, product_types_booked=None):
    """Suggest complementary products for a trip.

    e.g. if user booked a flight + hotel in Goa, suggest cabs and activities.
    """
    booked = set(product_types_booked or [])
    suggestions = []

    # Always suggest what's missing
    VERTICALS = ['hotel', 'flight', 'cab', 'activity']
    missing = [v for v in VERTICALS if v not in booked]

    for vertical in missing[:3]:
        suggestions.append({
            'product_type': vertical,
            'reason': f"Complete your {city} trip with a {vertical} booking",
            'search_params': {
                'city': city,
                'date': start_date.isoformat() if start_date else None,
            },
        })

    return suggestions
