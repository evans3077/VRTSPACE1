"""Run from Render Shell (or locally with SENTRY_DSN set) to verify
that Sentry is correctly capturing exceptions.

Usage:
    python manage.py sentry_test
    python manage.py sentry_test --message "deploy 2026-05-21"

The command:
  1. Captures an explicit "ping" message (so you see a non-error event too)
  2. Captures an exception via ``capture_exception``
  3. Raises a final ZeroDivisionError so Django's error handler also fires
     it through the Sentry middleware (belt + suspenders)

If SENTRY_DSN isn't configured, the command warns and exits cleanly.
"""

from __future__ import annotations

import os
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify Sentry capture is wired correctly by sending a ping + raising a test exception."

    def add_arguments(self, parser):
        parser.add_argument(
            "--message",
            default="sentry_test ping",
            help="Custom marker attached to the captured event (default: 'sentry_test ping').",
        )
        parser.add_argument(
            "--no-raise",
            action="store_true",
            help="Skip the final raise — useful for CI smoke tests.",
        )

    def handle(self, *args, **options):
        dsn = (os.environ.get("SENTRY_DSN") or "").strip()
        if not dsn:
            self.stdout.write(self.style.WARNING(
                "SENTRY_DSN is not set in the environment. "
                "Set it in Render's dashboard or your local .env, then re-run."
            ))
            return

        try:
            import sentry_sdk
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "sentry_sdk is not installed. Add `sentry-sdk[django]` to requirements.txt."
            ))
            sys.exit(1)

        marker = options["message"]
        # 1. Send a plain message so we can confirm reception without an exception
        sentry_sdk.capture_message(f"[sentry_test] {marker}", level="info")
        self.stdout.write(self.style.SUCCESS(f"OK Sent info message: {marker!r}"))

        # 2. Capture an exception via the explicit API
        try:
            raise RuntimeError(f"[sentry_test] explicit RuntimeError: {marker}")
        except RuntimeError as exc:
            sentry_sdk.capture_exception(exc)
            self.stdout.write(self.style.SUCCESS("OK Sent explicit exception via capture_exception"))

        # 3. Make sure the queue flushes before exit
        flushed = sentry_sdk.flush(timeout=5.0)
        self.stdout.write(self.style.SUCCESS(f"OK flushed (timeout 5s, returned {flushed})"))

        if options["no_raise"]:
            self.stdout.write("--no-raise set — skipping final raise.")
            return

        self.stdout.write("")
        self.stdout.write(
            "Now raising a final ZeroDivisionError so Django's middleware "
            "captures it through Sentry too. Check your Sentry dashboard within 30s."
        )
        # Intentional final raise — this is captured by Sentry's
        # auto-instrumentation (Django integration).
        _ = 1 / 0
