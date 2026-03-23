"""
Property Discount Engine — owner-controlled discount rules.

Discount stacking order (applied sequentially):
  1. Base property rate (from RoomType.base_price or InventoryCalendar)
  2. Property owner discount (this module)
  3. OTA promotional coupon (apps.promos)
  4. Wallet cashback (apps.wallet)

Supported discount types:
  - seasonal: peak/off-peak rates
  - last_minute: <48h before check-in
  - long_stay: 3+ night bookings
  - weekday: Mon-Thu discount
  - early_bird: 30+ days advance booking
  - bulk: 3+ rooms
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.pricing.discounts')


class PropertyDiscount(TimeStampedModel):
    """Owner-configured discount rule for a property."""

    SEASONAL = 'seasonal'
    LAST_MINUTE = 'last_minute'
    LONG_STAY = 'long_stay'
    WEEKDAY = 'weekday'
    EARLY_BIRD = 'early_bird'
    BULK = 'bulk'

    DISCOUNT_TYPES = [
        (SEASONAL, 'Seasonal Discount'),
        (LAST_MINUTE, 'Last Minute'),
        (LONG_STAY, 'Long Stay'),
        (WEEKDAY, 'Weekday Discount'),
        (EARLY_BIRD, 'Early Bird'),
        (BULK, 'Bulk Booking'),
    ]

    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='owner_discounts',
    )
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    # Value
    percent_off = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        help_text='Percentage discount (e.g. 15.00 = 15% off)',
    )
    flat_off = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='Flat discount amount (applied per night)',
    )
    max_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Cap on total discount amount',
    )

    # Eligibility rules
    valid_from = models.DateField()
    valid_to = models.DateField()
    min_nights = models.PositiveIntegerField(default=1)
    min_rooms = models.PositiveIntegerField(default=1)
    min_advance_days = models.PositiveIntegerField(
        default=0, help_text='Minimum days before check-in to qualify',
    )
    max_advance_days = models.PositiveIntegerField(
        default=365, help_text='Maximum days before check-in',
    )
    applicable_days = models.CharField(
        max_length=20, blank=True, default='0123456',
        help_text='Day numbers (0=Mon to 6=Sun) discount applies to',
    )

    # Room type restriction (null = all room types)
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE,
        null=True, blank=True, related_name='owner_discounts',
    )

    priority = models.PositiveIntegerField(
        default=10, help_text='Lower number = higher priority. '
        'When two same-type discounts overlap, highest priority wins.',
    )
    stackable = models.BooleanField(
        default=False,
        help_text='If True, can combine with other owner discounts (different types only)',
    )

    class Meta:
        app_label = 'pricing'
        ordering = ['priority', '-percent_off']
        indexes = [
            models.Index(fields=['property', 'discount_type', 'valid_from', 'valid_to']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_discount_type_display()}) — {self.property}"

    # ------------------------------------------------------------------
    # Eligibility checks
    # ------------------------------------------------------------------

    def is_applicable(
        self,
        check_in: date,
        check_out: date,
        rooms: int = 1,
        room_type_id: int = None,
    ) -> bool:
        """Check if this discount applies to the given booking params."""
        if not self.is_active:
            return False

        today = timezone.now().date()
        nights = (check_out - check_in).days

        # Date validity
        if not (self.valid_from <= check_in <= self.valid_to):
            return False

        # Advance booking check
        days_in_advance = (check_in - today).days
        if days_in_advance < self.min_advance_days or days_in_advance > self.max_advance_days:
            return False

        # Night count
        if nights < self.min_nights:
            return False

        # Room count
        if rooms < self.min_rooms:
            return False

        # Room type restriction
        if self.room_type_id and room_type_id and self.room_type_id != room_type_id:
            return False

        # Day-of-week filter
        if self.applicable_days:
            check_in_day = str(check_in.weekday())
            if check_in_day not in self.applicable_days:
                return False

        # Type-specific eligibility
        if self.discount_type == self.LAST_MINUTE and days_in_advance > 2:
            return False
        if self.discount_type == self.EARLY_BIRD and days_in_advance < 30:
            return False
        if self.discount_type == self.LONG_STAY and nights < 3:
            return False
        if self.discount_type == self.BULK and rooms < 3:
            return False
        if self.discount_type == self.WEEKDAY and check_in.weekday() >= 4:
            return False  # Fri-Sun not weekday

        return True

    def calculate(self, base_total: Decimal) -> Decimal:
        """Return the discount amount for a given base total."""
        discount = Decimal('0')
        if self.percent_off > 0:
            discount = base_total * self.percent_off / Decimal('100')
        if self.flat_off > 0:
            discount = max(discount, self.flat_off)
        if self.max_discount and discount > self.max_discount:
            discount = self.max_discount
        return min(discount, base_total)


# ============================================================================
# Discount resolution
# ============================================================================

def get_applicable_discounts(
    property_id: int,
    check_in: date,
    check_out: date,
    rooms: int = 1,
    room_type_id: int = None,
) -> list[PropertyDiscount]:
    """Return all applicable owner discounts for the given booking parameters."""
    discounts = PropertyDiscount.objects.filter(
        property_id=property_id,
        is_active=True,
        valid_from__lte=check_in,
        valid_to__gte=check_in,
    ).select_related('room_type').order_by('priority')

    applicable = []
    for d in discounts:
        if d.is_applicable(check_in, check_out, rooms, room_type_id):
            applicable.append(d)
    return applicable


def resolve_best_discount(
    property_id: int,
    check_in: date,
    check_out: date,
    base_total: Decimal,
    rooms: int = 1,
    room_type_id: int = None,
) -> dict:
    """
    Resolve the best owner discount(s), respecting stacking rules.

    Returns dict with:
      'discounts': list of applied discounts
      'total_discount': Decimal
      'effective_price': Decimal
    """
    applicable = get_applicable_discounts(property_id, check_in, check_out, rooms, room_type_id)
    if not applicable:
        return {'discounts': [], 'total_discount': Decimal('0'), 'effective_price': base_total}

    # Group by type — only one discount per type
    best_by_type: dict[str, tuple[PropertyDiscount, Decimal]] = {}
    for d in applicable:
        amount = d.calculate(base_total)
        existing = best_by_type.get(d.discount_type)
        if not existing or amount > existing[1]:
            best_by_type[d.discount_type] = (d, amount)

    # If stackable, combine different types; otherwise pick the single best
    stackable_discounts = [(d, amt) for d, amt in best_by_type.values() if d.stackable]
    non_stackable = [(d, amt) for d, amt in best_by_type.values() if not d.stackable]

    if stackable_discounts:
        # Stack all stackable ones
        total = sum(amt for _, amt in stackable_discounts)
        # Add best non-stackable if it beats just using stackables
        if non_stackable:
            best_ns = max(non_stackable, key=lambda x: x[1])
            if best_ns[1] > total:
                applied = [best_ns]
                total = best_ns[1]
            else:
                applied = stackable_discounts
        else:
            applied = stackable_discounts
    else:
        # No stackable — just pick the best single discount
        best = max(best_by_type.values(), key=lambda x: x[1])
        applied = [best]
        total = best[1]

    # Never exceed base total
    total = min(total, base_total)

    return {
        'discounts': [
            {
                'id': d.id,
                'name': d.name,
                'type': d.discount_type,
                'amount': float(amt),
                'percent': float(d.percent_off),
            }
            for d, amt in applied
        ],
        'total_discount': total,
        'effective_price': base_total - total,
    }


def calculate_final_price(
    property_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
    rooms: int = 1,
    promo_code: str = None,
    wallet_apply: bool = False,
    user=None,
) -> dict:
    """
    Full pricing pipeline following the stacking order:
      1. Base rate
      2. Owner discount
      3. OTA promo
      4. Wallet cashback

    Returns complete price breakdown.
    """
    from apps.rooms.models import RoomType
    from apps.inventory.models import InventoryCalendar

    nights = (check_out - check_in).days
    if nights <= 0:
        raise ValueError('check_out must be after check_in')

    room = RoomType.objects.get(id=room_type_id)
    base_per_night = room.base_price

    # Try inventory-specific pricing per night
    night_prices = []
    for i in range(nights):
        d = check_in + timedelta(days=i)
        inv = InventoryCalendar.objects.filter(
            room_type_id=room_type_id, date=d
        ).first()
        night_prices.append(inv.price if inv and inv.price else base_per_night)

    base_total = sum(night_prices) * rooms

    # Step 2: Owner discount
    owner_result = resolve_best_discount(
        property_id, check_in, check_out, base_total, rooms, room_type_id
    )
    after_owner = owner_result['effective_price']

    # Step 3: OTA promo
    promo_discount = Decimal('0')
    promo_detail = None
    if promo_code:
        try:
            from apps.promos.models import Promo
            promo = Promo.objects.get(code__iexact=promo_code, is_active=True)
            if promo.is_valid():
                if promo.discount_type == 'percentage':
                    promo_discount = after_owner * Decimal(str(promo.discount_value)) / Decimal('100')
                    if promo.max_discount:
                        promo_discount = min(promo_discount, Decimal(str(promo.max_discount)))
                else:
                    promo_discount = Decimal(str(promo.discount_value))
                promo_discount = min(promo_discount, after_owner)
                promo_detail = {'code': promo.code, 'amount': float(promo_discount)}
        except Exception as e:
            logger.warning('Promo apply failed: %s', e)

    after_promo = after_owner - promo_discount

    # Step 4: Wallet cashback
    cashback = Decimal('0')
    if wallet_apply and user and user.is_authenticated:
        try:
            from apps.wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            max_cashback = min(wallet.balance, after_promo * Decimal('0.15'))  # max 15% from wallet
            cashback = max_cashback
        except Exception:
            pass

    final = after_promo - cashback
    from apps.pricing.pricing_service import get_gst_rate
    tax_rate = get_gst_rate(final / max(nights * rooms, 1))
    tax = (final * tax_rate).quantize(Decimal('0.01'))

    return {
        'base_total': float(base_total),
        'nights': nights,
        'rooms': rooms,
        'night_prices': [float(p) for p in night_prices],
        'owner_discount': {
            'amount': float(owner_result['total_discount']),
            'details': owner_result['discounts'],
        },
        'promo_discount': promo_detail,
        'wallet_cashback': float(cashback),
        'subtotal': float(final),
        'tax': float(tax),
        'total': float(final + tax),
        'currency': 'INR',
    }
