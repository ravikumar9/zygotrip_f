from django.db import models
from django.utils import timezone
from .models import Promo


def get_active_promo(code):
    today = timezone.now().date()
    return Promo.objects.filter(
        code__iexact=code,
        is_active=True,
    ).filter(
        (models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=today)),
        (models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=today)),
    ).first()