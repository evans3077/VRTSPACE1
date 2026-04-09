from collections import Counter

from django.utils.text import slugify


ROOT_CAUSE_LABELS = {
    "answer-readiness": "Answer readiness",
    "content-depth": "Content depth",
    "crawl-foundation": "Crawl foundation",
    "entity-clarity": "Entity clarity",
    "internal-linking": "Internal linking",
    "local-intent": "Local intent",
    "on-page-structure": "On-page structure",
    "page-coverage": "Page coverage",
    "performance": "Performance",
}


def infer_root_cause_key(*, title="", category="", category_key="", recommended_fix=""):
    haystack = " ".join(
        [
            str(title or ""),
            str(category or ""),
            str(category_key or ""),
            str(recommended_fix or ""),
        ]
    ).lower()

    if any(
        token in haystack
        for token in ("title", "meta", "h1", "heading", "on-page", "metadata", "snippet")
    ):
        return "on-page-structure"
    if any(token in haystack for token in ("faq", "answer block", "answer-first", "schema", "citation")):
        return "answer-readiness"
    if any(token in haystack for token in ("internal link", "orphan", "authority flow", "path depth")):
        return "internal-linking"
    if any(token in haystack for token in ("entity", "service and location", "business type", "topic signals")):
        return "entity-clarity"
    if any(token in haystack for token in ("location", "city", "near me", "local modifier")):
        return "local-intent"
    if any(token in haystack for token in ("page layer", "missing page", "page coverage", "build ")) or (
        "missing" in haystack and "page" in haystack and "title" not in haystack and "h1" not in haystack and "meta" not in haystack
    ):
        return "page-coverage"
    if any(token in haystack for token in ("thin", "proof", "content depth", "deepen ", "completeness")):
        return "content-depth"
    if any(
        token in haystack
        for token in ("performance", "response time", "ttfb", "lcp", "tbt", "layout shift", "slow")
    ):
        return "performance"
    if any(
        token in haystack
        for token in ("technical", "sitemap", "robots", "canonical", "crawl", "index", "status code")
    ):
        return "crawl-foundation"

    fallback = category_key or category or title or "recommendation"
    return slugify(str(fallback)) or "recommendation"


def root_cause_label(root_cause_key):
    return ROOT_CAUSE_LABELS.get(
        root_cause_key,
        str(root_cause_key or "recommendation").replace("-", " ").replace("_", " ").title(),
    )


def _unique_urls(values):
    urls = []
    seen = set()
    for value in values or []:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        urls.append(value)
    return urls


def build_recommendation_evidence(
    *,
    page_targets=None,
    competitor_evidence=None,
    issue_count=0,
    technical_steps=None,
    source_signals=None,
):
    page_targets = _unique_urls(page_targets)
    technical_steps = [step for step in (technical_steps or []) if step]
    source_signals = [signal for signal in (source_signals or []) if signal]

    competitor_urls = []
    for evidence in competitor_evidence or []:
        if isinstance(evidence, dict):
            competitor_urls.append(evidence.get("url") or evidence.get("domain") or "")
        elif isinstance(evidence, str):
            competitor_urls.append(evidence)
    competitor_urls = _unique_urls(competitor_urls)

    score = 22
    score += min(24, int(issue_count or 0) * 4)
    score += min(20, len(page_targets) * 6)
    score += min(24, len(competitor_urls) * 8)
    score += min(12, len(technical_steps) * 3)
    score += min(12, len(source_signals) * 4)

    if not page_targets and not competitor_urls:
        score -= 8
    if not issue_count and not page_targets and not competitor_urls:
        score -= 12

    score = max(0, min(100, score))

    if score >= 78:
        confidence = "High confidence"
        status = "strong"
    elif score >= 58:
        confidence = "Medium confidence"
        status = "stable"
    elif score >= 40:
        confidence = "Watch confidence"
        status = "watch"
    else:
        confidence = "Low confidence"
        status = "weak"

    signal_parts = []
    if issue_count:
        signal_parts.append(f"{issue_count} grouped signal{'s' if issue_count != 1 else ''}")
    if page_targets:
        signal_parts.append(f"{len(page_targets)} page target{'s' if len(page_targets) != 1 else ''}")
    if competitor_urls:
        signal_parts.append(f"{len(competitor_urls)} competitor example{'s' if len(competitor_urls) != 1 else ''}")
    if source_signals:
        signal_parts.append(f"{len(source_signals)} supporting source signal{'s' if len(source_signals) != 1 else ''}")
    summary = ", ".join(signal_parts) if signal_parts else "Light supporting evidence"

    return {
        "score": score,
        "confidence_label": confidence,
        "status": status,
        "summary": summary,
        "page_target_count": len(page_targets),
        "competitor_evidence_count": len(competitor_urls),
        "issue_count": int(issue_count or 0),
        "source_signal_count": len(source_signals),
    }


def should_surface_recommendation(item, *, minimum_score=40):
    evidence = item.get("evidence") or {}
    evidence_score = int(evidence.get("score") or 0)
    priority_score = int(item.get("priority_score") or 0)
    if evidence_score >= minimum_score:
        return True
    return priority_score >= 90 and evidence_score >= max(28, minimum_score - 12)


def decorate_recommendation(
    item,
    *,
    page_targets=None,
    competitor_evidence=None,
    issue_count=0,
    technical_steps=None,
    source_signals=None,
):
    decorated = dict(item)
    root_cause_key = decorated.get("root_cause_key") or infer_root_cause_key(
        title=decorated.get("title", ""),
        category=decorated.get("category", ""),
        category_key=decorated.get("category_key", ""),
        recommended_fix=decorated.get("recommended_fix", ""),
    )
    decorated["root_cause_key"] = root_cause_key
    decorated["root_cause_label"] = root_cause_label(root_cause_key)
    evidence = build_recommendation_evidence(
        page_targets=page_targets,
        competitor_evidence=competitor_evidence,
        issue_count=issue_count,
        technical_steps=technical_steps,
        source_signals=source_signals,
    )
    decorated["evidence"] = evidence
    decorated["evidence_score"] = evidence["score"]
    decorated["confidence_label"] = evidence["confidence_label"]
    decorated["evidence_summary"] = evidence["summary"]
    decorated["evidence_status"] = evidence["status"]
    return decorated


def merge_root_cause_labels(items):
    counter = Counter(item.get("root_cause_label", "") for item in items if item.get("root_cause_label"))
    return [label for label, _count in counter.most_common()]
