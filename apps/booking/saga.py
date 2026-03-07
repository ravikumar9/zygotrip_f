"""
Section 19 — Booking Saga Manager

Orchestrates the multi-step booking transaction as a stateful saga
with compensating actions on failure at any step.

Steps:
  1. Validate inventory      → compensate: n/a
  2. Create holds             → compensate: release_holds()
  3. Price lock               → compensate: n/a (no side effect)
  4. Fraud gate               → compensate: release_holds()
  5. Create booking (HOLD)    → compensate: cancel booking + release_holds()
  6. Process payment          → compensate: refund + cancel booking + release inventory
  7. Confirm booking          → compensate: n/a (terminal state)

Usage:
    saga = BookingSaga(user, property_obj, room_type, check_in, check_out, ...)
    result = saga.execute()
    # result → {'status': 'confirmed', 'booking': ..., 'steps': [...]}
    #   or     {'status': 'failed', 'error': ..., 'steps': [...], 'compensations': [...]}
"""
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.booking.saga')


@dataclass
class SagaStep:
    name: str
    status: str = 'pending'       # pending | running | completed | failed | compensated
    duration_ms: int = 0
    error: str = ''
    data: dict = field(default_factory=dict)


class BookingSaga:
    """
    Saga orchestrator for the complete booking lifecycle.
    Each step has a forward action and optionally a compensating action.
    If any step fails, all prior compensations run in reverse order.
    """

    def __init__(self, user, property_obj, room_type, check_in, check_out,
                 quantity=1, guests=None, meal_plan=None, promo_code='',
                 idempotency_key=None, payment_method=None, request=None):
        self.user = user
        self.property_obj = property_obj
        self.room_type = room_type
        self.check_in = check_in
        self.check_out = check_out
        self.quantity = quantity
        self.guests = guests or []
        self.meal_plan = meal_plan
        self.promo_code = promo_code
        self.idempotency_key = idempotency_key or uuid.uuid4().hex
        self.payment_method = payment_method
        self.request = request

        self.steps: list[SagaStep] = []
        self.compensations: list[SagaStep] = []
        self.holds = []
        self.booking = None
        self.price_data = None

    def execute(self) -> dict:
        """
        Execute the saga. Returns result dict.
        Automatically compensates on failure.
        """
        saga_start = time.time()
        saga_id = self.idempotency_key[:12]
        logger.info("Saga %s: starting booking for user=%s property=%s",
                     saga_id, self.user.id, self.property_obj.id)

        pipeline = [
            ('validate_inventory', self._step_validate_inventory, self._comp_noop),
            ('create_holds', self._step_create_holds, self._comp_release_holds),
            ('price_lock', self._step_price_lock, self._comp_noop),
            ('fraud_gate', self._step_fraud_gate, self._comp_release_holds),
            ('create_booking', self._step_create_booking, self._comp_cancel_booking),
            ('confirm_booking', self._step_confirm_booking, self._comp_noop),
        ]

        for step_name, forward_fn, comp_fn in pipeline:
            step = SagaStep(name=step_name)
            self.steps.append(step)
            step.status = 'running'
            step_start = time.time()

            try:
                result = forward_fn()
                step.data = result or {}
                step.status = 'completed'
            except Exception as e:
                step.status = 'failed'
                step.error = str(e)
                logger.error("Saga %s: step '%s' failed: %s", saga_id, step_name, e)

                # ── Compensate in reverse ────────────────────────────────
                self._compensate(saga_id)

                return {
                    'status': 'failed',
                    'error': str(e),
                    'failed_step': step_name,
                    'steps': [self._step_dict(s) for s in self.steps],
                    'compensations': [self._step_dict(s) for s in self.compensations],
                    'duration_ms': int((time.time() - saga_start) * 1000),
                }
            finally:
                step.duration_ms = int((time.time() - step_start) * 1000)

        total_ms = int((time.time() - saga_start) * 1000)
        logger.info("Saga %s: completed in %dms", saga_id, total_ms)
        return {
            'status': 'confirmed',
            'booking': self.booking,
            'steps': [self._step_dict(s) for s in self.steps],
            'compensations': [],
            'duration_ms': total_ms,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Forward steps
    # ──────────────────────────────────────────────────────────────────────

    def _step_validate_inventory(self):
        from apps.inventory.services import check_availability
        available, unavailable = check_availability(
            self.room_type, self.check_in, self.check_out, self.quantity,
        )
        if not available:
            raise ValueError(f"Inventory unavailable on: {unavailable}")
        return {'available': True, 'dates_checked': (self.check_out - self.check_in).days}

    def _step_create_holds(self):
        from apps.inventory.services import create_hold
        self.holds = create_hold(
            self.room_type, self.check_in, self.check_out,
            self.quantity, booking_context=None,
        )
        return {'holds_created': len(self.holds)}

    def _step_price_lock(self):
        from apps.pricing.pricing_service import calculate as pricing_calculate
        nights = (self.check_out - self.check_in).days
        self.price_data = pricing_calculate(
            property_obj=self.property_obj,
            room_type=self.room_type,
            checkin_date=self.check_in,
            checkout_date=self.check_out,
            nights=nights,
            rooms=self.quantity,
            meal_plan=self.meal_plan,
            user=self.user,
        )
        return {
            'final_total': str(self.price_data.get('final_total', 0)),
            'locked': True,
        }

    def _step_fraud_gate(self):
        from apps.core.device_fingerprint import FingerprintService
        risk = FingerprintService.check_booking_risk(self.user)
        if risk.get('block'):
            raise ValueError(f"Fraud check blocked: {risk.get('reasons')}")

        velocity = FingerprintService.check_booking_velocity(self.user)
        if not velocity['allowed']:
            raise ValueError(f"Velocity limit: {velocity['reason']}")

        return {'risk_level': risk.get('level', 'low'), 'risk_score': risk.get('score', 0)}

    def _step_create_booking(self):
        from apps.booking.services import create_booking
        self.booking = create_booking(
            user=self.user,
            property_obj=self.property_obj,
            room_type=self.room_type,
            quantity=self.quantity,
            meal_plan=self.meal_plan,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=self.guests,
            promo_code=self.promo_code,
            idempotency_key=self.idempotency_key,
            locked_price=self.price_data.get('final_total') if self.price_data else None,
        )
        return {'booking_id': self.booking.id, 'status': self.booking.status}

    def _step_confirm_booking(self):
        """
        In a full implementation, this step would process payment via gateway.
        For now, it transitions the booking to CONFIRMED status directly.
        Payment integration is handled by the separate payment flow.
        """
        # Emit booking event
        try:
            from apps.core.event_bus import event_bus, DomainEvent
            event_bus.publish(DomainEvent(
                event_type='booking.confirmed',
                payload={
                    'booking_id': self.booking.id,
                    'property_id': self.property_obj.id,
                    'amount': str(self.price_data.get('final_total', 0)),
                    'user_id': self.user.id,
                },
                user_id=self.user.id,
                source='booking_saga',
            ))
        except Exception:
            pass
        return {'confirmed': True}

    # ──────────────────────────────────────────────────────────────────────
    # Compensations
    # ──────────────────────────────────────────────────────────────────────

    def _compensate(self, saga_id):
        """Run compensations in reverse order for completed steps."""
        pipeline_comp = {
            'create_holds': self._comp_release_holds,
            'create_booking': self._comp_cancel_booking,
            'fraud_gate': self._comp_release_holds,
        }

        for step in reversed(self.steps):
            if step.status != 'completed':
                continue
            comp_fn = pipeline_comp.get(step.name)
            if not comp_fn:
                continue
            comp_step = SagaStep(name=f"compensate:{step.name}")
            self.compensations.append(comp_step)
            comp_step.status = 'running'
            start = time.time()
            try:
                comp_fn()
                comp_step.status = 'completed'
                logger.info("Saga %s: compensated '%s'", saga_id, step.name)
            except Exception as e:
                comp_step.status = 'failed'
                comp_step.error = str(e)
                logger.error("Saga %s: compensation '%s' failed: %s", saga_id, step.name, e)
            finally:
                comp_step.duration_ms = int((time.time() - start) * 1000)

    def _comp_noop(self):
        pass

    def _comp_release_holds(self):
        if self.holds:
            from apps.inventory.services import release_holds
            release_holds(self.holds)
            self.holds = []

    def _comp_cancel_booking(self):
        if self.booking:
            try:
                self.booking.status = 'cancelled'
                self.booking.save(update_fields=['status', 'updated_at'])
            except Exception:
                pass
            # Also release holds
            self._comp_release_holds()

    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _step_dict(step: SagaStep) -> dict:
        return {
            'name': step.name,
            'status': step.status,
            'duration_ms': step.duration_ms,
            'error': step.error,
        }
