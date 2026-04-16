from collections import Counter

from .models import AuditIssue


CATEGORY_SCORE_FIELDS = {
    AuditIssue.Category.TECHNICAL: "technical_score",
    AuditIssue.Category.ON_PAGE: "on_page_score",
    AuditIssue.Category.CONTENT: "content_score",
    AuditIssue.Category.AEO: "aeo_score",
    AuditIssue.Category.INTERNAL_LINKING: "internal_linking_score",
    AuditIssue.Category.PERFORMANCE: "performance_score",
}

CATEGORY_LABELS = {
    AuditIssue.Category.TECHNICAL: "Technical",
    AuditIssue.Category.ON_PAGE: "On-page",
    AuditIssue.Category.CONTENT: "Content",
    AuditIssue.Category.AEO: "AEO",
    AuditIssue.Category.INTERNAL_LINKING: "Internal Linking",
    AuditIssue.Category.PERFORMANCE: "Performance",
    "accessibility": "Accessibility",
    "best_practices": "Best Practices",
    "seo": "SEO",
}

ISSUE_WEIGHTS = {
    AuditIssue.Severity.CRITICAL: 20,
    AuditIssue.Severity.HIGH: 12,
    AuditIssue.Severity.MEDIUM: 7,
    AuditIssue.Severity.LOW: 3,
}

TARGET_SCORE = 85

OVERALL_SCORE_WEIGHTS = {
    "technical": 0.20,
    "on_page": 0.17,
    "content": 0.17,
    "aeo": 0.18,
    "internal_linking": 0.10,
    "performance": 0.10,
    "accessibility": 0.04,
    "best_practices": 0.02,
    "seo": 0.02,
}

CORE_SCORE_KEYS = (
    "technical",
    "on_page",
    "content",
    "aeo",
    "internal_linking",
    "performance",
)

LIGHTHOUSE_SCORE_KEYS = ("accessibility", "best_practices", "seo")

CATEGORY_EXPLANATIONS = {
    "technical": "Structural crawl, indexation, and site-governance signals.",
    "on_page": "Metadata, heading clarity, and page-level relevance signals.",
    "content": "Depth, usefulness, and answer coverage across inspected pages.",
    "aeo": "Entity clarity, answer formatting, and AI-citation readiness.",
    "internal_linking": "Link pathways that help users and crawlers find priority pages.",
    "performance": "Speed and responsiveness impacting user friction and rankings.",
    "accessibility": "Lighthouse accessibility checks affecting usability and quality signals.",
    "best_practices": "Lighthouse implementation checks tied to front-end hygiene.",
    "seo": "Lighthouse SEO checks for crawlable basics and discoverability.",
}

CATEGORY_NEXT_STEPS = {
    "technical": "Resolve crawl blockers, indexation gaps, and status-code failures first.",
    "on_page": "Tighten titles, descriptions, headings, and social metadata on priority pages.",
    "content": "Expand thin pages with proof, examples, and clearer answer coverage.",
    "aeo": "Add direct answers, FAQ structures, and stronger entity signals on key pages.",
    "internal_linking": "Strengthen navigation to revenue pages and reduce orphan-style paths.",
    "performance": "Cut blocking assets and page weight before adding new interface complexity.",
    "accessibility": "Fix contrast, labeling, and semantic issues surfaced by Lighthouse.",
    "best_practices": "Clean up implementation gaps that reduce browser and platform trust.",
    "seo": "Fix baseline crawlability and metadata issues flagged by Lighthouse.",
}


def get_score_status(score):
    if score >= 90:
        return "strong"
    if score >= 75:
        return "stable"
    if score >= 50:
        return "weak"
    return "critical"


def calculate_issue_based_scores(issues):
    scores = {category: 100 for category in CATEGORY_SCORE_FIELDS}

    for issue in issues:
        scores[issue.category] = max(0, scores[issue.category] - ISSUE_WEIGHTS[issue.severity])

    return scores


def serialize_score_snapshot(audit_run):
    return {
        "overall": audit_run.overall_score,
        "technical": audit_run.technical_score,
        "on_page": audit_run.on_page_score,
        "content": audit_run.content_score,
        "aeo": audit_run.aeo_score,
        "internal_linking": audit_run.internal_linking_score,
        "performance": audit_run.performance_score,
        "accessibility": audit_run.accessibility_score,
        "best_practices": audit_run.best_practices_score,
        "seo": audit_run.seo_score,
    }


def calculate_overall_score(audit_run, *, has_pagespeed):
    score_snapshot = serialize_score_snapshot(audit_run)
    active_keys = list(CORE_SCORE_KEYS)
    if has_pagespeed:
        active_keys.extend(LIGHTHOUSE_SCORE_KEYS)

    weighted_total = 0
    total_weight = 0
    for key in active_keys:
        value = score_snapshot.get(key)
        if value is None:
            continue
        weight = OVERALL_SCORE_WEIGHTS[key]
        weighted_total += value * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    return round(weighted_total / total_weight)


def apply_audit_scores(audit_run, *, issues=None, has_pagespeed=False):
    issue_list = list(issues) if issues is not None else list(audit_run.issues.all())
    issue_scores = calculate_issue_based_scores(issue_list)

    audit_run.technical_score = issue_scores[AuditIssue.Category.TECHNICAL]
    audit_run.on_page_score = issue_scores[AuditIssue.Category.ON_PAGE]
    audit_run.content_score = issue_scores[AuditIssue.Category.CONTENT]
    audit_run.aeo_score = issue_scores[AuditIssue.Category.AEO]
    audit_run.internal_linking_score = issue_scores[AuditIssue.Category.INTERNAL_LINKING]

    # When Lighthouse is unavailable, keep performance meaningful instead of leaving the model default at 0.
    if not has_pagespeed:
        audit_run.performance_score = issue_scores[AuditIssue.Category.PERFORMANCE]

    audit_run.overall_score = calculate_overall_score(audit_run, has_pagespeed=has_pagespeed)
    return serialize_score_snapshot(audit_run)


def build_score_breakdown(audit_run, *, issues=None, has_pagespeed=False):
    issue_list = list(issues) if issues is not None else list(audit_run.issues.all())
    issue_counts = Counter(issue.category for issue in issue_list)
    score_snapshot = serialize_score_snapshot(audit_run)

    breakdown = {}
    keys = list(CORE_SCORE_KEYS)
    if has_pagespeed:
        keys.extend(LIGHTHOUSE_SCORE_KEYS)

    for key in keys:
        score = score_snapshot.get(key) or 0
        breakdown[key] = {
            "label": CATEGORY_LABELS[key],
            "score": score,
            "target": TARGET_SCORE,
            "gap": max(0, TARGET_SCORE - score),
            "status": get_score_status(score),
            "issues": issue_counts.get(key, 0),
            "source": (
                "Google PageSpeed Insights"
                if has_pagespeed and key in ("performance", "accessibility", "best_practices", "seo")
                else "crawler heuristic analysis"
            ),
            "explanation": CATEGORY_EXPLANATIONS[key],
            "next_step": CATEGORY_NEXT_STEPS[key],
        }

    return breakdown


def build_gauge_offsets(audit_run):
    score_snapshot = serialize_score_snapshot(audit_run)
    offsets = {
        "overall": round(515.22 * (1 - (score_snapshot["overall"] or 0) / 100)),
    }
    for key in (
        "technical",
        "on_page",
        "content",
        "aeo",
        "internal_linking",
        "performance",
        "accessibility",
        "best_practices",
        "seo",
    ):
        offsets[key] = round(138.23 * (1 - (score_snapshot.get(key) or 0) / 100))
    return offsets
