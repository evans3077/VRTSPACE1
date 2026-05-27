import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.content.services import sync_project_editorial_tasks
from apps.leads.billing import record_usage
from apps.leads.models import UsageRecord

from .backlinks import refresh_project_backlink_intelligence
from .services import refresh_project_seo_intelligence, sync_project_seo_campaigns

logger = logging.getLogger(__name__)

seo_executor = ThreadPoolExecutor(max_workers=settings.SEO_BACKGROUND_WORKERS)


# ---------------------------------------------------------------------------
# Stage Tracker
# ---------------------------------------------------------------------------

class _StageTracker:
    """
    Records per-stage start/end times during the SEO refresh job and writes
    them back to the profile metadata so the UI can show live stage state.

    Usage::
        tracker = _StageTracker(profile)
        tracker.start("discovery")
        ...
        tracker.finish("discovery")

    Stage names mirror the STAGE_BUDGET_* constants in settings.py:
      site_snapshot | discovery | competitor_crawl | analysis | opportunity | backlink
    """

    _BUDGETS = {
        "site_snapshot":   "STAGE_BUDGET_SITE_SNAPSHOT_SECONDS",
        "discovery":       "STAGE_BUDGET_DISCOVERY_SECONDS",
        "competitor_crawl":"STAGE_BUDGET_COMPETITOR_CRAWL_SECONDS",
        "analysis":        "STAGE_BUDGET_ANALYSIS_SECONDS",
        "opportunity":     "STAGE_BUDGET_OPPORTUNITY_SECONDS",
        "backlink":        "STAGE_BUDGET_BACKLINK_SECONDS",
    }

    def __init__(self, profile):
        self.profile = profile
        self._stages = {}
        self._job_start = time.monotonic()

    # --- public api ---

    def start(self, name):
        self._stages[name] = {
            "start": time.monotonic(),
            "elapsed": None,
            "status": "running",
        }
        self._flush()

    def finish(self, name, *, status="done"):
        stage = self._stages.get(name)
        if stage:
            stage["elapsed"] = round(time.monotonic() - stage["start"], 2)
            stage["status"] = status
            budget_attr = self._BUDGETS.get(name)
            if budget_attr:
                budget = getattr(settings, budget_attr, None)
                if budget and stage["elapsed"] > budget:
                    logger.warning(
                        "SEO refresh stage '%s' exceeded budget: %.1fs > %ds (project pk will appear in parent log)",
                        name, stage["elapsed"], budget,
                    )
                    stage["over_budget"] = True
        self._flush()

    def fail(self, name, error=""):
        self.finish(name, status=f"failed")
        if name in self._stages:
            self._stages[name]["error"] = str(error)[:200]
        self._flush()

    # --- helpers ---

    def elapsed_total(self):
        return time.monotonic() - self._job_start

    def over_total_budget(self):
        ceiling = getattr(settings, "STAGE_BUDGET_TOTAL_JOB_SECONDS", 300)
        return self.elapsed_total() > ceiling

    def stage_elapsed(self, name):
        stage = self._stages.get(name, {})
        return stage.get("elapsed") or 0

    def reporter(self, name, action):
        """Thin callable compatible with the (name, action) convention used in services."""
        if action == "start":
            self.start(name)
        elif action in ("done", "finish"):
            self.finish(name)
        elif action == "fail":
            self.fail(name)

    # --- persistence ---

    def _flush(self):
        try:
            metadata = dict(self.profile.metadata or {})
            metadata["refresh_stages"] = {
                stage: {
                    "elapsed": info.get("elapsed"),
                    "status": info.get("status"),
                    "over_budget": info.get("over_budget", False),
                }
                for stage, info in self._stages.items()
            }
            self.profile.metadata = metadata
            self.profile.save(update_fields=["metadata", "updated_at"])
        except Exception:
            # Never let flushing kill the job.
            pass

    def as_summary(self):
        return {
            name: {"elapsed": v.get("elapsed"), "status": v.get("status")}
            for name, v in self._stages.items()
        }


# ---------------------------------------------------------------------------
# Profile state helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Executor helpers
# ---------------------------------------------------------------------------

def enqueue_project_seo_refresh(project_id):
    seo_executor.submit(_run_project_seo_refresh_job, project_id)


def enqueue_project_backlink_refresh(project_id, *, context_snapshot_id=None, opportunity_snapshot_id=None):
    seo_executor.submit(
        _run_project_backlink_refresh_job,
        project_id,
        context_snapshot_id,
        opportunity_snapshot_id,
    )


# ---------------------------------------------------------------------------
# Main SEO refresh job
# ---------------------------------------------------------------------------

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

        profile = project.seo_profile
        _set_profile_refresh_state(profile, status="running")
        if _backlink_refresh_requested(profile):
            _set_profile_backlink_state(profile, status="queued")
        else:
            _set_profile_backlink_state(profile, status="skipped")

        tracker = _StageTracker(profile)

        context_snapshot, opportunity_snapshot = refresh_project_seo_intelligence(
            project, stage_tracker=tracker
        )

        # Secondary jobs — only run if we're still inside the total job budget.
        if tracker.over_total_budget():
            logger.warning(
                "SEO refresh for project %d exceeded total job budget (%.1fs); "
                "skipping campaign sync and editorial sync for this run.",
                project_id, tracker.elapsed_total(),
            )
        else:
            sync_project_seo_campaigns(
                project,
                context_snapshot=context_snapshot,
                opportunity_snapshot=opportunity_snapshot,
            )
            sync_project_editorial_tasks(project)

        if project.owner_id:
            record_usage(project.owner, UsageRecord.Metric.SEO_SNAPSHOT)

        _set_profile_refresh_state(profile, status="completed")
        logger.info(
            "SEO refresh for project %d completed in %.1fs — stages: %s",
            project_id, tracker.elapsed_total(), tracker.as_summary(),
        )

        if not _backlink_refresh_requested(profile):
            return

        # Skip backlink phase if the main job already overran the total budget.
        if tracker.over_total_budget():
            logger.warning(
                "SEO refresh for project %d: skipping backlink phase (total budget exceeded).",
                project_id,
            )
            _set_profile_backlink_state(profile, status="skipped_budget")
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
        logger.exception("SEO refresh failed for project %d: %s", project_id, exc)
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


# ---------------------------------------------------------------------------
# Backlink refresh job
# ---------------------------------------------------------------------------

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
        t_start = time.monotonic()

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

        elapsed = time.monotonic() - t_start
        budget = getattr(settings, "STAGE_BUDGET_BACKLINK_SECONDS", 90)
        if elapsed > budget:
            logger.warning(
                "Backlink refresh for project %d exceeded budget: %.1fs > %ds",
                project_id, elapsed, budget,
            )
        else:
            logger.info("Backlink refresh for project %d completed in %.1fs", project_id, elapsed)

        _set_profile_backlink_state(project.seo_profile, status="completed")

    except Exception as exc:
        logger.exception("Backlink refresh failed for project %d: %s", project_id, exc)
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
