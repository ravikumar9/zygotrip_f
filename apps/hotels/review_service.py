"""
Review Service — Production Implementation.

Uses the Review model from review_models.py for real data.
Falls back to Property.rating/review_count when no reviews exist yet.
Provides formatted review data for property listings and detail pages.

Includes:
  - Verified-stay review submission
  - Multi-dimensional ratings (5 sub-scores)
  - Review moderation workflow (auto + manual)
  - Owner response capability
  - Search ranking integration
  - Review analytics
"""
import logging
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

logger = logging.getLogger('zygotrip.reviews')


class ReviewService:
    """Provides review data from the Review model with consistent formatting."""

    RATING_LABELS = {
        5: 'Excellent',
        4.5: 'Very Good',
        4: 'Good',
        3.5: 'Average',
        3: 'Below Average',
        2: 'Poor',
        1: 'Very Poor',
    }

    @staticmethod
    def get_property_reviews(property_slug):
        """
        Get reviews for a property from the Review model.

        Returns:
            dict with rating, label, count, distribution, and display texts.
        """
        from apps.hotels.models import Property
        from apps.hotels.review_models import Review

        try:
            prop = Property.objects.get(slug=property_slug)
        except Property.DoesNotExist:
            return ReviewService._empty_review_data(property_slug)

        # Aggregate from approved reviews
        approved = Review.objects.filter(
            property=prop, status=Review.STATUS_APPROVED,
        )
        agg = approved.aggregate(
            avg_overall=Avg('overall_rating'),
            avg_cleanliness=Avg('cleanliness'),
            avg_service=Avg('service'),
            avg_location=Avg('location'),
            avg_amenities=Avg('amenities'),
            avg_value=Avg('value_for_money'),
            count=Count('id'),
        )

        review_count = agg['count'] or 0
        rating = float(agg['avg_overall'] or prop.rating or 0)

        if review_count == 0 and prop.rating:
            # Fall back to Property-level rating if no approved reviews yet
            rating = float(prop.rating)
            review_count = prop.review_count or 0

        star_category = int(round(rating))
        rating_label = ReviewService._get_rating_label(rating)

        # Real distribution from DB
        distribution = ReviewService._get_real_distribution(approved) if review_count > 0 else {
            5: 0, 4: 0, 3: 0, 2: 0, 1: 0,
        }

        # Sub-ratings
        sub_ratings = {}
        if agg['avg_cleanliness']:
            sub_ratings = {
                'cleanliness': round(float(agg['avg_cleanliness']), 1),
                'service': round(float(agg['avg_service'] or 0), 1),
                'location': round(float(agg['avg_location'] or 0), 1),
                'amenities': round(float(agg['avg_amenities'] or 0), 1),
                'value_for_money': round(float(agg['avg_value'] or 0), 1),
            }

        return {
            'property_slug': property_slug,
            'rating': round(rating, 1),
            'rating_label': rating_label,
            'review_count': review_count,
            'verified_reviews': review_count,
            'star_category': star_category,
            'display_text': f"{round(rating, 1)}★ {rating_label} ({review_count} reviews)",
            'display_text_short': f"{round(rating, 1)}★ {rating_label}",
            'distribution': distribution,
            'sub_ratings': sub_ratings,
            'source': 'database' if review_count > 0 else 'no_reviews',
        }

    @staticmethod
    def _empty_review_data(property_slug):
        return {
            'property_slug': property_slug,
            'rating': 0,
            'rating_label': 'No Rating',
            'review_count': 0,
            'verified_reviews': 0,
            'star_category': 0,
            'display_text': 'No reviews yet',
            'display_text_short': 'New',
            'distribution': {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
            'sub_ratings': {},
            'source': 'no_reviews',
        }

    @staticmethod
    def _get_rating_label(rating):
        for threshold in sorted(ReviewService.RATING_LABELS.keys(), reverse=True):
            if rating >= threshold:
                return ReviewService.RATING_LABELS[threshold]
        return 'No Rating'

    @staticmethod
    def _get_real_distribution(approved_qs):
        """Compute actual star distribution from approved reviews."""
        dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        rows = approved_qs.values('overall_rating').annotate(cnt=Count('id'))
        for row in rows:
            star_bucket = int(round(float(row['overall_rating'])))
            star_bucket = max(1, min(5, star_bucket))
            dist[star_bucket] += row['cnt']
        return dist

    @staticmethod
    def get_all_property_reviews(properties_qs):
        """Get reviews for multiple properties."""
        reviews = []
        for prop in properties_qs:
            review_data = ReviewService.get_property_reviews(prop.slug)
            reviews.append({
                'property_id': prop.id,
                'property_slug': prop.slug,
                'property_name': prop.name,
                **review_data,
            })
        return reviews

    @staticmethod
    def get_recent_reviews(property_slug, limit=10):
        """Get the most recent approved reviews for a property."""
        from apps.hotels.models import Property
        from apps.hotels.review_models import Review

        try:
            prop = Property.objects.get(slug=property_slug)
        except Property.DoesNotExist:
            return []

        reviews = Review.objects.filter(
            property=prop, status=Review.STATUS_APPROVED,
        ).select_related('user').order_by('-created_at')[:limit]

        return [
            {
                'id': r.id,
                'user_name': r.user.full_name if r.user else 'Anonymous',
                'overall_rating': float(r.overall_rating),
                'title': r.title,
                'comment': r.comment,
                'traveller_type': r.traveller_type,
                'created_at': r.created_at.isoformat(),
                'owner_response': r.owner_response or None,
                'sub_ratings': {
                    'cleanliness': float(r.cleanliness),
                    'service': float(r.service),
                    'location': float(r.location),
                    'amenities': float(r.amenities),
                    'value_for_money': float(r.value_for_money),
                },
            }
            for r in reviews
        ]

    @staticmethod
    def create_user_review(booking, user, rating_data):
        """
        Create a user review from a completed booking.

        Args:
            booking: Booking instance (must be CHECKED_OUT or SETTLED)
            user: User instance
            rating_data: dict with overall_rating, cleanliness, service,
                         location, amenities, value_for_money, title, comment,
                         traveller_type
        Returns:
            dict with status and review data or error
        """
        from apps.hotels.review_models import Review

        # Check if review already exists
        if Review.objects.filter(booking=booking).exists():
            return {'status': 'error', 'message': 'Review already exists for this booking'}

        try:
            review = Review(
                booking=booking,
                property=booking.property,
                user=user,
                overall_rating=Decimal(str(rating_data['overall_rating'])),
                cleanliness=Decimal(str(rating_data.get('cleanliness', rating_data['overall_rating']))),
                service=Decimal(str(rating_data.get('service', rating_data['overall_rating']))),
                location=Decimal(str(rating_data.get('location', rating_data['overall_rating']))),
                amenities=Decimal(str(rating_data.get('amenities', rating_data['overall_rating']))),
                value_for_money=Decimal(str(rating_data.get('value_for_money', rating_data['overall_rating']))),
                title=rating_data.get('title', ''),
                comment=rating_data.get('comment', ''),
                traveller_type=rating_data.get('traveller_type', ''),
                status=Review.STATUS_PENDING,
            )
            review.save()
            logger.info('Review created: booking=%s property=%s rating=%s',
                        booking.id, booking.property_id, rating_data['overall_rating'])
            return {
                'status': 'pending',
                'message': 'Your review has been submitted for approval',
                'review_id': review.id,
            }
        except Exception as e:
            logger.error('Review creation failed: %s', e)
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def format_review_badge(property_slug):
        """Format review badge for display on listing card."""
        review_data = ReviewService.get_property_reviews(property_slug)
        if review_data['review_count'] == 0:
            return 'New'
        return f"{review_data['rating']}★ ({review_data['review_count']})"

    @staticmethod
    def format_review_detail(property_slug):
        """Format detailed review for property detail page."""
        review_data = ReviewService.get_property_reviews(property_slug)
        if review_data['review_count'] == 0:
            return 'No reviews yet'
        return (
            f"{review_data['rating']} {review_data['rating_label']} "
            f"({review_data['review_count']} reviews)"
        )

    @staticmethod
    @transaction.atomic
    def approve_review(review_id, moderator=None):
        """Manually approve a pending review. Recalculates property aggregates."""
        from apps.hotels.review_models import Review
        review = Review.objects.select_for_update().get(id=review_id)
        if review.status != Review.STATUS_PENDING:
            return False
        review.status = Review.STATUS_APPROVED
        review.save(update_fields=['status', 'updated_at'])
        ReviewService._recalculate_aggregates(review.property)
        logger.info('Review approved: id=%s by=%s', review_id,
                     moderator.email if moderator else 'system')
        return True

    @staticmethod
    @transaction.atomic
    def reject_review(review_id, reason='', moderator=None):
        """Reject a review. Recalculates aggregates if previously approved."""
        from apps.hotels.review_models import Review
        review = Review.objects.select_for_update().get(id=review_id)
        was_approved = review.status == Review.STATUS_APPROVED
        review.status = Review.STATUS_REJECTED
        review.save(update_fields=['status', 'updated_at'])
        if was_approved:
            ReviewService._recalculate_aggregates(review.property)
        logger.info('Review rejected: id=%s reason=%s', review_id, reason[:100])
        return True

    @staticmethod
    @transaction.atomic
    def add_owner_response(review_id, owner, response_text):
        """Allow property owner to respond to a review."""
        from apps.hotels.review_models import Review
        review = Review.objects.get(id=review_id)
        if review.property.owner_id != owner.id:
            return False, 'Only the property owner can respond.'
        review.owner_response = response_text
        review.save(update_fields=['owner_response', 'updated_at'])
        return True, ''

    @staticmethod
    def _recalculate_aggregates(property_obj):
        """Recalculate property rating + RatingAggregate from approved reviews."""
        from apps.hotels.review_models import Review
        from apps.hotels.models import RatingAggregate

        reviews = Review.objects.filter(property=property_obj, status='approved')
        agg = reviews.aggregate(
            avg_overall=Avg('overall_rating'),
            avg_cleanliness=Avg('cleanliness'),
            avg_service=Avg('service'),
            avg_location=Avg('location'),
            avg_amenities=Avg('amenities'),
            avg_value=Avg('value_for_money'),
            count=Count('id'),
        )

        property_obj.rating = Decimal(str(agg['avg_overall'] or 0)).quantize(Decimal('0.1'))
        property_obj.review_count = agg['count']
        property_obj.save(update_fields=['rating', 'review_count', 'updated_at'])

        RatingAggregate.objects.update_or_create(
            property=property_obj,
            defaults={
                'cleanliness': agg['avg_cleanliness'] or 0,
                'service': agg['avg_service'] or 0,
                'location': agg['avg_location'] or 0,
                'amenities': agg['avg_amenities'] or 0,
                'value_for_money': agg['avg_value'] or 0,
                'total_reviews': agg['count'],
            },
        )

        # Trigger search index update
        try:
            from apps.search.signals import _schedule_property_index_rebuild
            _schedule_property_index_rebuild(property_obj.id)
        except Exception:
            pass

    @staticmethod
    def get_review_analytics(property_obj):
        """Review analytics for owner dashboard."""
        from apps.hotels.review_models import Review

        reviews = Review.objects.filter(property=property_obj, status='approved')
        agg = reviews.aggregate(
            avg_overall=Avg('overall_rating'),
            avg_cleanliness=Avg('cleanliness'),
            avg_service=Avg('service'),
            avg_location=Avg('location'),
            avg_amenities=Avg('amenities'),
            avg_value=Avg('value_for_money'),
            total=Count('id'),
        )

        dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        rows = reviews.values('overall_rating').annotate(cnt=Count('id'))
        for row in rows:
            star = max(1, min(5, int(round(float(row['overall_rating'])))))
            dist[star] += row['cnt']

        trend = list(
            reviews.filter(created_at__gte=timezone.now() - timedelta(days=365))
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(avg=Avg('overall_rating'), count=Count('id'))
            .order_by('month')
        )

        return {
            'averages': {
                'overall': float(agg['avg_overall'] or 0),
                'cleanliness': float(agg['avg_cleanliness'] or 0),
                'service': float(agg['avg_service'] or 0),
                'location': float(agg['avg_location'] or 0),
                'amenities': float(agg['avg_amenities'] or 0),
                'value_for_money': float(agg['avg_value'] or 0),
            },
            'total_reviews': agg['total'],
            'rating_distribution': dist,
            'trend': [
                {'month': str(t['month'].date()), 'avg': float(t['avg']), 'count': t['count']}
                for t in trend
            ],
        }


# ============================================================================
# Review Moderation Engine
# ============================================================================

class ReviewModerationEngine:
    """
    Auto-moderation for review content.
    Checks: profanity/spam, content length, rating consistency,
    verified stay, duplicates.
    """

    _BLOCKED_PATTERNS = {
        'http://', 'https://', 'www.', '.com/', 'buy now',
        'click here', 'free gift', 'earn money', 'bitcoin',
    }

    MIN_COMMENT_LENGTH = 20
    MIN_TITLE_LENGTH = 5

    @classmethod
    def auto_moderate(cls, review):
        """
        Returns dict: { action: 'approve'|'flag'|'reject', score: int, reasons: list }
        """
        reasons = []
        score = 100

        # 1. Content length
        comment = (review.comment or '').strip()
        title = (review.title or '').strip()
        if len(comment) < cls.MIN_COMMENT_LENGTH:
            reasons.append('Comment too short')
            score -= 20
        if title and len(title) < cls.MIN_TITLE_LENGTH:
            reasons.append('Title too short')
            score -= 10

        # 2. Spam/link detection
        text = f"{title} {comment}".lower()
        for pattern in cls._BLOCKED_PATTERNS:
            if pattern in text:
                reasons.append(f'Blocked content: {pattern}')
                score -= 30
                break

        # 3. Rating consistency
        sub_ratings = [review.cleanliness, review.service, review.location,
                       review.amenities, review.value_for_money]
        valid_subs = [float(r) for r in sub_ratings if r and float(r) > 0]
        if valid_subs and review.overall_rating:
            avg_sub = sum(valid_subs) / len(valid_subs)
            if abs(float(review.overall_rating) - avg_sub) > 2.0:
                reasons.append('Rating inconsistency')
                score -= 15

        # 4. Verified stay
        booking = review.booking
        if booking and booking.status not in ('checked_out', 'settled', 'confirmed'):
            reasons.append('Booking not completed')
            score -= 40

        # 5. Duplicate detection
        from apps.hotels.review_models import Review
        if Review.objects.filter(
            user=review.user, property=review.property,
            created_at__gte=timezone.now() - timedelta(days=7),
        ).exclude(id=review.id).exists():
            reasons.append('Duplicate review')
            score -= 50

        action = 'approve' if score >= 70 else ('flag' if score >= 40 else 'reject')
        return {'action': action, 'score': score, 'reasons': reasons}

    @classmethod
    def moderate_and_apply(cls, review):
        """Run auto-moderation and update review status."""
        result = cls.auto_moderate(review)
        from apps.hotels.review_models import Review
        if result['action'] == 'approve':
            review.status = Review.STATUS_APPROVED
            review.save(update_fields=['status', 'updated_at'])
            ReviewService._recalculate_aggregates(review.property)
        elif result['action'] == 'reject':
            review.status = Review.STATUS_REJECTED
            review.save(update_fields=['status', 'updated_at'])
        # 'flag' leaves status as 'pending' for manual review
        return result
