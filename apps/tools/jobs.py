import os
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import AuditRun
from .services import run_public_site_audit


AUDIT_BACKGROUND_WORKERS = max(1, int(os.environ.get("AUDIT_BACKGROUND_WORKERS", "2")))
audit_executor = ThreadPoolExecutor(max_workers=AUDIT_BACKGROUND_WORKERS)


def enqueue_public_site_audit(audit_run_id):
    if settings.AUDIT_USE_CELERY:
        from .tasks import run_public_site_audit_task

        run_public_site_audit_task.delay(audit_run_id)
        return
    audit_executor.submit(_run_public_site_audit_job, audit_run_id)


def run_public_site_audit_job(audit_run_id):
    close_old_connections()
    try:
        audit_run = AuditRun.objects.select_related("audit_request").get(pk=audit_run_id)
        run_public_site_audit(audit_run=audit_run)

        project = None
        if audit_run.audit_request_id and audit_run.status == AuditRun.Status.COMPLETED:
            from apps.leads.services import sync_client_project_from_audit_run
            from apps.content.services import sync_project_editorial_tasks
            from apps.seo.services import refresh_project_seo_intelligence
            from .notifications import deliver_workspace_audit_notifications
            from .reporting import create_audit_change_report

            project = sync_client_project_from_audit_run(audit_run)
            if project and getattr(project, "seo_profile", None):
                refresh_project_seo_intelligence(project)
                sync_project_editorial_tasks(project)
            change_report = create_audit_change_report(audit_run, project=project)
            deliver_workspace_audit_notifications(
                audit_run=audit_run,
                project=project,
                change_report=change_report,
            )
    except Exception as exc:
        try:
            audit_run = AuditRun.objects.get(pk=audit_run_id)
            audit_run.status = AuditRun.Status.FAILED
            audit_run.error_message = f"Audit worker failed: {exc}"
            audit_run.completed_at = timezone.now()
            audit_run.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        except AuditRun.DoesNotExist:
            pass
    finally:
        close_old_connections()


def _run_public_site_audit_job(audit_run_id):
    return run_public_site_audit_job(audit_run_id)
