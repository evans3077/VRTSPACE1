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
                "severity": issue.severity,
                "page_url": issue.page.url if issue.page_id and issue.page else None,
                "cta": "Fix this for me" if issue.severity in {AuditIssue.Severity.CRITICAL, AuditIssue.Severity.HIGH} else "Review this fix",
            }
        )

    return sorted(
        recommendations,
        key=lambda item: (-item["priority_score"], SEVERITY_ORDER[item["severity"]], item["title"]),
    )


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


def build_vitals_failures(pagespeed):
    vitals_failures = []
    if not pagespeed:
        return vitals_failures

    metrics = pagespeed.get("metrics", {})

    lcp_str = metrics.get("largest_contentful_paint", "0")
    try:
        lcp_val = float(re.findall(r"[\d.]+", lcp_str)[0])
        if lcp_val > 4.0:
            vitals_failures.append(
                {
                    "metric": "Largest Contentful Paint (LCP)",
                    "value": lcp_str,
                    "threshold": "4.0s",
                    "impact": "Slow loading of main content causes high user abandonment.",
                }
            )
    except (IndexError, ValueError):
        pass

    cls_str = metrics.get("cumulative_layout_shift", "0")
    try:
        cls_val = float(cls_str)
        if cls_val > 0.25:
            vitals_failures.append(
                {
                    "metric": "Cumulative Layout Shift (CLS)",
                    "value": cls_str,
                    "threshold": "0.25",
                    "impact": "Jumping content causes frustration and accidental clicks.",
                }
            )
    except ValueError:
        pass

    tbt_str = metrics.get("total_blocking_time", "0")
    try:
        tbt_val = float(re.findall(r"[\d.]+", tbt_str)[0])
        if tbt_val > 600:
            vitals_failures.append(
                {
                    "metric": "Total Blocking Time (TBT)",
                    "value": tbt_str,
                    "threshold": "600ms",
                    "impact": "Main thread blocking delays user interaction responsiveness.",
                }
            )
    except (IndexError, ValueError):
        pass

    return vitals_failures


def build_service_fit(audit_run, score_breakdown):
    fits = []

    if audit_run.technical_score < 80 or audit_run.on_page_score < 80:
        fits.append(
            {
                "title": "SEO Foundation",
                "reason": f"Technical and on-page signals are under target at {audit_run.technical_score}% and {audit_run.on_page_score}%.",
                "impact": "Tightening crawl and on-page signals should improve ranking stability and page discoverability.",
                "icon": "SEO",
                "anchor": "revenue",
            }
        )

    if audit_run.aeo_score < 85:
        aeo_issues = score_breakdown.get("aeo", {}).get("issues", 0)
        fits.append(
            {
                "title": "AEO / AI Search Optimization",
                "reason": f"AEO readiness is at {audit_run.aeo_score}%, with {aeo_issues} AI-answer formatting or entity issues detected.",
                "impact": "Improving direct answers and entity structure should increase citation readiness in answer engines.",
                "icon": "AEO",
                "anchor": "revenue",
            }
        )

    if audit_run.performance_score < 85:
        fits.append(
            {
                "title": "Performance Optimization",
                "reason": f"Performance is at {audit_run.performance_score}%, leaving measurable friction in mobile UX and conversion.",
                "impact": "Reducing speed bottlenecks should improve conversion resilience and search quality signals.",
                "icon": "Speed",
                "anchor": "growth",
            }
        )

    if audit_run.content_score < 85:
        fits.append(
            {
                "title": "Content Authority System",
                "reason": f"Content quality is at {audit_run.content_score}%, which suggests thin or weakly structured coverage.",
                "impact": "Expanding coverage and answer depth should improve topical authority and assist both SEO and AEO.",
                "icon": "Content",
                "anchor": "revenue",
            }
        )

    return fits[:4]


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

    summary = {
        "top_issues": build_top_issues(recommendations),
        "quick_wins": build_quick_wins(recommendations),
        "recommendations": recommendations[:12],
        "issue_summary": build_issue_summary(issue_list),
        "score_breakdown": score_breakdown,
        "vitals_failures": vitals_failures,
        "has_vitals_failure": len(vitals_failures) > 0,
        "service_fit": build_service_fit(audit_run, score_breakdown),
        "pages_crawled": audit_run.pages_crawled,
        "scores": serialize_score_snapshot(audit_run),
        "gauge_offsets": build_gauge_offsets(audit_run),
        "full_audit_teasers": [
            "Keyword Gap Analysis vs Top 3 Competitors",
            "Deep Backlink Profile & Toxic Link Detection",
            "Search Console Integration & Click-Through Optimization",
            "Entity-Based Content Gap Map",
            "Core Web Vitals Field Data (Real User Metrics)",
            "Conversion Rate Optimization (CRO) Heuristics",
        ],
        "performance_source": pagespeed["source"] if pagespeed else "heuristic crawler analysis",
    }
    if pagespeed:
        summary["pagespeed"] = pagespeed
    return summary
