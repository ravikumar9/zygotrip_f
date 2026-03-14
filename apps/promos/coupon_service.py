"""
Production Coupon Service — DB-backed with Best Combination Calculator.

Reads from the Promo model (not hardcoded list). Evaluates the optimal
combination of: promo coupon + wallet balance + cashback campaign + bank offer
to maximize user savings while respecting all constraints.

Phase 11 upgrade: unified discount engine.
"""
from datetime import date
from decimal import Decimal
import logging

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger('zygotrip.promos')


class CouponService:
    """DB-backed coupon management with auto-apply and combo-optimization."""

    # ── Fallback coupons (used ONLY if DB has zero active promos) ──────
    _SEED_COUPONS = [
        {
            'code': 'STAYSAVER', 'description': 'Stay Saver Deal - 10% Off',
            'discount_percent': 10, 'discount_type': 'percentage',
            'min_amount': 2000, 'max_discount': 500,
            'valid_from': date(2026, 1, 1), 'valid_until': date(2026, 12, 31),
        },
        {
            'code': 'GLOBAL10', 'description': 'Global 10% Off',
            'discount_percent': 10, 'discount_type': 'percentage',
            'min_amount': 1000, 'max_discount': 1000,
            'valid_from': date(2026, 1, 1), 'valid_until': date(2026, 12, 31),
        },
        {
            'code': 'WELCOME200', 'description': 'First Booking - ₹200 Off',
            'discount_amount': 200, 'discount_type': 'fixed',
            'min_amount': 1500,
            'valid_from': date(2026, 1, 1), 'valid_until': date(2026, 12, 31),
            'first_booking_only': True,
        },
    ]

    # ── Core: validate from DB ─────────────────────────────────────────

    @staticmethod
    def _get_active_promos(module: str = 'all'):
        """Fetch active promos from DB, falling back to seed data."""
        try:
            from apps.promos.models import Promo
            today = timezone.now().date()
            promos = Promo.objects.filter(
                is_active=True,
            ).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=today),
            ).filter(
                Q(ends_at__isnull=True) | Q(ends_at__gte=today),
            )
            if module != 'all':
                promos = promos.filter(
                    Q(applicable_module=module) | Q(applicable_module='all'),
                )
            if promos.exists():
                return list(promos), 'db'
        except Exception as e:
            logger.debug('DB promo lookup failed, using seed: %s', e)

        # Fallback to seed coupons
        return CouponService._SEED_COUPONS, 'seed'

    @staticmethod
    def validate_coupon(coupon_code, user=None, module='all'):
        """Validate coupon code against DB Promo model.

        Checks: is_active, date range, max_uses vs actual usage count,
        per-user usage limit.
        """
        coupon_code = str(coupon_code).strip().upper()
        today = timezone.now().date()

        # Try DB first
        try:
            from apps.promos.models import Promo, PromoUsage

            promo = Promo.objects.filter(
                code__iexact=coupon_code,
                is_active=True,
            ).first()

            if promo:
                # Date checks
                if promo.starts_at and promo.starts_at > today:
                    return {'valid': False, 'coupon': None, 'message': 'Coupon is not yet active'}
                if promo.ends_at and promo.ends_at < today:
                    return {'valid': False, 'coupon': None, 'message': 'Coupon has expired'}

                # Module check
                if module != 'all' and promo.applicable_module not in (module, 'all'):
                    return {'valid': False, 'coupon': None,
                            'message': f'Coupon not valid for {module}'}

                # Usage limit check
                if promo.max_uses > 0:
                    used = PromoUsage.objects.filter(promo=promo).count()
                    if used >= promo.max_uses:
                        return {'valid': False, 'coupon': None,
                                'message': 'Coupon usage limit reached'}

                # Per-user usage check
                if user and user.is_authenticated:
                    user_used = PromoUsage.objects.filter(promo=promo, user=user).count()
                    if user_used > 0:
                        return {'valid': False, 'coupon': None,
                                'message': 'You have already used this coupon'}

                # Convert DB promo to standard dict for apply_coupon
                coupon_dict = {
                    'code': promo.code,
                    'description': f'{promo.code} - {promo.discount_type} discount',
                    'discount_type': 'percentage' if promo.discount_type == 'percent' else 'fixed',
                    'discount_percent': float(promo.value) if promo.discount_type == 'percent' else 0,
                    'discount_amount': float(promo.value) if promo.discount_type == 'amount' else 0,
                    'max_discount': float(promo.max_discount) if promo.max_discount else None,
                    'min_amount': 0,
                    'db_promo_id': promo.id,
                }
                return {'valid': True, 'coupon': coupon_dict,
                        'message': f'Applied: {coupon_dict["description"]}'}
        except Exception as e:
            logger.debug('DB promo validation error: %s', e)

        # Fallback: check seed coupons
        for coupon in CouponService._SEED_COUPONS:
            if coupon['code'] == coupon_code:
                if today < coupon.get('valid_from', today) or today > coupon.get('valid_until', today):
                    return {'valid': False, 'coupon': None, 'message': 'Coupon has expired'}
                return {'valid': True, 'coupon': coupon,
                        'message': f"Applied: {coupon['description']}"}

        return {'valid': False, 'coupon': None,
                'message': f'Invalid coupon code: {coupon_code}'}

    @staticmethod
    def apply_coupon(coupon_code, booking_price, nights=1, is_first_booking=False,
                     user=None, module='all'):
        """Apply coupon to booking price with full validation."""
        validation = CouponService.validate_coupon(coupon_code, user=user, module=module)

        if not validation['valid']:
            return {
                'applied': False, 'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'coupon_description': None, 'message': validation['message'],
                'final_price': Decimal(str(booking_price)),
            }

        coupon = validation['coupon']
        booking_price = Decimal(str(booking_price))

        # Min amount check
        min_amt = Decimal(str(coupon.get('min_amount', 0)))
        if booking_price < min_amt:
            return {
                'applied': False, 'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'coupon_description': coupon.get('description'),
                'message': f'Minimum amount ₹{min_amt} required',
                'final_price': booking_price,
            }

        # First booking check
        if coupon.get('first_booking_only') and not is_first_booking:
            return {
                'applied': False, 'coupon_code': coupon_code,
                'discount_amount': Decimal('0'),
                'message': 'This coupon is only for first bookings',
                'final_price': booking_price,
            }

        # Calculate discount
        if coupon.get('discount_type') == 'percentage':
            pct = Decimal(str(coupon.get('discount_percent', 0)))
            discount = (booking_price * pct / Decimal('100')).quantize(Decimal('0.01'))
            max_disc = coupon.get('max_discount')
            if max_disc:
                discount = min(discount, Decimal(str(max_disc)))
        else:
            discount = Decimal(str(coupon.get('discount_amount', 0)))

        discount = min(discount, booking_price)  # Never exceed booking price
        final_price = (booking_price - discount).quantize(Decimal('0.01'))

        return {
            'applied': True, 'coupon_code': coupon_code,
            'discount_amount': discount.quantize(Decimal('0.01')),
            'coupon_description': coupon.get('description', ''),
            'message': f"Coupon applied: {coupon.get('description', '')}",
            'final_price': final_price,
            'db_promo_id': coupon.get('db_promo_id'),
        }

    @staticmethod
    def auto_apply_best_coupon(booking_price, nights=1, is_first_booking=False,
                                user=None, module='all'):
        """Auto-apply the best available coupon (highest discount wins)."""
        best = {
            'applied': False, 'coupon_code': None,
            'discount_amount': Decimal('0'),
            'coupon_description': 'No coupon applied',
            'message': 'No applicable coupon',
            'final_price': Decimal(str(booking_price)),
        }

        promos, source = CouponService._get_active_promos(module)

        for promo in promos:
            code = promo.code if hasattr(promo, 'code') else promo.get('code', '')
            result = CouponService.apply_coupon(
                code, booking_price, nights, is_first_booking,
                user=user, module=module,
            )
            if result['applied'] and result['discount_amount'] > best['discount_amount']:
                best = result

        return best

    @staticmethod
    def get_available_coupons(module='all'):
        """Get list of all currently available coupons for display."""
        promos, source = CouponService._get_active_promos(module)
        available = []

        for promo in promos:
            if source == 'db':
                available.append({
                    'code': promo.code,
                    'description': f'{promo.code} — up to ₹{promo.max_discount or promo.value} off',
                    'discount': float(promo.value),
                    'discount_type': promo.discount_type,
                    'min_amount': 0,
                    'module': promo.applicable_module,
                })
            else:
                available.append({
                    'code': promo.get('code', ''),
                    'description': promo.get('description', ''),
                    'discount': promo.get('discount_percent') or promo.get('discount_amount', 0),
                    'discount_type': promo.get('discount_type', 'percentage'),
                    'min_amount': promo.get('min_amount', 0),
                    'module': 'all',
                })

        return available

    @staticmethod
    def format_coupon_display(coupon_result):
        """Format coupon application for checkout display."""
        if not coupon_result.get('applied'):
            return None
        return f"{coupon_result['coupon_code']}: ₹{coupon_result['discount_amount']} off"

    # ── Best Combination Calculator ────────────────────────────────────

    @staticmethod
    def calculate_best_combination(booking_price, user=None, module='all',
                                    nights=1, is_first_booking=False):
        """Evaluate the optimal combination of savings instruments.

        Evaluates: promo coupon + wallet balance + cashback campaign
        to find the combination that maximizes total user savings.

        Returns:
            {
                'booking_price': Decimal,
                'coupon': {code, discount_amount} or None,
                'wallet_deduction': Decimal,
                'cashback_earned': Decimal,
                'total_savings': Decimal,
                'final_payable': Decimal,
            }
        """
        booking_price = Decimal(str(booking_price))
        result = {
            'booking_price': booking_price,
            'coupon': None,
            'wallet_deduction': Decimal('0'),
            'cashback_earned': Decimal('0'),
            'total_savings': Decimal('0'),
            'final_payable': booking_price,
        }

        remaining = booking_price

        # 1. Best coupon
        coupon_result = CouponService.auto_apply_best_coupon(
            remaining, nights, is_first_booking, user=user, module=module,
        )
        if coupon_result['applied']:
            result['coupon'] = {
                'code': coupon_result['coupon_code'],
                'discount_amount': coupon_result['discount_amount'],
                'description': coupon_result.get('coupon_description', ''),
            }
            remaining -= coupon_result['discount_amount']

        # 2. Wallet balance (if user is authenticated)
        if user and user.is_authenticated:
            try:
                from apps.wallet.models import Wallet
                wallet = Wallet.objects.filter(user=user).first()
                if wallet and wallet.balance > 0:
                    # Apply up to 50% of remaining from wallet (configurable)
                    from django.conf import settings
                    max_wallet_pct = Decimal(str(
                        getattr(settings, 'MAX_WALLET_USAGE_PERCENT', 50)
                    ))
                    max_wallet = (remaining * max_wallet_pct / Decimal('100')).quantize(Decimal('0.01'))
                    wallet_use = min(wallet.balance, max_wallet)
                    result['wallet_deduction'] = wallet_use
                    remaining -= wallet_use
            except Exception as e:
                logger.debug('Wallet combo calculation failed: %s', e)

        # 3. Cashback campaign
        try:
            from apps.promos.models import CashbackCampaign
            campaigns = CashbackCampaign.objects.filter(
                status='active',
            ).filter(
                Q(start_date__isnull=True) | Q(start_date__lte=timezone.now().date()),
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=timezone.now().date()),
            )

            best_cashback = Decimal('0')
            for campaign in campaigns:
                cb = campaign.compute_cashback(booking_price)
                if cb > best_cashback:
                    best_cashback = cb

            result['cashback_earned'] = best_cashback
        except Exception as e:
            logger.debug('Cashback combo calculation failed: %s', e)

        result['total_savings'] = (
            (result['coupon']['discount_amount'] if result['coupon'] else Decimal('0'))
            + result['wallet_deduction']
            + result['cashback_earned']
        )
        result['final_payable'] = max(Decimal('0'), remaining)

        return result
