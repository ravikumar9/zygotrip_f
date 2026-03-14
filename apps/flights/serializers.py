"""Flight API serializers."""
from rest_framework import serializers
from .models import (
    Airline, Airport, Flight, FlightLeg, FlightFareClass,
    FlightBooking, FlightPassenger, FlightPriceBreakdown,
)


class AirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airline
        fields = ['id', 'code', 'name', 'logo_url', 'is_lcc', 'alliance']


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ['id', 'iata_code', 'name', 'city', 'country',
                  'latitude', 'longitude']


class FlightLegSerializer(serializers.ModelSerializer):
    origin_code = serializers.CharField(source='origin.iata_code')
    destination_code = serializers.CharField(source='destination.iata_code')

    class Meta:
        model = FlightLeg
        fields = ['leg_number', 'origin_code', 'destination_code',
                  'departure_datetime', 'arrival_datetime',
                  'duration_minutes', 'flight_number', 'layover_minutes']


class FareClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightFareClass
        fields = ['id', 'cabin_type', 'fare_class_code', 'base_fare',
                  'taxes', 'total_fare', 'available_seats', 'is_refundable',
                  'baggage_allowance_kg', 'cabin_baggage_kg',
                  'meal_included', 'seat_selection_free',
                  'change_fee', 'cancellation_fee']


class FlightListSerializer(serializers.ModelSerializer):
    airline = AirlineSerializer(read_only=True)
    origin = AirportSerializer(read_only=True)
    destination = AirportSerializer(read_only=True)
    fare_classes = FareClassSerializer(many=True, read_only=True)
    legs = FlightLegSerializer(many=True, read_only=True)
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Flight
        fields = ['id', 'uuid', 'flight_number', 'airline',
                  'origin', 'destination', 'departure_datetime',
                  'arrival_datetime', 'duration_minutes', 'duration_display',
                  'stops', 'aircraft_type', 'is_codeshare',
                  'fare_classes', 'legs']


class FlightPassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightPassenger
        fields = ['id', 'title', 'first_name', 'last_name', 'pax_type',
                  'date_of_birth', 'passport_number', 'nationality',
                  'seat_number', 'meal_preference', 'extra_baggage_kg',
                  'fare_amount']


class FlightPriceBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightPriceBreakdown
        fields = ['base_fare', 'fuel_surcharge', 'airline_gst',
                  'passenger_service_fee', 'convenience_fee',
                  'baggage_charges', 'meal_charges', 'seat_charges',
                  'insurance_amount', 'promo_discount', 'total_amount']


class FlightBookingSerializer(serializers.ModelSerializer):
    passengers = FlightPassengerSerializer(many=True, read_only=True)
    price_breakdown = FlightPriceBreakdownSerializer(read_only=True)
    flight = FlightListSerializer(read_only=True)

    class Meta:
        model = FlightBooking
        fields = ['id', 'uuid', 'pnr', 'public_booking_id', 'status',
                  'trip_type', 'total_amount', 'discount_amount',
                  'final_amount', 'promo_code', 'contact_email',
                  'contact_phone', 'hold_expires_at', 'ticket_number',
                  'flight', 'passengers', 'price_breakdown', 'created_at']


class FlightSearchInputSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=3)
    destination = serializers.CharField(max_length=3)
    departure_date = serializers.DateField()
    return_date = serializers.DateField(required=False)
    cabin_type = serializers.ChoiceField(
        choices=['economy', 'premium_economy', 'business', 'first'],
        default='economy')
    adults = serializers.IntegerField(min_value=1, max_value=9, default=1)
    children = serializers.IntegerField(min_value=0, max_value=8, default=0)
    infants = serializers.IntegerField(min_value=0, max_value=4, default=0)
    sort_by = serializers.ChoiceField(
        choices=['price', 'duration', 'departure', 'arrival'],
        default='price')


class FlightBookingInputSerializer(serializers.Serializer):
    flight_id = serializers.IntegerField()
    fare_class_id = serializers.IntegerField()
    return_flight_id = serializers.IntegerField(required=False)
    return_fare_class_id = serializers.IntegerField(required=False)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=15)
    promo_code = serializers.CharField(max_length=50, required=False, default='')
    passengers = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=9)
