from django.utils.safestring import mark_safe


def get_score_color(score):
    if score is None:
        return "#64748b"  # slate-500
    if score >= 90:
        return "#16a34a"  # green-600
    if score >= 50:
        return "#ea580c"  # orange-600
    return "#dc2626"  # red-600

def format_score_pill(score):
    color = get_score_color(score)
    return mark_safe(
        f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 0.85em;">{score if score is not None else "N/A"}</span>'
    )

SERVICE_ADVICE = {
    "technical": {
        "title": "Technical SEO & Infrastructure",
        "service": "Technical SEO Audit & Fixes",
        "impact": "Improves crawlability and indexing. Ensures search engines can 'understand' and access your content without friction.",
    },
    "on_page": {
        "title": "On-Page Optimization",
        "service": "On-Page SEO Refactor",
        "impact": "Directly influences rankings for target keywords by aligning metadata and headings with search intent.",
    },
    "content": {
        "title": "Content Quality & Depth",
        "service": "Content Strategy & Clustering",
        "impact": "Builds topical authority and improves user engagement. Thin content is often ignored by modern search engines.",
    },
    "aeo": {
        "title": "Answer Engine Optimization (AEO)",
        "service": "AEO & Entity Mapping",
        "impact": "Critical for visibility in AI Search (ChatGPT, Gemini, Perplexity). Helps your brand become a cited source in AI answers.",
    },
    "internal_linking": {
        "title": "Link Architecture",
        "service": "Information Architecture Review",
        "impact": "Distributes 'link juice' effectively and helps users (and bots) discover your most important pages.",
    },
    "performance": {
        "title": "Performance & Speed",
        "service": "Performance Sprint / Rebuild",
        "impact": "Significant ranking factor. Slow sites lose 40%+ of visitors before they even load. Vital for mobile-first indexing.",
    },
}


def get_service_recommendations(audit_run):
    summary = audit_run.summary or {}
    summary_fits = summary.get("product_modules") or summary.get("service_fit") or []
    if summary_fits:
        recommendations = []
        for fit in summary_fits:
            score = None
            title = fit.get("title", "")
            score_key = fit.get("score_key")
            if score_key == "technical":
                score = min(audit_run.technical_score, audit_run.on_page_score)
            elif score_key == "aeo":
                score = audit_run.aeo_score
            elif score_key == "performance":
                score = audit_run.performance_score
            elif score_key == "content":
                score = audit_run.content_score
            elif score_key == "internal_linking":
                score = audit_run.internal_linking_score
            elif "SEO Foundation" in title or "Site Health" in title:
                score = min(audit_run.technical_score, audit_run.on_page_score)
            elif "AEO" in title or "AI Visibility" in title:
                score = audit_run.aeo_score
            elif "Performance" in title:
                score = audit_run.performance_score
            elif "Content" in title:
                score = audit_run.content_score

            recommendations.append(
                {
                    "category": fit.get("title", "Product Opportunity"),
                    "score": score,
                    "service": fit.get("title", "Workspace Upgrade"),
                    "impact": fit.get("impact", ""),
                    "reason": fit.get("reason", ""),
                    "color": get_score_color(score),
                }
            )
        return recommendations

    recommendations = []
    threshold = 85

    scores = {
        "technical": audit_run.technical_score,
        "on_page": audit_run.on_page_score,
        "content": audit_run.content_score,
        "aeo": audit_run.aeo_score,
        "internal_linking": audit_run.internal_linking_score,
        "performance": audit_run.performance_score,
    }
    
    for key, score in scores.items():
        if score < threshold and key in SERVICE_ADVICE:
            advice = SERVICE_ADVICE[key]
            recommendations.append({
                "category": advice["title"],
                "score": score,
                "service": advice["service"],
                "impact": advice["impact"],
                "reason": "",
                "color": get_score_color(score),
            })

    return recommendations
