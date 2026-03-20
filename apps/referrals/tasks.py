from celery import shared_task
from django.contrib.auth import get_user_model

from apps.referrals.models import ReferralProfile
from apps.referrals.services import get_or_create_profile


@shared_task
def backfill_missing_profiles():
    user_model = get_user_model()
    created = 0
    for user in user_model.objects.all().iterator():
        try:
            user.referrals_profile
            was_created = False
        except ReferralProfile.DoesNotExist:
            get_or_create_profile(user)
            was_created = True
        if was_created:
            created += 1
    return {'created_profiles': created}
