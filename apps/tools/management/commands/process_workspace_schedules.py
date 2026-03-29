from django.core.management.base import BaseCommand

from apps.tools.automation import process_due_workspace_schedules
from apps.tools.jobs import enqueue_public_site_audit


class Command(BaseCommand):
    help = "Queue due recurring workspace audits."

    def handle(self, *args, **options):
        summary = process_due_workspace_schedules(enqueue_fn=enqueue_public_site_audit)
        self.stdout.write(
            self.style.SUCCESS(
                "Processed {processed} schedules, queued {queued}, skipped {skipped}, failed {failed}.".format(
                    **summary
                )
            )
        )
