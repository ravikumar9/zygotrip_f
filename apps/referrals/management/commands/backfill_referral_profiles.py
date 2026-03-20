from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.referrals.models import ReferralProfile
from apps.referrals.services import get_or_create_profile


class Command(BaseCommand):
    help = 'Ensure every user has a referral profile.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        created_count = 0
        for user in user_model.objects.all().iterator():
            try:
                user.referrals_profile
                created = False
            except ReferralProfile.DoesNotExist:
                get_or_create_profile(user)
                created = True
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Backfill completed. Created: {created_count}'))
