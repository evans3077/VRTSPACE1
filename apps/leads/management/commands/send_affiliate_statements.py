from datetime import date

from django.core.management.base import BaseCommand

from apps.leads.affiliate import send_affiliate_monthly_statement
from apps.leads.models import Affiliate


class Command(BaseCommand):
    help = "Email monthly payout statements to all active affiliates."

    def add_arguments(self, parser):
        today = date.today()
        parser.add_argument(
            "--year",
            type=int,
            default=today.year,
            help="Statement year (default: current year)",
        )
        parser.add_argument(
            "--month",
            type=int,
            default=today.month,
            help="Statement month 1-12 (default: current month)",
        )
        parser.add_argument(
            "--code",
            type=str,
            default="",
            help="Limit to a single affiliate by code (optional)",
        )

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]
        code = options["code"].strip()

        qs = Affiliate.objects.filter(is_active=True)
        if code:
            qs = qs.filter(code=code)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No matching active affiliates found."))
            return

        for affiliate in qs:
            ok = send_affiliate_monthly_statement(affiliate, year, month)
            if ok:
                self.stdout.write(
                    self.style.SUCCESS(f"  Sent statement to {affiliate.name} <{affiliate.email}>")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"  Failed to send statement to {affiliate.name} <{affiliate.email}>")
                )
