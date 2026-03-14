"""Flight admin configuration."""
from django.contrib import admin
from .models import (
    Airline, Airport, Flight, FlightLeg, FlightFareClass,
    BaggageAllowance, FlightBooking, FlightBookingHistory,
    FlightPassenger, FlightPriceBreakdown, FlightCancellationPolicy,
)


class FlightLegInline(admin.TabularInline):
    model = FlightLeg
    extra = 0


class FlightFareClassInline(admin.TabularInline):
    model = FlightFareClass
    extra = 0


class FlightPassengerInline(admin.TabularInline):
    model = FlightPassenger
    extra = 0
    readonly_fields = ['fare_amount']


class FlightBookingHistoryInline(admin.TabularInline):
    model = FlightBookingHistory
    extra = 0
    readonly_fields = ['status', 'note', 'created_at']


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'country', 'is_lcc', 'alliance', 'is_active']
    list_filter = ['is_lcc', 'is_active', 'alliance']
    search_fields = ['code', 'name']


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ['iata_code', 'name', 'city', 'country', 'is_active']
    list_filter = ['country', 'is_active']
    search_fields = ['iata_code', 'name', 'city']


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ['flight_number', 'airline', 'origin', 'destination',
                    'departure_datetime', 'stops', 'is_active']
    list_filter = ['airline', 'stops', 'is_active', 'trip_type']
    search_fields = ['flight_number', 'airline__code']
    date_hierarchy = 'departure_datetime'
    inlines = [FlightLegInline, FlightFareClassInline]
    raw_id_fields = ['airline', 'origin', 'destination', 'operating_airline']


@admin.register(FlightBooking)
class FlightBookingAdmin(admin.ModelAdmin):
    list_display = ['pnr', 'user', 'flight', 'status', 'final_amount',
                    'trip_type', 'created_at']
    list_filter = ['status', 'trip_type']
    search_fields = ['pnr', 'public_booking_id', 'user__email',
                     'contact_email', 'ticket_number']
    readonly_fields = ['uuid', 'pnr', 'public_booking_id']
    inlines = [FlightPassengerInline, FlightBookingHistoryInline]
    raw_id_fields = ['user', 'flight', 'fare_class', 'return_flight',
                     'return_fare_class']


@admin.register(FlightFareClass)
class FlightFareClassAdmin(admin.ModelAdmin):
    list_display = ['flight', 'cabin_type', 'fare_class_code',
                    'total_fare', 'available_seats', 'is_refundable']
    list_filter = ['cabin_type', 'is_refundable']


@admin.register(FlightPriceBreakdown)
class FlightPriceBreakdownAdmin(admin.ModelAdmin):
    list_display = ['booking', 'base_fare', 'total_amount']


@admin.register(FlightCancellationPolicy)
class FlightCancellationPolicyAdmin(admin.ModelAdmin):
    list_display = ['fare_class', 'hours_before_departure',
                    'refund_percentage', 'cancellation_fee']
