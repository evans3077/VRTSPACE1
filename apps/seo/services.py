from collections import Counter, defaultdict
from types import SimpleNamespace
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils.text import slugify

from .discovery import discover_serp_competitors
from apps.tools.services import (
    ParsedPage,
    analyze_assets,
    choose_urls_to_crawl,
    detect_tech_stack,
    extract_domain,
    fetch_many,
    normalize_competitor_urls,
    normalize_url,
    parse_page,
    parse_sitemap,
    safe_fetch,
)

from .models import (
    SEOCampaign,
    SEOCompetitor,
    SEOCompetitorSnapshot,
    SEOContextSnapshot,
    SEOOpportunitySnapshot,
    SEOProjectProfile,
    SEOSiteStructureSnapshot,
)


INDUSTRY_RULES = {
    "automotive": {
        "label": "Automotive",
        "priority_page_types": ["inventory", "location", "service", "finance", "faq"],
        "goal_focus": "commercial and local intent queries that move buyers toward inquiry",
    },
    "agency": {
        "label": "Agency / Professional Services",
        "priority_page_types": ["service", "industry", "case_study", "pricing", "faq"],
        "goal_focus": "high-intent service and proof-led comparison searches",
    },
    "saas": {
        "label": "SaaS",
        "priority_page_types": ["feature", "comparison", "pricing", "use_case", "faq"],
        "goal_focus": "feature discovery, comparison intent, and product-led content expansion",
    },
    "hotel": {
        "label": "Hotel / Hospitality",
        "priority_page_types": ["location", "room", "event", "amenity", "faq"],
        "goal_focus": "local booking intent, amenity demand, and event-driven searches",
    },
    "ecommerce": {
        "label": "Ecommerce",
        "priority_page_types": ["category", "pricing", "comparison", "faq", "article"],
        "goal_focus": "transactional queries and category-level coverage",
    },
    "healthcare": {
        "label": "Healthcare",
        "priority_page_types": ["service", "location", "faq", "article", "about"],
        "goal_focus": "trust-led local demand and question-led discovery",
    },
    "real_estate": {
        "label": "Real Estate",
        "priority_page_types": ["location", "service", "faq", "article", "comparison"],
        "goal_focus": "location intent, area demand, and conversion-ready property research",
    },
    "local_service": {
        "label": "Local Service Business",
        "priority_page_types": ["service", "location", "pricing", "faq", "review"],
        "goal_focus": "map-pack and city-level service demand",
    },
}

BUSINESS_TYPE_KEYWORDS = {
    "automotive": ["car", "cars", "vehicle", "vehicles", "dealership", "dealer", "auto", "automotive", "financing"],
    "agency": ["agency", "marketing", "seo", "design", "branding", "consulting", "strategy", "case study"],
    "saas": ["software", "platform", "dashboard", "product", "features", "subscription", "app"],
    "hotel": ["hotel", "stay", "room", "rooms", "booking", "suite", "amenity", "resort"],
    "ecommerce": ["shop", "store", "product", "products", "checkout", "cart", "collection", "buy"],
    "healthcare": ["clinic", "care", "doctor", "patient", "appointment", "medical", "health"],
    "real_estate": ["property", "properties", "real estate", "home", "homes", "listing", "apartment"],
    "local_service": ["service", "services", "repair", "installation", "pricing", "quote", "booking"],
}

NON_COMPETITOR_PAGE_HINTS = {
    "directory",
    "directories",
    "listing",
    "listings",
    "blog",
    "wordpress",
    "top 10",
    "lead finder",
    "lead generation",
    "classifieds",
    "document",
    "pdf",
    "resource",
}

NON_COMPETITOR_HOST_HINTS = {
    "wordpress.com",
    "blogspot.com",
    "scribd.com",
}

FOREIGN_GEO_HINTS = {
    "austin",
    "texas",
    "tx",
    "fort worth",
    "dallas",
    "houston",
    "united states",
    "usa",
    "uk",
    "united kingdom",
    "london",
    "canada",
    "toronto",
    "australia",
    "india",
    "dubai",
}

COMPETITOR_REVIEW_DECISIONS = {
    "auto": "Automatic",
    "approved": "Approved",
    "pinned": "Pinned",
    "suppressed": "Suppressed",
    "rejected": "Rejected",
}

BUSINESS_TYPE_KEYWORD_TEMPLATES = {
    "automotive": {
        "core": [
            "{service} in {location}",
            "{service} {location}",
            "used cars for sale {location}",
            "car dealer {location}",
            "buy used cars {location}",
        ],
        "page_types": {
            "inventory": "used cars for sale {location}",
            "service": "car dealer {location}",
            "faq": "{service} {location} faq",
            "finance": "car financing {location}",
            "location": "used cars in {location}",
            "comparison": "best used car dealer {location}",
        },
    },
}

DEFAULT_RULE = {
    "label": "General",
    "priority_page_types": ["service", "faq", "pricing", "article"],
    "goal_focus": "high-intent organic discovery tied to the declared business goal",
}

PAGE_TYPE_PATTERNS = {
    "faq": ["faq", "faqs", "questions"],
    "contact": ["contact", "contact-us", "reach-us"],
    "about": ["about", "about-us", "company", "team"],
    "pricing": ["pricing", "plans", "cost", "fees", "quote"],
    "article": ["blog", "article", "news", "guide", "insights", "resources"],
    "comparison": ["compare", "comparison", "vs", "versus", "alternative"],
    "review": ["review", "reviews", "testimonials", "testimonial"],
    "service": ["services", "service"],
    "location": ["location", "locations", "areas", "city"],
    "feature": ["features", "feature", "platform", "solution"],
    "use_case": ["use-case", "use-cases", "for-", "industries"],
    "room": ["rooms", "room", "suite", "accommodation"],
    "event": ["event", "events", "conference", "wedding", "meeting"],
    "amenity": ["amenities", "spa", "restaurant", "pool"],
    "inventory": ["inventory", "vehicle", "vehicles", "cars", "stock"],
    "category": ["category", "categories", "collection", "shop", "products"],
    "finance": ["finance", "financing", "loan", "payment"],
    "case_study": ["case-study", "case-studies", "results"],
    "industry": ["industry", "industries", "sector"],
}


def get_industry_rule(business_type):
    return INDUSTRY_RULES.get((business_type or "").strip().lower(), DEFAULT_RULE)


def infer_business_type_for_project(project, *, audit_run=None, primary_service=""):
    audit_run = audit_run or getattr(project, "latest_audit_run", None)
    text_parts = [primary_service or ""]
    audit_request = getattr(project, "audit_request", None)
    if audit_request:
        text_parts.extend(
            [
                getattr(audit_request, "company_name", "") or "",
                getattr(audit_request, "website", "") or "",
            ]
        )
    if audit_run:
        for page in audit_run.pages.order_by("-word_count", "url")[:8]:
            text_parts.extend([page.url or "", page.title or "", page.h1 or "", page.meta_description or ""])

    haystack = " ".join(text_parts).lower()
    scores = {}
    for business_type, keywords in BUSINESS_TYPE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in haystack:
                score += 2 if " " in keyword else 1
        scores[business_type] = score
    inferred = max(scores, key=scores.get) if scores else "local_service"
    if scores.get(inferred, 0) <= 0:
        return "local_service"
    return inferred


def _tokenize_phrase(text):
    tokens = []
    for raw in str(text or "").replace("/", " ").replace("-", " ").split():
        token = raw.strip(" ,.:;!?()[]{}\"'").lower()
        if len(token) < 3:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _service_seed(profile):
    return (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()


def _keyword_template_group(profile):
    return BUSINESS_TYPE_KEYWORD_TEMPLATES.get(profile.business_type, {})


def _profile_topic_terms(profile):
    terms = []
    raw_terms = [_service_seed(profile), profile.business_type.replace("_", " ")]
    raw_terms.extend(BUSINESS_TYPE_KEYWORDS.get(profile.business_type, []))
    for raw in raw_terms:
        value = " ".join(str(raw or "").replace("/", " ").replace("-", " ").split()).strip().lower()
        if len(value) < 3 or value in terms:
            continue
        terms.append(value)
    return terms


def _has_foreign_geo_conflict(haystack, location):
    location_tokens = _tokenize_phrase(location)
    if any(token in haystack for token in location_tokens):
        return False
    return any(token in haystack for token in FOREIGN_GEO_HINTS)


def _candidate_text(parsed_page):
    return " ".join(
        [
            parsed_page.title or "",
            parsed_page.h1 or "",
            parsed_page.meta_description or "",
        ]
    ).lower()


def classify_page_type(url, parsed_page, business_type=""):
    parsed = urlparse(url)
    path = parsed.path.lower().strip("/") or "home"
    combined_text = _candidate_text(parsed_page)

    if path == "home":
        return "home"

    for page_type, patterns in PAGE_TYPE_PATTERNS.items():
        if any(segment in path for segment in patterns) or any(pattern in combined_text for pattern in patterns):
            return page_type

    if business_type == "automotive" and any(token in path for token in ("used", "new", "cars", "vehicle")):
        return "inventory"
    if business_type == "hotel" and any(token in path for token in ("stay", "book", "room")):
        return "room"
    if business_type == "saas" and any(token in path for token in ("integrations", "integration", "platform")):
        return "feature"
    if path.count("/") <= 1:
        return "service"
    return "general"


def _page_location_match(parsed_page, location):
    if not location:
        return False
    haystack = f"{parsed_page.title} {parsed_page.h1} {parsed_page.meta_description} {parsed_page.url}".lower()
    return location.lower() in haystack


def _serialize_page(parsed_page, *, business_type="", location=""):
    page_type = classify_page_type(parsed_page.url, parsed_page, business_type=business_type)
    assets = analyze_assets(parsed_page)
    tech_stack = detect_tech_stack(parsed_page)
    parsed_domain = extract_domain(parsed_page.url)
    internal_links = 0
    for link in parsed_page.links:
        normalized = normalize_url(link)
        if not normalized:
            continue
        if extract_domain(normalized) == parsed_domain:
            internal_links += 1
    return {
        "url": parsed_page.url,
        "title": parsed_page.title,
        "h1": parsed_page.h1,
        "meta_description": parsed_page.meta_description,
        "word_count": parsed_page.word_count,
        "schema_count": parsed_page.schema_count,
        "has_faq_schema": parsed_page.has_faq_schema,
        "response_time_ms": parsed_page.response_time_ms,
        "page_type": page_type,
        "location_match": _page_location_match(parsed_page, location),
        "asset_summary": assets,
        "tech_stack": tech_stack,
        "internal_link_count": internal_links,
    }


def _summarize_pages(pages):
    counts_by_type = Counter(page["page_type"] for page in pages)
    avg_word_count_by_type = {}
    asset_totals = Counter()
    cms_counter = Counter()
    framework_counter = Counter()
    for page_type in counts_by_type:
        relevant = [page["word_count"] for page in pages if page["page_type"] == page_type]
        avg_word_count_by_type[page_type] = round(sum(relevant) / max(len(relevant), 1))
    for page in pages:
        for asset_name, asset_value in (page.get("asset_summary") or {}).items():
            asset_totals[asset_name] += asset_value
        cms = ((page.get("tech_stack") or {}).get("cms") or "").strip()
        framework = ((page.get("tech_stack") or {}).get("framework") or "").strip()
        if cms:
            cms_counter[cms] += 1
        if framework:
            framework_counter[framework] += 1
    return {
        "counts_by_type": dict(counts_by_type),
        "avg_word_count_by_type": avg_word_count_by_type,
        "faq_schema_pages": len([page for page in pages if page["has_faq_schema"]]),
        "location_match_pages": len([page for page in pages if page["location_match"]]),
        "page_count": len(pages),
        "asset_totals": dict(asset_totals),
        "top_cms": cms_counter.most_common(3),
        "top_frameworks": framework_counter.most_common(3),
    }


def _score_competitor_page_fit(page, profile):
    haystack = " ".join(
        [
            page.get("url", ""),
            page.get("title", ""),
            page.get("h1", ""),
            page.get("meta_description", ""),
        ]
    ).lower()
    topic_score = 0
    local_score = 0
    penalty = 0
    signals = []

    for term in _profile_topic_terms(profile):
        if term and term in haystack:
            topic_score += 3 if " " in term else 1
            signals.append(f"topic:{term}")
    for token in _tokenize_phrase(profile.location):
        if token in haystack:
            local_score += 2
            signals.append(f"location:{token}")
    if any(hint in haystack for hint in NON_COMPETITOR_PAGE_HINTS):
        penalty += 5
        signals.append("non_competitor_pattern")
    if _has_foreign_geo_conflict(haystack, profile.location):
        penalty += 6
        signals.append("foreign_location_conflict")
    return {
        "score": topic_score + local_score - penalty,
        "topic_score": topic_score,
        "local_score": local_score,
        "penalty": penalty,
        "signals": signals[:8],
    }


def _score_competitor_payload_fit(payload, profile):
    pages = _normalized_competitor_pages(payload)
    domain = extract_domain(payload.get("url", ""))
    summary = payload.get("summary", {}) or {}
    page_scores = [_score_competitor_page_fit(page, profile) for page in pages]
    matching_pages = [item for item in page_scores if item["score"] >= 4]
    best_score = max((item["score"] for item in page_scores), default=0)
    total_topic = sum(item["topic_score"] for item in page_scores)
    total_local = sum(item["local_score"] for item in page_scores)
    total_penalty = sum(item["penalty"] for item in page_scores)
    signal_counter = Counter()
    penalty_counter = Counter()
    for item in page_scores:
        for signal in item.get("signals", []):
            if signal in {"non_competitor_pattern", "foreign_location_conflict"}:
                penalty_counter[signal] += 1
            else:
                signal_counter[signal] += 1
    accepted = bool(
        best_score >= 6
        and matching_pages
        and total_topic > total_penalty
        and not any(domain == hint or domain.endswith(f".{hint}") for hint in NON_COMPETITOR_HOST_HINTS)
    )
    if not accepted and summary.get("page_count", 0) and summary.get("location_match_pages", 0):
        accepted = True
    reason_parts = []
    if matching_pages:
        reason_parts.append(f"{len(matching_pages)} page(s) matched the declared niche and location.")
    if total_penalty:
        reason_parts.append("Some pages showed non-competitor or foreign-location signals.")
    if not accepted and not reason_parts:
        reason_parts.append("Low topic and local relevance for the declared business niche.")
    return {
        "accepted": accepted,
        "best_page_score": best_score,
        "matching_pages": len(matching_pages),
        "topic_score": total_topic,
        "local_score": total_local,
        "penalty": total_penalty,
        "match_signals": [signal for signal, _count in signal_counter.most_common(6)],
        "penalty_signals": [signal for signal, _count in penalty_counter.most_common(4)],
        "reason": " ".join(reason_parts).strip(),
    }


def _competitor_review(competitor):
    review = (competitor.metadata or {}).get("review")
    if not isinstance(review, dict):
        return {"decision": "auto", "label": COMPETITOR_REVIEW_DECISIONS["auto"], "note": ""}
    decision = str(review.get("decision") or "auto").strip().lower()
    if decision not in COMPETITOR_REVIEW_DECISIONS:
        decision = "auto"
    return {
        "decision": decision,
        "label": COMPETITOR_REVIEW_DECISIONS[decision],
        "note": str(review.get("note") or "").strip(),
    }


def _competitor_is_included(competitor, fit_summary):
    decision = _competitor_review(competitor)["decision"]
    if decision in {"approved", "pinned"}:
        return True
    if decision in {"suppressed", "rejected"}:
        return False
    return bool(fit_summary.get("accepted"))


def _competitor_final_decision(competitor, fit_summary):
    decision = _competitor_review(competitor)["decision"]
    if decision in {"approved", "pinned", "suppressed", "rejected"}:
        return decision
    return "accepted" if fit_summary.get("accepted") else "filtered_out"


def _build_competitor_trace(snapshot, profile):
    payload = snapshot.output_json or {}
    competitor = snapshot.competitor
    fit_summary = ((payload.get("summary") or {}).get("fit")) or _score_competitor_payload_fit(payload, profile)
    review = _competitor_review(competitor)
    serp_metadata = ((competitor.metadata or {}).get("serp") or {})
    final_decision = _competitor_final_decision(competitor, fit_summary)
    return {
        "competitor_id": competitor.pk,
        "domain": competitor.normalized_domain,
        "url": competitor.homepage_url,
        "source": competitor.source,
        "source_label": competitor.get_source_display(),
        "status": payload.get("status", "unknown"),
        "final_decision": final_decision,
        "final_decision_label": COMPETITOR_REVIEW_DECISIONS.get(final_decision, final_decision.replace("_", " ").title()),
        "included": payload.get("status") == "ok" and _competitor_is_included(competitor, fit_summary),
        "review_decision": review["decision"],
        "review_label": review["label"],
        "review_note": review["note"],
        "fit": fit_summary,
        "queries": serp_metadata.get("queries", []),
        "best_position": serp_metadata.get("best_position"),
        "average_relevance": serp_metadata.get("average_relevance"),
        "discovery_score": serp_metadata.get("discovery_score"),
        "match_signals": serp_metadata.get("match_signals", []),
        "sample_titles": serp_metadata.get("sample_titles", []),
        "sample_snippets": serp_metadata.get("sample_snippets", []),
        "page_count": (payload.get("summary") or {}).get("page_count", 0),
    }


def _accepted_competitor_snapshots(competitor_snapshots, profile):
    accepted = []
    for snapshot in competitor_snapshots:
        payload = snapshot.output_json or {}
        if payload.get("status") != "ok":
            continue
        if not profile:
            accepted.append(snapshot)
            continue
        fit_summary = ((payload.get("summary") or {}).get("fit")) or _score_competitor_payload_fit(payload, profile)
        if _competitor_is_included(snapshot.competitor, fit_summary):
            accepted.append(snapshot)
    return accepted


def _build_site_pages_from_audit(audit_run, *, business_type="", location=""):
    pages = []
    for audit_page in audit_run.pages.all():
        parsed_page = ParsedPage(
            url=audit_page.url,
            status_code=audit_page.status_code,
            response_time_ms=audit_page.response_time_ms,
            html="",
            headers={},
        )
        parsed_page.title = audit_page.title or ""
        parsed_page.meta_description = audit_page.meta_description or ""
        parsed_page.h1s = [audit_page.h1] if audit_page.h1 else []
        parsed_page.schema_blocks = ["faq"] if audit_page.has_faq_schema else ["schema"] * max(audit_page.schema_count, 0)
        parsed_page.word_count = audit_page.word_count or 0
        pages.append(_serialize_page(parsed_page, business_type=business_type, location=location))
    return pages


def build_site_structure_snapshot(*, project, audit_run, profile):
    effective_business_type = profile.business_type or infer_business_type_for_project(project, audit_run=audit_run)
    pages = _build_site_pages_from_audit(
        audit_run,
        business_type=effective_business_type,
        location=profile.location,
    )
    return {
        "domain": project.normalized_domain,
        "pages": pages,
        "summary": _summarize_pages(pages),
    }


def get_or_build_site_structure_snapshot(*, project, audit_run, profile):
    latest = (
        SEOSiteStructureSnapshot.objects.filter(project=project, source_audit_run=audit_run)
        .order_by("-created_at")
        .first()
    )
    if latest:
        return latest
    return SEOSiteStructureSnapshot.objects.create(
        project=project,
        source_audit_run=audit_run,
        output_json=build_site_structure_snapshot(project=project, audit_run=audit_run, profile=profile),
    )


def _default_competitor_urls(project):
    audit_request = getattr(project, "audit_request", None)
    own_domain = project.normalized_domain or extract_domain(project.website or "")
    return normalize_competitor_urls(
        getattr(audit_request, "competitor_urls", []),
        own_domain=own_domain,
    )


def sync_project_competitors(project, raw_values=None):
    own_domain = project.normalized_domain or extract_domain(project.website or "")
    urls = normalize_competitor_urls(raw_values or _default_competitor_urls(project), own_domain=own_domain)

    active_urls = set()
    for url in urls:
        normalized_domain = extract_domain(url)
        competitor = (
            SEOCompetitor.objects.filter(
                project=project,
                normalized_domain=normalized_domain,
                source=SEOCompetitor.Source.PROFILE,
            )
            .order_by("-is_active", "-updated_at")
            .first()
        )
        if not competitor:
            competitor = SEOCompetitor.objects.create(
                project=project,
                homepage_url=url,
                normalized_domain=normalized_domain,
                label=normalized_domain,
                source=SEOCompetitor.Source.PROFILE,
            )
        competitor.homepage_url = url
        competitor.normalized_domain = extract_domain(url)
        competitor.label = competitor.label or competitor.normalized_domain
        competitor.source = SEOCompetitor.Source.PROFILE
        competitor.is_active = True
        competitor.save(update_fields=["homepage_url", "normalized_domain", "label", "source", "is_active", "updated_at"])
        active_urls.add(url)

    SEOCompetitor.objects.filter(project=project, source=SEOCompetitor.Source.PROFILE).exclude(
        homepage_url__in=active_urls
    ).update(
        is_active=False,
    )
    return list(SEOCompetitor.objects.filter(project=project, is_active=True).order_by("homepage_url"))


def sync_discovered_competitors(project, profile):
    discovery = discover_serp_competitors(project, profile)
    active_urls = set()
    for item in discovery.get("competitors", []):
        if not isinstance(item, dict):
            continue
        homepage_url = item.get("homepage_url")
        normalized_domain = item.get("normalized_domain")
        label = item.get("label") or normalized_domain or extract_domain(homepage_url or "")
        if not homepage_url or not normalized_domain:
            continue
        competitor = (
            SEOCompetitor.objects.filter(
                project=project,
                normalized_domain=normalized_domain,
            )
            .order_by("source", "-is_active", "-updated_at")
            .first()
        )
        if not competitor:
            competitor = SEOCompetitor.objects.create(
                project=project,
                homepage_url=homepage_url,
                normalized_domain=normalized_domain,
                label=label,
                source=SEOCompetitor.Source.SERP,
                metadata={"serp": item},
            )
        metadata = competitor.metadata or {}
        metadata["serp"] = item
        competitor.homepage_url = homepage_url
        competitor.normalized_domain = normalized_domain
        competitor.label = label
        if competitor.source != SEOCompetitor.Source.PROFILE:
            competitor.source = SEOCompetitor.Source.SERP
        competitor.is_active = True
        competitor.metadata = metadata
        competitor.save(
            update_fields=[
                "homepage_url",
                "normalized_domain",
                "label",
                "source",
                "is_active",
                "metadata",
                "updated_at",
            ]
        )
        active_urls.add(homepage_url)

    for competitor in SEOCompetitor.objects.filter(project=project, source=SEOCompetitor.Source.SERP).exclude(
        homepage_url__in=active_urls
    ):
        if _competitor_review(competitor)["decision"] in {"approved", "pinned"}:
            continue
        competitor.is_active = False
        competitor.save(update_fields=["is_active", "updated_at"])
    return discovery


def _competitor_priority(competitor):
    serp_metadata = (competitor.metadata or {}).get("serp", {})
    review_priority = {
        "pinned": -2,
        "approved": -1,
        "auto": 0,
        "suppressed": 1,
        "rejected": 2,
    }.get(_competitor_review(competitor)["decision"], 0)
    source_priority = 0 if competitor.source == SEOCompetitor.Source.PROFILE else 1
    return (
        review_priority,
        source_priority,
        -float(serp_metadata.get("discovery_score", 0) or 0),
        float(serp_metadata.get("best_position", 999) or 999),
        competitor.homepage_url,
    )


def _fetch_competitor_pages(competitor_url, *, business_type="", location=""):
    session = requests.Session()
    homepage_response = safe_fetch(competitor_url, session=session)
    if (
        not homepage_response
        or homepage_response.get("status_code", 0) >= 400
        or "html" not in homepage_response.get("content_type", "").lower()
    ):
        return {
            "status": "unavailable",
            "url": competitor_url,
            "pages": [],
            "summary": {},
        }

    homepage = parse_page(homepage_response.get("final_url") or competitor_url, homepage_response)
    sitemap_response = safe_fetch(normalize_url(f"{competitor_url.rstrip('/')}/sitemap.xml"), session=session)
    sitemap_urls = []
    if sitemap_response and "xml" in sitemap_response.get("content_type", "").lower():
        sitemap_urls = parse_sitemap(sitemap_response.get("body", ""))

    crawl_urls = choose_urls_to_crawl(
        homepage.url,
        homepage,
        sitemap_urls,
        limit=settings.SEO_COMPETITOR_PAGE_LIMIT,
    )
    fetched = fetch_many(crawl_urls, session)
    pages = []
    for url, response in fetched.items():
        if not response or response.get("status_code", 0) >= 400 or "html" not in response.get("content_type", "").lower():
            continue
        parsed = parse_page(response.get("final_url") or url, response)
        pages.append(_serialize_page(parsed, business_type=business_type, location=location))

    if not pages:
        pages.append(_serialize_page(homepage, business_type=business_type, location=location))

    summary = _summarize_pages(pages)
    payload = {
        "status": "ok",
        "url": competitor_url,
        "pages": pages,
        "summary": summary,
    }
    payload["summary"]["fit"] = _score_competitor_payload_fit(
        payload,
        SimpleNamespace(
            business_type=business_type or "local_service",
            location=location or "",
            target_goal="",
            primary_service="",
            target_audience="",
        ),
    )
    return payload


def get_or_build_competitor_snapshot(*, competitor, audit_run, profile):
    latest = (
        SEOCompetitorSnapshot.objects.filter(competitor=competitor, source_audit_run=audit_run)
        .order_by("-created_at")
        .first()
    )
    if latest:
        return latest
    payload = _fetch_competitor_pages(
        competitor.homepage_url,
        business_type=profile.business_type,
        location=profile.location,
    )
    return SEOCompetitorSnapshot.objects.create(
        competitor=competitor,
        source_audit_run=audit_run,
        output_json=payload,
    )


def build_local_keyword_set(profile):
    service = _service_seed(profile)
    location = profile.location or "target area"
    audience = profile.target_audience or "buyers"
    templates = _keyword_template_group(profile).get("core") or [
        "{service} in {location}",
        "{service} {location}",
        "best {service} {location}",
        "{service} near me",
        "{service} for {audience}",
    ]

    keywords = [
        template.format(
            service=service,
            location=location,
            audience=audience,
        ).strip()
        for template in templates
    ]
    unique = []
    for keyword in keywords:
        if keyword not in unique:
            unique.append(keyword)
    return unique[:8]


def _competitor_title_phrases(profile, competitor_snapshots, location):
    phrases = []
    for snapshot in _accepted_competitor_snapshots(competitor_snapshots, profile):
        payload = snapshot.output_json or {}
        for page in _normalized_competitor_pages(payload):
            title = (page.get("title") or page.get("h1") or "").strip()
            if not title:
                continue
            title_lower = title.lower()
            if any(hint in title_lower for hint in NON_COMPETITOR_PAGE_HINTS):
                continue
            if _has_foreign_geo_conflict(title_lower, location):
                continue
            if location and location.lower() not in title_lower and len(phrases) >= 2:
                continue
            if title not in phrases:
                phrases.append(title)
            if len(phrases) >= 4:
                return phrases
    return phrases


def _competitor_language_patterns(profile, competitor_snapshots):
    phrases = []
    topic_terms = _profile_topic_terms(profile)
    location_tokens = _tokenize_phrase(profile.location)
    for snapshot in _accepted_competitor_snapshots(competitor_snapshots, profile):
        payload = snapshot.output_json or {}
        for page in _normalized_competitor_pages(payload):
            title = (page.get("title") or page.get("h1") or "").strip()
            if not title:
                continue
            title_lower = title.lower()
            if any(hint in title_lower for hint in NON_COMPETITOR_PAGE_HINTS):
                continue
            if _has_foreign_geo_conflict(title_lower, profile.location):
                continue
            if not any(term in title_lower for term in topic_terms[:8]):
                continue
            if location_tokens and not any(token in title_lower for token in location_tokens):
                continue
            if len(title) > 80:
                continue
            if title not in phrases:
                phrases.append(title)
            if len(phrases) >= 3:
                return phrases
    return phrases


def build_keyword_clusters(profile, competitor_snapshots):
    base_keywords = build_local_keyword_set(profile)
    competitor_titles = _competitor_title_phrases(profile, competitor_snapshots, profile.location)
    clusters = defaultdict(list)
    for keyword in base_keywords:
        if "near me" in keyword:
            clusters["local intent"].append(keyword)
        elif "best" in keyword or "for " in keyword:
            clusters["comparison intent"].append(keyword)
        else:
            clusters["core commercial"].append(keyword)
    for title in competitor_titles:
        if title not in clusters["competitor language"]:
            clusters["competitor language"].append(title)
    return dict(clusters)


def _page_evidence(snapshot_payload, page_type, limit=3):
    evidence = []
    for page in _normalized_competitor_pages(snapshot_payload):
        if page.get("page_type") != page_type:
            continue
        evidence.append(
            {
                "url": page.get("url", ""),
                "title": page.get("title", "") or page.get("h1", ""),
                "page_type": page_type,
            }
        )
        if len(evidence) >= limit:
            break
    return evidence


def _normalized_competitor_pages(snapshot_payload):
    normalized = []
    for raw_page in snapshot_payload.get("pages", []):
        if isinstance(raw_page, dict):
            normalized.append(raw_page)
            continue
        if isinstance(raw_page, str) and raw_page.strip():
            normalized.append(
                {
                    "url": raw_page.strip(),
                    "title": "",
                    "h1": "",
                    "page_type": "general",
                }
            )
    return normalized


def _site_pages_for_type(site_structure, page_type):
    return [page for page in site_structure.get("pages", []) if page.get("page_type") == page_type]


def _page_lookup(site_structure):
    return {
        page.get("url"): page
        for page in site_structure.get("pages", [])
        if page.get("url")
    }


def _link_source_candidates(site_structure, *, exclude_urls=None, preferred_types=None, limit=2):
    exclude_urls = set(exclude_urls or [])
    preferred_types = preferred_types or ("home", "service", "location")
    candidates = []
    for page in site_structure.get("pages", []):
        if page.get("url") in exclude_urls:
            continue
        if page.get("page_type") in preferred_types:
            candidates.append(page.get("url"))
        if len(candidates) >= limit:
            break
    return candidates


def _suggested_url(profile, page_type, keyword):
    domain = (profile.project.normalized_domain or "").strip("/")
    slug = slugify(keyword or f"{profile.primary_service or page_type} {profile.location}")
    if not domain:
        return f"/{slug}/"
    return f"https://{domain}/{slug}/"


def _build_issue_changes(*, page_type, keyword, issue_title, recommended_fix, link_sources):
    page_type_label = _page_type_label(page_type)
    lower_title = (issue_title or "").lower()
    changes = []

    if "h1" in lower_title:
        changes.extend(
            [
                f"Replace or add the main H1 so it clearly targets '{keyword}' and matches the page purpose.",
                "Update the opening paragraph so the first 2-3 sentences reinforce the same search intent.",
                "Check the template renders only one H1 on the page.",
            ]
        )
    elif "title tag" in lower_title or "meta title" in lower_title:
        changes.extend(
            [
                f"Rewrite the <title> tag to include '{keyword}' closer to the front.",
                "Make sure the meta description supports the same commercial or local intent.",
                "Keep the title, H1, and CTA aligned to the same promise.",
            ]
        )
    elif "response time" in lower_title or "slow" in lower_title or "performance" in lower_title:
        changes.extend(
            [
                "Audit the page template and assets serving this URL, starting with large images, scripts, and server response time.",
                "Enable or tighten caching, compress media, and defer non-critical scripts for this page template.",
                "Re-test this exact URL after deployment to confirm the response-time improvement.",
            ]
        )
    else:
        changes.extend(
            [
                f"Update the {page_type_label} page so the title tag, H1, and intro explicitly target '{keyword}'.",
                f"Apply the recommendation directly on the affected {page_type_label} content instead of a site-wide generic update.",
                recommended_fix or f"Improve the page so it better supports {keyword}.",
            ]
        )

    if page_type == "faq":
        changes.append("Add 4-6 FAQ blocks with direct answers and validate FAQ schema on the page.")
    if page_type in {"service", "location", "pricing", "inventory"}:
        changes.append("Add proof blocks, CTA placement above the fold, and a local modifier where relevant.")
    if link_sources:
        changes.append(f"Add internal links to this page from {', '.join(link_sources)}.")
    return changes[:5]


def _build_edit_targets(*, profile, site_structure, urls, page_type, keyword, issue_title="", recommended_fix="", missing=False):
    lookup = _page_lookup(site_structure)
    targets = []
    if not urls and missing:
        suggested = _suggested_url(profile, page_type, keyword)
        link_sources = _link_source_candidates(site_structure)
        targets.append(
            {
                "url": suggested,
                "page_title": f"New {_page_type_label(page_type).title()} page",
                "page_type": page_type,
                "change_scope": "new_page",
                "changes": _build_issue_changes(
                    page_type=page_type,
                    keyword=keyword,
                    issue_title=issue_title or f"Missing {page_type} page",
                    recommended_fix=recommended_fix,
                    link_sources=link_sources,
                ),
            }
        )
        return targets

    for url in urls[:3]:
        page = lookup.get(url, {})
        link_sources = _link_source_candidates(site_structure, exclude_urls={url})
        targets.append(
            {
                "url": url,
                "page_title": page.get("title") or page.get("h1") or url,
                "page_type": page.get("page_type") or page_type or "page",
                "change_scope": "existing_page",
                "changes": _build_issue_changes(
                    page_type=page.get("page_type") or page_type or "page",
                    keyword=keyword,
                    issue_title=issue_title,
                    recommended_fix=recommended_fix,
                    link_sources=link_sources,
                ),
            }
        )
    return targets


def build_structural_recommendations(*, profile, site_structure, competitor_snapshots):
    rule = get_industry_rule(profile.business_type)
    site_summary = site_structure.get("summary", {})
    recommendations = []
    available_competitors = _accepted_competitor_snapshots(competitor_snapshots, profile)
    if not available_competitors:
        return recommendations

    competitor_counts = defaultdict(list)
    competitor_word_counts = defaultdict(list)
    for snapshot in available_competitors:
        summary = snapshot.output_json.get("summary", {})
        for page_type, count in summary.get("counts_by_type", {}).items():
            competitor_counts[page_type].append(count)
        for page_type, avg_count in summary.get("avg_word_count_by_type", {}).items():
            competitor_word_counts[page_type].append(avg_count)

    for page_type in rule["priority_page_types"]:
        site_count = site_summary.get("counts_by_type", {}).get(page_type, 0)
        competitor_presence = sum(1 for count in competitor_counts.get(page_type, []) if count > 0)
        if competitor_presence >= max(1, len(available_competitors) // 2 + len(available_competitors) % 2) and site_count == 0:
            evidence = []
            for snapshot in available_competitors[:3]:
                evidence.extend(_page_evidence(snapshot.output_json, page_type))
            recommendations.append(
                {
                    "title": f"Add a {page_type.replace('_', ' ')} page layer",
                    "category": "Competitive gap",
                    "priority_score": 94 if page_type in {"service", "location", "pricing", "inventory"} else 82,
                    "why_it_matters": (
                        f"Competitors in the same niche are publishing {page_type.replace('_', ' ')} pages while your site does not. "
                        f"This limits visibility for {profile.target_goal.lower()} in {profile.location}."
                    ),
                    "recommended_fix": (
                        f"Create a dedicated {page_type.replace('_', ' ')} page tied to {profile.primary_service or profile.business_type.replace('_', ' ')} "
                        f"and local demand in {profile.location}."
                    ),
                    "where_to_apply": [],
                    "competitor_evidence": evidence[:3],
                    "example_keywords": build_local_keyword_set(profile)[:2],
                    "expected_impact": "Closes a structural gap where competitors already have indexable demand-capture pages.",
                }
            )

    for page_type, site_avg in site_summary.get("avg_word_count_by_type", {}).items():
        competitor_avg_values = competitor_word_counts.get(page_type, [])
        if not competitor_avg_values:
            continue
        competitor_avg = round(sum(competitor_avg_values) / max(len(competitor_avg_values), 1))
        if site_avg and competitor_avg - site_avg >= 150:
            site_pages = _site_pages_for_type(site_structure, page_type)[:3]
            evidence = []
            for snapshot in available_competitors[:3]:
                evidence.extend(_page_evidence(snapshot.output_json, page_type))
            recommendations.append(
                {
                    "title": f"Deepen {page_type.replace('_', ' ')} pages",
                    "category": "Content gap",
                    "priority_score": 78,
                    "why_it_matters": (
                        f"Your {page_type.replace('_', ' ')} pages are materially thinner than competitor pages in the same band, "
                        "which weakens relevance and topic completeness."
                    ),
                    "recommended_fix": f"Expand these {page_type.replace('_', ' ')} pages with direct answers, proof, FAQs, and clearer local intent coverage.",
                    "where_to_apply": [page.get("url", "") for page in site_pages if page.get("url")],
                    "competitor_evidence": evidence[:3],
                    "example_keywords": build_local_keyword_set(profile)[:2],
                    "expected_impact": "Improves topic depth and reduces the completeness gap against competing pages.",
                }
            )

    if site_summary.get("faq_schema_pages", 0) == 0 and any(
        (snapshot.output_json.get("summary", {}).get("faq_schema_pages", 0) > 0)
        for snapshot in available_competitors
    ):
        evidence = []
        for snapshot in available_competitors[:3]:
            evidence.extend(_page_evidence(snapshot.output_json, "faq"))
        recommendations.append(
            {
                "title": "Add FAQ or answer-block coverage",
                "category": "Schema gap",
                "priority_score": 81,
                "why_it_matters": "Competitors are supporting core pages with FAQ structure while your site is not exposing equivalent answer-ready content.",
                "recommended_fix": "Add FAQ sections and schema to the highest-intent service or location pages first.",
                "where_to_apply": [page.get("url", "") for page in _site_pages_for_type(site_structure, "service")[:3]],
                "competitor_evidence": evidence[:3],
                "example_keywords": build_local_keyword_set(profile)[:2],
                "expected_impact": "Improves answer coverage, long-tail relevance, and citation readiness.",
            }
        )

    if site_summary.get("location_match_pages", 0) == 0 and profile.location:
        recommendations.append(
            {
                "title": f"Add stronger {profile.location} modifiers to revenue pages",
                "category": "Local intent",
                "priority_score": 76,
                "why_it_matters": f"The site has limited visible location targeting for {profile.location}, which weakens local-intent relevance.",
                "recommended_fix": "Align titles, H1s, and opening summaries on service pages with the primary city or service area.",
                "where_to_apply": [page.get("url", "") for page in _site_pages_for_type(site_structure, "service")[:3]],
                "competitor_evidence": [],
                "example_keywords": build_local_keyword_set(profile)[:3],
                "expected_impact": "Improves city-level discoverability and clearer location matching for organic searches.",
            }
        )

    recommendations.sort(key=lambda item: -item["priority_score"])
    return recommendations[:8]


def _recommendation_cluster_key(item):
    title = (item.get("title") or "").lower()
    category = (item.get("category") or "").lower()
    if title.startswith("deepen "):
        return "content-depth"
    if "page layer" in title or title.startswith("add a "):
        return "page-coverage"
    if "faq" in title or "answer-block" in title or "schema" in category:
        return "answer-readiness"
    if "h1" in title or "title" in title or "meta" in title:
        return "on-page-structure"
    if "slow" in title or "response time" in title or "performance" in category:
        return "performance"
    if "sitemap" in title or "technical" in category:
        return "technical"
    return f"default:{category or title}"


def _merge_cluster_items(cluster_key, items):
    primary = max(items, key=lambda item: item.get("priority_score", 0))
    merged = dict(primary)
    where_to_apply = []
    for item in items:
        for url in item.get("where_to_apply", []):
            if url and url not in where_to_apply:
                where_to_apply.append(url)
    merged["where_to_apply"] = where_to_apply[:6]

    evidence_seen = set()
    merged_evidence = []
    for item in items:
        for evidence in item.get("competitor_evidence", []):
            key = (evidence.get("url", ""), evidence.get("title", ""))
            if key in evidence_seen:
                continue
            evidence_seen.add(key)
            merged_evidence.append(evidence)
    merged["competitor_evidence"] = merged_evidence[:4]

    keyword_seen = []
    for item in items:
        for keyword in item.get("example_keywords", []):
            if keyword and keyword not in keyword_seen:
                keyword_seen.append(keyword)
    merged["example_keywords"] = keyword_seen[:3]

    if len(items) > 1 and cluster_key == "content-depth":
        focus_areas = []
        for item in items:
            label = (item.get("title") or "").replace("Deepen ", "").replace(" pages", "").strip().lower()
            if label and label not in focus_areas:
                focus_areas.append(label)
        merged["title"] = "Deepen thin high-intent pages"
        merged["why_it_matters"] = "Several high-intent page types are thinner than the accepted competitor set, which weakens topic depth, local trust, and conversion readiness."
        merged["recommended_fix"] = "Expand the thinnest high-intent pages with stronger local modifiers, proof, FAQs, and clearer conversion sections."
        merged["focus_areas"] = focus_areas[:5]
    elif len(items) > 1 and cluster_key == "page-coverage":
        focus_areas = []
        for item in items:
            label = (item.get("title") or "").replace("Add a ", "").replace(" page layer", "").strip().lower()
            if label and label not in focus_areas:
                focus_areas.append(label)
        merged["title"] = "Close missing page coverage gaps"
        merged["why_it_matters"] = "The site is missing multiple page layers that accepted competitors use to capture demand across the buyer journey."
        merged["recommended_fix"] = "Add the missing page types competitors consistently publish for this niche, then connect them with internal links from your core revenue pages."
        merged["focus_areas"] = focus_areas[:5]

    return merged


def build_context_recommendations(audit_run, profile, site_structure, competitor_snapshots):
    summary = audit_run.summary or {}
    score_breakdown = summary.get("score_breakdown") or {}
    local_keywords = build_local_keyword_set(profile)
    audit_recommendations = []
    for recommendation in (summary.get("featured_recommendations") or summary.get("recommendations") or [])[:4]:
        category_key = recommendation.get("category_key", "")
        breakdown = score_breakdown.get(category_key, {})
        audit_recommendations.append(
            {
                "title": recommendation.get("title", "SEO opportunity"),
                "category": recommendation.get("category", "SEO"),
                "priority_score": recommendation.get("priority_score", 0),
                "why_it_matters": (
                    f"For a {get_industry_rule(profile.business_type)['label'].lower()} business in {profile.location}, "
                    f"this weakens {breakdown.get('label', recommendation.get('category', 'SEO')).lower()} visibility against {profile.target_goal}."
                ),
                "recommended_fix": recommendation.get("recommended_fix", ""),
                "where_to_apply": recommendation.get("page_examples") or ([recommendation.get("page_url")] if recommendation.get("page_url") else []),
                "competitor_evidence": [],
                "example_keywords": local_keywords[:2],
                "expected_impact": recommendation.get("estimated_impact", ""),
            }
        )

    structural = build_structural_recommendations(
        profile=profile,
        site_structure=site_structure,
        competitor_snapshots=competitor_snapshots,
    )
    clustered = defaultdict(list)
    for item in structural + audit_recommendations:
        clustered[_recommendation_cluster_key(item)].append(item)
    combined = [_merge_cluster_items(cluster_key, items) for cluster_key, items in clustered.items()]
    combined.sort(key=lambda item: -item["priority_score"])
    return combined[:8]


def build_priority_pages(profile, site_structure):
    rule = get_industry_rule(profile.business_type)
    current_types = set(site_structure.get("summary", {}).get("counts_by_type", {}).keys())
    ordered = []
    for page_type in rule["priority_page_types"]:
        label = page_type.replace("_", " ")
        prefix = "Strengthen" if page_type in current_types else "Build"
        ordered.append(f"{prefix} {label} pages")
    return ordered[:6]


def build_benchmark_summary(site_structure, competitor_snapshots):
    profile = None
    if competitor_snapshots:
        project = getattr(competitor_snapshots[0].competitor, "project", None)
        profile = getattr(project, "seo_profile", None)
    available = _accepted_competitor_snapshots(competitor_snapshots, profile)
    traces = [_build_competitor_trace(snapshot, profile) for snapshot in competitor_snapshots] if profile else []
    if not available:
        return {
            "available_competitors": 0,
            "included_competitors": 0,
            "site_page_count": site_structure.get("summary", {}).get("page_count", 0),
            "common_page_types": [],
            "discovery_queries": [],
            "average_relevance": 0,
            "top_match_signals": [],
            "manual_overrides": 0,
        }
    page_type_counter = Counter()
    match_signal_counter = Counter()
    relevance_values = []
    for snapshot in available:
        for page_type, count in (snapshot.output_json.get("summary", {}).get("counts_by_type", {}) or {}).items():
            if count > 0:
                page_type_counter[page_type] += 1
        serp_metadata = ((snapshot.competitor.metadata or {}).get("serp") or {})
        if serp_metadata.get("average_relevance") is not None:
            relevance_values.append(serp_metadata.get("average_relevance", 0))
        for signal in serp_metadata.get("match_signals", []):
            match_signal_counter[signal] += 1
    common_page_types = [
        page_type.replace("_", " ")
        for page_type, count in page_type_counter.items()
        if count >= max(1, len(available) // 2 + len(available) % 2)
    ]
    discovery_queries = []
    for snapshot in available:
        for query in (((snapshot.competitor.metadata or {}).get("serp") or {}).get("queries", [])):
            if query not in discovery_queries:
                discovery_queries.append(query)

    return {
        "available_competitors": len(available),
        "included_competitors": len([item for item in traces if item.get("included")]),
        "filtered_out_competitors": max(0, len(competitor_snapshots) - len(available)),
        "site_page_count": site_structure.get("summary", {}).get("page_count", 0),
        "common_page_types": common_page_types[:6],
        "discovery_queries": discovery_queries[:8],
        "average_relevance": round(sum(relevance_values) / max(len(relevance_values), 1), 1) if relevance_values else 0,
        "top_match_signals": [signal for signal, _count in match_signal_counter.most_common(6)],
        "manual_overrides": len([item for item in traces if item.get("review_decision") != "auto"]),
    }


def build_serp_evidence_history(project, limit=6):
    snapshots = list(
        SEOContextSnapshot.objects.filter(project=project)
        .order_by("-created_at")[:limit]
    )
    snapshots.reverse()
    history = []
    previous_relevance = None
    for snapshot in snapshots:
        payload = snapshot.output_json or {}
        summary = payload.get("benchmark_summary", {}) or {}
        discovery = payload.get("discovery", {}) or {}
        trace = payload.get("competitor_trace") or []
        included_domains = [item.get("domain", "") for item in trace if item.get("included") and item.get("domain")]
        average_relevance = float(summary.get("average_relevance") or 0)
        history.append(
            {
                "snapshot_id": snapshot.pk,
                "created_at": snapshot.created_at,
                "label": snapshot.created_at.strftime("%b %d"),
                "included_competitors": summary.get("included_competitors", summary.get("available_competitors", 0)),
                "filtered_out_competitors": summary.get("filtered_out_competitors", 0),
                "average_relevance": average_relevance,
                "relevance_delta": None if previous_relevance is None else round(average_relevance - previous_relevance, 1),
                "query_count": len(discovery.get("queries", []) or []),
                "top_queries": (discovery.get("queries", []) or [])[:3],
                "included_domains": included_domains[:4],
            }
        )
        previous_relevance = average_relevance
    return history


def build_competitor_trend_summary(project, limit=8):
    snapshots = list(
        SEOContextSnapshot.objects.filter(project=project)
        .order_by("-created_at")[:limit]
    )
    snapshots.reverse()
    aggregated = {}
    for snapshot in snapshots:
        for item in (snapshot.output_json or {}).get("competitor_trace", []):
            domain = item.get("domain", "").strip()
            if not domain:
                continue
            entry = aggregated.setdefault(
                domain,
                {
                    "domain": domain,
                    "url": item.get("url", ""),
                    "appearances": 0,
                    "included_runs": 0,
                    "best_position": None,
                    "latest_position": None,
                    "latest_relevance": 0,
                    "last_decision": "",
                    "last_seen_label": "",
                    "queries": [],
                },
            )
            entry["appearances"] += 1
            if item.get("included"):
                entry["included_runs"] += 1
            best_position = item.get("best_position")
            if isinstance(best_position, (int, float)):
                if entry["best_position"] is None or best_position < entry["best_position"]:
                    entry["best_position"] = best_position
                entry["latest_position"] = best_position
            entry["latest_relevance"] = item.get("average_relevance") or entry["latest_relevance"]
            entry["last_decision"] = item.get("final_decision_label", "")
            entry["last_seen_label"] = snapshot.created_at.strftime("%b %d")
            for query in item.get("queries", [])[:3]:
                if query not in entry["queries"]:
                    entry["queries"].append(query)
    ranked = sorted(
        aggregated.values(),
        key=lambda item: (-item["included_runs"], -item["appearances"], item["best_position"] or 999),
    )
    return ranked[:8]


def _page_type_label(page_type):
    return page_type.replace("_", " ")


def _build_target_keyword(profile, page_type):
    service = _service_seed(profile)
    location = (profile.location or "").strip()
    custom_templates = _keyword_template_group(profile).get("page_types", {})
    templates = {
        "service": f"{service} {location}".strip(),
        "location": f"{service} in {location}".strip(),
        "pricing": f"{service} pricing {location}".strip(),
        "faq": f"{service} {location} faq".strip(),
        "comparison": f"best {service} {location}".strip(),
        "article": f"{service} tips {location}".strip(),
        "inventory": f"{service} inventory {location}".strip(),
        "feature": f"{service} features".strip(),
        "use_case": f"{service} for {profile.target_audience or 'buyers'}".strip(),
        "case_study": f"{service} results".strip(),
        "review": f"{service} reviews {location}".strip(),
        "finance": f"{service} financing {location}".strip(),
    }
    if page_type in custom_templates:
        return custom_templates[page_type].format(
            service=service,
            location=location,
            audience=profile.target_audience or "buyers",
        ).strip()
    return templates.get(page_type, f"{service} {location}".strip())


def _majority_threshold(size):
    return max(1, size // 2 + size % 2)


def _competitor_summaries(competitor_snapshots):
    return [snapshot.output_json for snapshot in competitor_snapshots if (snapshot.output_json or {}).get("status") == "ok"]


def _pattern_title_terms(pages, location=""):
    counter = Counter()
    location_tokens = set(_tokenize_phrase(location))
    for page in pages:
        text = " ".join([page.get("title", ""), page.get("h1", "")]).strip().lower()
        for token in _tokenize_phrase(text):
            if token in location_tokens:
                continue
            counter[token] += 1
    return [token for token, count in counter.most_common(6) if count >= 2][:5]


def build_competitor_patterns(profile, competitor_snapshots):
    available_competitors = _competitor_summaries(_accepted_competitor_snapshots(competitor_snapshots, profile))
    items = []
    for page_type in get_industry_rule(profile.business_type)["priority_page_types"]:
        pages = [
            page
            for payload in available_competitors
            for page in _normalized_competitor_pages(payload)
            if page.get("page_type") == page_type
        ]
        if not pages:
            continue
        title_samples = []
        for page in pages:
            title = (page.get("title") or page.get("h1") or "").strip()
            if title and title not in title_samples:
                title_samples.append(title)
        faq_pages = [page for page in pages if page.get("has_faq_schema")]
        schema_pages = [page for page in pages if page.get("schema_count", 0) > 0]
        location_pages = [page for page in pages if page.get("location_match")]
        avg_word_count = round(sum(page.get("word_count", 0) for page in pages) / max(len(pages), 1))
        avg_internal_links = round(sum(page.get("internal_link_count", 0) for page in pages) / max(len(pages), 1), 1)
        items.append(
            {
                "page_type": page_type,
                "page_type_label": _page_type_label(page_type).title(),
                "competitor_page_count": len(pages),
                "avg_word_count": avg_word_count,
                "faq_rate": round((len(faq_pages) / max(len(pages), 1)) * 100),
                "schema_rate": round((len(schema_pages) / max(len(pages), 1)) * 100),
                "location_rate": round((len(location_pages) / max(len(pages), 1)) * 100),
                "avg_internal_links": avg_internal_links,
                "title_samples": title_samples[:3],
                "common_terms": _pattern_title_terms(pages, location=profile.location),
            }
        )
    return items


def build_page_comparisons(profile, site_structure, competitor_snapshots):
    patterns = build_competitor_patterns(profile, competitor_snapshots)
    comparisons = []
    for pattern in patterns:
        site_pages = _site_pages_for_type(site_structure, pattern["page_type"])
        site_page = max(site_pages, key=lambda item: item.get("word_count", 0), default=None)
        missing_elements = []
        if not site_page:
            missing_elements.append(f"No {_page_type_label(pattern['page_type'])} page exists on the current site.")
            status = "missing"
        else:
            if pattern["faq_rate"] >= 50 and not site_page.get("has_faq_schema"):
                missing_elements.append("Add FAQ coverage and FAQ schema to match common competitor structure.")
            if pattern["schema_rate"] >= 50 and site_page.get("schema_count", 0) == 0:
                missing_elements.append("Add structured data blocks that clarify page purpose and entity context.")
            if pattern["location_rate"] >= 50 and not site_page.get("location_match"):
                missing_elements.append(f"Add explicit {profile.location} modifiers in the title, H1, and proof sections.")
            if pattern["avg_word_count"] - site_page.get("word_count", 0) >= 150:
                missing_elements.append(f"Expand content depth by about {pattern['avg_word_count'] - site_page.get('word_count', 0)} words to match competitor coverage.")
            if pattern["avg_internal_links"] - site_page.get("internal_link_count", 0) >= 2:
                missing_elements.append("Add more internal links from core pages so this page is not isolated.")
            status = "gap" if missing_elements else "aligned"

        comparisons.append(
            {
                "page_type": pattern["page_type"],
                "page_type_label": pattern["page_type_label"],
                "status": status,
                "site_page_url": site_page.get("url", "") if site_page else "",
                "site_page_title": (site_page.get("title") or site_page.get("h1") or "") if site_page else "",
                "site_word_count": site_page.get("word_count", 0) if site_page else 0,
                "site_internal_links": site_page.get("internal_link_count", 0) if site_page else 0,
                "competitor_page_count": pattern["competitor_page_count"],
                "competitor_avg_word_count": pattern["avg_word_count"],
                "competitor_avg_internal_links": pattern["avg_internal_links"],
                "competitor_title_samples": pattern["title_samples"],
                "competitor_common_terms": pattern["common_terms"],
                "missing_elements": missing_elements,
                "recommended_action": (
                    f"Create the missing {_page_type_label(pattern['page_type'])} page using the accepted competitor pattern as the baseline."
                    if not site_page
                    else "Apply the missing structural elements on the current page, then rerun SEO and audit validation."
                ),
            }
        )
    return comparisons


def build_page_map(profile, site_structure, competitor_snapshots):
    rule = get_industry_rule(profile.business_type)
    site_summary = site_structure.get("summary", {})
    site_counts = site_summary.get("counts_by_type", {})
    site_word_counts = site_summary.get("avg_word_count_by_type", {})
    available_competitors = _competitor_summaries(_accepted_competitor_snapshots(competitor_snapshots, profile))
    competitor_count = len(available_competitors)
    competitor_counts = defaultdict(list)
    competitor_word_counts = defaultdict(list)

    for payload in available_competitors:
        summary = payload.get("summary", {})
        for page_type, count in summary.get("counts_by_type", {}).items():
            competitor_counts[page_type].append(count)
        for page_type, avg_count in summary.get("avg_word_count_by_type", {}).items():
            competitor_word_counts[page_type].append(avg_count)

    items = []
    for index, page_type in enumerate(rule["priority_page_types"], start=1):
        site_pages = _site_pages_for_type(site_structure, page_type)
        site_count = site_counts.get(page_type, 0)
        evidence = []
        for payload in available_competitors[:3]:
            evidence.extend(_page_evidence(payload, page_type))
        evidence = evidence[:3]
        competitor_presence = sum(1 for count in competitor_counts.get(page_type, []) if count > 0)
        competitor_avg = 0
        if competitor_word_counts.get(page_type):
            competitor_avg = round(sum(competitor_word_counts[page_type]) / len(competitor_word_counts[page_type]))
        site_avg = site_word_counts.get(page_type, 0)

        if site_count == 0 and competitor_presence >= _majority_threshold(competitor_count):
            status = "missing"
            action = f"Create a dedicated {_page_type_label(page_type)} page."
            priority_score = 97 - index
        elif site_count > 0 and competitor_avg and competitor_avg - site_avg >= 150:
            status = "expand"
            action = f"Expand the existing {_page_type_label(page_type)} pages with deeper coverage, proof, and FAQs."
            priority_score = 88 - index
        elif site_count > 0:
            status = "optimize"
            action = f"Tighten titles, headings, internal links, and local modifiers on {_page_type_label(page_type)} pages."
            priority_score = 74 - index
        else:
            status = "backlog"
            action = f"Monitor {_page_type_label(page_type)} demand and create this page type once the rest of the roadmap is in place."
            priority_score = 58 - index

        items.append(
            {
                "page_type": page_type,
                "page_type_label": _page_type_label(page_type).title(),
                "status": status,
                "priority_score": priority_score,
                "target_keyword": _build_target_keyword(profile, page_type),
                "target_urls": [page.get("url", "") for page in site_pages[:3] if page.get("url")],
                "site_count": site_count,
                "site_avg_word_count": site_avg,
                "competitor_presence": competitor_presence,
                "competitor_count": competitor_count,
                "competitor_avg_word_count": competitor_avg,
                "action": action,
                "reason": (
                    f"This page type matters for {profile.target_goal.lower()} in {profile.location} "
                    f"and is part of the {get_industry_rule(profile.business_type)['label']} structure profile."
                ),
                "competitor_evidence": evidence,
            }
        )

    items.sort(key=lambda item: -item["priority_score"])
    return items


def build_keyword_opportunities(profile, site_structure, competitor_snapshots, page_map):
    site_titles = {
        (page.get("title") or page.get("h1") or "").strip().lower()
        for page in site_structure.get("pages", [])
        if (page.get("title") or page.get("h1"))
    }
    opportunities = []

    for item in page_map:
        if item["status"] == "backlog":
            continue
        opportunities.append(
            {
                "keyword": item["target_keyword"],
                "intent": item["page_type_label"],
                "status": item["status"],
                "priority_score": item["priority_score"],
                "target_page_type": item["page_type"],
                "target_urls": item["target_urls"],
                "reason": item["reason"],
                "support_terms": build_local_keyword_set(profile)[:3],
                "competitor_evidence": item["competitor_evidence"][:2],
            }
        )

    for phrase in _competitor_language_patterns(profile, competitor_snapshots):
        normalized = phrase.strip().lower()
        if not normalized or normalized in site_titles:
            continue
        opportunities.append(
            {
                "keyword": phrase,
                "intent": "Competitor language",
                "status": "language_gap",
                "priority_score": 66,
                "target_page_type": "service",
                "target_urls": [],
                "reason": "Competitors are using this language in titles or headings and your current site language does not reflect it.",
                "support_terms": build_local_keyword_set(profile)[:2],
                "competitor_evidence": [
                    evidence
                    for snapshot in competitor_snapshots[:2]
                    for evidence in _page_evidence(snapshot.output_json or {}, "service", limit=1)
                ][:2],
            }
        )

    deduped = []
    seen = set()
    for item in sorted(opportunities, key=lambda candidate: -candidate["priority_score"]):
        key = (item["keyword"].lower(), item["target_page_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:10]


def build_execution_queue(profile, site_structure, recommendations, page_map, keyword_opportunities):
    tasks = []
    keyword_by_type = defaultdict(list)
    for item in keyword_opportunities:
        keyword_by_type[item["target_page_type"]].append(item["keyword"])

    for item in page_map[:6]:
        if item["status"] == "backlog":
            continue
        phase = "Build" if item["status"] == "missing" else "Upgrade"
        deliverable = (
            f"Launch a new {item['page_type_label']} page"
            if item["status"] == "missing"
            else f"Improve the current {item['page_type_label']} pages"
        )
        tasks.append(
            {
                "title": f"{phase} {item['page_type_label']} coverage",
                "phase": phase,
                "priority_score": item["priority_score"],
                "deliverable": deliverable,
                "target": item["page_type_label"],
                "target_urls": item["target_urls"],
                "linked_keywords": keyword_by_type.get(item["page_type"], [])[:3],
                "why_now": item["reason"],
                "edit_targets": _build_edit_targets(
                    profile=profile,
                    site_structure=site_structure,
                    urls=item["target_urls"],
                    page_type=item["page_type"],
                    keyword=item["target_keyword"],
                    issue_title=item["title"] if item.get("title") else f"{item['page_type_label']} coverage",
                    recommended_fix=item["action"],
                    missing=item["status"] == "missing",
                ),
                "action_steps": [
                    item["action"],
                    "Edit the listed page elements directly on each target URL instead of applying a generic site-wide change.",
                    "Re-run the audit and SEO refresh after publishing the update so the queue can verify the result.",
                ],
                "competitor_evidence": item["competitor_evidence"][:2],
            }
        )

    for recommendation in recommendations[:4]:
        if not recommendation.get("where_to_apply") and not recommendation.get("recommended_fix"):
            continue
        tasks.append(
            {
                "title": recommendation.get("title", "SEO optimization task"),
                "phase": "Optimize",
                "priority_score": recommendation.get("priority_score", 0),
                "deliverable": "Update the affected existing pages",
                "target": recommendation.get("category", "SEO"),
                "target_urls": recommendation.get("where_to_apply", []),
                "linked_keywords": recommendation.get("example_keywords", [])[:2],
                "why_now": recommendation.get("why_it_matters", ""),
                "edit_targets": _build_edit_targets(
                    profile=profile,
                    site_structure=site_structure,
                    urls=recommendation.get("where_to_apply", []),
                    page_type=recommendation.get("category_key") or recommendation.get("category", "page").lower().replace("-", "_").replace(" ", "_"),
                    keyword=(recommendation.get("example_keywords") or build_local_keyword_set(profile))[0],
                    issue_title=recommendation.get("title", "SEO optimization task"),
                    recommended_fix=recommendation.get("recommended_fix", ""),
                    missing=False,
                ),
                "action_steps": [
                    recommendation.get("recommended_fix", ""),
                    "Update the exact fields called out under each page target: title, H1, intro, schema, media, or internal links as relevant.",
                    "Re-run the audit and SEO refresh to validate the improvement.",
                ],
                "competitor_evidence": recommendation.get("competitor_evidence", [])[:2],
            }
        )

    tasks.sort(key=lambda item: -item["priority_score"])
    return tasks[:10]


def build_value_summary(competitor_snapshots, keyword_opportunities, page_map, execution_queue):
    profile = None
    if competitor_snapshots:
        project = getattr(competitor_snapshots[0].competitor, "project", None)
        profile = getattr(project, "seo_profile", None)
    accepted_competitors = _accepted_competitor_snapshots(competitor_snapshots, profile)
    profiled_competitors = _competitor_summaries(accepted_competitors)
    competitor_pages = sum(payload.get("summary", {}).get("page_count", 0) for payload in profiled_competitors)
    competitor_images = sum(
        payload.get("summary", {}).get("asset_totals", {}).get("images", 0)
        for payload in profiled_competitors
    )
    competitor_scripts = sum(
        payload.get("summary", {}).get("asset_totals", {}).get("scripts", 0)
        for payload in profiled_competitors
    )
    auto_discovered = len(
        [
            snapshot
            for snapshot in accepted_competitors
            if snapshot.competitor.source == SEOCompetitor.Source.SERP
            and (snapshot.output_json or {}).get("status") == "ok"
        ]
    )
    return {
        "competitors_benchmarked": len(profiled_competitors),
        "auto_discovered_competitors": auto_discovered,
        "filtered_out_competitors": max(0, len(competitor_snapshots) - len(accepted_competitors)),
        "competitor_pages_profiled": competitor_pages,
        "competitor_images_profiled": competitor_images,
        "competitor_scripts_profiled": competitor_scripts,
        "keyword_targets": len(keyword_opportunities),
        "page_actions": len([item for item in page_map if item["status"] in {"missing", "expand", "optimize"}]),
        "execution_items": len(execution_queue),
    }


def build_seo_context_payload(project, profile, audit_run):
    effective_business_type = profile.business_type or infer_business_type_for_project(
        project,
        audit_run=audit_run,
        primary_service=profile.primary_service,
    )
    site_structure_snapshot = get_or_build_site_structure_snapshot(
        project=project,
        audit_run=audit_run,
        profile=profile,
    )
    sync_project_competitors(project)
    discovery = sync_discovered_competitors(project, profile)
    competitors = sorted(
        SEOCompetitor.objects.filter(project=project, is_active=True),
        key=_competitor_priority,
    )[: settings.SEO_COMPETITOR_LIMIT]
    competitor_snapshots = [
        get_or_build_competitor_snapshot(
            competitor=competitor,
            audit_run=audit_run,
            profile=profile,
        )
        for competitor in competitors
    ]
    competitor_trace = [_build_competitor_trace(snapshot, profile) for snapshot in competitor_snapshots]
    accepted_competitor_snapshots = _accepted_competitor_snapshots(competitor_snapshots, profile)
    site_structure = site_structure_snapshot.output_json
    benchmark_summary = build_benchmark_summary(site_structure, competitor_snapshots)
    competitor_patterns = build_competitor_patterns(profile, accepted_competitor_snapshots)
    page_comparisons = build_page_comparisons(profile, site_structure, accepted_competitor_snapshots)
    recommendations = build_context_recommendations(
        audit_run,
        profile,
        site_structure,
        accepted_competitor_snapshots,
    )
    industry_rule = get_industry_rule(effective_business_type)
    return {
        "context": {
            "project": project.name,
            "domain": project.normalized_domain,
            "business_type": effective_business_type,
            "industry_label": industry_rule["label"],
            "business_type_source": "manual" if profile.business_type else "inferred",
            "location": profile.location,
            "target_goal": profile.target_goal,
            "primary_service": profile.primary_service,
            "target_audience": profile.target_audience,
            "goal_focus": industry_rule["goal_focus"],
            "priority_pages": build_priority_pages(profile, site_structure),
        },
        "keyword_clusters": build_keyword_clusters(profile, accepted_competitor_snapshots),
        "recommendations": recommendations,
        "audit_snapshot": {
            "overall_score": audit_run.overall_score,
            "seo_score": audit_run.seo_score,
            "technical_score": audit_run.technical_score,
            "on_page_score": audit_run.on_page_score,
            "content_score": audit_run.content_score,
            "aeo_score": audit_run.aeo_score,
        },
        "site_structure": site_structure,
        "benchmark_summary": benchmark_summary,
        "discovery": discovery,
        "competitor_trace": competitor_trace,
        "competitor_patterns": competitor_patterns,
        "page_comparisons": page_comparisons,
        "competitors": [
            {
                "domain": snapshot.competitor.normalized_domain,
                "url": snapshot.competitor.homepage_url,
                "source": snapshot.competitor.source,
                "metadata": snapshot.competitor.metadata or {},
                **(snapshot.output_json or {}),
            }
            for snapshot in accepted_competitor_snapshots
        ],
    }


def build_seo_opportunity_payload(project, profile, audit_run, context_snapshot=None):
    if context_snapshot is None:
        context_snapshot = get_or_build_seo_snapshot(project=project, profile=profile, audit_run=audit_run)
    context_payload = context_snapshot.output_json or {}
    competitor_trace = context_payload.get("competitor_trace") or [
        {
            "domain": item.get("domain", ""),
            "status": item.get("status", ""),
            "included": item.get("status") == "ok",
        }
        for item in context_payload.get("competitors", [])
    ]
    competitor_domains = {
        item.get("domain", "")
        for item in competitor_trace
        if item.get("included") and item.get("status") == "ok" and item.get("domain")
    }
    competitor_snapshots = list(
        SEOCompetitorSnapshot.objects.filter(
            source_audit_run=audit_run,
            competitor__project=project,
            competitor__normalized_domain__in=competitor_domains,
        ).select_related("competitor")
    )
    site_structure = context_payload.get("site_structure", {})
    recommendations = context_payload.get("recommendations", [])
    page_map = build_page_map(profile, site_structure, competitor_snapshots)
    keyword_opportunities = build_keyword_opportunities(profile, site_structure, competitor_snapshots, page_map)
    execution_queue = build_execution_queue(profile, site_structure, recommendations, page_map, keyword_opportunities)
    return {
        "value_summary": build_value_summary(competitor_snapshots, keyword_opportunities, page_map, execution_queue),
        "keyword_opportunities": keyword_opportunities,
        "page_map": page_map,
        "execution_queue": execution_queue,
    }


def _campaign_key(item):
    return slugify(
        f"{item.get('page_type', '')}-{item.get('target_keyword') or item.get('title') or item.get('deliverable') or 'campaign'}"
    )[:140]


def _campaign_success_criteria(item):
    criteria = []
    target_keyword = item.get("target_keyword")
    if target_keyword:
        criteria.append(f"Target page is aligned to the keyword '{target_keyword}'.")
    for step in item.get("action_steps", [])[:2]:
        if step and step not in criteria:
            criteria.append(step)
    criteria.append("Re-run SEO refresh and audit validation after the implementation is live.")
    return criteria[:4]


def sync_project_seo_campaigns(project, *, context_snapshot=None, opportunity_snapshot=None):
    if not project:
        return []
    if opportunity_snapshot is None:
        opportunity_snapshot = project.seo_opportunity_snapshots.order_by("-created_at").first()
    if context_snapshot is None:
        context_snapshot = project.seo_snapshots.order_by("-created_at").first()
    if not opportunity_snapshot:
        return []

    payload = opportunity_snapshot.output_json or {}
    queue = payload.get("execution_queue", []) or []
    active_keys = set()
    campaigns = []

    for item in queue:
        campaign_key = _campaign_key(item)
        if not campaign_key:
            continue
        active_keys.add(campaign_key)
        defaults = {
            "source_context_snapshot": context_snapshot,
            "source_opportunity_snapshot": opportunity_snapshot,
            "title": item.get("title") or item.get("deliverable") or "SEO campaign",
            "page_type": item.get("page_type", ""),
            "target_keyword": item.get("target_keyword", ""),
            "related_keywords": item.get("keywords", [])[:6],
            "related_page_urls": item.get("target_urls", [])[:6],
            "success_criteria": _campaign_success_criteria(item),
            "priority_score": item.get("priority_score", 0),
            "metadata": {
                "deliverable": item.get("deliverable", ""),
                "where_to_apply": item.get("where_to_apply", []),
                "edit_targets": item.get("edit_targets", []),
                "action_steps": item.get("action_steps", []),
            },
        }
        campaign, created = SEOCampaign.objects.get_or_create(
            project=project,
            campaign_key=campaign_key,
            defaults=defaults,
        )
        if not created:
            campaign.source_context_snapshot = context_snapshot
            campaign.source_opportunity_snapshot = opportunity_snapshot
            campaign.title = defaults["title"]
            campaign.page_type = defaults["page_type"]
            campaign.target_keyword = defaults["target_keyword"]
            campaign.related_keywords = defaults["related_keywords"]
            campaign.related_page_urls = defaults["related_page_urls"]
            campaign.success_criteria = defaults["success_criteria"]
            campaign.priority_score = defaults["priority_score"]
            campaign.metadata = {
                **(campaign.metadata or {}),
                **defaults["metadata"],
                "is_current": True,
            }
            if campaign.status not in {SEOCampaign.Status.COMPLETED, SEOCampaign.Status.ARCHIVED}:
                campaign.status = SEOCampaign.Status.QUEUED
            campaign.save(
                update_fields=[
                    "source_context_snapshot",
                    "source_opportunity_snapshot",
                    "title",
                    "page_type",
                    "target_keyword",
                    "related_keywords",
                    "related_page_urls",
                    "success_criteria",
                    "priority_score",
                    "metadata",
                    "status",
                    "updated_at",
                ]
            )
        else:
            campaign.metadata = {**campaign.metadata, "is_current": True}
            campaign.save(update_fields=["metadata", "updated_at"])
        campaigns.append(campaign)

    for campaign in project.seo_campaigns.exclude(campaign_key__in=active_keys):
        metadata = dict(campaign.metadata or {})
        metadata["is_current"] = False
        campaign.metadata = metadata
        if campaign.status == SEOCampaign.Status.QUEUED:
            campaign.status = SEOCampaign.Status.BLOCKED
            campaign.save(update_fields=["metadata", "status", "updated_at"])
        else:
            campaign.save(update_fields=["metadata", "updated_at"])

    return list(project.seo_campaigns.select_related("owner").order_by("status", "-priority_score", "-updated_at"))


def get_or_build_seo_snapshot(*, project, profile, audit_run):
    latest = (
        SEOContextSnapshot.objects.filter(project=project, source_audit_run=audit_run, profile=profile)
        .order_by("-created_at")
        .first()
    )
    if latest:
        return latest
    return SEOContextSnapshot.objects.create(
        project=project,
        profile=profile,
        source_audit_run=audit_run,
        output_json=build_seo_context_payload(project, profile, audit_run),
    )


def get_or_build_seo_opportunity_snapshot(*, project, profile, audit_run, context_snapshot=None):
    latest = (
        SEOOpportunitySnapshot.objects.filter(
            project=project,
            source_audit_run=audit_run,
            profile=profile,
        )
        .order_by("-created_at")
        .first()
    )
    if latest:
        return latest
    context_snapshot = context_snapshot or get_or_build_seo_snapshot(
        project=project,
        profile=profile,
        audit_run=audit_run,
    )
    return SEOOpportunitySnapshot.objects.create(
        project=project,
        profile=profile,
        source_audit_run=audit_run,
        source_context_snapshot=context_snapshot,
        output_json=build_seo_opportunity_payload(
            project,
            profile,
            audit_run,
            context_snapshot=context_snapshot,
        ),
    )


def refresh_project_seo_intelligence(project):
    profile = getattr(project, "seo_profile", None)
    if not profile or not can_generate_seo_snapshot(project):
        return None, None

    latest_audit = project.latest_audit_run
    context_snapshot = SEOContextSnapshot.objects.create(
        project=project,
        profile=profile,
        source_audit_run=latest_audit,
        output_json=build_seo_context_payload(project, profile, latest_audit),
    )
    opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
        project=project,
        profile=profile,
        source_audit_run=latest_audit,
        source_context_snapshot=context_snapshot,
        output_json=build_seo_opportunity_payload(
            project,
            profile,
            latest_audit,
            context_snapshot=context_snapshot,
        ),
    )
    return context_snapshot, opportunity_snapshot


def can_generate_seo_snapshot(project):
    return bool(project and getattr(project, "latest_audit_run", None) and project.latest_audit_run.status == "completed")
