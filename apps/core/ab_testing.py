"""
Enhanced A/B Testing & Conversion Funnel Engine.

Builds on the existing ABTestVariant model to provide:
- Experiment management with traffic allocation
- Statistical significance calculation (chi-squared)
- Multi-step funnel analysis with drop-off identification
- Revenue per user metrics
- Experiment results API
"""
import hashlib
import logging
import math
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, Sum, F, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.analytics')


class Experiment(TimeStampedModel):
    """A/B test experiment definition."""

    STATUS_DRAFT = 'draft'
    STATUS_RUNNING = 'running'
    STATUS_PAUSED = 'paused'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    CATEGORY_RANKING = 'ranking'
    CATEGORY_UI = 'ui'
    CATEGORY_PRICING = 'pricing'
    CATEGORY_CHOICES = [
        (CATEGORY_RANKING, 'Search Ranking'),
        (CATEGORY_UI, 'UI / UX'),
        (CATEGORY_PRICING, 'Pricing Strategy'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_UI)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Variants as JSON: {"control": 50, "variant_a": 25, "variant_b": 25}
    # Values are traffic percentage allocation
    variants = models.JSONField(default=dict)

    # Targeting
    traffic_percentage = models.IntegerField(
        default=100, help_text='% of total traffic included in experiment',
    )
    target_metric = models.CharField(
        max_length=50, default='conversion_rate',
        help_text='Primary metric to optimize',
    )

    # Timing
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # Results cache
    winner = models.CharField(max_length=50, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['status', '-created_at'], name='experiment_status_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


def assign_variant(experiment_name, user_id=None, session_id=None):
    """
    Deterministically assign a user/session to an experiment variant.
    Uses consistent hashing so the same user always sees the same variant.
    """
    try:
        experiment = Experiment.objects.get(name=experiment_name, status='running')
    except Experiment.DoesNotExist:
        return 'control'

    # Create deterministic hash from user/session + experiment
    key = f"{experiment_name}:{user_id or session_id or 'anon'}"
    hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100

    # Check if user is in the experiment traffic
    if hash_val >= experiment.traffic_percentage:
        return None  # Not in experiment

    # Assign to variant based on traffic allocation
    cumulative = 0
    for variant, pct in experiment.variants.items():
        cumulative += pct
        if hash_val < cumulative:
            return variant

    return 'control'


def record_conversion(experiment_name, variant, user=None, session_id='', value=None):
    """Record a conversion event for an A/B test variant."""
    from apps.core.analytics import ABTestVariant

    ABTestVariant.objects.create(
        experiment_name=experiment_name,
        variant=variant,
        user=user,
        session_id=session_id,
        converted=True,
        conversion_value=value,
    )


def get_experiment_results(experiment_name):
    """
    Calculate experiment results with statistical significance.
    Returns per-variant metrics and chi-squared test result.
    """
    from apps.core.analytics import ABTestVariant

    variants = ABTestVariant.objects.filter(
        experiment_name=experiment_name,
    ).values('variant').annotate(
        total=Count('id'),
        conversions=Count('id', filter=Q(converted=True)),
        revenue=Sum('conversion_value', filter=Q(converted=True)),
    )

    results = {}
    for v in variants:
        total = v['total']
        conversions = v['conversions']
        rate = (conversions / total * 100) if total > 0 else 0
        results[v['variant']] = {
            'total_participants': total,
            'conversions': conversions,
            'conversion_rate': round(rate, 2),
            'revenue': str(v['revenue'] or 0),
            'avg_revenue_per_user': str(
                round((v['revenue'] or 0) / max(total, 1), 2)
            ),
        }

    # Chi-squared significance test (control vs each variant)
    significance = {}
    control = results.get('control', {})
    if control:
        for variant_name, data in results.items():
            if variant_name == 'control':
                continue
            chi2 = _chi_squared(
                control['total_participants'], control['conversions'],
                data['total_participants'], data['conversions'],
            )
            significance[variant_name] = {
                'chi_squared': round(chi2, 4),
                'significant_95': chi2 > 3.841,  # 1 degree of freedom, p < 0.05
                'significant_99': chi2 > 6.635,  # p < 0.01
            }

    return {
        'experiment': experiment_name,
        'variants': results,
        'significance': significance,
    }


def _chi_squared(n1, c1, n2, c2):
    """Calculate chi-squared statistic for 2x2 contingency table."""
    if n1 == 0 or n2 == 0:
        return 0

    nc1 = n1 - c1  # non-converted in control
    nc2 = n2 - c2  # non-converted in variant
    total = n1 + n2
    total_converted = c1 + c2
    total_not = nc1 + nc2

    if total_converted == 0 or total_not == 0:
        return 0

    # Expected values
    e_c1 = n1 * total_converted / total
    e_nc1 = n1 * total_not / total
    e_c2 = n2 * total_converted / total
    e_nc2 = n2 * total_not / total

    chi2 = 0
    for observed, expected in [(c1, e_c1), (nc1, e_nc1), (c2, e_c2), (nc2, e_nc2)]:
        if expected > 0:
            chi2 += (observed - expected) ** 2 / expected

    return chi2


# ============================================================================
# Multi-Step Funnel Analysis
# ============================================================================

BOOKING_FUNNEL_STAGES = [
    'search',
    'property_view',
    'room_select',
    'booking_context_created',
    'payment_initiated',
    'payment_success',
    'booking_confirmed',
]


def analyze_funnel(start_date, end_date, vertical='hotel', city=None):
    """
    Analyze the complete booking funnel with drop-off points.
    Tracks user sessions through each stage.
    """
    from apps.core.analytics import AnalyticsEvent

    filters = Q(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    if city:
        filters &= Q(city__iexact=city)

    events = AnalyticsEvent.objects.filter(filters)

    stages = {}
    for stage in BOOKING_FUNNEL_STAGES:
        stage_events = events.filter(event_type=stage)
        stages[stage] = {
            'count': stage_events.count(),
            'unique_sessions': stage_events.values('session_id').distinct().count(),
            'unique_users': stage_events.exclude(user=None).values('user').distinct().count(),
        }

    # Calculate drop-off between stages
    dropoffs = []
    for i in range(1, len(BOOKING_FUNNEL_STAGES)):
        prev_stage = BOOKING_FUNNEL_STAGES[i - 1]
        curr_stage = BOOKING_FUNNEL_STAGES[i]
        prev_count = stages[prev_stage]['count']
        curr_count = stages[curr_stage]['count']
        drop = prev_count - curr_count
        drop_pct = round((drop / prev_count * 100), 1) if prev_count > 0 else 0

        dropoffs.append({
            'from': prev_stage,
            'to': curr_stage,
            'dropped': drop,
            'drop_percentage': drop_pct,
            'conversion_rate': round((curr_count / prev_count * 100), 1) if prev_count > 0 else 0,
        })

    # Revenue per unique user
    total_revenue = events.filter(
        event_type='booking_confirmed',
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_users = events.values('session_id').distinct().count()
    rpu = round(float(total_revenue) / max(total_users, 1), 2)

    return {
        'period': {'start': str(start_date), 'end': str(end_date)},
        'vertical': vertical,
        'city': city,
        'stages': stages,
        'dropoffs': dropoffs,
        'revenue_per_user': rpu,
        'overall_conversion': round(
            stages.get('booking_confirmed', {}).get('count', 0) /
            max(stages.get('search', {}).get('count', 0), 1) * 100,
            2,
        ),
    }
