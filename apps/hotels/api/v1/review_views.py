"""
Review REST API views.

Endpoints (appended to hotels API v1):
  GET    /api/v1/properties/<slug>/reviews/    — List reviews for a property
  POST   /api/v1/reviews/                      — Submit a review
  GET    /api/v1/reviews/my/                   — List my reviews
"""
import logging
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.booking.models import Booking
from apps.hotels.models import Property
from apps.hotels.review_models import Review

logger = logging.getLogger('zygotrip.reviews')


@api_view(['GET'])
@permission_classes([AllowAny])
def property_reviews(request, property_id):
    """
    GET /api/v1/properties/<slug>/reviews/

    Returns paginated approved reviews for a property.
    Query params: ?page=1&page_size=10&sort=newest|highest|lowest
    """
    try:
        prop = Property.objects.get_by_id_or_slug(property_id)
    except Property.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Property not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    qs = Review.objects.filter(
        property=prop, status=Review.STATUS_APPROVED,
    ).select_related('user')

    sort = request.query_params.get('sort', 'newest')
    if sort == 'highest':
        qs = qs.order_by('-overall_rating', '-created_at')
    elif sort == 'lowest':
        qs = qs.order_by('overall_rating', '-created_at')
    else:
        qs = qs.order_by('-created_at')

    page_size = min(int(request.query_params.get('page_size', 10)), 50)
    page = max(int(request.query_params.get('page', 1)), 1)
    offset = (page - 1) * page_size

    total = qs.count()
    reviews = qs[offset:offset + page_size]

    data = [
        {
            'id': r.id,
            'user_name': r.user.full_name,
            'overall_rating': str(r.overall_rating),
            'cleanliness': str(r.cleanliness),
            'service': str(r.service),
            'location': str(r.location),
            'amenities': str(r.amenities),
            'value_for_money': str(r.value_for_money),
            'title': r.title,
            'comment': r.comment,
            'traveller_type': r.traveller_type,
            'created_at': r.created_at.isoformat(),
            'owner_response': r.owner_response if r.owner_response else None,
            'owner_responded_at': r.owner_responded_at.isoformat() if r.owner_responded_at else None,
        }
        for r in reviews
    ]

    return Response({
        'success': True,
        'data': {
            'results': data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'property_rating': str(prop.rating),
            'property_review_count': prop.review_count,
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_review(request):
    """
    POST /api/v1/reviews/

    Body: {
      booking_uuid: "...",
      overall_rating: 4.5,
      cleanliness: 4.0,
      service: 5.0,
      location: 4.0,
      amenities: 3.5,
      value_for_money: 4.0,
      title: "Great stay!",
      comment: "Really enjoyed...",
      traveller_type: "couple"
    }
    """
    booking_uuid = request.data.get('booking_uuid')
    if not booking_uuid:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'booking_uuid is required'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        booking = Booking.objects.select_related('property').get(
            uuid=booking_uuid, user=request.user,
        )
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if already reviewed
    if Review.objects.filter(booking=booking).exists():
        return Response(
            {'success': False, 'error': {'code': 'already_reviewed', 'message': 'This booking has already been reviewed'}},
            status=status.HTTP_409_CONFLICT,
        )

    # Validate booking status
    if booking.status not in (Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED):
        return Response(
            {'success': False, 'error': {'code': 'invalid_status', 'message': 'Can only review confirmed or completed bookings'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Parse rating fields
    rating_fields = ['overall_rating', 'cleanliness', 'service', 'location', 'amenities', 'value_for_money']
    ratings = {}
    for field in rating_fields:
        val = request.data.get(field)
        if val is None:
            return Response(
                {'success': False, 'error': {'code': 'validation_error', 'message': f'{field} is required'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            d = Decimal(str(val))
            if d < 1 or d > 5:
                raise ValueError
            ratings[field] = d
        except (InvalidOperation, ValueError):
            return Response(
                {'success': False, 'error': {'code': 'validation_error', 'message': f'{field} must be between 1.0 and 5.0'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

    comment = request.data.get('comment', '')
    if len(comment) < 10:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Review comment must be at least 10 characters'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Device fingerprint fraud check for review spam ---
    try:
        from apps.core.device_fingerprint import FingerprintService
        fp = FingerprintService.collect_from_request(request)
        if fp.fraud_score >= 70:
            logger.warning('Review blocked: fraud score %d (user=%s, fp=%s)',
                           fp.fraud_score, request.user.email, fp.fingerprint_hash[:12])
            return Response(
                {'success': False, 'error': {'code': 'review_blocked', 'message': 'Review could not be submitted. Please contact support.'}},
                status=status.HTTP_403_FORBIDDEN,
            )
    except Exception as fp_err:
        logger.debug('Fingerprint check skipped for review: %s', fp_err)

    try:
        review = Review.objects.create(
            booking=booking,
            property=booking.property,
            user=request.user,
            title=request.data.get('title', ''),
            comment=comment,
            traveller_type=request.data.get('traveller_type', ''),
            **ratings,
        )
    except Exception as e:
        return Response(
            {'success': False, 'error': {'code': 'creation_failed', 'message': str(e)}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        'success': True,
        'data': {
            'review_id': review.id,
            'status': review.status,
            'message': 'Review submitted successfully. It will be visible after moderation.',
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_reviews(request):
    """GET /api/v1/reviews/my/ — List reviews submitted by the current user."""
    reviews = Review.objects.filter(user=request.user).select_related('property', 'booking').order_by('-created_at')

    data = [
        {
            'id': r.id,
            'property_name': r.property.name if r.property else '',
            'property_slug': r.property.slug if r.property else '',
            'booking_uuid': str(r.booking.uuid) if r.booking else '',
            'overall_rating': str(r.overall_rating),
            'title': r.title,
            'comment': r.comment[:100],
            'status': r.status,
            'created_at': r.created_at.isoformat(),
        }
        for r in reviews
    ]

    return Response({'success': True, 'data': data})
