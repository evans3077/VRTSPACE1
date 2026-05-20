"""
Send the weekly AI Visibility digest to every project with email reports enabled.

Run:
    python manage.py process_weekly_digests
    python manage.py process_weekly_digests --dry-run     # build payloads, log, don't send
    python manage.py process_weekly_digests --project 7   # just one project
    python manage.py process_weekly_digests --to me@x.com # override recipient (testing)
"""

from __future__ import annotations

import os
import sys

# Windows console — UTF-8 for unicode arrows in log output
if sys.platform == "win32" and os.environ.get("PYTHONIOENCODING") is None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse

from apps.aeo.digest_service import build_weekly_digest, get_digest_recipients
from apps.leads.models import ClientProject
from apps.tools.audit_exports import build_absolute_app_url


class Command(BaseCommand):
    help = "Build and send the weekly AI Visibility digest to opted-in projects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build the digest payloads and log a summary but don't send.",
        )
        parser.add_argument(
            "--project",
            type=int,
            default=None,
            help="Only process this single project ID.",
        )
        parser.add_argument(
            "--to",
            type=str,
            default=None,
            help="Override recipient email (testing).",
        )
        parser.add_argument(
            "--include-empty",
            action="store_true",
            help="Send even if there's no activity this week (default: skip).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        project_id = options.get("project")
        override_to = options.get("to")
        include_empty = options.get("include_empty")

        qs = ClientProject.objects.filter(
            owner__isnull=False,
        ).select_related("owner", "audit_schedule")
        if project_id:
            qs = qs.filter(pk=project_id)
        else:
            # Default policy: only projects with email reports enabled on their schedule
            qs = qs.filter(audit_schedule__email_reports_enabled=True)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No projects matched the digest criteria."))
            return

        sent = 0
        skipped_empty = 0
        skipped_no_recipient = 0
        failed = 0

        for project in qs:
            try:
                payload = build_weekly_digest(project)
            except Exception as exc:  # pragma: no cover - defensive
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"FAIL build for project {project.pk}: {exc}")
                )
                continue

            if not payload["has_data"] and not include_empty:
                skipped_empty += 1
                self.stdout.write(
                    f"  - skip (no activity): {project.name} (#{project.pk})"
                )
                continue

            recipients = [override_to] if override_to else get_digest_recipients(project)
            if not recipients:
                skipped_no_recipient += 1
                self.stdout.write(
                    f"  - skip (no recipient): {project.name} (#{project.pk})"
                )
                continue

            # Build URLs used in the email
            try:
                dashboard_path = reverse("tools:workspace-dashboard")
            except Exception:
                dashboard_path = "/workspace/"
            payload["dashboard_url"] = build_absolute_app_url(dashboard_path)
            payload["unsubscribe_url"] = ""  # TODO: real prefs page

            subject = (
                f"AI Visibility weekly: {payload['aeo_score']}/100 "
                f"({'+' if payload['aeo_score_delta'] >= 0 else ''}{payload['aeo_score_delta']}) "
                f"- {payload['brand_name']}"
            )
            html_body = render_to_string("emails/weekly_digest.html", payload)
            text_body = self._render_text(payload)

            if dry_run:
                sent += 1
                self.stdout.write(
                    f"  - [DRY] would send to {recipients}: subject='{subject[:80]}'"
                )
                continue

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@vrtspaceagency.com")
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=recipients,
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=False)
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(f"OK sent to {recipients[0]}: {payload['brand_name']}")
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"FAIL send for project {project.pk}: {exc}")
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Processed {total} - sent {sent}, "
            f"skipped {skipped_empty} (no activity), "
            f"{skipped_no_recipient} (no recipient), "
            f"failed {failed}."
        ))

    @staticmethod
    def _render_text(payload: dict) -> str:
        """Plain-text fallback for clients that don't render HTML."""
        lines = [
            f"AI Visibility weekly digest -- {payload['brand_name']}",
            f"Period: {payload['period_start']} -- {payload['period_end']}",
            "",
            f"AI Visibility Score: {payload['aeo_score']}/100 "
            f"({'+' if payload['aeo_score_delta'] >= 0 else ''}{payload['aeo_score_delta']} vs last week)",
            f"Citations this week: {payload['citations_this_week']} "
            f"({'+' if payload['citation_delta'] >= 0 else ''}{payload['citation_delta']})",
            f"Share of voice: {payload['share_pct_this_week']}% "
            f"({'+' if payload['share_pct_delta'] >= 0 else ''}{payload['share_pct_delta']} pts)",
            "",
        ]
        if payload["new_wins"]:
            lines.append("Started getting cited for:")
            for w in payload["new_wins"]:
                lines.append(f"  + {w}")
            lines.append("")
        if payload["new_losses"]:
            lines.append("Stopped being cited for:")
            for w in payload["new_losses"]:
                lines.append(f"  - {w}")
            lines.append("")
        if payload["biggest_opportunity"]:
            op = payload["biggest_opportunity"]
            lines.append(
                f"Biggest opportunity: '{op['prompt']}' -- "
                f"{op['gap']} pts to a citation on {op['engine']}"
            )
            lines.append("")
        lines.append("Open your workspace:")
        lines.append(payload.get("dashboard_url", ""))
        return "\n".join(lines)
