from django.core.management.base import BaseCommand

from apps.content.services import sync_project_editorial_tasks
from apps.leads.models import ClientProject


class Command(BaseCommand):
    help = "Sync SEO-driven editorial queues for projects with SEO snapshots."

    def handle(self, *args, **options):
        processed = 0
        queued_items = 0
        for project in ClientProject.objects.select_related("seo_profile").all():
            if not getattr(project, "seo_profile", None):
                continue
            tasks = sync_project_editorial_tasks(project)
            processed += 1
            queued_items += len(tasks)

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced editorial queues for {processed} project(s) with {queued_items} tracked item(s)."
            )
        )
