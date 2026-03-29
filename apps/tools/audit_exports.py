import csv
import secrets
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from .models import AuditShareLink


def build_absolute_app_url(path):
    base_url = (settings.APP_BASE_URL or "").rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{path}" if base_url else path


def get_or_create_audit_share_link(audit_run, *, created_by=None):
    now = timezone.now()
    share_link = (
        AuditShareLink.objects.filter(audit_run=audit_run)
        .filter(expires_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if not share_link:
        share_link = (
            AuditShareLink.objects.filter(audit_run=audit_run, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
    if share_link:
        return share_link

    return AuditShareLink.objects.create(
        audit_run=audit_run,
        created_by=created_by,
        token=secrets.token_urlsafe(24),
        expires_at=now + timedelta(days=settings.DEFAULT_AUDIT_SHARE_EXPIRY_DAYS),
    )


def build_audit_export_payload(audit_run):
    summary = audit_run.summary or {}
    return {
        "audit_run_id": audit_run.pk,
        "domain": audit_run.normalized_domain,
        "status": audit_run.status,
        "overall_score": audit_run.overall_score,
        "pages_crawled": audit_run.pages_crawled,
        "completed_at": audit_run.completed_at.isoformat() if audit_run.completed_at else None,
        "scores": {
            "technical": audit_run.technical_score,
            "on_page": audit_run.on_page_score,
            "content": audit_run.content_score,
            "aeo": audit_run.aeo_score,
            "internal_linking": audit_run.internal_linking_score,
            "performance": audit_run.performance_score,
            "accessibility": audit_run.accessibility_score,
            "best_practices": audit_run.best_practices_score,
            "seo": audit_run.seo_score,
        },
        "score_breakdown": summary.get("score_breakdown", {}),
        "issue_summary": summary.get("issue_summary", {}),
        "recommendations": summary.get("recommendations", []),
        "product_modules": summary.get("product_modules", []),
        "context_analysis": summary.get("context_analysis", {}),
        "change_report": getattr(getattr(audit_run, "change_report", None), "summary", {}),
    }


def build_audit_csv_export(audit_run):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["audit", "domain", audit_run.normalized_domain])
    writer.writerow(["audit", "overall_score", audit_run.overall_score])
    writer.writerow(["audit", "pages_crawled", audit_run.pages_crawled])

    summary = audit_run.summary or {}
    for key, item in (summary.get("score_breakdown") or {}).items():
        writer.writerow(["score_breakdown", f"{key}.score", item.get("score", 0)])
        writer.writerow(["score_breakdown", f"{key}.status", item.get("status", "")])
        writer.writerow(["score_breakdown", f"{key}.issues", item.get("issues", 0)])

    for index, recommendation in enumerate(summary.get("recommendations", [])[:25], start=1):
        writer.writerow(["recommendation", f"{index}.title", recommendation.get("title", "")])
        writer.writerow(["recommendation", f"{index}.category", recommendation.get("category", "")])
        writer.writerow(["recommendation", f"{index}.priority", recommendation.get("priority_score", 0)])
        writer.writerow(["recommendation", f"{index}.fix", recommendation.get("recommended_fix", "")])

    context_analysis = summary.get("context_analysis") or {}
    for index, insight in enumerate(context_analysis.get("insights", []), start=1):
        writer.writerow(["context_analysis", f"{index}.insight", insight])

    return output.getvalue()
