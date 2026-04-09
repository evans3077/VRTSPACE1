import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.tools.audit_exports import build_absolute_app_url

from .models import SEOShareLink
from .services import (
    build_campaign_value_summary,
    build_campaign_workspace_items,
    build_competitor_trend_summary,
    build_serp_evidence_history,
    sync_project_campaign_chain,
)


def get_seo_reporting_bundle(project, *, profile=None, context_snapshot=None, opportunity_snapshot=None, backlink_snapshot=None):
    if not project:
        return {}
    profile = profile or getattr(project, "seo_profile", None)
    context_snapshot = context_snapshot or (
        project.seo_snapshots.filter(profile=profile).order_by("-created_at").first()
        if profile
        else None
    )
    opportunity_snapshot = opportunity_snapshot or (
        project.seo_opportunity_snapshots.filter(profile=profile).order_by("-created_at").first()
        if profile
        else None
    )
    backlink_snapshot = backlink_snapshot or (
        project.backlink_snapshots.filter(profile=profile).order_by("-created_at").first()
        if profile
        else None
    )
    campaign_items = (
        build_campaign_workspace_items(project, campaigns=sync_project_campaign_chain(project))
        if opportunity_snapshot
        else []
    )
    return {
        "project": project,
        "profile": profile,
        "context_snapshot": context_snapshot,
        "opportunity_snapshot": opportunity_snapshot,
        "backlink_snapshot": backlink_snapshot,
        "campaign_items": campaign_items,
    }


def build_seo_export_payload(project, *, bundle=None):
    bundle = bundle or get_seo_reporting_bundle(project)
    profile = bundle.get("profile")
    context_snapshot = bundle.get("context_snapshot")
    opportunity_snapshot = bundle.get("opportunity_snapshot")
    backlink_snapshot = bundle.get("backlink_snapshot")
    campaign_items = bundle.get("campaign_items", [])
    context_payload = (getattr(context_snapshot, "output_json", None) or {})
    opportunity_payload = (getattr(opportunity_snapshot, "output_json", None) or {})
    backlink_payload = (getattr(backlink_snapshot, "output_json", None) or {})

    return {
        "project": {
            "id": project.pk,
            "name": project.name,
            "domain": project.normalized_domain,
            "website": project.website,
            "latest_score": getattr(project, "latest_score", 0),
        },
        "generated_at": timezone.now().isoformat(),
        "profile": {
            "business_type": getattr(profile, "business_type", ""),
            "location": getattr(profile, "location", ""),
            "target_goal": getattr(profile, "target_goal", ""),
            "primary_service": getattr(profile, "primary_service", ""),
            "target_audience": getattr(profile, "target_audience", ""),
        },
        "context": context_payload.get("context", {}),
        "benchmark_summary": context_payload.get("benchmark_summary", {}),
        "discovery": context_payload.get("discovery", {}),
        "competitor_trace": context_payload.get("competitor_trace", [])[:20],
        "competitor_patterns": context_payload.get("competitor_patterns", [])[:10],
        "page_comparisons": context_payload.get("page_comparisons", [])[:10],
        "keyword_clusters": context_payload.get("keyword_clusters", {}),
        "recommendations": context_payload.get("recommendations", [])[:12],
        "value_summary": opportunity_payload.get("value_summary", {}),
        "keyword_opportunities": opportunity_payload.get("keyword_opportunities", [])[:15],
        "page_map": opportunity_payload.get("page_map", [])[:12],
        "execution_queue": opportunity_payload.get("execution_queue", [])[:12],
        "serp_history": build_serp_evidence_history(project),
        "competitor_trends": build_competitor_trend_summary(project),
        "campaign_value_summary": build_campaign_value_summary(project, campaign_items=campaign_items),
        "campaigns": [
            {
                "title": item["campaign"].title,
                "status": item["campaign"].status,
                "validation_status": item["campaign"].validation_status,
                "target_keyword": item["campaign"].target_keyword,
                "related_page_urls": item["campaign"].related_page_urls,
                "success_criteria": item["campaign"].success_criteria,
                "priority_score": item["campaign"].priority_score,
                "brief_title": getattr(item.get("editorial_task"), "title", ""),
                "draft_title": getattr(item.get("latest_draft"), "title", ""),
                "backlink_prospect_count": item.get("backlink_prospect_count", 0),
                "acquired_backlink_count": item.get("acquired_backlink_count", 0),
            }
            for item in campaign_items[:12]
        ],
        "backlink_summary": backlink_payload.get("summary", {}),
        "linkable_assets": backlink_payload.get("linkable_assets", [])[:8],
        "backlink_prospects": [
            {
                "domain": prospect.domain,
                "prospect_url": prospect.prospect_url,
                "status": prospect.status,
                "prospect_type": prospect.prospect_type,
                "total_score": prospect.total_score,
                "target_asset_title": prospect.target_asset_title,
                "suggested_anchor_text": prospect.suggested_anchor_text,
            }
            for prospect in project.backlink_prospects.order_by("-total_score", "-updated_at")[:15]
        ],
    }


def get_or_create_seo_share_link(project, *, bundle=None, created_by=None):
    bundle = bundle or get_seo_reporting_bundle(project)
    context_snapshot = bundle.get("context_snapshot")
    opportunity_snapshot = bundle.get("opportunity_snapshot")
    backlink_snapshot = bundle.get("backlink_snapshot")
    profile = bundle.get("profile")
    if not context_snapshot or not opportunity_snapshot:
        return None

    now = timezone.now()
    share_link = (
        SEOShareLink.objects.filter(
            project=project,
            profile=profile,
            source_context_snapshot=context_snapshot,
            source_opportunity_snapshot=opportunity_snapshot,
            source_backlink_snapshot=backlink_snapshot,
        )
        .filter(expires_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if not share_link:
        share_link = (
            SEOShareLink.objects.filter(
                project=project,
                profile=profile,
                source_context_snapshot=context_snapshot,
                source_opportunity_snapshot=opportunity_snapshot,
                source_backlink_snapshot=backlink_snapshot,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
    if share_link:
        return share_link

    return SEOShareLink.objects.create(
        project=project,
        profile=profile,
        source_context_snapshot=context_snapshot,
        source_opportunity_snapshot=opportunity_snapshot,
        source_backlink_snapshot=backlink_snapshot,
        created_by=created_by,
        token=secrets.token_urlsafe(24),
        expires_at=now + timedelta(days=settings.DEFAULT_AUDIT_SHARE_EXPIRY_DAYS),
    )


def build_seo_share_urls(share_link):
    return {
        "share_url": build_absolute_app_url(f"/share/seo/{share_link.token}/"),
        "pdf_url": build_absolute_app_url(f"/share/seo/{share_link.token}/report.pdf"),
    }
