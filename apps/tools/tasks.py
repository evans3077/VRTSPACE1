from celery import shared_task


@shared_task
def run_public_site_audit_task(audit_run_id):
    from .jobs import run_public_site_audit_job

    return run_public_site_audit_job(audit_run_id)


@shared_task
def send_audit_report_email_task(audit_run_id):
    from apps.leads.services import sync_client_project_from_audit_run
    from .models import AuditRun
    from .notifications import deliver_workspace_audit_notifications
    from .reporting import create_audit_change_report

    audit_run = AuditRun.objects.select_related("audit_request").get(pk=audit_run_id)
    project = sync_client_project_from_audit_run(audit_run) if audit_run.audit_request_id else None
    change_report = getattr(audit_run, "change_report", None) or create_audit_change_report(audit_run, project=project)
    return deliver_workspace_audit_notifications(
        audit_run=audit_run,
        project=project,
        change_report=change_report,
    )
