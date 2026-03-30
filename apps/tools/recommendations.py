import re
from collections import Counter

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
            }
        )

    return sorted(
        recommendations,
        key=lambda item: (-item["priority_score"], SEVERITY_ORDER[item["severity"]], item["title"]),
    )


def build_featured_recommendations(recommendations, limit=6):
    grouped = {}
    for recommendation in recommendations:
        key = (
            recommendation["category_key"],
            recommendation["title"],
            recommendation["recommended_fix"],
        )
        if key not in grouped:
            grouped[key] = {
                **recommendation,
                "page_examples": [],
            }
        current = grouped[key]
        if recommendation.get("page_url") and recommendation["page_url"] not in current["page_examples"]:
            current["page_examples"].append(recommendation["page_url"])
        current["duplicate_issue_count"] = max(
            current.get("duplicate_issue_count", 1),
            recommendation.get("duplicate_issue_count", 1),
        )
        current["priority_score"] = max(current["priority_score"], recommendation["priority_score"])

    collapsed = []
    for item in grouped.values():
        page_examples = item["page_examples"][:3]
        affected_pages = max(len(item["page_examples"]), item.get("duplicate_issue_count", 1))
        if affected_pages > 1:
            item["description"] = (
                f"Detected on {affected_pages} pages. This is lowering the {item['category']} score."
            )
        item["page_examples"] = page_examples
        item["affected_pages_count"] = affected_pages
        collapsed.append(item)

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
    return [
        {
            "category": recommendation["category"],
            "severity": recommendation["severity"],
            "message": recommendation["title"],
            "recommendation": recommendation["recommended_fix"],
        }
        for recommendation in recommendations[:8]
    ]


def build_quick_wins(recommendations):
    quick_wins = []
    seen_categories = set()
    for recommendation in recommendations:
        if recommendation["severity"] not in {AuditIssue.Severity.HIGH, AuditIssue.Severity.MEDIUM}:
            continue
        if recommendation["category_key"] in seen_categories:
            continue
        quick_wins.append(
            {
                "category": recommendation["category"],
                "problem": recommendation["title"],
                "fix": recommendation["recommended_fix"],
                "url": recommendation["page_url"],
            }
        )
        seen_categories.add(recommendation["category_key"])
        if len(quick_wins) >= 6:
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
        if normalized > config["critical_threshold"]:
            status = "critical"
            impact = config["critical_impact"]
        elif normalized > config["warning_threshold"]:
            status = "warning"
            impact = config["warning_impact"]

        performance_metrics.append(
            {
                "key": config["key"],
                "label": config["label"],
                "short_label": config["short_label"],
                "value": str(raw_value),
                "normalized_value": normalized,
                "status": status,
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
    vitals_failures = build_vitals_failures(pagespeed)
    product_modules = build_product_modules(audit_run, score_breakdown)
    custom_work_items = build_custom_work_items(audit_run)

    summary = {
        "top_issues": build_top_issues(recommendations),
        "quick_wins": build_quick_wins(recommendations),
        "featured_recommendations": build_featured_recommendations(recommendations),
        "recommendations": recommendations[:12],
        "issue_summary": build_issue_summary(issue_list),
        "score_breakdown": score_breakdown,
        "vitals_failures": vitals_failures,
        "has_vitals_failure": len(vitals_failures) > 0,
        "performance_metrics": build_performance_metrics(pagespeed),
        "product_modules": product_modules,
        "custom_work_items": custom_work_items,
        "service_fit": product_modules,
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
