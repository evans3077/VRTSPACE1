from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests
from django.utils.text import slugify

from .discovery import discover_serp_competitors
from apps.tools.services import (
    ParsedPage,
    choose_urls_to_crawl,
    extract_domain,
    fetch_many,
    normalize_competitor_urls,
    normalize_url,
    parse_page,
    parse_sitemap,
    safe_fetch,
)

from .models import (
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
    }


def _summarize_pages(pages):
    counts_by_type = Counter(page["page_type"] for page in pages)
    avg_word_count_by_type = {}
    for page_type in counts_by_type:
        relevant = [page["word_count"] for page in pages if page["page_type"] == page_type]
        avg_word_count_by_type[page_type] = round(sum(relevant) / max(len(relevant), 1))
    return {
        "counts_by_type": dict(counts_by_type),
        "avg_word_count_by_type": avg_word_count_by_type,
        "faq_schema_pages": len([page for page in pages if page["has_faq_schema"]]),
        "location_match_pages": len([page for page in pages if page["location_match"]]),
        "page_count": len(pages),
    }


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
    pages = _build_site_pages_from_audit(
        audit_run,
        business_type=profile.business_type,
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
        competitor, _created = SEOCompetitor.objects.get_or_create(
            project=project,
            homepage_url=url,
            defaults={
                "normalized_domain": extract_domain(url),
                "label": extract_domain(url),
                "source": SEOCompetitor.Source.PROFILE,
            },
        )
        competitor.normalized_domain = extract_domain(url)
        competitor.label = competitor.label or competitor.normalized_domain
        competitor.source = SEOCompetitor.Source.PROFILE
        competitor.is_active = True
        competitor.save(update_fields=["normalized_domain", "label", "source", "is_active", "updated_at"])
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
        competitor, _created = SEOCompetitor.objects.get_or_create(
            project=project,
            homepage_url=item["homepage_url"],
            defaults={
                "normalized_domain": item["normalized_domain"],
                "label": item["label"],
                "source": SEOCompetitor.Source.SERP,
                "metadata": {"serp": item},
            },
        )
        metadata = competitor.metadata or {}
        metadata["serp"] = item
        competitor.normalized_domain = item["normalized_domain"]
        competitor.label = item["label"]
        if competitor.source != SEOCompetitor.Source.PROFILE:
            competitor.source = SEOCompetitor.Source.SERP
        competitor.is_active = True
        competitor.metadata = metadata
        competitor.save(
            update_fields=[
                "normalized_domain",
                "label",
                "source",
                "is_active",
                "metadata",
                "updated_at",
            ]
        )
        active_urls.add(item["homepage_url"])

    SEOCompetitor.objects.filter(project=project, source=SEOCompetitor.Source.SERP).exclude(
        homepage_url__in=active_urls
    ).update(is_active=False)
    return discovery


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
        limit=6,
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

    return {
        "status": "ok",
        "url": competitor_url,
        "pages": pages,
        "summary": _summarize_pages(pages),
    }


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
    service = profile.primary_service or "service"
    location = profile.location or "target area"
    audience = profile.target_audience or "buyers"

    keywords = [
        f"{service} in {location}",
        f"{service} {location}",
        f"best {service} {location}",
        f"{service} near me",
        f"{service} for {audience}",
    ]
    unique = []
    for keyword in keywords:
        if keyword not in unique:
            unique.append(keyword)
    return unique[:8]


def _competitor_title_phrases(competitor_snapshots, location):
    phrases = []
    for snapshot in competitor_snapshots:
        payload = snapshot.output_json or {}
        for page in _normalized_competitor_pages(payload):
            title = (page.get("title") or page.get("h1") or "").strip()
            if not title:
                continue
            if location and location.lower() not in title.lower() and len(phrases) >= 3:
                continue
            if title not in phrases:
                phrases.append(title)
            if len(phrases) >= 6:
                return phrases
    return phrases


def build_keyword_clusters(profile, competitor_snapshots):
    base_keywords = build_local_keyword_set(profile)
    competitor_titles = _competitor_title_phrases(competitor_snapshots, profile.location)
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
    available_competitors = [snapshot for snapshot in competitor_snapshots if (snapshot.output_json or {}).get("status") == "ok"]
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
    combined = structural + audit_recommendations
    combined.sort(key=lambda item: -item["priority_score"])
    return combined[:10]


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
    available = [snapshot for snapshot in competitor_snapshots if (snapshot.output_json or {}).get("status") == "ok"]
    if not available:
        return {
            "available_competitors": 0,
            "site_page_count": site_structure.get("summary", {}).get("page_count", 0),
            "common_page_types": [],
            "discovery_queries": [],
        }
    page_type_counter = Counter()
    for snapshot in available:
        for page_type, count in (snapshot.output_json.get("summary", {}).get("counts_by_type", {}) or {}).items():
            if count > 0:
                page_type_counter[page_type] += 1
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
        "site_page_count": site_structure.get("summary", {}).get("page_count", 0),
        "common_page_types": common_page_types[:6],
        "discovery_queries": discovery_queries[:8],
    }


def _page_type_label(page_type):
    return page_type.replace("_", " ")


def _build_target_keyword(profile, page_type):
    service = (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()
    location = (profile.location or "").strip()
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
    return templates.get(page_type, f"{service} {location}".strip())


def _majority_threshold(size):
    return max(1, size // 2 + size % 2)


def _competitor_summaries(competitor_snapshots):
    return [snapshot.output_json for snapshot in competitor_snapshots if (snapshot.output_json or {}).get("status") == "ok"]


def build_page_map(profile, site_structure, competitor_snapshots):
    rule = get_industry_rule(profile.business_type)
    site_summary = site_structure.get("summary", {})
    site_counts = site_summary.get("counts_by_type", {})
    site_word_counts = site_summary.get("avg_word_count_by_type", {})
    available_competitors = _competitor_summaries(competitor_snapshots)
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

    for phrase in _competitor_title_phrases(competitor_snapshots, profile.location):
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
    profiled_competitors = _competitor_summaries(competitor_snapshots)
    competitor_pages = sum(payload.get("summary", {}).get("page_count", 0) for payload in profiled_competitors)
    auto_discovered = len(
        [
            snapshot
            for snapshot in competitor_snapshots
            if snapshot.competitor.source == SEOCompetitor.Source.SERP
            and (snapshot.output_json or {}).get("status") == "ok"
        ]
    )
    return {
        "competitors_benchmarked": len(profiled_competitors),
        "auto_discovered_competitors": auto_discovered,
        "competitor_pages_profiled": competitor_pages,
        "keyword_targets": len(keyword_opportunities),
        "page_actions": len([item for item in page_map if item["status"] in {"missing", "expand", "optimize"}]),
        "execution_items": len(execution_queue),
    }


def build_seo_context_payload(project, profile, audit_run):
    site_structure_snapshot = get_or_build_site_structure_snapshot(
        project=project,
        audit_run=audit_run,
        profile=profile,
    )
    sync_project_competitors(project)
    discovery = sync_discovered_competitors(project, profile)
    competitors = list(
        SEOCompetitor.objects.filter(project=project, is_active=True).order_by("source", "homepage_url")
    )
    competitor_snapshots = [
        get_or_build_competitor_snapshot(
            competitor=competitor,
            audit_run=audit_run,
            profile=profile,
        )
        for competitor in competitors
    ]
    site_structure = site_structure_snapshot.output_json
    benchmark_summary = build_benchmark_summary(site_structure, competitor_snapshots)
    recommendations = build_context_recommendations(
        audit_run,
        profile,
        site_structure,
        competitor_snapshots,
    )
    return {
        "context": {
            "project": project.name,
            "domain": project.normalized_domain,
            "business_type": profile.business_type,
            "industry_label": get_industry_rule(profile.business_type)["label"],
            "location": profile.location,
            "target_goal": profile.target_goal,
            "primary_service": profile.primary_service,
            "target_audience": profile.target_audience,
            "goal_focus": get_industry_rule(profile.business_type)["goal_focus"],
            "priority_pages": build_priority_pages(profile, site_structure),
        },
        "keyword_clusters": build_keyword_clusters(profile, competitor_snapshots),
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
        "competitors": [
            {
                "domain": snapshot.competitor.normalized_domain,
                "url": snapshot.competitor.homepage_url,
                "source": snapshot.competitor.source,
                "metadata": snapshot.competitor.metadata or {},
                **(snapshot.output_json or {}),
            }
            for snapshot in competitor_snapshots
        ],
    }


def build_seo_opportunity_payload(project, profile, audit_run, context_snapshot=None):
    if context_snapshot is None:
        context_snapshot = get_or_build_seo_snapshot(project=project, profile=profile, audit_run=audit_run)
    context_payload = context_snapshot.output_json or {}
    competitor_domains = {
        item.get("domain", "")
        for item in context_payload.get("competitors", [])
        if item.get("status") == "ok" and item.get("domain")
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
