from django.db import transaction

from apps.seo.models import SEOProjectProfile
from apps.tools.evidence import decorate_recommendation, should_surface_recommendation
from apps.tools.models import AuditRun

from .models import AEOAudit, AIRecommendation, VisibilitySnapshot


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


def _priority_page_targets(audit_run, limit=3):
    pages = []
    for page in audit_run.pages.order_by("-word_count", "url")[: max(limit * 2, 6)]:
        if not page.url:
            continue
        pages.append(page.url)
        if len(pages) >= limit:
            break
    return pages


def _aeo_cluster_key(item):
    category = (item.get("category") or "").lower()
    if "answer" in category or "direct-answer" in category:
        return "answer-readiness"
    if "content" in category:
        return "content-depth"
    if "entity" in category:
        return "entity-clarity"
    if "competitive" in category:
        return "page-coverage"
    return "answer-readiness"


def _merge_aeo_cluster(cluster_key, items):
    primary = max(items, key=lambda item: item.get("priority_score", 0))
    merged = dict(primary)
    urls = []
    for item in items:
        for url in item.get("where_to_apply", []):
            if url and url not in urls:
                urls.append(url)
    merged["where_to_apply"] = urls[:4]
    merged["cluster_size"] = len(items)
    if len(items) > 1:
        merged["issue"] = primary.get("cluster_title") or primary.get("issue")
        merged["fix"] = primary.get("cluster_fix") or primary.get("fix")
    return decorate_recommendation(
        merged,
        page_targets=merged.get("where_to_apply", []),
        competitor_evidence=merged.get("competitor_evidence", []),
        issue_count=max(len(items), len(merged.get("where_to_apply", [])), 1),
        technical_steps=merged.get("action_steps", []),
        source_signals=[merged.get("category", ""), "aeo"],
    )


def build_aeo_recommendations(*, audit_run, profile=None, target_keyword=""):
    summary = audit_run.summary or {}
    recommendations = []
    location = getattr(profile, "location", "")
    service = getattr(profile, "primary_service", "") or getattr(profile, "business_type", "service").replace("_", " ")
    keyword = target_keyword or f"{service} {location}".strip()
    target_urls = _priority_page_targets(audit_run)
    competitor_context = summary.get("context_analysis", {}).get("competitors") or []

    if audit_run.aeo_score < 80:
        recommendations.append(
            decorate_recommendation(
                {
                "issue": "Direct-answer coverage is weak.",
                "category": "Answer structure",
                "priority_score": 92,
                "why_ai_ignores_this": "AI systems prefer concise passages that answer a question directly before adding detail.",
                "fix": "Add short answer-first blocks near the top of priority pages and support them with FAQ sections.",
                "example_rewrite": f"{service.title()} in {location} should open with a direct answer explaining the offer, the audience, and the next step.",
                "expected_impact": "Improves answer extraction and citation readiness for AI search surfaces.",
                "where_to_apply": target_urls,
                "action_steps": [
                    "Add a direct answer summary in the first visible section of the target page.",
                    "Support that summary with 3 to 5 short FAQs tied to the same intent.",
                    "Keep the answer block close to the H1 and service-location summary.",
                ],
                "cluster_title": "Build stronger answer-ready page openings",
                "cluster_fix": "Add answer-first intros, FAQ coverage, and structured summaries to the highest-intent pages.",
                },
                page_targets=target_urls,
                competitor_evidence=competitor_context[:2],
                issue_count=max(len(target_urls), 1),
                technical_steps=[
                    "Add short answer-first blocks near the top of priority pages and support them with FAQ sections."
                ],
                source_signals=["aeo_score", "answer-structure"],
            )
        )
    if audit_run.content_score < 80:
        recommendations.append(
            decorate_recommendation(
                {
                "issue": "Content completeness is below AI-ready depth.",
                "category": "Content depth",
                "priority_score": 84,
                "why_ai_ignores_this": "Thin pages rarely provide enough context for AI engines to cite confidently.",
                "fix": "Expand core pages with proof, summaries, FAQs, and direct examples tied to the user intent.",
                "example_rewrite": f"For queries like '{keyword}', add a short summary, proof points, and a compact FAQ block on the target page.",
                "expected_impact": "Improves completeness and makes the content easier for AI systems to summarize accurately.",
                "where_to_apply": target_urls,
                "action_steps": [
                    "Add proof blocks, examples, and short summaries to the target page.",
                    "Use FAQ coverage to fill likely follow-up questions around the target query.",
                    "Keep the answer concise enough to be cited, then expand with proof below.",
                ],
                "cluster_title": "Increase AI-citable content depth",
                "cluster_fix": "Deepen weak pages with proofs, summaries, examples, and question coverage that can be cited cleanly.",
                },
                page_targets=target_urls,
                competitor_evidence=competitor_context[:2],
                issue_count=max(len(target_urls), 1),
                technical_steps=["Expand core pages with proof, summaries, FAQs, and direct examples tied to the user intent."],
                source_signals=["content_score", "content-depth"],
            )
        )
    if audit_run.on_page_score < 75:
        recommendations.append(
            decorate_recommendation(
                {
                "issue": "Entity and topic signals are inconsistent on page.",
                "category": "Entity clarity",
                "priority_score": 79,
                "why_ai_ignores_this": "If headings and metadata do not clearly define the business, service, and location, AI systems struggle to map the page to an answer.",
                "fix": "Align titles, H1s, and summary copy with the business type, service, and location.",
                "example_rewrite": f"Use a heading like '{service.title()} in {location}' and follow it with a clear one-paragraph summary of the offer.",
                "expected_impact": "Improves entity recognition and answer relevance.",
                "where_to_apply": target_urls,
                "action_steps": [
                    "Rewrite the title and H1 to name the business type, service, and location clearly.",
                    "Match the opening summary to the same entity language used in the title and H1.",
                    "Remove vague hero copy that hides the actual offer or location.",
                ],
                },
                page_targets=target_urls,
                competitor_evidence=[],
                issue_count=max(len(target_urls), 1),
                technical_steps=["Align titles, H1s, and summary copy with the business type, service, and location."],
                source_signals=["on_page_score", "entity-clarity"],
            )
        )
    if not summary.get("context_analysis", {}).get("competitors"):
        recommendations.append(
            decorate_recommendation(
                {
                "issue": "Competitor answer patterns are missing from the analysis.",
                "category": "Competitive context",
                "priority_score": 70,
                "why_ai_ignores_this": "Without benchmarked competitor patterns, it is harder to identify what makes cited answers structurally stronger.",
                "fix": "Add competitor URLs to the audit and compare how their pages structure direct answers, FAQs, and schema.",
                "example_rewrite": f"Compare how competing pages in {location} answer '{keyword}' and mirror the strongest answer structure with clearer evidence.",
                "expected_impact": "Improves competitive positioning for answer-driven searches.",
                "where_to_apply": target_urls[:1],
                "action_steps": [
                    "Benchmark direct competitors that target the same location and service.",
                    "Compare how their pages structure direct answers, FAQs, schema, and proof.",
                    "Use the strongest common answer pattern as the baseline for your priority pages.",
                ],
                },
                page_targets=target_urls[:1],
                competitor_evidence=[],
                issue_count=1,
                technical_steps=["Add competitor URLs to the audit and compare how their pages structure direct answers, FAQs, and schema."],
                source_signals=["competitive-context"],
            )
        )

    clustered = {}
    for item in recommendations:
        clustered.setdefault(_aeo_cluster_key(item), []).append(item)
    merged = [
        item
        for cluster_key, items in clustered.items()
        for item in [_merge_aeo_cluster(cluster_key, items)]
        if should_surface_recommendation(item, minimum_score=40)
    ]
    merged.sort(key=lambda item: -item.get("priority_score", 0))
    return merged[:6]


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

    domain = audit_run.normalized_domain
    if domain:
        target_query = target_keyword or getattr(profile, "primary_service", "service")
        base_prob = payload["scores"]["completeness_score"] + payload["scores"]["structure_score"]
        
        snapshots = []
        for engine in [VisibilitySnapshot.Engine.CHATGPT, VisibilitySnapshot.Engine.GEMINI, VisibilitySnapshot.Engine.PERPLEXITY]:
            prob = base_prob
            if engine == VisibilitySnapshot.Engine.CHATGPT:
                prob += 20 if audit_run.content_score > 70 else -10
            elif engine == VisibilitySnapshot.Engine.GEMINI:
                prob += 30 if audit_run.aeo_score > 60 else -20
            elif engine == VisibilitySnapshot.Engine.PERPLEXITY:
                prob += 10 if audit_run.on_page_score > 80 else -15
                
            freq = 0
            ans = False
            if prob > 130:
                ans = True
                freq = 2 if prob > 160 else 1
                
            snapshots.append(
                VisibilitySnapshot(
                    aeo_audit=aeo_audit,
                    engine=engine,
                    prompt=f"Best {target_query}?",
                    cited_url=f"https://{domain}" if ans else "",
                    answer_present=ans,
                    citation_frequency=freq,
                    notes="Algorithmically predicted visibility based on audit AEO structural density."
                )
            )
        if snapshots:
            VisibilitySnapshot.objects.bulk_create(snapshots)

    return aeo_audit


def get_latest_aeo_audit(project):
    if not project:
        return None
    return (
        AEOAudit.objects.select_related("seo_profile", "source_audit_run")
        .prefetch_related("recommendations", "visibility_snapshots")
        .filter(project=project)
        .order_by("-created_at")
        .first()
    )
