import os
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections
from django.utils import timezone

from .models import AuditRun
from .services import run_public_site_audit


AUDIT_BACKGROUND_WORKERS = max(1, int(os.environ.get("AUDIT_BACKGROUND_WORKERS", "2")))
audit_executor = ThreadPoolExecutor(max_workers=AUDIT_BACKGROUND_WORKERS)


def enqueue_public_site_audit(audit_run_id):
    audit_executor.submit(_run_public_site_audit_job, audit_run_id)


def _run_public_site_audit_job(audit_run_id):
    close_old_connections()
    try:
        audit_run = AuditRun.objects.select_related("audit_request").get(pk=audit_run_id)
        run_public_site_audit(audit_run=audit_run)

        project = None
        if audit_run.audit_request_id and audit_run.status == AuditRun.Status.COMPLETED:
            from apps.leads.services import sync_client_project_from_audit_run
            from .reporting import create_audit_change_report

            project = sync_client_project_from_audit_run(audit_run)
            create_audit_change_report(audit_run, project=project)
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
