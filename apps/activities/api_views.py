"""Activity API views."""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Activity, ActivityCategory, ActivityReview, ActivityBooking
from .serializers import (
    ActivitySearchInputSerializer, ActivityBookingInputSerializer,
    ActivityBookingSerializer, ActivityDetailSerializer,
    ActivityCategorySerializer, ActivityTimeSlotSerializer,
    ActivityReviewSerializer,
)
from .services import (
    search_activities, create_activity_booking,
    cancel_activity_booking,
)

logger = logging.getLogger('zygotrip.activities')


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_search(request):
    """Search activities by city with optional filters."""
    ser = ActivitySearchInputSerializer(data=request.query_params)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data
    results = search_activities(
        city=d['city'], date=d.get('date'),
        category_slug=d.get('category'),
        min_price=d.get('min_price'), max_price=d.get('max_price'),
        difficulty=d.get('difficulty'), sort_by=d['sort_by'])
    return Response({'results': results})


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_detail(request, slug):
    """Get full activity detail with images."""
    try:
        activity = Activity.objects.select_related('category').prefetch_related(
            'images').get(slug=slug, is_active=True)
    except Activity.DoesNotExist:
        return Response({'error': 'Activity not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ActivityDetailSerializer(activity).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_slots(request, pk):
    """Get available time slots for an activity on a date."""
    date = request.query_params.get('date')
    if not date:
        return Response({'error': 'date parameter required'},
                        status=status.HTTP_400_BAD_REQUEST)
    from .models import ActivityTimeSlot
    from django.db.models import F
    slots = ActivityTimeSlot.objects.filter(
        activity_id=pk, date=date, is_active=True
    ).exclude(booked_count__gte=F('max_capacity'))
    return Response({
        'slots': ActivityTimeSlotSerializer(slots, many=True).data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_reviews(request, pk):
    """Get reviews for an activity."""
    reviews = ActivityReview.objects.filter(
        activity_id=pk, is_active=True
    ).select_related('user').order_by('-created_at')[:50]
    return Response({
        'reviews': ActivityReviewSerializer(reviews, many=True).data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_categories(request):
    """List all activity categories."""
    cats = ActivityCategory.objects.filter(is_active=True).order_by('sort_order')
    return Response({
        'categories': ActivityCategorySerializer(cats, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activity_book(request):
    """Create an activity booking."""
    ser = ActivityBookingInputSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data
    try:
        booking = create_activity_booking(
            user=request.user,
            activity_id=d['activity_id'],
            time_slot_id=d['time_slot_id'],
            adults=d['adults'],
            children=d['children'],
            participants_data=d['participants'],
            contact_name=d['contact_name'],
            contact_email=d['contact_email'],
            contact_phone=d['contact_phone'],
            special_requests=d.get('special_requests', ''),
            promo_code=d.get('promo_code', ''),
        )
        return Response(
            ActivityBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activity_booking_detail(request, ref):
    """Get booking detail by reference."""
    try:
        booking = ActivityBooking.objects.get(
            booking_ref=ref.upper(), user=request.user)
    except ActivityBooking.DoesNotExist:
        return Response({'error': 'Booking not found'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(ActivityBookingSerializer(booking).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activity_my_bookings(request):
    """List user's activity bookings."""
    bookings = ActivityBooking.objects.filter(
        user=request.user
    ).select_related('activity', 'time_slot').order_by('-created_at')[:50]
    return Response({
        'bookings': ActivityBookingSerializer(bookings, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activity_cancel(request, ref):
    """Cancel an activity booking."""
    try:
        booking = ActivityBooking.objects.get(
            booking_ref=ref.upper(), user=request.user)
    except ActivityBooking.DoesNotExist:
        return Response({'error': 'Booking not found'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        result = cancel_activity_booking(booking.id)
        return Response(result)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
