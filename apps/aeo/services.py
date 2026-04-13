from django.db import transaction

from apps.seo.models import SEOProjectProfile
from apps.tools.evidence import decorate_recommendation, should_surface_recommendation
from apps.tools.models import AuditRun

from .models import AEOAudit, AIRecommendation, VisibilitySnapshot


def _build_entity_score(profile, audit_run, target_keyword=""):
    """Score how well the site's identity matches the target keyword."""
    score = 30
    if profile:
        if profile.primary_service:
            score += 15
        if profile.location:
            score += 15
        if profile.business_type:
            score += 10
        if profile.target_goal:
            score += 5
    if audit_run.normalized_domain:
        score += 5
    
    # Keyword-aware: check if pages match the target keyword
    if target_keyword:
        kw_lower = target_keyword.lower()
        pages = list(audit_run.pages.all()[:15])
        kw_in_title = sum(1 for p in pages if kw_lower in (p.title or "").lower())
        kw_in_h1 = sum(1 for p in pages if kw_lower in (p.h1 or "").lower())
        kw_location_match = 0
        if profile and profile.location:
            loc_tokens = [t.strip().lower() for t in profile.location.split(",") if t.strip()]
            if any(t in kw_lower for t in loc_tokens):
                kw_location_match = 1
        score += kw_in_title * 5 + kw_in_h1 * 5 + kw_location_match * 10
    
    return min(score, 100)


def _build_structure_score(audit_run, target_keyword=""):
    """Score structural AEO signals — schema, H1, FAQ presence."""
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
    
    # Penalty: if keyword has a geographic modifier, check that at least one page has H1/title with it
    if target_keyword:
        kw_lower = target_keyword.lower()
        has_kw_structure = any(
            kw_lower in (p.title or "").lower() or kw_lower in (p.h1 or "").lower()
            for p in pages
        )
        if not has_kw_structure:
            score -= 10  # structural gap: keyword not in any H1 or title
    
    return min(max(score, 0), 100)


def _build_completeness_score(audit_run, target_keyword=""):
    """Score content completeness and depth relative to the target keyword."""
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
    
    # Keyword-aware: does any page have a meta_description or high word_count page matching the keyword?
    if target_keyword:
        kw_lower = target_keyword.lower()
        kw_meta = sum(1 for p in pages if kw_lower in (p.meta_description or "").lower())
        kw_dense = sum(1 for p in pages if (p.word_count or 0) >= 500 and kw_lower in (p.title or p.h1 or "").lower())
        score += kw_meta * 3 + kw_dense * 5
        # If keyword targets a city that isn't referenced anywhere, apply a gap penalty
        kw_words = set(kw_lower.split())
        any_page_matches = any(
            bool(kw_words.intersection(set((p.title or "").lower().split())))
            for p in pages
        )
        if not any_page_matches:
            score -= 8
    
    return min(max(score, 0), 100)


def _build_visibility_score(audit_run, target_keyword=""):
    """Visibility: average of AEO, content, on-page, adjusted for keyword match strength."""
    base = max(
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
    
    # Keyword modifier: if pages strongly match the keyword, boost; else penalise
    if target_keyword:
        kw_lower = target_keyword.lower()
        pages = list(audit_run.pages.all()[:15])
        kw_match_count = sum(
            1 for p in pages
            if kw_lower in (p.title or "").lower() or kw_lower in (p.h1 or "").lower()
        )
        if kw_match_count >= 2:
            base = min(base + 5, 100)
        elif kw_match_count == 0:
            base = max(base - 8, 0)
    
    return base


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
    visibility_score = _build_visibility_score(audit_run, target_keyword)
    entity_score = _build_entity_score(profile, audit_run, target_keyword)
    structure_score = _build_structure_score(audit_run, target_keyword)
    completeness_score = _build_completeness_score(audit_run, target_keyword)
    recommendations = build_aeo_recommendations(
        audit_run=audit_run,
        profile=profile,
        target_keyword=target_keyword,
    )

    # ── Citation Readiness Score (weighted headline composite) ──────────────
    citation_readiness = round(
        visibility_score * 0.35
        + entity_score * 0.25
        + structure_score * 0.25
        + completeness_score * 0.15
    )

    # ── Per-engine internal score approximations (mirror create_aeo_audit) ──
    CITE_THRESHOLD = 68
    aeo_s = int(audit_run.aeo_score or 0)
    content_s = int(audit_run.content_score or 0)
    on_page_s = int(audit_run.on_page_score or 0)

    chatgpt_raw = entity_score * 0.4 + completeness_score * 0.3 + aeo_s * 0.3
    gemini_raw = on_page_s * 0.35 + structure_score * 0.35 + entity_score * 0.3
    perplexity_raw = content_s * 0.4 + completeness_score * 0.3 + aeo_s * 0.3

    engine_gaps = [
        {
            "engine": "ChatGPT",
            "score": round(chatgpt_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(chatgpt_raw)),
            "cited": chatgpt_raw >= CITE_THRESHOLD,
            "color": "#10a37f",
            "icon": "🤖",
            "lever": "Add FAQ schema and answer-first headings" if chatgpt_raw < CITE_THRESHOLD else "Maintain current answer structure",
        },
        {
            "engine": "Gemini",
            "score": round(gemini_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(gemini_raw)),
            "cited": gemini_raw >= CITE_THRESHOLD,
            "color": "#4285f4",
            "icon": "✦",
            "lever": "Add JSON-LD schema and align keyword with location" if gemini_raw < CITE_THRESHOLD else "Keep E-E-A-T and schema markup consistent",
        },
        {
            "engine": "Perplexity",
            "score": round(perplexity_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(perplexity_raw)),
            "cited": perplexity_raw >= CITE_THRESHOLD,
            "color": "#a855f7",
            "icon": "⊕",
            "lever": "Expand pages to 600+ words with structured facts" if perplexity_raw < CITE_THRESHOLD else "Maintain content depth and sourcing quality",
        },
    ]

    # Sort: closest to threshold first (biggest opportunity)
    engine_gaps.sort(key=lambda e: (e["cited"], -e["score"]))

    top_priority_fix = recommendations[0] if recommendations else None

    return {
        "scores": {
            "visibility_score": visibility_score,
            "entity_score": entity_score,
            "structure_score": structure_score,
            "completeness_score": completeness_score,
            "citation_readiness": citation_readiness,
        },
        "context": {
            "business_type": getattr(profile, "business_type", ""),
            "location": getattr(profile, "location", ""),
            "target_goal": getattr(profile, "target_goal", ""),
            "primary_service": getattr(profile, "primary_service", ""),
            "target_keyword": target_keyword,
        },
        "engine_gaps": engine_gaps,
        "top_priority_fix": top_priority_fix,
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
        pages = list(audit_run.pages.all()[:15])
        kw_lower = target_query.lower()
        
        # Shared keyword-page signals
        kw_in_title_count = sum(1 for p in pages if kw_lower in (p.title or "").lower())
        kw_in_h1_count = sum(1 for p in pages if kw_lower in (p.h1 or "").lower())
        kw_in_meta_count = sum(1 for p in pages if kw_lower in (p.meta_description or "").lower())
        has_faq_schema = any(p.has_faq_schema for p in pages)
        has_schema = any((p.schema_count or 0) > 0 for p in pages)
        avg_word_count = sum((p.word_count or 0) for p in pages) / max(len(pages), 1)
        high_depth_pages = sum(1 for p in pages if (p.word_count or 0) >= 600)
        
        # Location match in keyword (signals local intent)
        location_in_kw = False
        if profile and profile.location:
            loc_tokens = [t.strip().lower() for t in profile.location.split(",") if len(t.strip()) >= 3]
            location_in_kw = any(t in kw_lower for t in loc_tokens)

        snapshots = []
        
        # === ChatGPT: Favours direct answers, FAQ schema, entity clarity, answer-first structure ===
        chatgpt_score = payload["scores"]["entity_score"] * 0.4 + payload["scores"]["completeness_score"] * 0.3 + int(audit_run.aeo_score or 0) * 0.3
        chatgpt_score += kw_in_title_count * 4 + kw_in_h1_count * 4
        chatgpt_score += 12 if has_faq_schema else 0
        chatgpt_score -= 10 if kw_in_title_count == 0 else 0
        chatgpt_ans = chatgpt_score >= 68
        chatgpt_freq = 2 if chatgpt_score >= 85 else (1 if chatgpt_ans else 0)
        chatgpt_reason = (
            "Answer-first structure and FAQ schema detected \u2014 strong fit for ChatGPT citation." if chatgpt_ans and has_faq_schema
            else "FAQ schema and structured answers boost your ChatGPT citability significantly." if not has_faq_schema
            else "Entity and answer signals present but keyword alignment in headings is weak." if kw_in_title_count == 0
            else "Moderate entity clarity. Strengthen direct-answer blocks for higher citation frequency."
        )
        snapshots.append(VisibilitySnapshot(
            aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.CHATGPT,
            prompt=f"{target_query}?",
            cited_url=f"https://{domain}" if chatgpt_ans else "",
            answer_present=chatgpt_ans, citation_frequency=chatgpt_freq,
            notes=chatgpt_reason,
        ))
        
        # === Gemini: Favours Google E-E-A-T, schema markup, local presence, on-page quality ===
        gemini_score = int(audit_run.on_page_score or 0) * 0.35 + payload["scores"]["structure_score"] * 0.35 + payload["scores"]["entity_score"] * 0.3
        gemini_score += 15 if has_schema else 0
        gemini_score += 12 if location_in_kw else 0
        gemini_score += kw_in_meta_count * 5
        gemini_score -= 12 if not location_in_kw and (profile and profile.location) else 0
        gemini_ans = gemini_score >= 68
        gemini_freq = 2 if gemini_score >= 85 else (1 if gemini_ans else 0)
        gemini_reason = (
            "Schema markup and local location signals align with Gemini\u2019s E-E-A-T requirements." if gemini_ans and has_schema and location_in_kw
            else "Schema markup present but the keyword lacks a geographic modifier that matches your location." if has_schema and not location_in_kw
            else "Missing structured schema markup \u2014 Gemini heavily weights Schema.org signals for local queries." if not has_schema
            else "Keyword-location alignment is strong. Add JSON-LD schema to convert to a reliable citation."
        )
        snapshots.append(VisibilitySnapshot(
            aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.GEMINI,
            prompt=f"{target_query}",
            cited_url=f"https://{domain}" if gemini_ans else "",
            answer_present=gemini_ans, citation_frequency=gemini_freq,
            notes=gemini_reason,
        ))
        
        # === Perplexity: Favours fact-dense, high word-count, well-cited, sourced content ===
        perplexity_score = int(audit_run.content_score or 0) * 0.4 + payload["scores"]["completeness_score"] * 0.3 + int(audit_run.aeo_score or 0) * 0.3
        perplexity_score += high_depth_pages * 6
        perplexity_score += 8 if avg_word_count >= 400 else -8
        perplexity_score += kw_in_title_count * 3
        perplexity_score -= 10 if avg_word_count < 200 else 0
        perplexity_ans = perplexity_score >= 68
        perplexity_freq = 2 if perplexity_score >= 85 else (1 if perplexity_ans else 0)
        perplexity_reason = (
            f"Content depth is strong ({high_depth_pages} high-density pages) \u2014 Perplexity can source directly." if perplexity_ans and high_depth_pages >= 2
            else "Content depth is thin. Perplexity favours pages with 600+ words, direct facts, and clear sourcing." if high_depth_pages == 0
            else "Moderate depth. Expand core service pages with structured evidence blocks to capture Perplexity citations."
        )
        snapshots.append(VisibilitySnapshot(
            aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.PERPLEXITY,
            prompt=f"What is {target_query}?",
            cited_url=f"https://{domain}" if perplexity_ans else "",
            answer_present=perplexity_ans, citation_frequency=perplexity_freq,
            notes=perplexity_reason,
        ))
        
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


def build_aeo_competitor_benchmarks(project, profile=None, target_keyword="", aeo_intelligence=None):
    """Build a side-by-side AEO benchmark comparing the client site against discovered competitors.

    Sources in priority order:
    1. Active SEOCompetitor records with snapshots
    2. Local Pack entries from intelligence metadata
    3. AEO Overview source domains from intelligence metadata
    Falls back to an empty list when no competitor data is available.
    """
    from apps.seo.models import SEOCompetitor

    benchmarks = []
    seen_domains = set()

    # ── Client site baseline ───────────────────────────────────────────────
    audit_run = getattr(project, "latest_audit_run", None)
    if not audit_run:
        return {"client": None, "competitors": [], "dimensions": []}

    client_vis = _build_visibility_score(audit_run, target_keyword)
    client_ent = _build_entity_score(profile, audit_run, target_keyword)
    client_str = _build_structure_score(audit_run, target_keyword)
    client_cmp = _build_completeness_score(audit_run, target_keyword)
    client_readiness = round(client_vis * 0.35 + client_ent * 0.25 + client_str * 0.25 + client_cmp * 0.15)

    client = {
        "label": audit_run.normalized_domain or "Your Site",
        "domain": audit_run.normalized_domain or "",
        "is_client": True,
        "visibility": client_vis,
        "entity": client_ent,
        "structure": client_str,
        "completeness": client_cmp,
        "readiness": client_readiness,
        "has_faq_schema": any(p.has_faq_schema for p in audit_run.pages.all()[:15]),
        "has_schema": any((p.schema_count or 0) > 0 for p in audit_run.pages.all()[:15]),
        "avg_words": round(sum((p.word_count or 0) for p in audit_run.pages.all()[:15]) / max(audit_run.pages.all()[:15].count(), 1)),
        "source": "audit",
    }
    if audit_run.normalized_domain:
        seen_domains.add(audit_run.normalized_domain)

    # ── Source 1: SEOCompetitor records with snapshots ─────────────────────
    active_comps = SEOCompetitor.objects.filter(
        project=project, is_active=True, normalized_domain__isnull=False
    ).prefetch_related("snapshots")[:4]

    for comp in active_comps:
        domain = comp.normalized_domain
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        snap = comp.snapshots.order_by("-created_at").first()
        if snap and snap.output_json:
            pages_data = snap.output_json.get("pages", [])
            has_faq = any(p.get("has_faq_schema") for p in pages_data)
            has_schema = any((p.get("schema_count") or 0) > 0 for p in pages_data)
            avg_w = round(sum(p.get("word_count", 0) for p in pages_data) / max(len(pages_data), 1))
            # Approximate AEO dimensions from snapshot data
            vis = min(round((snap.output_json.get("aeo_score", 0) + snap.output_json.get("content_score", 0) + snap.output_json.get("on_page_score", 0)) / 3), 100)
            ent = 45 + (15 if has_schema else 0) + (10 if has_faq else 0)
            struct = 40 + (20 if has_faq else 0) + (15 if has_schema else 0)
            comp_ = 45 + (10 if avg_w >= 200 else 0) + (15 if avg_w >= 500 else 0)
        else:
            # Heuristic-only if no snapshot — score is opaque/unknown
            has_faq = has_schema = False
            avg_w = 0
            vis = ent = struct = comp_ = 0  # unknown

        readiness = round(vis * 0.35 + ent * 0.25 + struct * 0.25 + comp_ * 0.15)
        benchmarks.append({
            "label": comp.label or domain,
            "domain": domain,
            "is_client": False,
            "visibility": vis,
            "entity": ent,
            "structure": struct,
            "completeness": comp_,
            "readiness": readiness,
            "has_faq_schema": has_faq,
            "has_schema": has_schema,
            "avg_words": avg_w,
            "source": "competitor_record",
            "unknown": vis == 0,
        })

    # ── Source 2 & 3: SERP intelligence (Local Pack + AEO sources) ─────────
    intel = aeo_intelligence or {}
    serp_sources = []

    # Local pack competitors
    for place in intel.get("local_pack", [])[:3]:
        domain = place.get("link", "").replace("https://", "").replace("http://", "").split("/")[0]
        if domain and domain not in seen_domains:
            serp_sources.append({"label": place.get("title", domain), "domain": domain, "source": "local_pack"})
            seen_domains.add(domain)

    # AEO overview source domains
    for source in intel.get("aeo_overview", {}).get("sources", [])[:3]:
        raw = source.get("link", "")
        domain = raw.replace("https://", "").replace("http://", "").split("/")[0]
        if domain and domain not in seen_domains:
            serp_sources.append({"label": source.get("text", domain), "domain": domain, "source": "serp_source"})
            seen_domains.add(domain)

    for entry in serp_sources[:3]:
        # No page data for SERP sources — show as "competitor spotted in AI results"
        benchmarks.append({
            "label": entry["label"],
            "domain": entry["domain"],
            "is_client": False,
            "visibility": None,
            "entity": None,
            "structure": None,
            "completeness": None,
            "readiness": None,
            "has_faq_schema": None,
            "has_schema": None,
            "avg_words": None,
            "source": entry["source"],
            "unknown": True,
        })

    return {
        "client": client,
        "competitors": benchmarks[:4],
        "dimensions": ["visibility", "entity", "structure", "completeness"],
        "has_data": bool(benchmarks),
    }
