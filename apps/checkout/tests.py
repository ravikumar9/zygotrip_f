from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase

from apps.checkout.api.v1.serializers import BookingConfirmationSerializer
from apps.checkout.services import _build_price_snapshot, extract_snapshot_total


class _RoomsRelation:
    def __init__(self, booking_room):
        self._booking_room = booking_room

    def select_related(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._booking_room


class CheckoutPricingSnapshotTests(SimpleTestCase):
    def test_build_price_snapshot_uses_canonical_pricing_keys(self):
        snapshot = _build_price_snapshot({
            'base_price': Decimal('4200.00'),
            'meal_plan_price': Decimal('800.00'),
            'service_fee': Decimal('250.00'),
            'gst_amount': Decimal('945.00'),
            'final_total': Decimal('6195.00'),
            'tariff_per_night': Decimal('4200.00'),
        })

        self.assertEqual(snapshot['gst'], '945.00')
        self.assertEqual(snapshot['gst_amount'], '945.00')
        self.assertEqual(snapshot['total'], '6195.00')
        self.assertEqual(snapshot['final_total'], '6195.00')

    def test_extract_snapshot_total_supports_canonical_and_legacy_keys(self):
        self.assertEqual(
            extract_snapshot_total({'final_total': '5100.00'}),
            Decimal('5100.00'),
        )
        self.assertEqual(
            extract_snapshot_total({'total_after_tax': '5300.00'}),
            Decimal('5300.00'),
        )
        self.assertEqual(
            extract_snapshot_total({'total': '5400.00'}),
            Decimal('5400.00'),
        )


class BookingConfirmationSerializerTests(SimpleTestCase):
    def test_serializer_uses_booking_uuid_public_id_and_first_room_type(self):
        room_type = SimpleNamespace(name='Deluxe Suite')
        booking_room = SimpleNamespace(room_type=room_type)
        booking = SimpleNamespace(
            uuid=uuid4(),
            public_booking_id='BK-20260314-HTL-ABCD1234',
            status='confirmed',
            total_amount=Decimal('6195.00'),
            check_in='2026-04-01',
            check_out='2026-04-03',
            property=SimpleNamespace(name='Aurora Bay Hotel'),
            rooms=_RoomsRelation(booking_room),
        )

        data = BookingConfirmationSerializer(booking).data

        self.assertEqual(data['booking_id'], booking.public_booking_id)
        self.assertEqual(data['booking_uuid'], str(booking.uuid))
        self.assertEqual(data['property_name'], 'Aurora Bay Hotel')
        self.assertEqual(data['room_type_name'], 'Deluxe Suite')
