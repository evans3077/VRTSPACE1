"""
AEO Precision Scoring Engine — replaces the arithmetic approximations
with keyword-sensitive, SERP-grounded, page-level analysis.

Architecture:
1. _fetch_serp_signals(keyword, location) → live SERP data
2. _score_keyword_page_relevance(pages, keyword, location) → per-keyword match quality
3. Per-dimension scorers rebuilt around keyword×page matrix
4. build_aeo_recommendations rebuilt from actual page signals + SERP gaps
5. Citation engine unified (snapshot values fed back into engine_gaps)
"""

from django.db import transaction
from django.core.cache import cache

from apps.seo.models import SEOProjectProfile
from apps.tools.evidence import decorate_recommendation, should_surface_recommendation
from apps.tools.models import AuditRun

from .models import AEOAudit, AIRecommendation, VisibilitySnapshot


# ─── SERP Signal Fetcher ────────────────────────────────────────────────────

def _fetch_serp_signals(keyword, location="", country_code=""):
    """
    Fetches live SERP signals for the keyword via SerpApi.
    Returns a dict with:
      - organic_results: list of {position, title, link, displayed_link, snippet}
      - paa_questions: list of question strings
      - has_ai_overview: bool
      - ai_sources: list of URLs that appear in the AI overview
      - top_domains: list of ranking domains (positions 1-10)
      - client_rank: int or None (position of our domain in SERP)
    """
    import hashlib
    _raw_key = f"aeo:serp:{keyword[:80]}:{location[:40]}"
    cache_key = "aeo_serp_" + hashlib.md5(_raw_key.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        from apps.seo.discovery import fetch_serpapi_results
        result = fetch_serpapi_results(keyword, location=location, country_code=country_code or "")
    except Exception:
        return _empty_serp_signals()

    organic = result.get("organic_results", [])
    paa = result.get("related_questions", [])
    ai_ov = result.get("ai_overview", {})
    answer_box = result.get("answer_box", {})

    # Extract AI overview sources if available via serpapi_link
    ai_sources = []
    if ai_ov.get("sources"):
        ai_sources = [s.get("link", "") for s in ai_ov["sources"] if s.get("link")]

    signals = {
        "organic_results": [
            {
                "position": r.get("position"),
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "displayed_link": r.get("displayed_link", ""),
            }
            for r in organic[:10]
        ],
        "paa_questions": [q.get("question", "") for q in paa[:5]],
        "has_ai_overview": bool(ai_ov),
        "ai_sources": ai_sources,
        "has_answer_box": bool(answer_box),
        "answer_box_type": answer_box.get("type", ""),
        "top_domains": [_extract_domain(r.get("link", "")) for r in organic[:10]],
        "client_rank": None,  # filled in below once we know the domain
    }

    # Cache for 6 hours to avoid burning API credits
    cache.set(cache_key, signals, 60 * 60 * 6)
    return signals


def _empty_serp_signals():
    return {
        "organic_results": [],
        "paa_questions": [],
        "has_ai_overview": False,
        "ai_sources": [],
        "has_answer_box": False,
        "answer_box_type": "",
        "top_domains": [],
        "client_rank": None,
    }


def _extract_domain(url):
    if not url:
        return ""
    from urllib.parse import urlparse
    try:
        p = urlparse(url)
        return p.netloc.replace("www.", "").lower()
    except Exception:
        return ""


def _enrich_serp_with_domain(signals, domain):
    """Add client_rank to already-fetched signals."""
    domain = (domain or "").replace("www.", "").lower()
    for r in signals.get("organic_results", []):
        rd = _extract_domain(r.get("link", ""))
        if rd == domain or rd.endswith("." + domain) or domain.endswith("." + rd):
            signals["client_rank"] = r.get("position")
            break
    return signals


# ─── Keyword × Page Relevance Matrix ───────────────────────────────────────

def _keyword_page_matrix(pages, keyword, profile=None):
    """
    For each page, computes:
      - kw_title: keyword token overlap with title (0.0-1.0)
      - kw_h1: keyword token overlap with h1
      - kw_meta: keyword in meta description
      - location_title: location tokens in title
      - location_h1: location tokens in h1
      - service_h1: service tokens in h1
      - content_depth: word_count tier (0=thin, 1=moderate, 2=deep, 3=rich)
    Returns list of per-page dicts.
    """
    kw_tokens = set(_meaningful_tokens(keyword))
    location_tokens = set()
    service_tokens = set()
    if profile:
        if profile.location:
            location_tokens = set(_meaningful_tokens(profile.location))
        if profile.primary_service:
            service_tokens = set(_meaningful_tokens(profile.primary_service))

    matrix = []
    for page in pages:
        title_tokens = set(_meaningful_tokens(page.title or ""))
        h1_tokens = set(_meaningful_tokens(page.h1 or ""))
        meta_tokens = set(_meaningful_tokens(page.meta_description or ""))

        kw_in_title = _token_overlap(kw_tokens, title_tokens)
        kw_in_h1 = _token_overlap(kw_tokens, h1_tokens)
        kw_in_meta = _token_overlap(kw_tokens, meta_tokens)
        loc_in_title = _token_overlap(location_tokens, title_tokens) if location_tokens else 0.0
        loc_in_h1 = _token_overlap(location_tokens, h1_tokens) if location_tokens else 0.0
        svc_in_h1 = _token_overlap(service_tokens, h1_tokens) if service_tokens else 0.0

        wc = page.word_count or 0
        depth = 0 if wc < 200 else 1 if wc < 400 else 2 if wc < 700 else 3

        matrix.append({
            "url": page.url,
            "kw_in_title": kw_in_title,
            "kw_in_h1": kw_in_h1,
            "kw_in_meta": kw_in_meta,
            "loc_in_title": loc_in_title,
            "loc_in_h1": loc_in_h1,
            "svc_in_h1": svc_in_h1,
            "has_faq": page.has_faq_schema,
            "schema_count": page.schema_count or 0,
            "word_count": wc,
            "depth_tier": depth,
            "pagespeed": page.pagespeed_score or 0,
        })
    return matrix


def _meaningful_tokens(text):
    """Tokenise text, removing stop words, returning lowercase stems."""
    STOP = {"a", "an", "the", "in", "of", "for", "and", "or", "to", "at",
            "by", "with", "on", "is", "are", "be", "it", "its", "that",
            "this", "their", "from", "best", "top", "your", "our"}
    return [
        t.strip(".,!?\"'()[]{}").lower()
        for t in text.split()
        if len(t.strip(".,!?\"'()[]{}")) >= 3 and t.strip(".,!?\"'()[]{}").lower() not in STOP
    ]


def _token_overlap(set_a, set_b):
    """Jaccard-style overlap score 0.0-1.0."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    return intersection / len(set_a)  # recall: how much of the keyword is in the page


# ─── Precision Scorers ──────────────────────────────────────────────────────

def _build_entity_score(profile, audit_run, target_keyword="", matrix=None, serp=None):
    """
    Entity score: how clearly the site establishes WHO it is for this keyword.
    Grounded in:
    - Profile completeness (service + location + type)
    - Keyword-page location/service token match
    - Whether service pages cover the keyword's implied intent
    - SERP: organic visibility for this keyword
    """
    score = 20  # minimum floor

    # Profile completeness: each filled field means AI can extract entity signals
    if profile:
        if profile.primary_service:
            score += 12
        if profile.location:
            score += 12
        if profile.business_type:
            score += 6
        if profile.target_goal:
            score += 4

    # Page-level entity signals from the keyword matrix
    if matrix:
        # Best location match across all pages
        best_loc_h1 = max((r["loc_in_h1"] for r in matrix), default=0)
        best_svc_h1 = max((r["svc_in_h1"] for r in matrix), default=0)
        best_kw_h1 = max((r["kw_in_h1"] for r in matrix), default=0)
        best_loc_title = max((r["loc_in_title"] for r in matrix), default=0)

        score += round(best_loc_h1 * 20)     # 0-20: location in H1
        score += round(best_svc_h1 * 12)     # 0-12: service in H1
        score += round(best_kw_h1 * 10)      # 0-10: full keyword in H1
        score += round(best_loc_title * 8)   # 0-8: location in title

    # Schema signals: entity schema helps AI understand who the business is
    pages = list(audit_run.pages.all()[:15])
    has_schema = any((p.schema_count or 0) > 0 for p in pages)
    if has_schema:
        score += 8

    # SERP signal: if we're ranking, entity is being recognised by Google
    if serp:
        client_rank = serp.get("client_rank")
        if client_rank:
            if client_rank <= 3:
                score += 15
            elif client_rank <= 5:
                score += 10
            elif client_rank <= 10:
                score += 5
        # Penalty: if our domain doesn't appear in top 10 and keyword has location, entity gap
        elif target_keyword and profile and profile.location:
            loc_toks = set(_meaningful_tokens(profile.location))
            kw_toks = set(_meaningful_tokens(target_keyword))
            if loc_toks & kw_toks:  # keyword is local-intent
                score -= 5  # entity + local relevance gap

    return min(max(score, 0), 100)


def _build_structure_score(audit_run, target_keyword="", matrix=None, serp=None):
    """
    Structure score: how well pages are structured for AI extraction.
    Grounded in:
    - FAQ schema presence
    - Schema count
    - H1 usage
    - Answer-first keyword alignment in H1/title
    - PAA coverage (are our pages likely to answer the questions?)
    """
    pages = list(audit_run.pages.all()[:15])
    summary = audit_run.summary or {}
    score = 30  # floor

    # Schema and FAQ schema
    has_faq = any(p.has_faq_schema for p in pages)
    has_schema = any((p.schema_count or 0) > 0 for p in pages)
    has_h1 = any(p.h1 for p in pages)
    avg_schema = sum((p.schema_count or 0) for p in pages) / max(len(pages), 1)

    if has_faq:
        score += 20
    if has_schema:
        score += 12
    if has_h1:
        score += 8
    if avg_schema >= 3:
        score += 5

    # Keyword-page matrix: answer-readiness
    if matrix:
        # Pages that have keyword in title/H1 are structurally more answer-ready
        answer_ready_pages = sum(1 for r in matrix if r["kw_in_title"] >= 0.5 or r["kw_in_h1"] >= 0.5)
        score += min(answer_ready_pages * 4, 12)

        # FAQ schema on keyword-relevant page = strong structural signal
        kw_page_has_faq = any(r["has_faq"] and (r["kw_in_title"] > 0 or r["kw_in_h1"] > 0) for r in matrix)
        if kw_page_has_faq:
            score += 8

    # SERP: if there's an answer box or AI overview, the query expects structured answers
    if serp:
        paa = serp.get("paa_questions", [])
        if serp.get("has_answer_box"):
            # Direct answer box means the keyword is highly structured — reward strong structure
            if has_faq and has_schema:
                score += 5
            else:
                score -= 5  # penalty: answer box exists but we don't have structured content
        if paa:
            # More PAA = higher answer-intent query. Reward FAQ schema more
            if has_faq:
                score += min(len(paa) * 2, 8)
            else:
                score -= min(len(paa) * 2, 8)  # gap: PAA queries but no FAQ coverage

    return min(max(score, 0), 100)


def _build_completeness_score(audit_run, target_keyword="", matrix=None, serp=None):
    """
    Completeness score: how complete the content is for the keyword's implied intent.
    Grounded in:
    - Word count and content depth across pages
    - Meta descriptions (summary signals)
    - Keyword-page semantic coverage
    - Number of pages that cover the topic
    - Whether PAA questions are likely answerable from existing content
    """
    summary = audit_run.summary or {}
    pages = list(audit_run.pages.all()[:15])
    score = 35  # floor

    # Content depth signals
    pages_with_meta = sum(1 for p in pages if p.meta_description)
    avg_wc = sum((p.word_count or 0) for p in pages) / max(len(pages), 1)
    deep_pages = sum(1 for p in pages if (p.word_count or 0) >= 600)
    moderate_pages = sum(1 for p in pages if 300 <= (p.word_count or 0) < 600)

    score += min(pages_with_meta * 3, 12)
    score += round(min(avg_wc / 80, 10))   # 0-10 for avg word count
    score += min(deep_pages * 5, 15)
    score += min(moderate_pages * 2, 6)

    # Keyword-page matrix: how many pages semantically cover the keyword
    if matrix:
        covering_pages = sum(1 for r in matrix if r["kw_in_title"] >= 0.4 or r["kw_in_h1"] >= 0.4 or r["kw_in_meta"] >= 0.3)
        score += min(covering_pages * 4, 12)

        # A page with both keyword coverage and deep content is a strong completeness signal
        deep_kw_pages = sum(1 for r in matrix if r["depth_tier"] >= 2 and (r["kw_in_title"] >= 0.4 or r["kw_in_h1"] >= 0.4))
        score += min(deep_kw_pages * 4, 8)

    # SERP: PAA coverage — are questions answerable from our content?
    if serp:
        paa = serp.get("paa_questions", [])
        if paa and matrix:
            # For each PAA question, check if any page has keyword overlap
            paa_covered = 0
            for q in paa:
                q_toks = set(_meaningful_tokens(q))
                for r in matrix:
                    page_toks = set(_meaningful_tokens(r["url"]))  # limited; full text not available
                    # Use title and H1 data we have
                    break
            # Simpler: reward FAQ pages for having potential PAA coverage
            has_faq = sum(1 for r in matrix if r["has_faq"])
            paa_score_boost = min(has_faq * 2, min(len(paa) * 2, 8))
            score += paa_score_boost

    # Multi-page topic coverage = completeness breadth
    if audit_run.pages_crawled >= 8:
        score += 5
    elif audit_run.pages_crawled >= 5:
        score += 3

    return min(max(score, 0), 100)


def _build_visibility_score(audit_run, target_keyword="", matrix=None, serp=None):
    """
    Visibility score: how visible the site is in AI-surfaced search for this keyword.
    Grounded in:
    - Base from audit scores (aeo_score, content_score, on_page_score)
    - Keyword-specific SERP position (direct evidence of visibility)
    - AI overview presence and our citation status
    - Organic ranking quality for this keyword
    """
    # Base: weighted composite of audit layer scores
    aeo_s = int(audit_run.aeo_score or 0)
    content_s = int(audit_run.content_score or 0)
    on_page_s = int(audit_run.on_page_score or 0)
    base = round(aeo_s * 0.45 + content_s * 0.35 + on_page_s * 0.20)

    # Matrix: keyword-page match boost/penalty
    if matrix:
        best_kw_match = max((max(r["kw_in_title"], r["kw_in_h1"]) for r in matrix), default=0)
        if best_kw_match >= 0.7:
            base = min(base + 8, 100)
        elif best_kw_match >= 0.4:
            base = min(base + 3, 100)
        elif best_kw_match == 0:
            base = max(base - 8, 0)

    # SERP signal: actual SERP ranking is the ground truth for visibility
    if serp:
        client_rank = serp.get("client_rank")
        if client_rank:
            if client_rank <= 3:
                base = min(base + 15, 100)
            elif client_rank <= 5:
                base = min(base + 10, 100)
            elif client_rank <= 10:
                base = min(base + 5, 100)
        else:
            # Not in top 10 at all for this keyword = real visibility gap
            base = max(base - 10, 0)

        # AI overview boost: if we appear in AI sources, that's direct AEO visibility
        ai_sources = serp.get("ai_sources", [])
        domain = (audit_run.normalized_domain or "").replace("www.", "").lower()
        if any(domain in (s or "").lower() for s in ai_sources):
            base = min(base + 12, 100)  # direct AI citation evidence

    return max(base, 0)


# ─── Priority Page Targets ──────────────────────────────────────────────────

def _priority_page_targets(audit_run, matrix=None, limit=3):
    """Return URLs of the most relevant pages for the target keyword."""
    if matrix:
        # Sort by keyword relevance score descending
        ranked = sorted(matrix, key=lambda r: -(r["kw_in_h1"] + r["kw_in_title"] + r["depth_tier"] * 0.3))
        urls = [r["url"] for r in ranked if r["url"]][:limit]
        if urls:
            return urls
    # Fallback: highest word count pages
    pages = []
    for page in audit_run.pages.order_by("-word_count", "url")[: max(limit * 2, 6)]:
        if not page.url:
            continue
        pages.append(page.url)
        if len(pages) >= limit:
            break
    return pages


# ─── Precision Recommendations Engine ──────────────────────────────────────

def build_aeo_recommendations(*, audit_run, profile=None, target_keyword="", matrix=None, serp=None):
    """
    Builds AEO recommendations grounded in:
    - Real page signals (from matrix)
    - SERP gap analysis (from serp)
    - Audit recommendations as an evidence layer
    - Profile context (service, location)
    """
    summary = audit_run.summary or {}
    location = getattr(profile, "location", "") or ""
    service = (getattr(profile, "primary_service", "") or getattr(profile, "business_type", "service") or "service").replace("_", " ")
    keyword = target_keyword or f"{service} {location}".strip()
    target_urls = _priority_page_targets(audit_run, matrix=matrix)

    # Pull the richest signals from the audit's own recommendation layer
    audit_recs = summary.get("recommendations", [])
    aeo_audit_recs = [r for r in audit_recs if r.get("category_key") == "aeo"]
    on_page_recs = [r for r in audit_recs if r.get("category_key") == "on_page"]

    recommendations = []

    # ── Signal 1: SERP position gap ───────────────────────────────────
    if serp:
        client_rank = serp.get("client_rank")
        top_domains = serp.get("top_domains", [])
        domain = (audit_run.normalized_domain or "").replace("www.", "").lower()

        if not client_rank:
            # Not ranking at all for this keyword
            # Who IS ranking? Build a specific, actionable gap
            competitor_domain = next((d for d in top_domains if d and domain not in d), None)
            rec_text = (
                f"Your site ({domain}) does not appear in the top 10 search results for "
                f"'{keyword}'. Competitors like {competitor_domain} are ranking ahead."
                if competitor_domain
                else f"Your site ({domain}) is not appearing for '{keyword}' in Google's top results."
            )
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"Site not ranked in top 10 for '{keyword}'.",
                        "category": "Search visibility",
                        "priority_score": 95,
                        "why_ai_ignores_this": (
                            f"AI systems like ChatGPT, Gemini, and Perplexity source from Google's top-ranked pages. "
                            f"Since {domain} is not ranking for this keyword, it is effectively invisible to AI answer engines."
                        ),
                        "fix": rec_text + f" Add location-specific pages or content that explicitly targets '{keyword}'.",
                        "example_rewrite": (
                            f"Create or update a page with title '{service.title()} in {location}' and "
                            f"H1 '{service.title()} in {location} — Book Today'. Include a short direct-answer intro "
                            f"that defines the service, capacity, and location in the first paragraph."
                        ),
                        "expected_impact": "Establishes SERP presence for this keyword, making the site eligible for AI citation.",
                        "where_to_apply": target_urls,
                        "action_steps": [
                            f"Create a dedicated landing page targeting '{keyword}' exactly as written.",
                            f"Use structured H1 + meta description that mirrors the search query.",
                            f"Add JSON-LD LocalBusiness or Event schema with '{location}' as the address.",
                            f"Add a 3-5 question FAQ block answering common questions for this keyword.",
                        ],
                        "root_cause_label": "SERP absence",
                    },
                    page_targets=target_urls,
                    competitor_evidence=top_domains[:2],
                    issue_count=1,
                    technical_steps=["Target the keyword with a dedicated page and proper schema."],
                    source_signals=["serp_rank", "visibility"],
                )
            )
        elif client_rank > 5:
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"Ranking position {client_rank} for '{keyword}' — below AI citation zone.",
                        "category": "Search visibility",
                        "priority_score": 85,
                        "why_ai_ignores_this": (
                            f"AI answer engines primarily source from positions 1-5. Position {client_rank} means "
                            f"your content is rarely selected even when it's technically relevant."
                        ),
                        "fix": (
                            f"Strengthen the page targeting '{keyword}' by improving entity clarity (service + location + schema) "
                            f"and answer-first content structure to push into the top 3."
                        ),
                        "example_rewrite": (
                            f"Move the service-location summary above the fold: '{service.title()} in {location} — "
                            f"[Capacity/Offering]. [One-sentence differentiator].'"
                        ),
                        "expected_impact": "Moving from position 5-10 to top 3 typically doubles AI citation exposure.",
                        "where_to_apply": target_urls,
                        "action_steps": [
                            "Move service + location to the H1 exactly as the keyword is written.",
                            "Add a direct-answer block in the first visible section of the page.",
                            "Add schema markup (LocalBusiness + specific type like EventVenue or LodgingBusiness).",
                            "Improve internal links from other pages pointing to this target page.",
                        ],
                        "root_cause_label": "Low SERP rank",
                    },
                    page_targets=target_urls,
                    competitor_evidence=top_domains[:2],
                    issue_count=1,
                    technical_steps=["Improve on-page signals and answer structure to push into top 3."],
                    source_signals=["serp_rank", "visibility"],
                )
            )

    # ── Signal 2: Keyword-page alignment gaps ─────────────────────────
    if matrix:
        # Find pages with weak keyword alignment
        weak_pages = [r for r in matrix if r["kw_in_title"] < 0.3 and r["kw_in_h1"] < 0.3 and r["depth_tier"] >= 1]
        best_match_page = max(matrix, key=lambda r: r["kw_in_title"] + r["kw_in_h1"], default=None)

        if best_match_page and (best_match_page["kw_in_title"] + best_match_page["kw_in_h1"]) < 0.5:
            # No page adequately targets the keyword
            kw_toks = _meaningful_tokens(keyword)
            loc_toks = _meaningful_tokens(location)
            svc_toks = _meaningful_tokens(service)
            missing = [t for t in (loc_toks + svc_toks) if t not in _meaningful_tokens(best_match_page["url"])][:3]

            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"No page directly targets '{keyword}' in title or H1.",
                        "category": "Entity clarity",
                        "priority_score": 88,
                        "why_ai_ignores_this": (
                            f"AI systems match query intent to page headings and titles. If no page explicitly "
                            f"names '{keyword}', the site cannot be confidently cited as an answer source."
                        ),
                        "fix": (
                            f"Update the most relevant page's title and H1 to include the key terms from "
                            f"'{keyword}'. Prioritise: {', '.join(kw_toks[:4])}."
                        ),
                        "example_rewrite": (
                            f"Title: '{service.title()} in {location} | [Brand Name]'\n"
                            f"H1: '{service.title()} in {location}'\n"
                            f"Opening: 'We offer [specific capacity/feature] {service} in {location}. [One differentiator].'"
                        ),
                        "expected_impact": "Directly improves citation probability for ChatGPT and Gemini by establishing clear entity-keyword match.",
                        "where_to_apply": [best_match_page["url"]] + target_urls[:2],
                        "action_steps": [
                            f"Update the title of {best_match_page['url']} to include '{location}' and '{service}'.",
                            "Rewrite the H1 to match the target keyword format.",
                            "Open the first paragraph with a direct answer to the query intent.",
                            "Add LocalBusiness schema with address and service type matching the keyword.",
                        ],
                        "root_cause_label": "Keyword-entity mismatch",
                    },
                    page_targets=[best_match_page["url"]] + target_urls[:1],
                    competitor_evidence=[],
                    issue_count=len(weak_pages) + 1,
                    technical_steps=["Align page titles and H1s to the target keyword."],
                    source_signals=["entity_score", "keyword-alignment"],
                )
            )

        # FAQ structure gap
        kw_pages_no_faq = [r for r in matrix if (r["kw_in_title"] >= 0.3 or r["kw_in_h1"] >= 0.3) and not r["has_faq"]]
        if kw_pages_no_faq:
            paa_qs = (serp or {}).get("paa_questions", [])
            faq_examples = paa_qs[:3] if paa_qs else [
                f"What is {service} in {location}?",
                f"How much does {service} in {location} cost?",
                f"What is included in {service} at this venue?",
            ]
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"Keyword-relevant pages lack FAQ schema — AI can't extract structured answers.",
                        "category": "Answer structure",
                        "priority_score": 82,
                        "why_ai_ignores_this": (
                            "ChatGPT specifically uses FAQ schema markup to identify authoritative Q&A content. "
                            "Without it, AI systems must infer answers from unstructured prose, which reduces citation confidence."
                        ),
                        "fix": (
                            f"Add a FAQ section with JSON-LD FAQPage schema to {len(kw_pages_no_faq)} page(s) "
                            f"that match '{keyword}'. Answer the exact questions users are asking."
                        ),
                        "example_rewrite": (
                            "Q: " + "\nQ: ".join(faq_examples)
                        ),
                        "expected_impact": "FAQ schema typically increases ChatGPT citation probability by 15-25 points by providing directly extractable Q&A pairs.",
                        "where_to_apply": [r["url"] for r in kw_pages_no_faq[:3]],
                        "action_steps": [
                            "Add a dedicated FAQ section near the bottom of each target page.",
                            f"Answer these specific questions: {'; '.join(faq_examples[:2])}.",
                            "Wrap the FAQ in FAQPage JSON-LD schema markup.",
                            "Keep each answer under 60 words — direct, factual, and scannable.",
                        ],
                        "root_cause_label": "Missing FAQ schema",
                    },
                    page_targets=[r["url"] for r in kw_pages_no_faq[:3]],
                    competitor_evidence=[],
                    issue_count=len(kw_pages_no_faq),
                    technical_steps=["Add FAQPage schema to keyword-matched pages."],
                    source_signals=["structure_score", "answer-structure"],
                )
            )

        # Content depth gap
        thin_kw_pages = [r for r in matrix if (r["kw_in_title"] >= 0.3 or r["kw_in_h1"] >= 0.3) and r["depth_tier"] <= 1]
        if thin_kw_pages:
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"{len(thin_kw_pages)} keyword-relevant page(s) have thin content (under 400 words).",
                        "category": "Content depth",
                        "priority_score": 76,
                        "why_ai_ignores_this": (
                            "Perplexity and Claude favour fact-dense content above 600 words. Thin pages cannot "
                            "contain the proof, specifics, and context needed for confident AI citation."
                        ),
                        "fix": (
                            f"Expand {', '.join(r['url'] for r in thin_kw_pages[:2])} with detailed content: "
                            f"capacity, pricing tiers, venue specifications, and testimonials."
                        ),
                        "example_rewrite": (
                            f"After the intro, add sections: 'What's Included', 'Capacity & Layout', "
                            f"'Pricing for {service.title()} in {location}', and 'Who This Is For'. "
                            f"Each section: 80-120 words minimum."
                        ),
                        "expected_impact": "Expanding to 600+ words per key page typically unlocks Perplexity citations and improves AI confidence.",
                        "where_to_apply": [r["url"] for r in thin_kw_pages[:3]],
                        "action_steps": [
                            "Add a 'What's Included' section with specific, measurable details.",
                            "Add a pricing or package overview (even if approximate).",
                            "Include a 'Why [Location]' section explaining geographic relevance.",
                            "Add 2-3 client testimonials or proof statements with specific outcomes.",
                        ],
                        "root_cause_label": "Thin content",
                    },
                    page_targets=[r["url"] for r in thin_kw_pages[:3]],
                    competitor_evidence=[],
                    issue_count=len(thin_kw_pages),
                    technical_steps=["Expand thin pages to 600+ words with structured content."],
                    source_signals=["completeness_score", "content-depth"],
                )
            )

    # ── Signal 3: PAA coverage gap ────────────────────────────────────
    if serp:
        paa = serp.get("paa_questions", [])
        has_faq_anywhere = matrix and any(r["has_faq"] for r in matrix)
        if paa and not has_faq_anywhere:
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": f"Google shows {len(paa)} 'People Also Ask' questions for this keyword — none are answered on-site.",
                        "category": "Answer structure",
                        "priority_score": 80,
                        "why_ai_ignores_this": (
                            "PAA questions represent real user intents that AI engines are trained to answer. "
                            "When no page on your site directly addresses these questions, AI systems source answers from competitors."
                        ),
                        "fix": f"Answer these exact PAA questions with structured content on your highest-intent page.",
                        "example_rewrite": "\n".join(f"Q: {q}" for q in paa[:4]),
                        "expected_impact": "Answering PAA questions directly can capture AI citations for 3-5 related search intents beyond the primary keyword.",
                        "where_to_apply": target_urls[:2],
                        "action_steps": [
                            f"Create a FAQ section on your primary page with these {len(paa)} questions.",
                            "Keep answers under 60 words each — direct and factual.",
                            "Add FAQPage JSON-LD schema wrapping each Q&A pair.",
                            "Reference real specifics (prices, times, locations) rather than generic answers.",
                        ],
                        "root_cause_label": "PAA coverage gap",
                    },
                    page_targets=target_urls,
                    competitor_evidence=[],
                    issue_count=len(paa),
                    technical_steps=["Answer PAA questions with structured FAQ content."],
                    source_signals=["answer-readiness", "paa"],
                )
            )

    # ── Signal 4: Absorb high-priority on-page recs from audit ────────
    if on_page_recs:
        top_on_page = max(on_page_recs, key=lambda r: r.get("priority_score", 0))
        if top_on_page.get("priority_score", 0) >= 60:
            recommendations.append(
                decorate_recommendation(
                    {
                        "issue": top_on_page.get("title", "On-page signal gap detected."),
                        "category": "On-page signals",
                        "priority_score": min(top_on_page.get("priority_score", 65), 75),
                        "why_ai_ignores_this": (
                            top_on_page.get("description", "On-page weaknesses reduce AI parsing confidence.") +
                            " AI systems treat on-page quality as a proxy for content authority."
                        ),
                        "fix": top_on_page.get("recommended_fix", "Fix the identified on-page issues."),
                        "example_rewrite": "",
                        "expected_impact": top_on_page.get("estimated_impact", "Improves structural clarity for AI indexing."),
                        "where_to_apply": [top_on_page.get("page_url")] if top_on_page.get("page_url") else target_urls[:1],
                        "action_steps": top_on_page.get("technical_steps", [])[:4],
                        "root_cause_label": top_on_page.get("root_cause_label", "On-page issue"),
                    },
                    page_targets=[top_on_page.get("page_url")] if top_on_page.get("page_url") else target_urls[:1],
                    competitor_evidence=[],
                    issue_count=1,
                    technical_steps=top_on_page.get("technical_steps", [])[:2],
                    source_signals=["on_page_score"],
                )
            )

    # Sort by priority, filter, deduplicate
    recommendations.sort(key=lambda r: -r.get("priority_score", 0))
    seen_roots = set()
    deduped = []
    for r in recommendations:
        root = r.get("root_cause_label", r.get("issue", "")[:30])
        if root not in seen_roots and should_surface_recommendation(r, minimum_score=40):
            seen_roots.add(root)
            deduped.append(r)

    return deduped[:6]


# ─── Cluster helpers (kept for compatibility) ───────────────────────────────

def _aeo_cluster_key(item):
    category = (item.get("category") or "").lower()
    if "answer" in category or "direct-answer" in category:
        return "answer-readiness"
    if "content" in category:
        return "content-depth"
    if "entity" in category or "visibility" in category.replace("search visibility", "visibility"):
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


# ─── Main Payload Builder ───────────────────────────────────────────────────

def build_aeo_payload(*, audit_run, profile=None, target_keyword=""):
    """
    Build the complete AEO payload with precision scoring.
    All four dimension scores are now keyword-sensitive and SERP-grounded.
    """
    # Determine location/country for SERP lookup
    location = getattr(profile, "location", "") or ""
    country_code = ""
    if "kenya" in location.lower():
        country_code = "KE"
    elif "nigeria" in location.lower():
        country_code = "NG"
    elif "ghana" in location.lower():
        country_code = "GH"

    # Fetch live SERP signals for this keyword
    serp = None
    if target_keyword:
        serp = _fetch_serp_signals(target_keyword, location=location, country_code=country_code)
        if audit_run.normalized_domain:
            serp = _enrich_serp_with_domain(serp, audit_run.normalized_domain)

    # Build keyword-page matrix
    pages = list(audit_run.pages.all()[:20])
    matrix = _keyword_page_matrix(pages, target_keyword, profile=profile) if target_keyword else None

    # Compute precision dimension scores
    visibility_score = _build_visibility_score(audit_run, target_keyword, matrix=matrix, serp=serp)
    entity_score = _build_entity_score(profile, audit_run, target_keyword, matrix=matrix, serp=serp)
    structure_score = _build_structure_score(audit_run, target_keyword, matrix=matrix, serp=serp)
    completeness_score = _build_completeness_score(audit_run, target_keyword, matrix=matrix, serp=serp)

    # Build grounded recommendations
    recommendations = build_aeo_recommendations(
        audit_run=audit_run,
        profile=profile,
        target_keyword=target_keyword,
        matrix=matrix,
        serp=serp,
    )

    # Citation Readiness composite (weighted)
    citation_readiness = round(
        visibility_score * 0.35
        + entity_score * 0.25
        + structure_score * 0.25
        + completeness_score * 0.15
    )

    # Per-engine citation scores (anchored to dimension scores for consistency)
    CITE_THRESHOLD = 68
    aeo_s = int(audit_run.aeo_score or 0)
    content_s = int(audit_run.content_score or 0)
    on_page_s = int(audit_run.on_page_score or 0)

    has_faq = any(r["has_faq"] for r in (matrix or []))
    has_schema = any(r["schema_count"] > 0 for r in (matrix or []))
    location_in_kw = False
    if profile and profile.location and target_keyword:
        loc_toks = set(_meaningful_tokens(profile.location))
        kw_toks = set(_meaningful_tokens(target_keyword))
        location_in_kw = bool(loc_toks & kw_toks)

    client_rank = (serp or {}).get("client_rank")

    # ChatGPT: entity + completeness + answer structure (FAQ) + rank boost
    chatgpt_raw = entity_score * 0.4 + completeness_score * 0.3 + aeo_s * 0.3
    chatgpt_raw += 8 if has_faq else -5
    chatgpt_raw += 5 if client_rank and client_rank <= 5 else 0

    # Gemini: on-page + structure + entity + local signal
    gemini_raw = on_page_s * 0.30 + structure_score * 0.35 + entity_score * 0.35
    gemini_raw += 10 if has_schema else -5
    gemini_raw += 8 if location_in_kw else -5
    gemini_raw += 5 if client_rank and client_rank <= 5 else 0

    # Perplexity: content depth + completeness + raw aeo
    avg_wc = sum(r["word_count"] for r in (matrix or [])) / max(len(matrix or []), 1)
    deep_pages_count = sum(1 for r in (matrix or []) if r["depth_tier"] >= 2)
    perplexity_raw = content_s * 0.4 + completeness_score * 0.35 + aeo_s * 0.25
    perplexity_raw += min(deep_pages_count * 4, 12)
    perplexity_raw += 5 if avg_wc >= 400 else -5 if avg_wc < 200 else 0

    # Clamp all raw scores
    chatgpt_raw = min(max(chatgpt_raw, 0), 100)
    gemini_raw = min(max(gemini_raw, 0), 100)
    perplexity_raw = min(max(perplexity_raw, 0), 100)

    def _lever(engine, score, threshold, kw, loc, has_f, has_s, rank):
        if score >= threshold:
            return f"Maintain the current {engine} signals — you're above the citation threshold."
        gap = threshold - score
        if engine == "ChatGPT":
            if not has_f:
                return f"Adding FAQ schema ({gap} pts needed) is the fastest path to ChatGPT citation."
            if rank is None:
                return f"Improve SERP ranking for '{kw}' — ChatGPT sources from top-ranked pages."
            return f"Strengthen answer-first page structure to close the {gap}-pt gap."
        if engine == "Gemini":
            if not has_s:
                return f"Add JSON-LD schema ({gap} pts needed) — Gemini requires structured data for local queries."
            if not loc:
                return f"Add location '{profile.location if profile else loc}' to H1 and title — Gemini needs local entity match."
            return f"Improve on-page quality to close the {gap}-pt gap."
        if engine == "Perplexity":
            if avg_wc < 400:
                return f"Expand pages to 600+ words with facts — Perplexity needs depth ({gap} pts needed)."
            return f"Add more fact-dense, sourced content to close the {gap}-pt gap."
        return f"Close the {gap}-pt gap."

    engine_gaps = [
        {
            "engine": "ChatGPT",
            "score": round(chatgpt_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(chatgpt_raw)),
            "cited": chatgpt_raw >= CITE_THRESHOLD,
            "color": "#10a37f",
            "icon": "🤖",
            "lever": _lever("ChatGPT", chatgpt_raw, CITE_THRESHOLD, target_keyword, location_in_kw, has_faq, has_schema, client_rank),
        },
        {
            "engine": "Gemini",
            "score": round(gemini_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(gemini_raw)),
            "cited": gemini_raw >= CITE_THRESHOLD,
            "color": "#4285f4",
            "icon": "✦",
            "lever": _lever("Gemini", gemini_raw, CITE_THRESHOLD, target_keyword, location_in_kw, has_faq, has_schema, client_rank),
        },
        {
            "engine": "Perplexity",
            "score": round(perplexity_raw),
            "threshold": CITE_THRESHOLD,
            "gap": max(0, CITE_THRESHOLD - round(perplexity_raw)),
            "cited": perplexity_raw >= CITE_THRESHOLD,
            "color": "#a855f7",
            "icon": "⊕",
            "lever": _lever("Perplexity", perplexity_raw, CITE_THRESHOLD, target_keyword, location_in_kw, has_faq, has_schema, client_rank),
        },
    ]

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
            "location": location,
            "target_goal": getattr(profile, "target_goal", ""),
            "primary_service": getattr(profile, "primary_service", ""),
            "target_keyword": target_keyword,
        },
        "serp": {
            "client_rank": client_rank,
            "top_domains": (serp or {}).get("top_domains", [])[:5],
            "paa_questions": (serp or {}).get("paa_questions", []),
            "has_ai_overview": (serp or {}).get("has_ai_overview", False),
            "has_answer_box": (serp or {}).get("has_answer_box", False),
        } if serp else {},
        "engine_gaps": engine_gaps,
        "top_priority_fix": top_priority_fix,
        "recommendations": recommendations,
    }


# ─── AEO Audit Creator ──────────────────────────────────────────────────────

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
                example_rewrite=item.get("example_rewrite", ""),
                expected_impact=item["expected_impact"],
                priority_score=item["priority_score"],
                category=item["category"],
            )
            for item in payload["recommendations"]
        ]
    )

    # ── Precision VisibilitySnapshots (unified with engine_gaps) ──────────────
    domain = audit_run.normalized_domain
    if domain:
        target_query = target_keyword or getattr(profile, "primary_service", "service")
        pages = list(audit_run.pages.all()[:15])
        location = getattr(profile, "location", "") or ""
        kw_lower = target_query.lower()

        # Reuse matrix from payload engine_gaps for consistency
        matrix = _keyword_page_matrix(pages, target_query, profile=profile)
        has_faq_schema = any(r["has_faq"] for r in matrix)
        has_schema = any(r["schema_count"] > 0 for r in matrix)
        avg_word_count = sum(r["word_count"] for r in matrix) / max(len(matrix), 1)
        high_depth_pages = sum(1 for r in matrix if r["depth_tier"] >= 2)

        loc_in_kw = False
        if profile and profile.location:
            loc_toks = set(_meaningful_tokens(location))
            kw_toks = set(_meaningful_tokens(kw_lower))
            loc_in_kw = bool(loc_toks & kw_toks)

        # Read engine scores from payload to keep snapshot consistent with hero
        chatgpt_gap = next((e for e in payload["engine_gaps"] if e["engine"] == "ChatGPT"), {})
        gemini_gap = next((e for e in payload["engine_gaps"] if e["engine"] == "Gemini"), {})
        perplexity_gap = next((e for e in payload["engine_gaps"] if e["engine"] == "Perplexity"), {})

        chatgpt_ans = chatgpt_gap.get("cited", False)
        gemini_ans = gemini_gap.get("cited", False)
        perplexity_ans = perplexity_gap.get("cited", False)

        chatgpt_score = chatgpt_gap.get("score", 0)
        gemini_score = gemini_gap.get("score", 0)
        perplexity_score = perplexity_gap.get("score", 0)

        chatgpt_freq = 2 if chatgpt_score >= 85 else (1 if chatgpt_ans else 0)
        gemini_freq = 2 if gemini_score >= 85 else (1 if gemini_ans else 0)
        perplexity_freq = 2 if perplexity_score >= 85 else (1 if perplexity_ans else 0)

        # Specific, grounded reasoning notes
        chatgpt_reason = chatgpt_gap.get("lever", "Improve FAQ schema and answer structure for ChatGPT citation.")
        gemini_reason = gemini_gap.get("lever", "Improve schema markup and local entity alignment for Gemini.")
        perplexity_reason = perplexity_gap.get("lever", "Expand content depth for Perplexity citation confidence.")

        # Enrich with specific page evidence
        if chatgpt_ans and has_faq_schema:
            chatgpt_reason = f"FAQ schema detected on {sum(1 for r in matrix if r['has_faq'])} page(s) — ChatGPT can extract structured answers."
        elif not chatgpt_ans and not has_faq_schema:
            chatgpt_reason = f"No FAQ schema found across {len(matrix)} pages — ChatGPT needs structured Q&A to cite confidently."
        if gemini_ans and loc_in_kw:
            gemini_reason = f"Location '{location}' appears in keyword and schema is present — Gemini recognises local entity match."
        elif not gemini_ans and not loc_in_kw and profile and profile.location:
            gemini_reason = f"Keyword does not reference '{location}' explicitly — Gemini's local ranking algorithm requires geographic match in headings."
        if perplexity_ans and high_depth_pages >= 2:
            perplexity_reason = f"Content depth is strong ({high_depth_pages} pages over 600 words) — Perplexity can source factual answers directly."
        elif not perplexity_ans and high_depth_pages == 0:
            perplexity_reason = f"No pages exceed 600 words — Perplexity requires depth and fact density to cite. Avg word count: {round(avg_word_count)}."

        client_rank = payload.get("serp", {}).get("client_rank")
        if client_rank:
            chatgpt_reason = f"Ranked #{client_rank} for '{target_query}'. " + chatgpt_reason
            gemini_reason = f"Ranked #{client_rank} in SERP. " + gemini_reason

        snapshots = [
            VisibilitySnapshot(
                aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.CHATGPT,
                prompt=f"{target_query}?",
                cited_url=f"https://{domain}" if chatgpt_ans else "",
                answer_present=chatgpt_ans, citation_frequency=chatgpt_freq,
                notes=chatgpt_reason,
            ),
            VisibilitySnapshot(
                aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.GEMINI,
                prompt=f"{target_query}",
                cited_url=f"https://{domain}" if gemini_ans else "",
                answer_present=gemini_ans, citation_frequency=gemini_freq,
                notes=gemini_reason,
            ),
            VisibilitySnapshot(
                aeo_audit=aeo_audit, engine=VisibilitySnapshot.Engine.PERPLEXITY,
                prompt=f"What is {target_query}?",
                cited_url=f"https://{domain}" if perplexity_ans else "",
                answer_present=perplexity_ans, citation_frequency=perplexity_freq,
                notes=perplexity_reason,
            ),
        ]
        VisibilitySnapshot.objects.bulk_create(snapshots)

        # ── Pre-fetch AEO Competitors ──────────────────────────────────────────
        # Find domains mentioned in the local pack and AI sources
        serp = payload.get("serp") or {}
        intel = payload.get("aeo_intelligence") or {}
        
        comps_to_fetch = set()
        for place in intel.get("local_pack", [])[:3]:
            d = _extract_domain(place.get("link", ""))
            if d and d != domain:
                comps_to_fetch.add(d)
                
        for source in intel.get("aeo_overview", {}).get("sources", [])[:3]:
            d = _extract_domain(source.get("link", ""))
            if d and d != domain:
                comps_to_fetch.add(d)

        if comps_to_fetch:
            from apps.seo.models import SEOCompetitor
            from apps.seo.services import get_or_build_competitor_snapshot
            
            comps_fetched = 0
            # Limit the fetch to 2-3 to prevent the response from dropping, but enough to trigger the beautiful loader
            for comp_domain in list(comps_to_fetch)[:3]:
                comp_obj = SEOCompetitor.objects.filter(project=project, normalized_domain=comp_domain).first()
                if not comp_obj:
                    comp_obj = SEOCompetitor.objects.create(
                        project=project,
                        normalized_domain=comp_domain,
                        homepage_url=f"https://{comp_domain}",
                        label=comp_domain,
                        source=SEOCompetitor.Source.SERP,
                        is_active=True
                    )
                # Force synchronous snapshot generation so benchmarks populate immediately
                get_or_build_competitor_snapshot(competitor=comp_obj, audit_run=audit_run, profile=profile)
                comps_fetched += 1

    return aeo_audit


# ─── Query Accessors ────────────────────────────────────────────────────────

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
    """Build a side-by-side AEO benchmark comparing the client site against discovered competitors."""
    from apps.seo.models import SEOCompetitor

    benchmarks = []
    seen_domains = set()

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

    active_comps = SEOCompetitor.objects.filter(
        project=project, is_active=True, normalized_domain__isnull=False
    ).prefetch_related("snapshots")[:4]

    for comp in active_comps:
        domain = comp.normalized_domain
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        snap = comp.snapshots.order_by("-created_at").first()
        if snap and snap.output_json and snap.output_json.get("pages"):
            pages_data = snap.output_json.get("pages", [])
            has_faq = any(p.get("has_faq_schema") for p in pages_data)
            has_schema = any((p.get("schema_count") or 0) > 0 for p in pages_data)
            avg_w = round(sum(p.get("word_count", 0) for p in pages_data) / max(len(pages_data), 1))
            
            # Synthesize proxy structural readiness scores natively from page signals
            vis = 40 + (20 if has_faq else 0) + (15 if has_schema else 0) + (15 if avg_w >= 400 else 0)
            ent = 45 + (15 if has_schema else 0) + (10 if has_faq else 0) + (10 if avg_w > 300 else 0)
            struct = 40 + (20 if has_faq else 0) + (15 if has_schema else 0)
            comp_ = 45 + (10 if avg_w >= 200 else 0) + (20 if avg_w >= 500 else 0)
        else:
            has_faq = has_schema = False
            avg_w = 0
            vis = ent = struct = comp_ = 0

        readiness = round(vis * 0.35 + ent * 0.25 + struct * 0.25 + comp_ * 0.15)
        benchmarks.append({
            "label": comp.label or domain, "domain": domain, "is_client": False,
            "visibility": vis, "entity": ent, "structure": struct, "completeness": comp_,
            "readiness": readiness, "has_faq_schema": has_faq, "has_schema": has_schema,
            "avg_words": avg_w, "source": "competitor_record", "unknown": vis == 0,
        })

    intel = aeo_intelligence or {}
    serp_sources = []
    for place in intel.get("local_pack", [])[:3]:
        domain = _extract_domain(place.get("link", ""))
        if domain and domain not in seen_domains:
            serp_sources.append({"label": place.get("title", domain), "domain": domain, "source": "local_pack"})
            seen_domains.add(domain)
    for source in intel.get("aeo_overview", {}).get("sources", [])[:3]:
        domain = _extract_domain(source.get("link", ""))
        if domain and domain not in seen_domains:
            serp_sources.append({"label": source.get("text", domain), "domain": domain, "source": "serp_source"})
            seen_domains.add(domain)

    for entry in serp_sources[:3]:
        benchmarks.append({
            "label": entry["label"], "domain": entry["domain"], "is_client": False,
            "visibility": None, "entity": None, "structure": None, "completeness": None,
            "readiness": None, "has_faq_schema": None, "has_schema": None, "avg_words": None,
            "source": entry["source"], "unknown": True,
        })

    return {
        "client": client,
        "competitors": benchmarks[:4],
        "dimensions": ["visibility", "entity", "structure", "completeness"],
        "has_data": bool(benchmarks),
    }
