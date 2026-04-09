from django.core.mail import EmailMessage
from django.utils import timezone

from apps.leads.billing import can_access_audit_feature

from .audit_exports import build_absolute_app_url, get_or_create_audit_share_link
from .models import WorkspaceAuditSchedule
from .pdf_reports import build_audit_report_pdf


def normalize_recipient_list(values):
    recipients = []
    for value in values or []:
        email = str(value).strip().lower()
        if email and email not in recipients:
            recipients.append(email)
    return recipients


def get_schedule_recipients(schedule):
    if not schedule:
        return []
    return normalize_recipient_list(schedule.report_recipients)


def send_audit_report_email(*, audit_run, recipients, change_report=None, share_link=None, subject_prefix="Audit report"):
    recipients = normalize_recipient_list(recipients)
    if not recipients:
        return 0

    share_url = ""
    if share_link:
        share_url = build_absolute_app_url(f"/share/audits/{share_link.token}/")
    lines = [
        f"{subject_prefix} for {audit_run.normalized_domain}",
        "",
        f"Overall score: {audit_run.overall_score}",
        f"Pages crawled: {audit_run.pages_crawled}",
        f"Completed at: {audit_run.completed_at or timezone.now()}",
    ]
    if change_report:
        lines.extend(
            [
                "",
                change_report.summary.get("headline", ""),
                f"New issues: {change_report.new_issue_count}",
                f"Resolved issues: {change_report.resolved_issue_count}",
            ]
        )
    if share_url:
        lines.extend(["", f"Shareable report link: {share_url}"])
    lines.extend(["", "The full PDF report is attached to this email."])

    message = EmailMessage(
        subject=f"{subject_prefix}: {audit_run.normalized_domain}",
        body="\n".join(lines),
        to=recipients,
    )
    message.attach(
        f"audit-report-{audit_run.normalized_domain or audit_run.pk}.pdf",
        build_audit_report_pdf(audit_run),
        "application/pdf",
    )
    message.send(fail_silently=False)
    return len(recipients)


def deliver_workspace_audit_notifications(*, audit_run, project=None, change_report=None):
    if not project:
        return {"reports_sent": 0, "alerts_sent": 0}

    schedule = WorkspaceAuditSchedule.objects.filter(project=project).first()
    recipients = get_schedule_recipients(schedule)
    if not schedule or not recipients:
        return {"reports_sent": 0, "alerts_sent": 0}

    reports_sent = 0
    alerts_sent = 0
    email_allowed, _ = can_access_audit_feature(project.owner, "email_reports_enabled")
    share_allowed, _ = can_access_audit_feature(project.owner, "stakeholder_sharing_enabled")
    share_link = get_or_create_audit_share_link(audit_run, created_by=project.owner) if share_allowed else None

    if schedule.email_reports_enabled and email_allowed:
        reports_sent = send_audit_report_email(
            audit_run=audit_run,
            recipients=recipients,
            change_report=change_report,
            share_link=share_link,
            subject_prefix="Scheduled audit report",
        )

    alert_required = False
    if change_report and schedule.alert_on_score_drop and change_report.overall_score_delta < 0:
        alert_required = True
    if change_report and schedule.alert_on_new_issues and change_report.new_issue_count > 0:
        alert_required = True

    if alert_required and email_allowed:
        alerts_sent = send_audit_report_email(
            audit_run=audit_run,
            recipients=recipients,
            change_report=change_report,
            share_link=share_link,
            subject_prefix="Audit alert",
        )

    return {"reports_sent": reports_sent, "alerts_sent": alerts_sent}
