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

                # Run location-aware SEO/AEO intelligence pipeline
                try:
                    from apps.seo.intelligence import run_seo_aeo_pipeline
                    profile = project.seo_profile
                    location = getattr(profile, "location", "") or getattr(project, "location", "") or ""
                    primary_service = getattr(profile, "primary_service", "") or ""
                    business_type = getattr(profile, "business_type", "") or getattr(project, "business_type", "") or "local_service"
                    if primary_service and location and location.lower() != "worldwide":
                        query = f"{primary_service} {location}".strip()
                        intelligence = run_seo_aeo_pipeline(
                            query=query,
                            location=location,
                            business_type=business_type,
                        )
                        # Store intelligence results in the profile metadata for later display
                        metadata = getattr(profile, "metadata", {}) or {}
                        metadata["intelligence"] = {
                            "aeo_overview": {
                                "snippets": intelligence.get("aeo_overview").snippets if intelligence.get("aeo_overview") else [],
                                "sources": [
                                    {"text": s.text, "link": s.link}
                                    for s in (intelligence.get("aeo_overview").sources if intelligence.get("aeo_overview") else [])
                                ],
                            },
                            "related_questions": [
                                {
                                    "question": q.question,
                                    "snippet": q.snippet,
                                    "link": q.link,
                                    "title": q.title,
                                }
                                for q in intelligence.get("related_questions", [])
                            ],
                            "local_pack": [
                                {
                                    "title": p.title,
                                    "position": p.position,
                                    "rating": p.rating,
                                    "reviews": p.reviews,
                                    "address": p.address,
                                    "type": p.type,
                                }
                                for p in intelligence.get("local_pack", [])
                            ],
                            "query": intelligence.get("query", ""),
                            "location": intelligence.get("location", ""),
                        }
                        profile.metadata = metadata
                        profile.save(update_fields=["metadata", "updated_at"])
                except Exception as intel_exc:
                    # Intelligence errors must never crash the audit job
                    import logging
                    logging.getLogger(__name__).warning(
                        "Intelligence pipeline failed for audit %s: %s", audit_run_id, intel_exc
                    )

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
