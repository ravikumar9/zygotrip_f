"""Flight API views."""
import logging
from datetime import datetime

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    FlightSearchInputSerializer, FlightBookingInputSerializer,
    FlightBookingSerializer, AirportSerializer,
)
from .services import (
    search_flights, search_roundtrip, create_flight_booking,
    cancel_flight_booking, get_fare_calendar,
)
from .models import Airport, FlightBooking

logger = logging.getLogger('zygotrip.flights')


@api_view(['GET'])
@permission_classes([AllowAny])
def flight_search(request):
    """Search flights by route & date. Supports oneway and roundtrip."""
    ser = FlightSearchInputSerializer(data=request.query_params)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data

    if d.get('return_date'):
        results = search_roundtrip(
            d['origin'], d['destination'], d['departure_date'],
            d['return_date'], d['cabin_type'], d['adults'],
            d['children'], d['infants'])
    else:
        results = search_flights(
            d['origin'], d['destination'], d['departure_date'],
            d['cabin_type'], d['adults'], d['children'], d['infants'],
            d['sort_by'])
        results = {'outbound': results, 'trip_type': 'oneway'}

    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def flight_fare_calendar(request):
    """Get cheapest fares across a date range for flexible date selection."""
    origin = request.query_params.get('origin', '').strip()
    dest = request.query_params.get('destination', '').strip()
    date_str = request.query_params.get('start_date', '')
    cabin = request.query_params.get('cabin_type', 'economy')

    if not origin or not dest or not date_str:
        return Response({'error': 'origin, destination, start_date required'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        start = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date format (use YYYY-MM-DD)'},
                        status=status.HTTP_400_BAD_REQUEST)

    calendar = get_fare_calendar(origin, dest, start, cabin_type=cabin)
    return Response({'fare_calendar': calendar})


@api_view(['GET'])
@permission_classes([AllowAny])
def airport_search(request):
    """Search airports by city or IATA code."""
    from django.db.models import Q

    q = request.query_params.get('q', '').strip()
    if len(q) < 2:
        return Response({'results': []})

    airports = Airport.objects.filter(is_active=True).filter(
        Q(iata_code__icontains=q) | Q(city__icontains=q) | Q(name__icontains=q)
    )[:15]

    return Response({
        'results': AirportSerializer(airports, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def flight_book(request):
    """Create a flight booking with passenger details."""
    ser = FlightBookingInputSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data

    try:
        booking = create_flight_booking(
            user=request.user,
            flight_id=d['flight_id'],
            fare_class_id=d['fare_class_id'],
            passengers_data=d['passengers'],
            contact_email=d['contact_email'],
            contact_phone=d['contact_phone'],
            promo_code=d.get('promo_code', ''),
            return_flight_id=d.get('return_flight_id'),
            return_fare_class_id=d.get('return_fare_class_id'),
        )
        return Response(
            FlightBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED)
    except ValueError as e:
        return Response({'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flight_booking_detail(request, pnr):
    """Get flight booking by PNR."""
    try:
        booking = FlightBooking.objects.get(pnr=pnr.upper(), user=request.user)
    except FlightBooking.DoesNotExist:
        return Response({'error': 'Booking not found'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(FlightBookingSerializer(booking).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flight_my_bookings(request):
    """List authenticated user's flight bookings."""
    bookings = FlightBooking.objects.filter(
        user=request.user
    ).select_related(
        'flight__airline', 'flight__origin', 'flight__destination',
        'fare_class'
    ).order_by('-created_at')[:50]

    return Response({
        'bookings': FlightBookingSerializer(bookings, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def flight_cancel(request, pnr):
    """Cancel a flight booking."""
    try:
        booking = FlightBooking.objects.get(pnr=pnr.upper(), user=request.user)
    except FlightBooking.DoesNotExist:
        return Response({'error': 'Booking not found'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        result = cancel_flight_booking(booking.id)
        return Response(result)
    except ValueError as e:
        return Response({'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST)
