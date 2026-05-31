"""
Usage:
    python manage.py create_test_affiliate

Creates a test affiliate account for QA / demo purposes.
Safe to run multiple times — will reset the password if the user already exists.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.affiliates.models import Affiliate

TEST_EMAIL = "affiliate.test@vrtspace.co"
TEST_PASSWORD = "TestAffiliate2026!"
TEST_SLUG = "testpartner"
TEST_NAME = "Test Partner"


class Command(BaseCommand):
    help = "Create (or reset) a test affiliate account for QA."

    def handle(self, *args, **options):
        User = get_user_model()

        user, created = User.objects.get_or_create(
            email=TEST_EMAIL,
            defaults={"username": TEST_EMAIL},
        )
        user.set_password(TEST_PASSWORD)
        if not hasattr(user, "last_login") or user.last_login is None:
            user.last_login = timezone.now()
        user.save()

        affiliate, aff_created = Affiliate.objects.get_or_create(
            slug=TEST_SLUG,
            defaults={
                "user": user,
                "display_name": TEST_NAME,
                "contact_email": TEST_EMAIL,
                "status": Affiliate.Status.ACTIVE,
            },
        )
        if not aff_created:
            affiliate.user = user
            affiliate.status = Affiliate.Status.ACTIVE
            affiliate.save(update_fields=["user", "status", "updated_at"])

        self.stdout.write(self.style.SUCCESS("Test affiliate ready."))
        self.stdout.write(f"  Login email : {TEST_EMAIL}")
        self.stdout.write(f"  Password    : {TEST_PASSWORD}")
        self.stdout.write(f"  Referral URL: /r/{TEST_SLUG}/")
        self.stdout.write(f"  Dashboard   : /workspace/affiliates/")
