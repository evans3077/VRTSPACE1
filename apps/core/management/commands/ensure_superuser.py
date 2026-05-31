"""
Creates or promotes the primary admin superuser account.

Set SUPERUSER_EMAIL and SUPERUSER_PASSWORD env vars, then run:
    python manage.py ensure_superuser

On Render: add those env vars in the dashboard, run once from Shell tab.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Ensure the primary superuser account exists."

    def handle(self, *args, **options):
        email = os.environ.get("SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("SUPERUSER_PASSWORD", "").strip()
        if not email or not password:
            raise CommandError(
                "Set SUPERUSER_EMAIL and SUPERUSER_PASSWORD env vars before running."
            )
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email},
        )
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        status = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Superuser {status}: {email}"))
