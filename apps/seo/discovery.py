from collections import defaultdict
from urllib.parse import urlparse

import requests
from django.conf import settings

from apps.tools.services import extract_domain, normalize_url


BLOCKED_COMPETITOR_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "wikipedia.org",
    "reddit.com",
    "yelp.com",
    "tripadvisor.com",
    "booking.com",
    "expedia.com",
    "yellowpages.com",
    "mapquest.com",
    "maps.google.com",
    "google.com",
}


def build_discovery_queries(profile):
    service = (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()
    location = (profile.location or "").strip()
    audience = (profile.target_audience or "").strip()
    goal = (profile.target_goal or "").strip().lower()

    queries = [
        f"{service} {location}".strip(),
        f"best {service} {location}".strip(),
        f"{service} near me".strip(),
    ]
    if audience:
        queries.append(f"{service} for {audience}".strip())
    if "lead" in goal or "inquiry" in goal or "book" in goal:
        queries.append(f"{service} {location} contact".strip())

    unique = []
    for query in queries:
        query = " ".join(query.split())
        if query and query not in unique:
            unique.append(query)
    return unique[: settings.SERP_DISCOVERY_QUERY_LIMIT]


def _serpapi_params(query, location):
    params = {
        "engine": "google",
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
        "num": settings.SERP_DISCOVERY_RESULTS_PER_QUERY,
    }
    if location:
        params["location"] = location
    return params


def fetch_serpapi_results(query, location=""):
    response = requests.get(
        "https://serpapi.com/search.json",
        params=_serpapi_params(query, location),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _candidate_link(result):
    if isinstance(result, str):
        return result.strip()
    if not isinstance(result, dict):
        return ""
    for key in ("link", "website", "url"):
        value = result.get(key)
        if value:
            return value
    sitelinks = result.get("sitelinks")
    if isinstance(sitelinks, dict):
        for group in ("expanded", "inline"):
            for item in sitelinks.get(group, []) or []:
                if isinstance(item, dict):
                    value = item.get("link") or item.get("url")
                    if value:
                        return value
    return ""


def _is_blocked_domain(domain, own_domain):
    if not domain or domain == own_domain:
        return True
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_COMPETITOR_DOMAINS)


def _domain_root_url(link):
    parsed = urlparse(link)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return normalize_url(f"{parsed.scheme}://{parsed.netloc}/")


def _parse_result(result, *, query, own_domain):
    link = _candidate_link(result)
    if not link:
        return None
    domain = extract_domain(link)
    if _is_blocked_domain(domain, own_domain):
        return None
    result_dict = result if isinstance(result, dict) else {}
    position = result_dict.get("position") or result_dict.get("rank") or 99
    try:
        position = int(position)
    except (TypeError, ValueError):
        position = 99
    return {
        "homepage_url": _domain_root_url(link) or normalize_url(link),
        "normalized_domain": domain,
        "position": position,
        "title": (result_dict.get("title") or "").strip(),
        "snippet": (result_dict.get("snippet") or result_dict.get("description") or "").strip(),
        "query": query,
        "result_url": link,
    }


def _result_items(payload, key):
    if not isinstance(payload, dict):
        return []
    items = payload.get(key, [])
    if isinstance(items, dict):
        for nested_key in ("places", "results"):
            nested = items.get(nested_key, [])
            if isinstance(nested, list):
                return nested
        return []
    if isinstance(items, list):
        return items
    return []


def _aggregate_candidates(raw_candidates):
    aggregated = defaultdict(
        lambda: {
            "homepage_url": "",
            "normalized_domain": "",
            "positions": [],
            "queries": [],
            "titles": [],
            "snippets": [],
            "result_urls": [],
        }
    )
    for item in raw_candidates:
        entry = aggregated[item["normalized_domain"]]
        entry["homepage_url"] = item["homepage_url"]
        entry["normalized_domain"] = item["normalized_domain"]
        entry["positions"].append(item["position"])
        if item["query"] not in entry["queries"]:
            entry["queries"].append(item["query"])
        if item["title"] and item["title"] not in entry["titles"]:
            entry["titles"].append(item["title"])
        if item["snippet"] and item["snippet"] not in entry["snippets"]:
            entry["snippets"].append(item["snippet"])
        if item["result_url"] and item["result_url"] not in entry["result_urls"]:
            entry["result_urls"].append(item["result_url"])

    discovered = []
    for domain, item in aggregated.items():
        appearances = len(item["positions"])
        average_position = round(sum(item["positions"]) / max(appearances, 1), 1)
        best_position = min(item["positions"]) if item["positions"] else 99
        discovery_score = appearances * 20 + max(0, 15 - best_position)
        discovered.append(
            {
                "homepage_url": item["homepage_url"],
                "normalized_domain": domain,
                "label": domain,
                "queries": item["queries"],
                "query_count": len(item["queries"]),
                "best_position": best_position,
                "average_position": average_position,
                "sample_titles": item["titles"][:4],
                "sample_snippets": item["snippets"][:3],
                "result_urls": item["result_urls"][:6],
                "discovery_score": discovery_score,
            }
        )

    discovered.sort(key=lambda item: (-item["discovery_score"], item["average_position"]))
    return discovered


def discover_serp_competitors(project, profile):
    if not settings.SERP_DISCOVERY_ENABLED or not profile:
        return {
            "provider": settings.SERP_DISCOVERY_PROVIDER,
            "enabled": False,
            "queries": [],
            "competitors": [],
            "errors": [],
        }

    own_domain = project.normalized_domain or extract_domain(project.website or "")
    queries = build_discovery_queries(profile)
    raw_candidates = []
    errors = []

    for query in queries:
        try:
            payload = fetch_serpapi_results(query, location=profile.location)
        except requests.RequestException as exc:
            errors.append({"query": query, "message": str(exc)})
            continue
        try:
            for result in _result_items(payload, "organic_results"):
                parsed = _parse_result(result, query=query, own_domain=own_domain)
                if parsed:
                    raw_candidates.append(parsed)
            for result in _result_items(payload, "local_results"):
                parsed = _parse_result(result, query=query, own_domain=own_domain)
                if parsed:
                    raw_candidates.append(parsed)
        except Exception as exc:
            errors.append({"query": query, "message": f"SERP parsing error: {exc}"})
            continue

    competitors = _aggregate_candidates(raw_candidates)
    return {
        "provider": settings.SERP_DISCOVERY_PROVIDER,
        "enabled": True,
        "queries": queries,
        "competitors": competitors,
        "errors": errors,
    }
