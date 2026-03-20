"""
PriceGuard — Pre-payment price revalidation enforcer.

Problem:
  Users spend time filling in guest details. By the time they hit "Pay",
  the price may have changed (demand surge, promo expired, rate plan update).
  Charging the old price is incorrect. Rejecting silently is bad UX.

Solution:
  1. FRESHNESS CHECK — if price was validated < 5 min ago, skip revalidation.
  2. LIVE REVALIDATION — query pricing engine for current price.
  3. DRIFT CHECK — allow ±3% price change (within normal rate fluctuation).
  4. BLOCK — if drift > 3%, raise PriceChangedException so the frontend can
     show the user the new price and ask them to confirm.

Business rules:
  - Freshness TTL: 5 minutes (300s)
  - Allowed drift: ±3% of original price
  - If drift ≤ 3%: update snapshot silently, proceed with NEW price
  - If drift > 3%: block payment, return old + new price to frontend

Usage::

    from apps.checkout.price_guard import PriceGuard

    # In create_payment_intent (checkout/services.py):
    session, amount = PriceGuard.validate_before_payment(session)
    # `amount` is always the freshly-validated price to charge.
"""
import logging
from decimal import Decimal
from typing import Tuple

from django.utils import timezone

logger = logging.getLogger('zygotrip.checkout.price_guard')

# ── Configuration ─────────────────────────────────────────────────────────────
FRESHNESS_TTL_SECONDS: int = 300          # 5 minutes
MAX_DRIFT_PERCENT: Decimal = Decimal('3.0')   # ±3% allowed price change


class PriceGuard:
    """
    Stateless pre-payment price validation guard.

    All methods are class methods — no instance required.
    """

    @classmethod
    def is_fresh(cls, session) -> bool:
        """
        Return True if the price snapshot was revalidated within FRESHNESS_TTL_SECONDS.

        A freshly-validated price doesn't need another round-trip to the pricing engine.
        """
        if not session.price_revalidated_at:
            return False
        age = (timezone.now() - session.price_revalidated_at).total_seconds()
        return age <= FRESHNESS_TTL_SECONDS

    @classmethod
    def _compute_drift_pct(cls, old_total: Decimal, new_total: Decimal) -> Decimal:
        """Return absolute percentage drift between old and new total."""
        if old_total <= 0:
            return Decimal('0')
        return abs((new_total - old_total) / old_total) * 100

    @classmethod
    def validate_before_payment(cls, session) -> Tuple[object, Decimal]:
        """
        Validate that the session price is current before creating a payment.

        Steps:
          1. Check freshness — if < 5 min old, return fast (no DB hit)
          2. Revalidate price via pricing engine
          3. Check drift — if ≤ 3%, update snapshot and proceed
          4. If drift > 3%, raise PriceChangedException

        Args:
            session: BookingSession instance

        Returns:
            Tuple (session, amount: Decimal) — amount is the amount to charge.

        Raises:
            PriceChangedException: Price drifted beyond MAX_DRIFT_PERCENT.
            SessionExpiredException: Session has expired.
        """
        from apps.checkout.exceptions import (
            PriceChangedException,
            SessionExpiredException,
        )
        from apps.checkout.services import revalidate_price

        if session.is_expired:
            raise SessionExpiredException("Session expired during PriceGuard validation")

        old_total = Decimal(str(session.price_snapshot.get('total', '0') or '0'))
        if old_total <= 0:
            from apps.checkout.services import extract_snapshot_total
            old_total = extract_snapshot_total(session.price_snapshot)

        # ── Fast path: price is fresh, no revalidation needed ─────────────
        if cls.is_fresh(session):
            logger.debug(
                'PriceGuard FAST PATH: session=%s amount=%s (validated %ds ago)',
                session.session_id,
                old_total,
                (timezone.now() - session.price_revalidated_at).seconds
                if session.price_revalidated_at else -1,
            )
            return session, old_total

        # ── Stale price: revalidate against live pricing engine ───────────
        logger.info(
            'PriceGuard: revalidating stale price — session=%s old_total=%s',
            session.session_id, old_total,
        )

        # `revalidate_price` in services.py has a 2% hard tolerance.
        # We intercept PriceChangedException and re-apply our 3% tolerance.
        try:
            session, price_changed, new_total = revalidate_price(session)

        except PriceChangedException as exc:
            # services.py's 2% tolerance tripped — apply our 3% check
            old_exc = exc.old_price
            new_exc = exc.new_price
            drift = cls._compute_drift_pct(old_exc, new_exc)

            if drift <= MAX_DRIFT_PERCENT:
                # Within 3% — silently accept the new price
                logger.info(
                    'PriceGuard: drift %.2f%% within %.1f%% tolerance — '
                    'accepting new price: session=%s old=%s new=%s',
                    drift, MAX_DRIFT_PERCENT,
                    session.session_id, old_exc, new_exc,
                )
                # Update the snapshot to reflect new price
                session.price_snapshot['total'] = str(new_exc)
                session.price_revalidated_at = timezone.now()
                session.price_changed = True
                session.save(update_fields=[
                    'price_snapshot', 'price_revalidated_at', 'price_changed', 'updated_at',
                ])
                return session, new_exc
            else:
                # Beyond 3% — block payment, inform frontend
                logger.warning(
                    'PriceGuard DEBUG_ALLOWED: drift %.2f%% exceeds %.1f%% — '
                    'session=%s old=%s new=%s',
                    drift, MAX_DRIFT_PERCENT,
                    session.session_id, old_exc, new_exc,
                )
                raise   # re-raise original PriceChangedException

        # ── Price within services.py 2% tolerance (no exception raised) ──
        if price_changed:
            drift = cls._compute_drift_pct(old_total, new_total)
            logger.info(
                'PriceGuard: price changed %.2f%% (within tolerance) — '
                'session=%s old=%s new=%s',
                drift, session.session_id, old_total, new_total,
            )

        return session, new_total
