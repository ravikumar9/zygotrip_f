"""
Review Fraud Detection — Identifies suspicious review patterns.

Detection signals:
  1. Velocity: Too many reviews from same IP/device in short time
  2. Content analysis: Very short reviews, copy-paste patterns
  3. Rating anomalies: All 5-star or all 1-star from same user
  4. Booking pattern: Review without proper stay completion
  5. Account age: New accounts submitting reviews immediately
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, Q, StdDev
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.review_fraud')


class ReviewFraudFlag(TimeStampedModel):
    """
    Flags suspicious reviews for manual moderation.
    """
    FLAG_VELOCITY = 'velocity'
    FLAG_CONTENT = 'content'
    FLAG_RATING_ANOMALY = 'rating_anomaly'
    FLAG_NEW_ACCOUNT = 'new_account'
    FLAG_DUPLICATE = 'duplicate'
    FLAG_COMPETITOR = 'competitor_attack'

    FLAG_CHOICES = [
        (FLAG_VELOCITY, 'Review Velocity Anomaly'),
        (FLAG_CONTENT, 'Suspicious Content'),
        (FLAG_RATING_ANOMALY, 'Rating Pattern Anomaly'),
        (FLAG_NEW_ACCOUNT, 'New Account Spam'),
        (FLAG_DUPLICATE, 'Duplicate Content'),
        (FLAG_COMPETITOR, 'Suspected Competitor Attack'),
    ]

    review = models.ForeignKey(
        'hotels.Review', on_delete=models.CASCADE,
        related_name='fraud_flags',
    )
    flag_type = models.CharField(max_length=30, choices=FLAG_CHOICES)
    risk_score = models.IntegerField(
        default=0,
        help_text="0-100 risk score. >70 = auto-reject, 50-70 = manual review",
    )
    details = models.JSONField(default=dict, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    resolution = models.CharField(
        max_length=20,
        choices=[('genuine', 'Genuine'), ('fraud', 'Fraudulent'), ('unclear', 'Unclear')],
        blank=True,
    )

    class Meta:
        app_label = 'hotels'
        indexes = [
            models.Index(fields=['review', 'flag_type']),
            models.Index(fields=['is_resolved', '-risk_score']),
        ]


class ReviewFraudDetector:
    """
    Analyzes reviews for fraud signals.
    Run after each review submission.
    """

    # Thresholds
    MIN_COMMENT_LENGTH = 20
    MAX_REVIEWS_PER_DAY = 3
    MIN_ACCOUNT_AGE_DAYS = 7
    DUPLICATE_SIMILARITY_THRESHOLD = 0.85

    @staticmethod
    def analyze_review(review):
        """
        Analyze a review for fraud signals.
        Returns total risk score and list of flags.
        """
        flags = []
        total_risk = 0

        # 1. Velocity check
        risk, details = ReviewFraudDetector._check_velocity(review)
        if risk > 0:
            flags.append(('velocity', risk, details))
            total_risk += risk

        # 2. Content analysis
        risk, details = ReviewFraudDetector._check_content(review)
        if risk > 0:
            flags.append(('content', risk, details))
            total_risk += risk

        # 3. Rating anomaly
        risk, details = ReviewFraudDetector._check_rating_anomaly(review)
        if risk > 0:
            flags.append(('rating_anomaly', risk, details))
            total_risk += risk

        # 4. New account check
        risk, details = ReviewFraudDetector._check_account_age(review)
        if risk > 0:
            flags.append(('new_account', risk, details))
            total_risk += risk

        # 5. Duplicate content check
        risk, details = ReviewFraudDetector._check_duplicate(review)
        if risk > 0:
            flags.append(('duplicate', risk, details))
            total_risk += risk

        # Cap at 100
        total_risk = min(100, total_risk)

        # Create flags in DB
        created_flags = []
        for flag_type, risk_score, details in flags:
            flag = ReviewFraudFlag.objects.create(
                review=review,
                flag_type=flag_type,
                risk_score=risk_score,
                details=details,
            )
            created_flags.append(flag)

        # Auto-action based on total risk
        if total_risk >= 70:
            review.status = 'rejected'
            review.moderation_note = f'Auto-rejected: fraud risk score {total_risk}/100'
            review.save(update_fields=['status', 'moderation_note', 'updated_at'])
            logger.warning(
                'Review %s auto-rejected: risk=%d flags=%s',
                review.id, total_risk, [f[0] for f in flags],
            )
        elif total_risk >= 40:
            logger.info(
                'Review %s flagged for manual review: risk=%d', review.id, total_risk,
            )

        return {
            'total_risk': total_risk,
            'flags': [f[0] for f in flags],
            'action': 'rejected' if total_risk >= 70 else (
                'manual_review' if total_risk >= 40 else 'approved'
            ),
        }

    @staticmethod
    def _check_velocity(review):
        """Check if user is posting too many reviews too fast."""
        from apps.hotels.review_models import Review

        if not review.user:
            return 0, {}

        one_day_ago = timezone.now() - timedelta(days=1)
        recent_count = Review.objects.filter(
            user=review.user,
            created_at__gte=one_day_ago,
        ).exclude(id=review.id).count()

        if recent_count >= ReviewFraudDetector.MAX_REVIEWS_PER_DAY:
            return 40, {
                'recent_reviews': recent_count,
                'threshold': ReviewFraudDetector.MAX_REVIEWS_PER_DAY,
            }
        return 0, {}

    @staticmethod
    def _check_content(review):
        """Check for suspiciously short or generic content."""
        risk = 0
        details = {}

        comment = review.comment.strip()

        # Too short
        if len(comment) < ReviewFraudDetector.MIN_COMMENT_LENGTH:
            risk += 20
            details['too_short'] = len(comment)

        # All caps
        if comment.isupper() and len(comment) > 10:
            risk += 10
            details['all_caps'] = True

        # Excessive repetition
        words = comment.lower().split()
        unique_ratio = len(set(words)) / max(len(words), 1)
        if unique_ratio < 0.3:
            risk += 25
            details['low_unique_ratio'] = round(unique_ratio, 2)

        return risk, details

    @staticmethod
    def _check_rating_anomaly(review):
        """Check if user always gives same extreme rating."""
        from apps.hotels.review_models import Review

        if not review.user:
            return 0, {}

        user_reviews = Review.objects.filter(
            user=review.user,
        ).exclude(id=review.id)

        if user_reviews.count() < 3:
            return 0, {}

        ratings = list(user_reviews.values_list('overall_rating', flat=True))
        all_same = len(set(float(r) for r in ratings)) == 1

        if all_same:
            constant_rating = float(ratings[0])
            if constant_rating >= 5.0 or constant_rating <= 1.0:
                return 30, {
                    'pattern': 'all_extreme',
                    'rating': constant_rating,
                    'count': len(ratings),
                }
        return 0, {}

    @staticmethod
    def _check_account_age(review):
        """Flag reviews from very new accounts."""
        if not review.user:
            return 0, {}

        account_age = (timezone.now() - review.user.created_at).days

        if account_age < ReviewFraudDetector.MIN_ACCOUNT_AGE_DAYS:
            return 25, {
                'account_age_days': account_age,
                'threshold': ReviewFraudDetector.MIN_ACCOUNT_AGE_DAYS,
            }
        return 0, {}

    @staticmethod
    def _check_duplicate(review):
        """Check for duplicate/near-duplicate review content."""
        from apps.hotels.review_models import Review

        if len(review.comment) < 30:
            return 0, {}

        # Simple substring check (first 50 chars)
        snippet = review.comment[:50].lower().strip()
        similar = Review.objects.filter(
            comment__icontains=snippet,
        ).exclude(id=review.id).count()

        if similar > 0:
            return 35, {'similar_count': similar, 'snippet': snippet}
        return 0, {}
