from django.db import transaction

from apps.seo.models import SEOProjectProfile
from apps.tools.models import AuditRun

from .models import AEOAudit, AIRecommendation


def _build_entity_score(profile, audit_run):
    score = 35
    if profile:
        if profile.primary_service:
            score += 20
        if profile.location:
            score += 20
        if profile.business_type:
            score += 15
        if profile.target_goal:
            score += 10
    if audit_run.normalized_domain:
        score += 5
    return min(score, 100)


def _build_structure_score(audit_run):
    pages = list(audit_run.pages.all()[:15])
    summary = audit_run.summary or {}
    score = 40
    if any(page.has_faq_schema for page in pages):
        score += 20
    if any(page.schema_count > 0 for page in pages):
        score += 15
    if any(page.h1 for page in pages):
        score += 10
    if not any(rec.get("category_key") == "aeo" for rec in summary.get("recommendations", [])):
        score += 10
    return min(score, 100)


def _build_completeness_score(audit_run):
    summary = audit_run.summary or {}
    pages = list(audit_run.pages.all()[:15])
    score = 45
    if audit_run.pages_crawled >= 5:
        score += 10
    if any(page.meta_description for page in pages):
        score += 10
    if any(page.word_count >= 200 for page in pages):
        score += 15
    if summary.get("context_analysis", {}).get("competitors"):
        score += 10
    return min(score, 100)


def _build_visibility_score(audit_run):
    return max(
        0,
        min(
            100,
            round(
                (
                    int(audit_run.aeo_score or 0)
                    + int(audit_run.content_score or 0)
                    + int(audit_run.on_page_score or 0)
                ) / 3
            ),
        ),
    )


def build_aeo_recommendations(*, audit_run, profile=None, target_keyword=""):
    summary = audit_run.summary or {}
    recommendations = []
    location = getattr(profile, "location", "")
    service = getattr(profile, "primary_service", "") or getattr(profile, "business_type", "service").replace("_", " ")
    keyword = target_keyword or f"{service} {location}".strip()

    if audit_run.aeo_score < 80:
        recommendations.append(
            {
                "issue": "Direct-answer coverage is weak.",
                "category": "Answer structure",
                "priority_score": 92,
                "why_ai_ignores_this": "AI systems prefer concise passages that answer a question directly before adding detail.",
                "fix": "Add short answer-first blocks near the top of priority pages and support them with FAQ sections.",
                "example_rewrite": f"{service.title()} in {location} should open with a direct answer explaining the offer, the audience, and the next step.",
                "expected_impact": "Improves answer extraction and citation readiness for AI search surfaces.",
            }
        )
    if audit_run.content_score < 80:
        recommendations.append(
            {
                "issue": "Content completeness is below AI-ready depth.",
                "category": "Content depth",
                "priority_score": 84,
                "why_ai_ignores_this": "Thin pages rarely provide enough context for AI engines to cite confidently.",
                "fix": "Expand core pages with proof, summaries, FAQs, and direct examples tied to the user intent.",
                "example_rewrite": f"For queries like '{keyword}', add a short summary, proof points, and a compact FAQ block on the target page.",
                "expected_impact": "Improves completeness and makes the content easier for AI systems to summarize accurately.",
            }
        )
    if audit_run.on_page_score < 75:
        recommendations.append(
            {
                "issue": "Entity and topic signals are inconsistent on page.",
                "category": "Entity clarity",
                "priority_score": 79,
                "why_ai_ignores_this": "If headings and metadata do not clearly define the business, service, and location, AI systems struggle to map the page to an answer.",
                "fix": "Align titles, H1s, and summary copy with the business type, service, and location.",
                "example_rewrite": f"Use a heading like '{service.title()} in {location}' and follow it with a clear one-paragraph summary of the offer.",
                "expected_impact": "Improves entity recognition and answer relevance.",
            }
        )
    if not summary.get("context_analysis", {}).get("competitors"):
        recommendations.append(
            {
                "issue": "Competitor answer patterns are missing from the analysis.",
                "category": "Competitive context",
                "priority_score": 70,
                "why_ai_ignores_this": "Without benchmarked competitor patterns, it is harder to identify what makes cited answers structurally stronger.",
                "fix": "Add competitor URLs to the audit and compare how their pages structure direct answers, FAQs, and schema.",
                "example_rewrite": f"Compare how competing pages in {location} answer '{keyword}' and mirror the strongest answer structure with clearer evidence.",
                "expected_impact": "Improves competitive positioning for answer-driven searches.",
            }
        )
    return recommendations[:6]


def build_aeo_payload(*, audit_run, profile=None, target_keyword=""):
    visibility_score = _build_visibility_score(audit_run)
    entity_score = _build_entity_score(profile, audit_run)
    structure_score = _build_structure_score(audit_run)
    completeness_score = _build_completeness_score(audit_run)
    recommendations = build_aeo_recommendations(
        audit_run=audit_run,
        profile=profile,
        target_keyword=target_keyword,
    )
    return {
        "scores": {
            "visibility_score": visibility_score,
            "entity_score": entity_score,
            "structure_score": structure_score,
            "completeness_score": completeness_score,
        },
        "context": {
            "business_type": getattr(profile, "business_type", ""),
            "location": getattr(profile, "location", ""),
            "target_goal": getattr(profile, "target_goal", ""),
            "primary_service": getattr(profile, "primary_service", ""),
            "target_keyword": target_keyword,
        },
        "recommendations": recommendations,
    }


@transaction.atomic
def create_aeo_audit(*, project, target_keyword=""):
    audit_run = getattr(project, "latest_audit_run", None)
    if not audit_run or audit_run.status != AuditRun.Status.COMPLETED:
        raise ValueError("A completed audit is required before creating an AEO audit.")

    profile = SEOProjectProfile.objects.filter(project=project).first()
    payload = build_aeo_payload(audit_run=audit_run, profile=profile, target_keyword=target_keyword)
    aeo_audit = AEOAudit.objects.create(
        project=project,
        seo_profile=profile,
        source_audit_run=audit_run,
        target_keyword=target_keyword,
        visibility_score=payload["scores"]["visibility_score"],
        entity_score=payload["scores"]["entity_score"],
        structure_score=payload["scores"]["structure_score"],
        completeness_score=payload["scores"]["completeness_score"],
        output_json=payload,
    )
    AIRecommendation.objects.bulk_create(
        [
            AIRecommendation(
                aeo_audit=aeo_audit,
                issue=item["issue"],
                why_ai_ignores_this=item["why_ai_ignores_this"],
                fix=item["fix"],
                example_rewrite=item["example_rewrite"],
                expected_impact=item["expected_impact"],
                priority_score=item["priority_score"],
                category=item["category"],
            )
            for item in payload["recommendations"]
        ]
    )
    return aeo_audit


def get_latest_aeo_audit(project):
    if not project:
        return None
    return (
        AEOAudit.objects.select_related("seo_profile", "source_audit_run")
        .prefetch_related("recommendations")
        .filter(project=project)
        .order_by("-created_at")
        .first()
    )
