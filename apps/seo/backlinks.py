from collections import Counter, defaultdict

from apps.tools.services import extract_domain, normalize_url

from .discovery import (
    BLOCKED_COMPETITOR_DOMAINS,
    fetch_search_results,
)
from .models import BacklinkProspect, BacklinkSnapshot, SEOCompetitor
from .services import build_local_keyword_set, build_priority_pages, infer_business_type_for_project


BACKLINK_HINTS = {
    "resource": ["resources", "guide", "learn", "faq", "help"],
    "directory": ["directory", "listing", "listings", "business", "companies"],
    "association": ["association", "society", "council", "chamber", "organization"],
    "blog": ["blog", "news", "insights", "editorial", "magazine"],
    "media": ["press", "media", "newsroom", "publication"],
    "partner": ["partners", "partner", "vendors", "suppliers"],
}


def _project_competitor_domains(project):
    return {
        competitor.normalized_domain
        for competitor in project.seo_competitors.filter(is_active=True)
        if competitor.normalized_domain
    }


def _classify_prospect_type(link, title, snippet):
    haystack = " ".join([link or "", title or "", snippet or ""]).lower()
    if any(hint in haystack for hint in BACKLINK_HINTS["association"]):
        return BacklinkProspect.ProspectType.ASSOCIATION
    if any(hint in haystack for hint in BACKLINK_HINTS["directory"]):
        return BacklinkProspect.ProspectType.DIRECTORY
    if any(hint in haystack for hint in BACKLINK_HINTS["media"]):
        return BacklinkProspect.ProspectType.MEDIA
    if any(hint in haystack for hint in BACKLINK_HINTS["partner"]):
        return BacklinkProspect.ProspectType.PARTNER
    if any(hint in haystack for hint in BACKLINK_HINTS["blog"]):
        return BacklinkProspect.ProspectType.BLOG
    return BacklinkProspect.ProspectType.RESOURCE


def _asset_from_page_map_item(project, profile, item):
    asset_type = item.get("page_type_label", item.get("page_type", "page"))
    target_url = (item.get("target_urls") or [""])[0]
    if not target_url:
        website = (project.website or "").rstrip("/")
        if website:
            target_url = normalize_url(
                f"{website}/{item.get('target_keyword', '').lower().replace(' ', '-')}/"
            ) or project.website
        else:
            target_url = ""
    target_keyword = item.get("target_keyword", "")
    target_urls = item.get("target_urls", [])
    asset_kind = "linkable page"
    if item.get("page_type") in {"comparison", "article", "faq"}:
        asset_kind = "information asset"
    elif item.get("page_type") in {"location", "service"}:
        asset_kind = "commercial asset"
    return {
        "asset_key": f"page-map-{item.get('page_type', 'page')}-{target_keyword}".lower()[:120],
        "asset_title": f"{item.get('page_type_label', 'Page')} asset for {target_keyword}",
        "asset_type": item.get("page_type", "page"),
        "asset_kind": asset_kind,
        "asset_url": target_url,
        "supporting_urls": target_urls[:3],
        "target_keyword": target_keyword,
        "support_terms": item.get("support_terms", []),
        "reason": item.get("reason", ""),
        "priority_score": item.get("priority_score", 0),
        "outreach_angle": item.get("action", ""),
        "pitch_hook": (
            f"Use this {asset_kind} to give sites in {profile.location} something concrete to cite, list, or reference "
            f"around {target_keyword or profile.primary_service or profile.business_type}."
        ),
    }


def _asset_from_generated_content(draft):
    brief = draft.brief_json or {}
    return {
        "asset_key": f"draft-{draft.pk}",
        "asset_title": draft.title,
        "asset_type": draft.output_type,
        "asset_kind": "generated draft",
        "asset_url": "",
        "supporting_urls": brief.get("target_urls", [])[:3],
        "target_keyword": (draft.target_keywords or [""])[0],
        "support_terms": (draft.target_keywords or [])[1:4],
        "reason": brief.get("summary", ""),
        "priority_score": 70,
        "outreach_angle": brief.get("action", "") or draft.cta,
        "pitch_hook": "Convert this draft into a publishable link asset before outreach begins.",
    }


def build_linkable_assets(project, profile, opportunity_payload):
    assets = []
    seen = set()
    for item in (opportunity_payload.get("page_map") or [])[:6]:
        if item.get("status") == "backlog":
            continue
        asset = _asset_from_page_map_item(project, profile, item)
        if asset["asset_key"] in seen:
            continue
        seen.add(asset["asset_key"])
        assets.append(asset)

    for draft in project.generated_content.order_by("-created_at")[:4]:
        asset = _asset_from_generated_content(draft)
        if asset["asset_key"] in seen:
            continue
        seen.add(asset["asset_key"])
        assets.append(asset)

    assets.sort(key=lambda item: -item["priority_score"])
    return assets[:8]


def build_backlink_queries(profile, asset):
    keyword = asset.get("target_keyword") or profile.primary_service or profile.business_type.replace("_", " ")
    location = profile.location or ""
    business_type = infer_business_type_for_project(profile.project, primary_service=profile.primary_service)
    priority_pages = build_priority_pages(profile, {"summary": {"counts_by_type": {}}})
    base_queries = [
        f"{keyword} resources {location}".strip(),
        f"{keyword} directory {location}".strip(),
        f"{keyword} association {location}".strip(),
        f"{keyword} blog".strip(),
        f"{keyword} partners".strip(),
    ]
    if business_type in {"automotive", "local_service", "real_estate", "healthcare"}:
        base_queries.append(f"{keyword} local listing {location}".strip())
    if asset.get("asset_type") in {"faq", "answer_block"}:
        base_queries.append(f"{keyword} faq resources".strip())
    if priority_pages:
        base_queries.append(f"{priority_pages[0]} {location}".strip())

    unique = []
    for query in base_queries:
        query = " ".join(query.split())
        if query and query not in unique:
            unique.append(query)
    return unique[:4]


def _prospect_score(profile, asset, result):
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    link = result.get("result_url", "")
    haystack = " ".join([title, snippet, link]).lower()
    location_tokens = [token for token in profile.location.lower().split() if len(token) > 2] if profile.location else []
    keyword_tokens = [token for token in (asset.get("target_keyword") or "").lower().split() if len(token) > 2]
    service_tokens = [token for token in (profile.primary_service or profile.business_type).lower().replace("_", " ").split() if len(token) > 2]

    relevance = 0
    for token in keyword_tokens[:4]:
        if token in haystack:
            relevance += 18
    for token in service_tokens[:4]:
        if token in haystack:
            relevance += 12
    prospect_type = _classify_prospect_type(link, title, snippet)

    authority_fit = 25
    domain = extract_domain(link)
    if domain.endswith(".org"):
        authority_fit += 18
    if domain.endswith(".gov"):
        authority_fit += 20
    if any(hint in haystack for hint in ("association", "chamber", "council", "society", "publication")):
        authority_fit += 12

    local_fit = 0
    for token in location_tokens[:3]:
        if token in haystack:
            local_fit += 18
    if prospect_type == BacklinkProspect.ProspectType.DIRECTORY and location_tokens:
        local_fit += 10

    outreach_likelihood = 15
    if any(hint in haystack for hint in ("submit", "directory", "listing", "partners", "resources", "write for us", "contribute")):
        outreach_likelihood += 22
    if prospect_type in {BacklinkProspect.ProspectType.ASSOCIATION, BacklinkProspect.ProspectType.DIRECTORY}:
        outreach_likelihood += 12

    total = min(100, round(relevance * 0.4 + authority_fit * 0.2 + local_fit * 0.2 + outreach_likelihood * 0.2))
    return {
        "prospect_type": prospect_type,
        "relevance_score": min(relevance, 100),
        "authority_fit_score": min(authority_fit, 100),
        "local_fit_score": min(local_fit, 100),
        "outreach_likelihood_score": min(outreach_likelihood, 100),
        "total_score": total,
    }


def _build_outreach_packet(profile, asset, result, scores):
    target_keyword = asset.get("target_keyword") or profile.primary_service or profile.business_type.replace("_", " ")
    asset_title = asset.get("asset_title", "resource")
    pitch_angle = (
        f"{asset_title} gives {extract_domain(result.get('result_url', ''))} a focused resource around {target_keyword} "
        f"that supports {profile.location or 'the target market'} demand."
    )
    subject_lines = [
        f"Resource idea for {result.get('title') or extract_domain(result.get('result_url', ''))}",
        f"{target_keyword.title()} asset worth listing",
    ]
    proof_points = [
        asset.get("reason", ""),
        asset.get("outreach_angle", ""),
        f"Priority score {asset.get('priority_score', 0)} in the SEO roadmap.",
    ]
    proof_points = [item for item in proof_points if item]
    return {
        "subject_lines": subject_lines,
        "pitch_angle": pitch_angle,
        "proof_points": proof_points[:3],
        "cta": f"Would you consider including or referencing {asset_title.lower()}?",
    }


def build_backlink_snapshot_payload(project, profile, context_payload, opportunity_payload):
    assets = build_linkable_assets(project, profile, opportunity_payload)
    own_domain = project.normalized_domain or extract_domain(project.website or "")
    competitor_domains = _project_competitor_domains(project)
    prospect_rows = []
    search_errors = []
    source_counter = Counter()

    for asset in assets[:4]:
        queries = build_backlink_queries(profile, asset)
        asset_results = []
        for query in queries:
            search_response = fetch_search_results(query, location=profile.location)
            provider = search_response.get("provider", "")
            payload = search_response.get("payload") or {}
            if provider:
                source_counter[provider] += 1
            for error in search_response.get("errors", []):
                search_errors.append({"query": query, **error})
            for result in (payload.get("organic_results") or [])[:8]:
                if not isinstance(result, dict):
                    continue
                link = normalize_url(result.get("link") or result.get("url") or result.get("website"))
                if not link:
                    continue
                domain = extract_domain(link)
                if not domain or domain == own_domain or domain in competitor_domains:
                    continue
                if any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_COMPETITOR_DOMAINS):
                    continue
                scores = _prospect_score(profile, asset, {**result, "result_url": link})
                if scores["total_score"] < 35:
                    continue
                asset_results.append(
                    {
                        "domain": domain,
                        "homepage_url": normalize_url(f"https://{domain}/"),
                        "prospect_url": link,
                        "title": (result.get("title") or "").strip(),
                        "snippet": (result.get("snippet") or result.get("description") or "").strip(),
                        "query": query,
                        "source_provider": provider,
                        **scores,
                        "prospect_type": scores["prospect_type"],
                        "target_asset_title": asset["asset_title"],
                        "target_asset_type": asset["asset_type"],
                        "target_asset_url": asset["asset_url"],
                        "suggested_anchor_text": asset.get("target_keyword", "")[:255],
                        "outreach_packet": _build_outreach_packet(profile, asset, {**result, "result_url": link}, scores),
                        "metadata": {
                            "query": query,
                            "asset_key": asset["asset_key"],
                            "asset_kind": asset.get("asset_kind", ""),
                            "support_terms": asset.get("support_terms", []),
                            "reason": asset.get("reason", ""),
                        },
                    }
                )
        deduped = {}
        for item in sorted(asset_results, key=lambda row: -row["total_score"]):
            dedupe_key = (item["prospect_url"], item["target_asset_url"])
            if dedupe_key not in deduped:
                deduped[dedupe_key] = item
        prospect_rows.extend(list(deduped.values())[:8])

    prospect_rows.sort(key=lambda row: -row["total_score"])
    return {
        "linkable_assets": assets,
        "prospects": prospect_rows[:20],
        "summary": {
            "linkable_asset_count": len(assets),
            "prospect_count": len(prospect_rows[:20]),
            "providers_used": dict(source_counter),
            "average_total_score": round(
                sum(item["total_score"] for item in prospect_rows[:20]) / max(len(prospect_rows[:20]), 1),
                1,
            ) if prospect_rows else 0,
        },
        "errors": search_errors[:20],
        "context": {
            "location": profile.location,
            "business_type": profile.business_type,
            "goal": profile.target_goal,
            "priority_pages": context_payload.get("context", {}).get("priority_pages", []),
            "keyword_hints": build_local_keyword_set(profile)[:4],
        },
    }


def refresh_project_backlink_intelligence(project, *, context_snapshot=None, opportunity_snapshot=None):
    profile = getattr(project, "seo_profile", None)
    latest_audit = getattr(project, "latest_audit_run", None)
    if not profile or not latest_audit:
        return None

    context_snapshot = context_snapshot or project.seo_snapshots.filter(
        profile=profile,
        source_audit_run=latest_audit,
    ).order_by("-created_at").first()
    opportunity_snapshot = opportunity_snapshot or project.seo_opportunity_snapshots.filter(
        profile=profile,
        source_audit_run=latest_audit,
    ).order_by("-created_at").first()
    if not context_snapshot or not opportunity_snapshot:
        return None

    payload = build_backlink_snapshot_payload(
        project,
        profile,
        context_snapshot.output_json or {},
        opportunity_snapshot.output_json or {},
    )
    snapshot = BacklinkSnapshot.objects.create(
        project=project,
        profile=profile,
        source_audit_run=latest_audit,
        source_context_snapshot=context_snapshot,
        source_opportunity_snapshot=opportunity_snapshot,
        output_json=payload,
    )
    sync_backlink_prospects(project, snapshot)
    return snapshot


def sync_backlink_prospects(project, snapshot):
    rows = (snapshot.output_json or {}).get("prospects", [])
    prospect_ids = []
    campaigns = list(project.seo_campaigns.all())
    campaign_by_url = {}
    campaign_by_keyword = {}
    for campaign in campaigns:
        for url in campaign.related_page_urls or []:
            if url:
                campaign_by_url[url] = campaign
        if campaign.target_keyword:
            campaign_by_keyword[campaign.target_keyword.lower()] = campaign
    for row in rows:
        campaign = None
        target_asset_url = row.get("target_asset_url", "")
        if target_asset_url:
            campaign = campaign_by_url.get(target_asset_url)
        if not campaign:
            anchor_text = str(row.get("suggested_anchor_text", "")).strip().lower()
            if anchor_text:
                campaign = campaign_by_keyword.get(anchor_text)
        prospect, _created = BacklinkProspect.objects.update_or_create(
            project=project,
            prospect_url=row.get("prospect_url", ""),
            target_asset_url=row.get("target_asset_url", ""),
            defaults={
                "snapshot": snapshot,
                "seo_campaign": campaign,
                "domain": row.get("domain", ""),
                "homepage_url": row.get("homepage_url", ""),
                "title": row.get("title", ""),
                "prospect_type": row.get("prospect_type", BacklinkProspect.ProspectType.RESOURCE),
                "relevance_score": row.get("relevance_score", 0),
                "authority_fit_score": row.get("authority_fit_score", 0),
                "local_fit_score": row.get("local_fit_score", 0),
                "outreach_likelihood_score": row.get("outreach_likelihood_score", 0),
                "total_score": row.get("total_score", 0),
                "target_asset_title": row.get("target_asset_title", ""),
                "target_asset_type": row.get("target_asset_type", ""),
                "suggested_anchor_text": row.get("suggested_anchor_text", ""),
                "outreach_packet": row.get("outreach_packet", {}),
                "metadata": row.get("metadata", {}),
            },
        )
        prospect_ids.append(prospect.pk)
    if prospect_ids:
        project.backlink_prospects.exclude(pk__in=prospect_ids).update(snapshot=snapshot)
    return list(project.backlink_prospects.order_by("-total_score", "-updated_at")[:20])
