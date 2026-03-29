import calendar
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.leads.billing import BillingError, create_workspace_rerun_for_user, get_effective_capabilities
from apps.leads.models import ClientProject

from .models import WorkspaceAuditSchedule


def get_workspace_schedule(project):
    if not getattr(project, "pk", None):
        return None
    return WorkspaceAuditSchedule.objects.filter(project=project).select_related("project__owner").first()


def calculate_next_run_at(cadence, *, from_time=None):
    from_time = from_time or timezone.now()
    if cadence == WorkspaceAuditSchedule.Cadence.MONTHLY:
        next_month = from_time.month + 1
        year = from_time.year
        if next_month > 12:
            next_month = 1
            year += 1
        day = min(from_time.day, calendar.monthrange(year, next_month)[1])
        return from_time.replace(year=year, month=next_month, day=day)
    return from_time + timedelta(days=7)


def can_manage_recurring_audits(user):
    capabilities = get_effective_capabilities(user)
    if not settings.AUDIT_TIER_ENFORCEMENT:
        return True, capabilities
    return capabilities["recurring_audits_enabled"], capabilities


def update_workspace_schedule(*, user, cadence, is_active):
    project = (
        ClientProject.objects.select_related("audit_request", "owner")
        .filter(owner=user)
        .order_by("-updated_at")
        .first()
    )
    if not project:
        raise BillingError("No workspace project is attached to this account yet.")

    allowed, _capabilities = can_manage_recurring_audits(user)
    if is_active and not allowed:
        raise BillingError("Recurring audits require a plan that supports automation.")

    schedule, _created = WorkspaceAuditSchedule.objects.get_or_create(project=project)
    schedule.cadence = cadence
    schedule.is_active = is_active
    if is_active:
        schedule.next_run_at = calculate_next_run_at(cadence, from_time=timezone.now())
        schedule.last_error_message = ""
    else:
        schedule.next_run_at = None
    schedule.save()
    return schedule


def process_due_workspace_schedules(*, now=None, enqueue_fn):
    now = now or timezone.now()
    due_schedules = list(
        WorkspaceAuditSchedule.objects.select_related("project__owner", "project__audit_request")
        .filter(is_active=True, next_run_at__isnull=False, next_run_at__lte=now)
        .order_by("next_run_at")
    )

    summary = {"processed": 0, "queued": 0, "skipped": 0, "failed": 0}

    for schedule in due_schedules:
        summary["processed"] += 1
        owner = schedule.project.owner
        if not owner:
            schedule.last_error_message = "Recurring audit skipped because the workspace has no owner."
            schedule.next_run_at = calculate_next_run_at(schedule.cadence, from_time=now)
            schedule.save(update_fields=["last_error_message", "next_run_at", "updated_at"])
            summary["skipped"] += 1
            continue

        allowed, _capabilities = can_manage_recurring_audits(owner)
        if not allowed:
            schedule.last_error_message = "Recurring audit skipped because the current plan does not allow automation."
            schedule.next_run_at = calculate_next_run_at(schedule.cadence, from_time=now)
            schedule.save(update_fields=["last_error_message", "next_run_at", "updated_at"])
            summary["skipped"] += 1
            continue

        try:
            audit_run = create_workspace_rerun_for_user(owner, project=schedule.project)
            enqueue_fn(audit_run.pk)
            schedule.last_run_at = now
            schedule.last_audit_run = audit_run
            schedule.last_error_message = ""
            schedule.next_run_at = calculate_next_run_at(schedule.cadence, from_time=now)
            schedule.save(
                update_fields=[
                    "last_run_at",
                    "last_audit_run",
                    "last_error_message",
                    "next_run_at",
                    "updated_at",
                ]
            )
            summary["queued"] += 1
        except BillingError as exc:
            schedule.last_error_message = str(exc)
            schedule.next_run_at = calculate_next_run_at(schedule.cadence, from_time=now)
            schedule.save(update_fields=["last_error_message", "next_run_at", "updated_at"])
            summary["failed"] += 1

    return summary
