"""
Review Moderation Service — Orchestrates review lifecycle.

Handles:
  - Auto-moderation pipeline (fraud check → profanity → sentiment)
  - Bulk moderation for admin panel
  - Owner response workflow with notification
  - Moderation queue with priority scoring
  - Review analytics for properties
"""
import logging
import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, F, Q, Value
from django.db.models.functions import Length
from django.utils import timezone

logger = logging.getLogger('zygotrip.moderation')

# ── Profanity word list (minimal, extend via settings) ──
_PROFANITY_PATTERNS = [
    r'\b(spam|scam|fake|fraud)\b',
    r'\b(worst|terrible|horrible|disgusting)\s+(ever|place|hotel)\b',
]
_COMPILED_PROFANITY = [re.compile(p, re.IGNORECASE) for p in _PROFANITY_PATTERNS]


class ReviewModerationService:
    """
    Central moderation service orchestrating the review lifecycle.
    """

    @staticmethod
    @transaction.atomic
    def submit_review(review):
        """
        Full moderation pipeline after a review is submitted.
        1. Run fraud detection
        2. Check profanity
        3. Basic sentiment analysis
        4. Set status (auto-approve, flag, or auto-reject)
        Returns moderation result dict.
        """
        from apps.hotels.review_fraud import ReviewFraudDetector

        # Step 1: Fraud detection
        fraud_result = ReviewFraudDetector.analyze_review(review)

        if fraud_result['action'] == 'rejected':
            return {
                'status': 'rejected',
                'reason': 'fraud_detection',
                'risk_score': fraud_result['total_risk'],
                'flags': fraud_result['flags'],
            }

        # Step 2: Profanity check
        profanity_hits = _check_profanity(review.comment)
        if review.title:
            profanity_hits += _check_profanity(review.title)

        # Step 3: Sentiment scoring
        sentiment = _analyze_sentiment(review)

        # Step 4: Decision
        total_risk = fraud_result['total_risk']
        if profanity_hits > 2:
            total_risk += 30

        if total_risk >= 70:
            review.status = 'rejected'
            review.moderation_note = f'Auto-rejected: combined risk {total_risk}'
            review.save(update_fields=['status', 'moderation_note', 'updated_at'])
            action = 'rejected'
        elif total_risk >= 30 or profanity_hits > 0:
            # Keep as pending for manual review
            review.moderation_note = (
                f'Flagged: risk={total_risk}, profanity={profanity_hits}, '
                f'sentiment={sentiment["label"]}'
            )
            review.save(update_fields=['moderation_note', 'updated_at'])
            action = 'pending'
        else:
            # Auto-approve clean reviews
            review.status = 'approved'
            review.moderation_note = 'Auto-approved'
            review.save(update_fields=['status', 'moderation_note', 'updated_at'])
            action = 'approved'

        logger.info(
            'Review %s moderated: action=%s risk=%d profanity=%d sentiment=%s',
            review.id, action, total_risk, profanity_hits, sentiment['label'],
        )

        return {
            'status': action,
            'risk_score': total_risk,
            'profanity_count': profanity_hits,
            'sentiment': sentiment,
            'flags': fraud_result.get('flags', []),
        }

    @staticmethod
    @transaction.atomic
    def approve_review(review, moderator, note=''):
        """Admin approves a review."""
        from apps.hotels.review_models import Review

        if review.status == Review.STATUS_APPROVED:
            return False

        review.status = Review.STATUS_APPROVED
        review.moderation_note = note or f'Approved by {moderator.email}'
        review.save(update_fields=['status', 'moderation_note', 'updated_at'])

        # Resolve any open fraud flags
        review.fraud_flags.filter(is_resolved=False).update(
            is_resolved=True,
            resolved_by=moderator,
            resolution='genuine',
        )

        logger.info('Review %s approved by %s', review.id, moderator.email)
        return True

    @staticmethod
    @transaction.atomic
    def reject_review(review, moderator, note=''):
        """Admin rejects a review."""
        from apps.hotels.review_models import Review

        if review.status == Review.STATUS_REJECTED:
            return False

        review.status = Review.STATUS_REJECTED
        review.moderation_note = note or f'Rejected by {moderator.email}'
        review.save(update_fields=['status', 'moderation_note', 'updated_at'])

        review.fraud_flags.filter(is_resolved=False).update(
            is_resolved=True,
            resolved_by=moderator,
            resolution='fraud',
        )

        logger.info('Review %s rejected by %s', review.id, moderator.email)
        return True

    @staticmethod
    @transaction.atomic
    def bulk_moderate(review_ids, action, moderator, note=''):
        """
        Bulk approve/reject reviews.
        Returns count of successfully moderated reviews.
        """
        from apps.hotels.review_models import Review

        if action not in ('approve', 'reject'):
            raise ValueError(f'Invalid action: {action}')

        new_status = Review.STATUS_APPROVED if action == 'approve' else Review.STATUS_REJECTED
        resolution = 'genuine' if action == 'approve' else 'fraud'

        reviews = Review.objects.filter(
            id__in=review_ids,
            status=Review.STATUS_PENDING,
        ).select_for_update()

        count = reviews.update(
            status=new_status,
            moderation_note=note or f'Bulk {action} by {moderator.email}',
        )

        # Resolve fraud flags
        from apps.hotels.review_fraud import ReviewFraudFlag
        ReviewFraudFlag.objects.filter(
            review_id__in=review_ids,
            is_resolved=False,
        ).update(
            is_resolved=True,
            resolved_by=moderator,
            resolution=resolution,
        )

        # Re-compute ratings for affected properties
        property_ids = Review.objects.filter(
            id__in=review_ids,
        ).values_list('property_id', flat=True).distinct()

        for pid in property_ids:
            _recompute_property_rating(pid)

        logger.info('Bulk %s: %d reviews by %s', action, count, moderator.email)
        return count

    @staticmethod
    @transaction.atomic
    def add_owner_response(review, owner_user, response_text):
        """Property owner responds to a review."""
        if not response_text or len(response_text.strip()) < 10:
            raise ValueError('Response must be at least 10 characters.')

        review.owner_response = response_text.strip()
        review.owner_responded_at = timezone.now()
        review.save(update_fields=['owner_response', 'owner_responded_at', 'updated_at'])

        logger.info('Owner responded to review %s', review.id)
        return True

    @staticmethod
    def get_moderation_queue(property_id=None, page_size=50, offset=0):
        """
        Get reviews pending moderation, ordered by priority.
        Reviews with fraud flags come first, then by age.
        """
        from apps.hotels.review_models import Review

        qs = Review.objects.filter(status=Review.STATUS_PENDING)
        if property_id:
            qs = qs.filter(property_id=property_id)

        qs = qs.select_related('user', 'property', 'booking').prefetch_related(
            'fraud_flags', 'photos',
        ).annotate(
            flag_count=Count('fraud_flags', filter=Q(fraud_flags__is_resolved=False)),
            max_risk=Avg('fraud_flags__risk_score'),
        ).order_by('-flag_count', '-max_risk', 'created_at')

        return qs[offset:offset + page_size]

    @staticmethod
    def get_review_stats(property_id):
        """
        Get review statistics for a property (for owner/admin dashboard).
        """
        from apps.hotels.review_models import Review, ReviewHelpfulness

        reviews = Review.objects.filter(
            property_id=property_id, status=Review.STATUS_APPROVED,
        )

        stats = reviews.aggregate(
            avg_rating=Avg('overall_rating'),
            avg_cleanliness=Avg('cleanliness'),
            avg_service=Avg('service'),
            avg_location=Avg('location'),
            avg_amenities=Avg('amenities'),
            avg_value=Avg('value_for_money'),
            total=Count('id'),
        )

        # Rating distribution
        distribution = {}
        for star in range(1, 6):
            distribution[star] = reviews.filter(
                overall_rating__gte=star, overall_rating__lt=star + 1,
            ).count()

        # Traveller type breakdown
        traveller_breakdown = dict(
            reviews.values_list('traveller_type').annotate(c=Count('id')).values_list('traveller_type', 'c')
        )

        # Response rate
        total_reviews = stats['total'] or 0
        responded = reviews.exclude(owner_response='').count()
        response_rate = (responded / total_reviews * 100) if total_reviews > 0 else 0

        # Pending moderation count
        pending_count = Review.objects.filter(
            property_id=property_id, status=Review.STATUS_PENDING,
        ).count()

        return {
            **stats,
            'distribution': distribution,
            'traveller_breakdown': traveller_breakdown,
            'response_rate': round(response_rate, 1),
            'pending_moderation': pending_count,
        }


def _check_profanity(text):
    """Count profanity pattern matches in text."""
    count = 0
    for pattern in _COMPILED_PROFANITY:
        count += len(pattern.findall(text))
    return count


def _analyze_sentiment(review):
    """
    Basic rule-based sentiment analysis from review ratings and text.
    Returns {'score': float, 'label': str}.
    """
    # Rating component (0-1 scale)
    rating_score = float(review.overall_rating) / 5.0

    # Text length indicates effort (longer = more balanced)
    comment_len = len(review.comment)
    effort_bonus = min(0.1, comment_len / 5000)

    # Sub-rating consistency (low spread = genuine)
    sub_ratings = [
        float(review.cleanliness), float(review.service),
        float(review.location), float(review.amenities),
        float(review.value_for_money),
    ]
    avg_sub = sum(sub_ratings) / len(sub_ratings)
    spread = sum(abs(r - avg_sub) for r in sub_ratings) / len(sub_ratings)
    consistency_score = max(0, 1.0 - spread / 2.0)

    final = (rating_score * 0.5) + (consistency_score * 0.3) + effort_bonus + 0.1

    if final >= 0.7:
        label = 'positive'
    elif final >= 0.4:
        label = 'neutral'
    else:
        label = 'negative'

    return {'score': round(final, 3), 'label': label}


def _recompute_property_rating(property_id):
    """Recompute property rating from approved reviews."""
    from apps.hotels.models import Property, RatingAggregate
    from apps.hotels.review_models import Review

    approved = Review.objects.filter(
        property_id=property_id, status=Review.STATUS_APPROVED,
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

    Property.objects.filter(pk=property_id).update(
        rating=Decimal(str(round(agg['avg_overall'] or 0, 1))),
        review_count=agg['count'] or 0,
    )

    rating_agg, _ = RatingAggregate.objects.get_or_create(property_id=property_id)
    rating_agg.cleanliness = Decimal(str(round(agg['avg_cleanliness'] or 0, 1)))
    rating_agg.service = Decimal(str(round(agg['avg_service'] or 0, 1)))
    rating_agg.location = Decimal(str(round(agg['avg_location'] or 0, 1)))
    rating_agg.amenities = Decimal(str(round(agg['avg_amenities'] or 0, 1)))
    rating_agg.value_for_money = Decimal(str(round(agg['avg_value'] or 0, 1)))
    rating_agg.total_reviews = agg['count'] or 0
    rating_agg.save()
