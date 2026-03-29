from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.content.services import sync_project_editorial_tasks
from apps.leads.billing import record_usage
from apps.leads.models import UsageRecord

from .services import refresh_project_seo_intelligence


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


def enqueue_project_seo_refresh(project_id):
    seo_executor.submit(_run_project_seo_refresh_job, project_id)


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
        refresh_project_seo_intelligence(project)
        sync_project_editorial_tasks(project)
        if project.owner_id:
            record_usage(project.owner, UsageRecord.Metric.SEO_SNAPSHOT)
        _set_profile_refresh_state(project.seo_profile, status="completed")
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
