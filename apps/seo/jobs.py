from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.content.services import sync_project_editorial_tasks
from apps.leads.billing import record_usage
from apps.leads.models import UsageRecord

from .backlinks import refresh_project_backlink_intelligence
from .services import refresh_project_seo_intelligence, sync_project_seo_campaigns


seo_executor = ThreadPoolExecutor(max_workers=settings.SEO_BACKGROUND_WORKERS)


def _set_profile_refresh_state(profile, *, status, error_message=""):
    metadata = dict(profile.metadata or {})
    metadata["refresh_status"] = status
    metadata["refresh_error"] = error_message
    metadata["refresh_updated_at"] = timezone.now().isoformat()
    if status == "completed":
        metadata["last_completed_at"] = timezone.now().isoformat()
    profile.metadata = metadata
    profile.save(update_fields=["metadata", "updated_at"])


def _set_profile_backlink_state(profile, *, status, error_message=""):
    metadata = dict(profile.metadata or {})
    metadata["backlink_refresh_status"] = status
    metadata["backlink_refresh_error"] = error_message
    metadata["backlink_refresh_updated_at"] = timezone.now().isoformat()
    profile.metadata = metadata
    profile.save(update_fields=["metadata", "updated_at"])


def _backlink_refresh_requested(profile):
    metadata = dict(profile.metadata or {})
    return metadata.get("backlink_refresh_requested", True)


def enqueue_project_seo_refresh(project_id):
    seo_executor.submit(_run_project_seo_refresh_job, project_id)


def enqueue_project_backlink_refresh(project_id, *, context_snapshot_id=None, opportunity_snapshot_id=None):
    seo_executor.submit(
        _run_project_backlink_refresh_job,
        project_id,
        context_snapshot_id,
        opportunity_snapshot_id,
    )


def _run_project_seo_refresh_job(project_id):
    close_old_connections()
    try:
        from apps.leads.models import ClientProject

        project = (
            ClientProject.objects.select_related("seo_profile", "latest_audit_run", "owner")
            .filter(pk=project_id)
            .first()
        )
        if not project or not getattr(project, "seo_profile", None):
            return
        _set_profile_refresh_state(project.seo_profile, status="running")
        if _backlink_refresh_requested(project.seo_profile):
            _set_profile_backlink_state(project.seo_profile, status="queued")
        else:
            _set_profile_backlink_state(project.seo_profile, status="skipped")
        context_snapshot, opportunity_snapshot = refresh_project_seo_intelligence(project)
        sync_project_seo_campaigns(
            project,
            context_snapshot=context_snapshot,
            opportunity_snapshot=opportunity_snapshot,
        )
        sync_project_editorial_tasks(project)
        if project.owner_id:
            record_usage(project.owner, UsageRecord.Metric.SEO_SNAPSHOT)
        _set_profile_refresh_state(project.seo_profile, status="completed")
        if not _backlink_refresh_requested(project.seo_profile):
            return
        if settings.SEO_BACKLINK_ASYNC:
            enqueue_project_backlink_refresh(
                project.pk,
                context_snapshot_id=getattr(context_snapshot, "pk", None),
                opportunity_snapshot_id=getattr(opportunity_snapshot, "pk", None),
            )
        else:
            _run_project_backlink_refresh_job(
                project.pk,
                getattr(context_snapshot, "pk", None),
                getattr(opportunity_snapshot, "pk", None),
            )
    except Exception as exc:
        try:
            from apps.leads.models import ClientProject

            project = (
                ClientProject.objects.select_related("seo_profile")
                .filter(pk=project_id)
                .first()
            )
            if project and getattr(project, "seo_profile", None):
                _set_profile_refresh_state(
                    project.seo_profile,
                    status="failed",
                    error_message=str(exc)[:500],
                )
        finally:
            close_old_connections()
    finally:
        close_old_connections()


def _run_project_backlink_refresh_job(project_id, context_snapshot_id=None, opportunity_snapshot_id=None):
    close_old_connections()
    try:
        from apps.leads.models import ClientProject
        from .models import SEOContextSnapshot, SEOOpportunitySnapshot

        project = (
            ClientProject.objects.select_related("seo_profile", "latest_audit_run")
            .filter(pk=project_id)
            .first()
        )
        if not project or not getattr(project, "seo_profile", None):
            return
        if not _backlink_refresh_requested(project.seo_profile):
            _set_profile_backlink_state(project.seo_profile, status="skipped")
            return
        _set_profile_backlink_state(project.seo_profile, status="running")
        context_snapshot = None
        opportunity_snapshot = None
        if context_snapshot_id:
            context_snapshot = SEOContextSnapshot.objects.filter(pk=context_snapshot_id).first()
        if opportunity_snapshot_id:
            opportunity_snapshot = SEOOpportunitySnapshot.objects.filter(pk=opportunity_snapshot_id).first()
        refresh_project_backlink_intelligence(
            project,
            context_snapshot=context_snapshot,
            opportunity_snapshot=opportunity_snapshot,
        )
        _set_profile_backlink_state(project.seo_profile, status="completed")
    except Exception as exc:
        try:
            from apps.leads.models import ClientProject

            project = (
                ClientProject.objects.select_related("seo_profile")
                .filter(pk=project_id)
                .first()
            )
            if project and getattr(project, "seo_profile", None):
                _set_profile_backlink_state(
                    project.seo_profile,
                    status="failed",
                    error_message=str(exc)[:500],
                )
        finally:
            close_old_connections()
    finally:
        close_old_connections()
