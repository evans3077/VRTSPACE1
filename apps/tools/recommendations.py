import re
from collections import Counter
from urllib.parse import urlparse

from .evidence import decorate_recommendation
from .models import AuditIssue
from .scoring import build_gauge_offsets, build_score_breakdown, serialize_score_snapshot


SEVERITY_ORDER = {
    AuditIssue.Severity.CRITICAL: 0,
    AuditIssue.Severity.HIGH: 1,
    AuditIssue.Severity.MEDIUM: 2,
    AuditIssue.Severity.LOW: 3,
}

SEVERITY_PRIORITY_BASE = {
    AuditIssue.Severity.CRITICAL: 90,
    AuditIssue.Severity.HIGH: 72,
    AuditIssue.Severity.MEDIUM: 54,
    AuditIssue.Severity.LOW: 36,
}

CATEGORY_IMPACT = {
    AuditIssue.Category.TECHNICAL: "Improves crawl trust and index coverage.",
    AuditIssue.Category.ON_PAGE: "Improves ranking alignment and click-through clarity.",
    AuditIssue.Category.CONTENT: "Improves authority, usefulness, and search-intent coverage.",
    AuditIssue.Category.AEO: "Improves answer-engine citation potential and entity clarity.",
    AuditIssue.Category.INTERNAL_LINKING: "Improves page discovery and authority flow.",
    AuditIssue.Category.PERFORMANCE: "Improves load speed, UX, and conversion resilience.",
}

CATEGORY_TECHNICAL_STEPS = {
    AuditIssue.Category.TECHNICAL: [
        "Check crawlability and indexation for the affected URL pattern.",
        "Resolve status-code, robots, canonical, or sitemap conflicts before re-crawling.",
    ],
    AuditIssue.Category.ON_PAGE: [
        "Rewrite the metadata and heading stack for the affected page.",
        "Align the primary heading and page summary with the real search intent.",
    ],
    AuditIssue.Category.CONTENT: [
        "Expand the page with proof, examples, and more complete answer coverage.",
        "Reduce thin sections and make the primary topic easier to understand quickly.",
    ],
    AuditIssue.Category.AEO: [
        "Add direct answers, question blocks, or structured summaries to the page.",
        "Strengthen entity references and schema where the content can support them cleanly.",
    ],
    AuditIssue.Category.INTERNAL_LINKING: [
        "Add more contextual links from strong pages into the affected page.",
        "Reduce orphan-style navigation patterns and tighten path depth.",
    ],
    AuditIssue.Category.PERFORMANCE: [
        "Inspect blocking assets, image weight, and slow third-party scripts first.",
        "Re-measure the page after each change to confirm the improvement.",
    ],
}

CATEGORY_PLAN_MAP = {
    AuditIssue.Category.TECHNICAL: "Growth",
    AuditIssue.Category.ON_PAGE: "Growth",
    AuditIssue.Category.CONTENT: "Authority",
    AuditIssue.Category.AEO: "Authority",
    AuditIssue.Category.INTERNAL_LINKING: "Growth",
    AuditIssue.Category.PERFORMANCE: "Growth",
}

ROOT_CAUSE_PLAYBOOK = {
    "on-page-structure": {
        "problem": "Search snippets are not presenting the offer clearly enough, which makes clicks harder to win.",
        "fix": "Tighten the title and heading so the main page promise is obvious in a single glance.",
        "steps": [
            "Start with {first_url} and trim the title to roughly 50 to 60 characters.",
            "Lead with the main service or page topic before the brand name.",
            "Match the title, H1, and opening copy so the promise is consistent.",
        ],
        "next_title": "Clean up the first search-facing page signals.",
        "next_body": "Fix the highest-visibility title and heading issues first, then rerun the audit to confirm the page reads cleanly in search.",
    },
    "answer-readiness": {
        "problem": "Important pages are not yet packaged in a way answer engines can quote and cite easily.",
        "fix": "Add short question-and-answer blocks to the strongest service pages and support them with clean structured formatting.",
        "steps": [
            "Start with {first_url} and add 3 to 5 questions real visitors ask before converting.",
            "Answer each question in direct, plain language before expanding with extra detail.",
            "Add FAQ schema only where those questions genuinely exist on the page.",
        ],
        "next_title": "Turn the strongest pages into citation-ready answers.",
        "next_body": "Use the audit pages with the clearest answer-readiness gaps as the first AEO improvements inside the workspace.",
    },
    "crawl-foundation": {
        "problem": "Crawl and index signals are sending mixed messages, which weakens discovery and trust.",
        "fix": "Clean up canonical, robots, sitemap, or status-code conflicts so search engines see one clear version of every important page.",
        "steps": [
            "Start with {first_url} and confirm the preferred canonical and indexable version.",
            "Resolve any robots, status-code, or duplication conflict before rerunning the crawl.",
            "Update the sitemap so important pages are easy for search engines to find again.",
        ],
        "next_title": "Stabilize crawl and index foundations first.",
        "next_body": "Fix the technical discovery blockers first so later SEO and AEO work has a clean base to build on.",
    },
    "content-depth": {
        "problem": "The page exists, but it does not yet answer the topic deeply enough to feel authoritative.",
        "fix": "Expand the page with clearer proof, stronger examples, and fuller answers to the main user intent.",
        "steps": [
            "Start with {first_url} and list the top questions the page should answer before a user contacts you.",
            "Add proof elements such as examples, process detail, outcomes, or trust signals.",
            "Remove thin filler copy and make the page easier to scan for the core decision points.",
        ],
        "next_title": "Deepen the pages that should be carrying trust.",
        "next_body": "Strengthen the thinnest high-value pages first so the site feels more complete and credible to both users and search engines.",
    },
    "performance": {
        "problem": "Slow rendering is creating trust friction before users reach the core offer.",
        "fix": "Reduce the heaviest assets and server delays first so the page feels responsive from the first visit.",
        "steps": [
            "Start with {first_url} and remove or defer the assets blocking the first screen.",
            "Compress large images, fonts, and third-party scripts loading before the main content.",
            "Rerun the audit after each speed change so you can confirm the metric actually moved.",
        ],
        "next_title": "Take the first speed blockers off the page.",
        "next_body": "Fix the slowest rendering and server-response problems first because they affect both conversion trust and visibility.",
    },
    "internal-linking": {
        "problem": "Important pages are not getting enough support from the rest of the site.",
        "fix": "Add clearer contextual links from strong pages so priority URLs are easier to discover and rank.",
        "steps": [
            "Start with {first_url} and identify stronger pages that should link into it naturally.",
            "Add links using descriptive anchor text that matches the page topic.",
            "Reduce orphan-style paths so important pages are no more than a few clicks deep.",
        ],
        "next_title": "Strengthen the routes into your priority pages.",
        "next_body": "Use the workspace to map and improve the internal paths that should be carrying authority into the most valuable URLs.",
    },
    "entity-clarity": {
        "problem": "The site is not sending a strong enough signal about what the business is and what it is best known for.",
        "fix": "Make the service, entity, and business context more explicit across the main pages.",
        "steps": [
            "Start with {first_url} and make the main service or business type obvious in the first screen.",
            "Repeat the core entity terms consistently across headings, summaries, and supporting copy.",
            "Add structured context only where the on-page content clearly supports it.",
        ],
        "next_title": "Clarify the business signal before expanding coverage.",
        "next_body": "Make the core entity and offer clearer first so later SEO and AEO work has a stronger identity base.",
    },
    "local-intent": {
        "problem": "Location intent is not being made clear enough for users and search engines.",
        "fix": "Bring the service and location terms closer together on the pages that should win local searches.",
        "steps": [
            "Start with {first_url} and place the main service plus location in the title and heading.",
            "Support the location intent with proof, FAQs, and nearby-service language where relevant.",
            "Keep the location wording natural so the page still reads like it was written for people first.",
        ],
        "next_title": "Make the local service intent unmistakable.",
        "next_body": "Use the first local-intent pages to sharpen location relevance before expanding the same pattern site-wide.",
    },
    "page-coverage": {
        "problem": "The site is missing page coverage that users and search engines expect to find.",
        "fix": "Create or strengthen the missing page types so important intents are not being left uncovered.",
        "steps": [
            "Start with {first_url} or the closest existing page and confirm which intent is still missing.",
            "Create a dedicated page instead of forcing multiple intents into one weak URL.",
            "Link the new page from related service or navigation paths so it can be discovered quickly.",
        ],
        "next_title": "Fill the first obvious content gaps.",
        "next_body": "Use the audit to identify which missing pages would unlock the clearest visibility gains next.",
    },
}

PERFORMANCE_METRIC_CONFIG = [
    {
        "key": "largest_contentful_paint",
        "label": "Largest Contentful Paint (LCP)",
        "short_label": "LCP",
        "unit": "s",
        "target_label": "<= 2.5s",
        "warning_threshold": 2.5,
        "critical_threshold": 4.0,
        "description": "Shows how quickly the main content becomes visible.",
        "warning_impact": "Main content feels slow to load, which weakens trust and conversion.",
        "critical_impact": "Main content loads late enough to cause abandonment and ranking pressure.",
    },
    {
        "key": "server_response_time",
        "label": "Time to First Byte (TTFB)",
        "short_label": "TTFB",
        "unit": "ms",
        "target_label": "<= 800ms",
        "warning_threshold": 800,
        "critical_threshold": 1800,
        "description": "Shows how quickly the server starts responding to the first request.",
        "warning_impact": "The server is slow to respond, which delays rendering and undermines trust.",
        "critical_impact": "Server response is slow enough to drag down the full page experience and follow-on metrics.",
    },
    {
        "key": "total_blocking_time",
        "label": "Total Blocking Time (TBT)",
        "short_label": "TBT",
        "unit": "ms",
        "target_label": "<= 200ms",
        "warning_threshold": 200,
        "critical_threshold": 600,
        "description": "Shows how long the main thread is blocked from responding.",
        "warning_impact": "Users feel delayed interactions while the page is busy.",
        "critical_impact": "Main thread blocking is high enough to make the page feel unresponsive.",
    },
    {
        "key": "cumulative_layout_shift",
        "label": "Cumulative Layout Shift (CLS)",
        "short_label": "CLS",
        "unit": "score",
        "target_label": "<= 0.10",
        "warning_threshold": 0.10,
        "critical_threshold": 0.25,
        "description": "Shows how much the page layout jumps while loading.",
        "warning_impact": "Layout movement makes the experience feel unstable.",
        "critical_impact": "Large layout shifts create a visibly poor experience and accidental clicks.",
    },
]


def _issue_context(issue):
    if issue.page_id and issue.page:
        return f"Detected on {issue.page.url}."
    return "Detected across site-level crawl signals."


def _technical_steps(issue):
    steps = []
    if issue.page_id and issue.page:
        steps.append(f"Inspect {issue.page.url} for the failing {issue.get_category_display().lower()} signal.")
    if issue.recommendation:
        steps.append(" ".join(issue.recommendation.split()))
    for step in CATEGORY_TECHNICAL_STEPS.get(issue.category, []):
        if step not in steps:
            steps.append(step)
    return steps[:3]


def _normalize_sentence(value):
    text = " ".join(str(value or "").split())
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def _unique_urls(values):
    seen = set()
    urls = []
    for value in values or []:
        value = (value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        urls.append(value)
    return urls


def _short_url(url):
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return url or ""
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc}{path}" if path != "/" else parsed.netloc


def _page_targets_for(recommendation, limit=3):
    targets = recommendation.get("page_examples") or []
    if recommendation.get("page_url"):
        targets = [recommendation["page_url"], *targets]
    return _unique_urls(targets)[:limit]


def _page_scope_label(recommendation, urls):
    affected_count = recommendation.get("affected_pages_count") or recommendation.get("duplicate_issue_count") or len(urls)
    if affected_count <= 0:
        return "Site-wide signal"
    if affected_count == 1:
        return "1 priority URL affected"
    return f"{affected_count} URLs need attention"


def _playbook_for(recommendation):
    return ROOT_CAUSE_PLAYBOOK.get(recommendation.get("root_cause_key"), {})


def _action_steps_for(recommendation, urls):
    playbook = _playbook_for(recommendation)
    first_url = _short_url(urls[0]) if urls else "the first affected page"
    steps = []

    for step in playbook.get("steps", []):
        formatted = _normalize_sentence(step.format(first_url=first_url))
        if formatted and formatted not in steps:
            steps.append(formatted)

    for step in recommendation.get("technical_steps", []):
        cleaned = _normalize_sentence(step)
        if cleaned and cleaned not in steps:
            steps.append(cleaned)

    fix = _normalize_sentence(playbook.get("fix") or recommendation.get("recommended_fix"))
    if fix and fix not in steps:
        steps.append(fix)

    return steps[:3]


def _present_recommendation(recommendation):
    urls = _page_targets_for(recommendation)
    playbook = _playbook_for(recommendation)
    return {
        "category": recommendation["category"],
        "severity": recommendation["severity"],
        "message": recommendation["title"],
        "summary": playbook.get("problem") or _normalize_sentence(recommendation.get("description")),
        "recommendation": _normalize_sentence(playbook.get("fix") or recommendation.get("recommended_fix")),
        "urls": urls,
        "url_labels": [_short_url(url) for url in urls],
        "scope_label": _page_scope_label(recommendation, urls),
        "action_steps": _action_steps_for(recommendation, urls),
        "impact": recommendation.get("estimated_impact", ""),
        "root_cause_label": recommendation.get("root_cause_label", recommendation.get("category")),
        "confidence_label": recommendation.get("confidence_label", ""),
        "evidence_status": recommendation.get("evidence_status", ""),
        "page_url": recommendation.get("page_url"),
    }


def build_ranked_recommendations(audit_run, *, issues=None, score_breakdown=None):
    issue_list = list(issues) if issues is not None else list(audit_run.issues.select_related("page"))
    breakdown = score_breakdown or build_score_breakdown(
        audit_run,
        issues=issue_list,
        has_pagespeed=bool((audit_run.summary or {}).get("pagespeed")),
    )
    duplicate_counts = Counter((issue.category, issue.code, issue.message) for issue in issue_list)

    recommendations = []
    for issue in issue_list:
        score_info = breakdown.get(issue.category, {})
        gap = score_info.get("gap", 0)
        priority_score = min(
            100,
            SEVERITY_PRIORITY_BASE[issue.severity] + min(20, gap) + (5 if issue.page_id is None else 0),
        )
        recommendations.append(
            decorate_recommendation(
                {
                "title": issue.message,
                "description": f"{_issue_context(issue)} This is lowering the {issue.get_category_display()} score.",
                "impact_level": issue.severity.title(),
                "priority_score": priority_score,
                "affected_metric": issue.get_category_display(),
                "recommended_fix": issue.recommendation,
                "technical_steps": _technical_steps(issue),
                "estimated_impact": CATEGORY_IMPACT.get(issue.category, "Improves audit health and recommendation clarity."),
                "category": issue.get_category_display(),
                "category_key": issue.category,
                "category_issue_count": score_info.get("issues", 0),
                "duplicate_issue_count": duplicate_counts[(issue.category, issue.code, issue.message)],
                "suggested_plan": CATEGORY_PLAN_MAP.get(issue.category, "Growth"),
                "severity": issue.severity,
                "page_url": issue.page.url if issue.page_id and issue.page else None,
                "cta": "Fix this for me" if issue.severity in {AuditIssue.Severity.CRITICAL, AuditIssue.Severity.HIGH} else "Review this fix",
                },
                page_targets=[issue.page.url] if issue.page_id and issue.page else [],
                competitor_evidence=[],
                issue_count=max(duplicate_counts[(issue.category, issue.code, issue.message)], 1),
                technical_steps=_technical_steps(issue),
                source_signals=[issue.category, issue.severity],
            )
        )

    return sorted(
        recommendations,
        key=lambda item: (-item["priority_score"], SEVERITY_ORDER[item["severity"]], item["title"]),
    )


def build_featured_recommendations(recommendations, limit=6):
    grouped = {}
    for recommendation in recommendations:
        key = recommendation.get("root_cause_key") or recommendation["category_key"]
        if key not in grouped:
            grouped[key] = {
                **recommendation,
                "page_examples": [],
                "grouped_issue_titles": [],
            }
        current = grouped[key]
        if recommendation.get("page_url") and recommendation["page_url"] not in current["page_examples"]:
            current["page_examples"].append(recommendation["page_url"])
        if recommendation.get("title") and recommendation["title"] not in current["grouped_issue_titles"]:
            current["grouped_issue_titles"].append(recommendation["title"])
        current["duplicate_issue_count"] = max(
            current.get("duplicate_issue_count", 1),
            recommendation.get("duplicate_issue_count", 1),
        )
        current["priority_score"] = max(current["priority_score"], recommendation["priority_score"])

    collapsed = []
    for item in grouped.values():
        page_examples = item["page_examples"][:3]
        affected_pages = max(len(item["page_examples"]), item.get("duplicate_issue_count", 1))
        grouped_issue_count = len(item.get("grouped_issue_titles", [])) or 1
        if grouped_issue_count > 1:
            item["description"] = (
                f"This root cause is showing up through {grouped_issue_count} issue variants across "
                f"{affected_pages} pages. It is lowering the {item['category']} score."
            )
        elif affected_pages > 1:
            item["description"] = (
                f"Detected on {affected_pages} pages. This is lowering the {item['category']} score."
            )
        item["page_examples"] = page_examples
        item["affected_pages_count"] = affected_pages
        item["grouped_issue_count"] = grouped_issue_count
        collapsed.append(
            decorate_recommendation(
                item,
                page_targets=item["page_examples"],
                competitor_evidence=[],
                issue_count=max(grouped_issue_count, affected_pages),
                technical_steps=item.get("technical_steps", []),
                source_signals=[item.get("category_key", ""), item.get("severity", "")],
            )
        )

    collapsed.sort(
        key=lambda item: (-item["priority_score"], SEVERITY_ORDER[item["severity"]], item["title"]),
    )

    featured = []
    used_categories = set()

    for recommendation in collapsed:
        if recommendation["category_key"] in used_categories:
            continue
        featured.append(recommendation)
        used_categories.add(recommendation["category_key"])
        if len(featured) >= limit:
            return featured

    for recommendation in collapsed:
        if recommendation in featured:
            continue
        featured.append(recommendation)
        if len(featured) >= limit:
            break

    return featured


def build_top_issues(recommendations):
    issue_candidates = [
        recommendation
        for recommendation in recommendations
        if recommendation["severity"] in {
            AuditIssue.Severity.CRITICAL,
            AuditIssue.Severity.HIGH,
            AuditIssue.Severity.MEDIUM,
        }
    ]
    if len(issue_candidates) < min(3, len(recommendations)):
        for recommendation in recommendations:
            if recommendation in issue_candidates:
                continue
            issue_candidates.append(recommendation)
            if len(issue_candidates) >= min(3, len(recommendations)):
                break
    if not issue_candidates:
        issue_candidates = list(recommendations)
    return [_present_recommendation(recommendation) for recommendation in issue_candidates[:6]]


def build_quick_wins(recommendations):
    quick_wins = []
    for recommendation in recommendations:
        if recommendation["severity"] == AuditIssue.Severity.CRITICAL:
            continue
        presented = _present_recommendation(recommendation)
        if presented["root_cause_label"] in {item["root_cause_label"] for item in quick_wins}:
            continue
        quick_wins.append(
            {
                "category": presented["category"],
                "problem": presented["message"],
                "summary": presented["summary"],
                "fix": presented["recommendation"],
                "urls": presented["urls"],
                "url_labels": presented["url_labels"],
                "scope_label": presented["scope_label"],
                "action_steps": presented["action_steps"],
                "root_cause_label": presented["root_cause_label"],
            }
        )
        if len(quick_wins) >= 4:
            break
    return quick_wins


def build_issue_summary(issues):
    issue_list = list(issues)
    return {
        "total": len(issue_list),
        "by_severity": dict(Counter(issue.severity for issue in issue_list)),
        "by_category": dict(Counter(issue.category for issue in issue_list)),
    }


def _parse_metric_value(raw_value):
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    match = re.findall(r"[\d.]+", str(raw_value))
    if not match:
        return None
    try:
        return float(match[0])
    except ValueError:
        return None


def _normalize_metric_value(raw_value, *, unit):
    parsed = _parse_metric_value(raw_value)
    if parsed is None:
        return None

    normalized = parsed
    value_text = str(raw_value).lower()

    if unit == "ms":
        if " s" in value_text and "ms" not in value_text:
            normalized = parsed * 1000
    elif unit == "s":
        if "ms" in value_text:
            normalized = parsed / 1000

    return normalized


def build_performance_metrics(pagespeed):
    if not pagespeed:
        return []

    metrics = pagespeed.get("metrics", {})
    performance_metrics = []

    for config in PERFORMANCE_METRIC_CONFIG:
        raw_value = metrics.get(config["key"])
        normalized = _normalize_metric_value(raw_value, unit=config["unit"])
        if raw_value in (None, "") or normalized is None:
            continue

        status = "strong"
        impact = config["description"]
        status_label = "Healthy"
        if normalized > config["critical_threshold"]:
            status = "critical"
            impact = config["critical_impact"]
            status_label = "Needs attention"
        elif normalized > config["warning_threshold"]:
            status = "warning"
            impact = config["warning_impact"]
            status_label = "Watch closely"

        performance_metrics.append(
            {
                "key": config["key"],
                "label": config["label"],
                "short_label": config["short_label"],
                "value": str(raw_value),
                "normalized_value": normalized,
                "status": status,
                "status_label": status_label,
                "target_label": config["target_label"],
                "description": config["description"],
                "impact": impact,
            }
        )

    return performance_metrics


def build_vitals_failures(pagespeed):
    vitals_failures = []
    for metric in build_performance_metrics(pagespeed):
        if metric["status"] != "critical":
            continue
        vitals_failures.append(
            {
                "metric": metric["label"],
                "value": metric["value"],
                "threshold": metric["target_label"].replace("<=", "").strip(),
                "impact": metric["impact"],
            }
        )
    return vitals_failures


def build_product_modules(audit_run, score_breakdown):
    modules = []

    if audit_run.technical_score < 80 or audit_run.on_page_score < 80:
        modules.append(
            {
                "title": "Site Health Monitor",
                "reason": f"Technical and on-page signals are under target at {audit_run.technical_score}% and {audit_run.on_page_score}%.",
                "impact": "Continuously track crawl, metadata, indexation, and priority-page issues inside the workspace.",
                "icon": "Monitor",
                "plan": "Growth",
                "score_key": "technical",
                "delivery_mode": "self_serve",
                "cta_label": "Unlock monitoring",
            }
        )

    if audit_run.aeo_score < 85:
        aeo_issues = score_breakdown.get("aeo", {}).get("issues", 0)
        modules.append(
            {
                "title": "AI Visibility Tracker",
                "reason": f"AEO readiness is at {audit_run.aeo_score}%, with {aeo_issues} AI-answer formatting or entity issues detected.",
                "impact": "Turn citation readiness, entity coverage, and answer formatting into a tracked product workflow.",
                "icon": "AI",
                "plan": "Authority",
                "score_key": "aeo",
                "delivery_mode": "self_serve",
                "cta_label": "Unlock AI tracking",
            }
        )

    if audit_run.performance_score < 85:
        modules.append(
            {
                "title": "Performance Lab",
                "reason": f"Performance is at {audit_run.performance_score}%, leaving measurable friction in mobile UX and conversion.",
                "impact": "Prioritize speed fixes, rerun audits, and track performance gains over time without leaving the platform.",
                "icon": "Speed",
                "plan": "Growth",
                "score_key": "performance",
                "delivery_mode": "self_serve",
                "cta_label": "Unlock performance workflows",
            }
        )

    if audit_run.content_score < 85:
        modules.append(
            {
                "title": "Content Intelligence",
                "reason": f"Content quality is at {audit_run.content_score}%, which suggests thin or weakly structured coverage.",
                "impact": "Prioritize weak pages, content gaps, and answer-depth opportunities inside a single product workflow.",
                "icon": "Content",
                "plan": "Authority",
                "score_key": "content",
                "delivery_mode": "self_serve",
                "cta_label": "Unlock content workflows",
            }
        )

    if audit_run.internal_linking_score < 80:
        modules.append(
            {
                "title": "Internal Link Mapper",
                "reason": f"Internal linking is at {audit_run.internal_linking_score}%, which means important pages are not getting enough path support.",
                "impact": "Map weak link paths and strengthen discovery for revenue pages without manual spreadsheet work.",
                "icon": "Links",
                "plan": "Growth",
                "score_key": "internal_linking",
                "delivery_mode": "self_serve",
                "cta_label": "Unlock link mapping",
            }
        )

    return modules[:4]


def build_custom_work_items(audit_run):
    items = []

    if audit_run.performance_score < 50 or audit_run.technical_score < 50:
        items.append(
            {
                "title": "Website or app rebuild",
                "reason": "Structural and performance signals are low enough that a platform-level rebuild may be faster than incremental patching.",
                "impact": "Use this when the issue is architecture, not just optimization.",
                "cta_label": "Request custom build",
                "delivery_mode": "custom",
            }
        )

    if (
        audit_run.aeo_score < 60
        and audit_run.content_score < 60
        and audit_run.pages_crawled >= 3
    ):
        items.append(
            {
                "title": "Custom implementation",
                "reason": "The current domain likely needs bespoke content, schema, or workflow customization that falls outside the standard product modules.",
                "impact": "Use this for custom automations, integrations, or specialized rollout support.",
                "cta_label": "Request customization",
                "delivery_mode": "custom",
            }
        )

    return items[:2]


def build_service_fit(audit_run, score_breakdown):
    return build_product_modules(audit_run, score_breakdown)


def build_diagnosis(audit_run, score_breakdown, recommendations):
    ranked_dimensions = sorted(
        score_breakdown.values(),
        key=lambda item: item.get("score", 100),
    )
    weakest_dimensions = [item.get("label", "").lower() for item in ranked_dimensions[:2] if item.get("label")]
    weakest_summary = " and ".join(weakest_dimensions) if weakest_dimensions else "technical visibility"

    overall_score = audit_run.overall_score or 0
    if overall_score >= 85:
        headline = "Strong base with a few visible gaps."
    elif overall_score >= 70:
        headline = "Healthy baseline, but important gaps still need attention."
    elif overall_score >= 50:
        headline = "The site has real visibility blockers that should be fixed before scaling."
    else:
        headline = "Foundational issues are holding the site back."

    summary = (
        f"The clearest pressure points in this audit are around {weakest_summary}. "
        "The goal is to remove the blockers that are most likely to affect discovery, trust, and conversion first."
    )
    next_recommendation = recommendations[0] if recommendations else {}
    playbook = _playbook_for(next_recommendation)
    return {
        "headline": headline,
        "summary": summary,
        "next_step_title": playbook.get("next_title") or next_recommendation.get("title", "Review the priority fixes"),
        "next_step_body": playbook.get("next_body")
        or next_recommendation.get(
            "recommended_fix",
            "Start with the clearest high-impact recommendation, then rerun the audit to validate the change.",
        ),
    }


def build_recommended_next_step(recommendations, product_modules):
    recommendation = recommendations[0] if recommendations else {}
    module = product_modules[0] if product_modules else {}
    playbook = _playbook_for(recommendation)
    page_targets = _page_targets_for(recommendation, limit=3)
    checklist = _action_steps_for(recommendation, page_targets)
    return {
        "title": playbook.get("next_title") or module.get("title") or recommendation.get("title") or "Move into the next layer",
        "body": playbook.get("next_body")
        or module.get("impact")
        or recommendation.get("recommended_fix")
        or "Use the audit to decide the next product layer and fix sequence.",
        "cta_label": module.get("cta_label") or "Open the workspace",
        "plan": module.get("plan", ""),
        "checklist": checklist,
        "scope_label": _page_scope_label(recommendation, page_targets),
        "focus_urls": page_targets,
    }


def build_captured_context(audit_run):
    audit_request = getattr(audit_run, "audit_request", None)
    if not audit_request:
        return {}
    return {
        "business_type": audit_request.business_type,
        "business_subtype": audit_request.business_subtype,
        "target_audience": audit_request.target_audience,
        "location": audit_request.location,
        "target_goal": audit_request.target_goal,
        "primary_service": audit_request.primary_service,
        "notes": audit_request.notes,
    }


def build_audit_summary(audit_run, *, issues=None):
    issue_list = list(issues) if issues is not None else list(audit_run.issues.select_related("page"))
    prior_summary = audit_run.summary if isinstance(audit_run.summary, dict) else {}
    pagespeed = prior_summary.get("pagespeed")
    has_pagespeed = bool(pagespeed)

    score_breakdown = build_score_breakdown(audit_run, issues=issue_list, has_pagespeed=has_pagespeed)
    recommendations = build_ranked_recommendations(
        audit_run,
        issues=issue_list,
        score_breakdown=score_breakdown,
    )
    featured_recommendations = build_featured_recommendations(recommendations)
    vitals_failures = build_vitals_failures(pagespeed)
    product_modules = build_product_modules(audit_run, score_breakdown)
    custom_work_items = build_custom_work_items(audit_run)

    summary = {
        "diagnosis": build_diagnosis(audit_run, score_breakdown, recommendations),
        "top_issues": build_top_issues(featured_recommendations),
        "quick_wins": build_quick_wins(featured_recommendations),
        "featured_recommendations": featured_recommendations,
        "recommendations": recommendations[:12],
        "issue_summary": build_issue_summary(issue_list),
        "score_breakdown": score_breakdown,
        "vitals_failures": vitals_failures,
        "has_vitals_failure": len(vitals_failures) > 0,
        "performance_metrics": build_performance_metrics(pagespeed),
        "product_modules": product_modules,
        "custom_work_items": custom_work_items,
        "service_fit": product_modules,
        "recommended_next_step": build_recommended_next_step(featured_recommendations or recommendations, product_modules),
        "captured_context": build_captured_context(audit_run),
        "pages_crawled": audit_run.pages_crawled,
        "scores": serialize_score_snapshot(audit_run),
        "gauge_offsets": build_gauge_offsets(audit_run),
        "full_audit_teasers": [
            "Recurring audits and score history",
            "Saved issue queue and fix tracking",
            "AI visibility and answer-readiness workflows",
            "Page-level content and internal-link opportunities",
            "Workspace reporting and exports",
            "Plan-based automation and monitoring",
        ],
        "performance_source": pagespeed["source"] if pagespeed else "heuristic crawler analysis",
    }
    if pagespeed:
        summary["pagespeed"] = pagespeed
    return summary
