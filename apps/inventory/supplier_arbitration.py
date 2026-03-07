"""
Section 4 — Supplier Arbitration Engine

Dynamic supplier selection based on:
  1. Price competitiveness  (40%)
  2. Supplier health score  (25%)
  3. Cancellation rate      (15%)
  4. Latency/reliability    (20%)

Usage:
  engine = SupplierArbitrationEngine()
  winner = engine.select_best(room_type, check_in, check_out, quantity)
  # winner → {'source': 'supplier', 'supplier_name': 'hotelbeds', 'rate': Decimal, ...}
  #   or     {'source': 'direct', 'rate': Decimal, ...}
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger('zygotrip.inventory.arbitration')


class SupplierArbitrationEngine:
    """
    Select the best inventory source for a (room_type, date-range, qty) request.
    Considers price, health, cancellation risk, and latency.
    """

    # Scoring weights (sum = 1.0)
    W_PRICE = 0.40
    W_HEALTH = 0.25
    W_CANCEL = 0.15
    W_LATENCY = 0.20

    # Thresholds
    MAX_ERROR_RATE = 0.30      # Skip supplier if error_rate >30%
    MAX_LATENCY_MS = 5000      # Skip supplier if avg latency >5s

    def select_best(self, room_type, check_in, check_out, quantity=1):
        """
        Return the best source dict or None if nothing is available.

        Returns:
            dict with keys: source, supplier_name (if supplier), rate, total,
                            rooms_available, score, details
        """
        candidates = self._gather_candidates(room_type, check_in, check_out, quantity)
        if not candidates:
            return None

        # Score each candidate
        rates = [c['rate'] for c in candidates if c['rate'] > 0]
        min_rate = min(rates) if rates else Decimal('1')
        max_rate = max(rates) if rates else Decimal('1')

        for c in candidates:
            c['score'] = self._score(c, min_rate, max_rate)

        candidates.sort(key=lambda c: c['score'], reverse=True)

        winner = candidates[0]
        logger.info(
            "Arbitration winner for %s: source=%s supplier=%s rate=₹%s score=%.2f",
            room_type, winner['source'],
            winner.get('supplier_name', 'direct'),
            winner['rate'], winner['score'],
        )
        return winner

    def select_all_ranked(self, room_type, check_in, check_out, quantity=1):
        """Return all candidates sorted by score (best first)."""
        candidates = self._gather_candidates(room_type, check_in, check_out, quantity)
        rates = [c['rate'] for c in candidates if c['rate'] > 0]
        min_rate = min(rates) if rates else Decimal('1')
        max_rate = max(rates) if rates else Decimal('1')
        for c in candidates:
            c['score'] = self._score(c, min_rate, max_rate)
        candidates.sort(key=lambda c: c['score'], reverse=True)
        return candidates

    # ------------------------------------------------------------------

    def _gather_candidates(self, room_type, check_in, check_out, quantity):
        """Collect direct + supplier inventory candidates for each date."""
        from datetime import timedelta
        from apps.inventory.models import InventoryCalendar, SupplierInventory, SupplierHealth

        nights = (check_out - check_in).days
        if nights <= 0:
            return []

        # -- Direct inventory --
        direct_ok = True
        direct_total_rate = Decimal('0')
        for offset in range(nights):
            d = check_in + timedelta(days=offset)
            try:
                cal = InventoryCalendar.objects.get(room_type=room_type, date=d)
                if cal.is_closed or cal.available_rooms < quantity:
                    direct_ok = False
                    break
                direct_total_rate += cal.effective_rate * quantity
            except InventoryCalendar.DoesNotExist:
                direct_ok = False
                break

        candidates = []
        if direct_ok:
            candidates.append({
                'source': 'direct',
                'supplier_name': 'direct',
                'rate': direct_total_rate / nights if nights else direct_total_rate,
                'total': direct_total_rate,
                'rooms_available': quantity,  # already validated
                'health_score': 1.0,
                'cancel_rate': 0.0,
                'avg_latency_ms': 0,
                'details': {'type': 'own_inventory'},
            })

        # -- Supplier inventory --
        supplier_rows = (
            SupplierInventory.objects
            .filter(
                supplier_room__room_type=room_type,
                date__gte=check_in,
                date__lt=check_out,
                is_closed=False,
                available_rooms__gte=quantity,
            )
            .select_related('supplier_room__supplier_map')
        )

        # Group by supplier
        supplier_map = {}
        for si in supplier_rows:
            sname = si.supplier_room.supplier_map.supplier_name
            supplier_map.setdefault(sname, []).append(si)

        for sname, rows in supplier_map.items():
            # Must cover ALL nights
            if len(rows) < nights:
                continue

            total_rate = sum(Decimal(str(r.rate_per_night)) * quantity for r in rows)
            avg_rate = total_rate / nights if nights else total_rate
            min_avail = min(r.available_rooms for r in rows)

            # Health data
            health_score = 1.0
            cancel_rate = 0.0
            avg_latency = 0.0
            try:
                sh = SupplierHealth.objects.get(supplier_name=sname)
                if not sh.is_healthy:
                    continue  # Skip disabled suppliers
                health_score = max(0, 1.0 - sh.error_rate)
                avg_latency = sh.avg_latency_ms
            except SupplierHealth.DoesNotExist:
                pass

            if avg_latency > self.MAX_LATENCY_MS:
                continue  # Too slow

            candidates.append({
                'source': 'supplier',
                'supplier_name': sname,
                'rate': avg_rate,
                'total': total_rate,
                'rooms_available': min_avail,
                'health_score': health_score,
                'cancel_rate': cancel_rate,
                'avg_latency_ms': avg_latency,
                'details': {'nights_covered': len(rows)},
            })

        return candidates

    def _score(self, c, min_rate, max_rate):
        """
        Compute composite score (0..1) for a candidate.
        """
        # Price score (lower price → higher score)
        rate_range = max_rate - min_rate
        if rate_range > 0:
            price_score = float(1.0 - (c['rate'] - min_rate) / rate_range)
        else:
            price_score = 1.0

        # Health score (already 0-1)
        health = c.get('health_score', 1.0)

        # Cancellation risk (lower → better)
        cancel = 1.0 - c.get('cancel_rate', 0.0)

        # Latency score (lower → better; cap at 5s)
        lat = c.get('avg_latency_ms', 0)
        latency_score = max(0, 1.0 - lat / self.MAX_LATENCY_MS) if lat > 0 else 1.0

        return (
            price_score * self.W_PRICE
            + health * self.W_HEALTH
            + cancel * self.W_CANCEL
            + latency_score * self.W_LATENCY
        )
