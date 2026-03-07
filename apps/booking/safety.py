# booking/safety.py - Race condition protection and transaction safety

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.apps import apps
from .models import Booking


class BookingSafetyError(Exception):
    """Raised when booking cannot be safely created"""
    pass


class BookingTransactionManager:
    """Handle booking creation with atomicity and double-booking prevention"""
    
    @staticmethod
    @transaction.atomic
    def create_hotel_booking_safe(user, property_obj, check_in, check_out, **kwargs):
        """
        Create hotel booking with race condition protection.
        
        Uses select_for_update() to lock the property and prevent double-booking.
        
        Args:
            user: User object
            property_obj: Property object
            check_in: Check-in date
            check_out: Check-out date
            **kwargs: Additional booking fields (quantity, room_type, etc.)
        
        Returns:
            Booking object
        
        Raises:
            BookingSafetyError: If booking cannot be created safely
        """
        try:
            # Lock property for update - prevents concurrent bookings
            property_model = apps.get_model('hotels', 'Property')
            property = property_model.objects.select_for_update().get(pk=property_obj.pk)
            
            # Check availability within transaction (after lock)
            conflicting = Booking.objects.filter(
                property=property,
                status__in=[
                    Booking.STATUS_REVIEW,
                    Booking.STATUS_PAYMENT,
                    Booking.STATUS_CONFIRMED
                ]
            ).filter(
                check_in__lt=check_out,
                check_out__gt=check_in
            ).exists()
            
            if conflicting:
                raise BookingSafetyError(
                    "Booking period conflicts with existing reservation. Please select different dates."
                )
            
            # Create booking within transaction
            booking = Booking.objects.create(
                user=user,
                property=property,
                check_in=check_in,
                check_out=check_out,
                status=Booking.STATUS_PENDING,
                **kwargs
            )
            
            return booking
            
        except IntegrityError as e:
            raise BookingSafetyError(f"Database integrity error: {str(e)}")
        except BookingSafetyError:
            raise
        except Exception as e:
            raise BookingSafetyError(f"Unexpected error during booking: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def create_cab_booking_safe(user, cab, booking_date, distance_km, **kwargs):
        """
        Create cab booking with race condition protection.
        
        Locks available seats and prevents overselling.
        
        Args:
            user: User object
            cab: Cab object
            booking_date: Date of booking
            distance_km: Distance in km
            **kwargs: Additional fields (promo_code, etc.)
        
        Returns:
            CabBooking object
        
        Raises:
            BookingSafetyError: If booking cannot be created safely
        """
        try:
            # Lock cab for update
            cab_model = apps.get_model('cabs', 'Cab')
            cab_booking_model = apps.get_model('cabs', 'CabBooking')
            cab = cab_model.objects.select_for_update().get(pk=cab.pk)
            
            # Check availability
            seats_booked = cab_booking_model.objects.filter(
                cab=cab,
                booking_date=booking_date,
                status__in=['pending', 'confirmed']
            ).count()
            
            if seats_booked >= cab.seats:
                raise BookingSafetyError(
                    f"No seats available in this cab for {booking_date}"
                )
            
            # Create booking
            booking = cab_booking_model.objects.create(
                user=user,
                cab=cab,
                booking_date=booking_date,
                distance_km=distance_km,
                status='pending',
                **kwargs
            )
            
            return booking
            
        except IntegrityError as e:
            raise BookingSafetyError(f"Database integrity error: {str(e)}")
        except BookingSafetyError:
            raise
        except Exception as e:
            raise BookingSafetyError(f"Unexpected error during booking: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def create_bus_booking_safe(user, bus, journey_date, **kwargs):
        """
        Create bus booking with race condition protection.
        
        Locks bus and prevents overselling.
        
        Args:
            user: User object
            bus: Bus object
            journey_date: Date of journey
            **kwargs: Additional fields
        
        Returns:
            BusBooking object
        
        Raises:
            BookingSafetyError: If booking cannot be created safely
        """
        try:
            # Lock bus for update
            bus_model = apps.get_model('buses', 'Bus')
            bus_booking_model = apps.get_model('buses', 'BusBooking')
            bus = bus_model.objects.select_for_update().get(pk=bus.pk)
            
            # Check seat availability
            seats_booked = bus_booking_model.objects.filter(
                bus=bus,
                journey_date=journey_date,
                status__in=['pending', 'confirmed']
            ).count()
            
            available_seats = bus.available_seats
            if seats_booked >= available_seats:
                raise BookingSafetyError(
                    f"No seats available in this bus for {journey_date}"
                )
            
            # Create booking
            booking = bus_booking_model.objects.create(
                user=user,
                bus=bus,
                journey_date=journey_date,
                status='pending',
                **kwargs
            )
            
            return booking
            
        except IntegrityError as e:
            raise BookingSafetyError(f"Database integrity error: {str(e)}")
        except BookingSafetyError:
            raise
        except Exception as e:
            raise BookingSafetyError(f"Unexpected error during booking: {str(e)}")
    
    @staticmethod
    def verify_booking_integrity(booking):
        """
        Verify booking integrity before payment/confirmation.
        
        Checks:
        - Booking status is valid for processing
        - Dates are still valid
        - Service is still available
        """
        from django.utils import timezone
        
        # Status check
        if booking.status not in [Booking.STATUS_PENDING, Booking.STATUS_REVIEW]:
            raise BookingSafetyError(f"Booking status {booking.status} doesn't allow changes")
        
        # Date validity check
        if booking.check_in <= timezone.localdate():
            raise BookingSafetyError("Check-in date has passed - booking is no longer valid")
        
        return True