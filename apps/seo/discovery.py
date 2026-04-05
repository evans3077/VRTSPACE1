from collections import defaultdict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

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

DISCOVERY_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "your",
    "you",
    "into",
    "near",
    "best",
    "top",
    "home",
    "about",
    "contact",
    "page",
}

GENERIC_RESULT_HINTS = {
    "jobs",
    "career",
    "careers",
    "wikipedia",
    "reddit",
    "directory",
    "listing",
    "forum",
}

NON_COMPETITOR_RESULT_HINTS = {
    "lead finder",
    "lead generation",
    "directory",
    "directories",
    "listing",
    "listings",
    "blog",
    "wordpress",
    "blogspot",
    "top 10",
    "document",
    "pdf",
    "resource",
    "resources",
    "classifieds",
}

NON_COMPETITOR_DOMAIN_HINTS = {
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

INDUSTRY_DISCOVERY_TERMS = {
    "automotive": ["used car dealership", "used cars for sale", "car dealer", "vehicle financing"],
    "agency": ["services", "pricing", "case study", "consulting"],
    "saas": ["software", "platform", "pricing", "features"],
    "hotel": ["rooms", "booking", "amenities", "events"],
    "ecommerce": ["shop", "products", "category", "pricing"],
    "healthcare": ["clinic", "appointment", "care", "service"],
    "real_estate": ["property", "listing", "homes", "real estate"],
    "local_service": ["services", "near me", "pricing", "reviews"],
}

INDUSTRY_MUST_HAVE_TERMS = {
    "automotive": ["car", "cars", "vehicle", "vehicles", "dealer", "dealership", "used car", "auto"],
    "agency": ["agency", "marketing", "seo", "design", "consulting"],
    "saas": ["software", "platform", "app", "tool", "dashboard"],
    "hotel": ["hotel", "room", "booking", "stay"],
    "ecommerce": ["shop", "store", "product", "products"],
    "healthcare": ["clinic", "doctor", "medical", "care"],
    "real_estate": ["property", "real estate", "home", "homes"],
    "local_service": ["service", "services", "repair", "installation"],
}

DISCOVERY_QUERY_TEMPLATES = {
    "default": [
        "{service} {location}",
        "best {service} {location}",
        "{service} pricing {location}",
        "{service} faq {location}",
        "{service} contact {location}",
        "{service} near me",
    ],
    "automotive": [
        "{service} {location}",
        "best {service} {location}",
        "{service} near me",
        "used cars for sale {location}",
        "car dealer {location}",
        "car financing {location}",
        "sell your car {location}",
        "best used car dealer {location}",
    ],
    "agency": [
        "{service} {location}",
        "seo agency {location}",
        "digital marketing agency {location}",
        "{service} pricing {location}",
        "best {service} {location}",
        "{service} case study {location}",
    ],
    "hotel": [
        "{service} {location}",
        "hotel {location}",
        "rooms in {location}",
        "best hotel {location}",
        "{service} amenities {location}",
        "{service} booking {location}",
    ],
    "real_estate": [
        "{service} {location}",
        "property for sale {location}",
        "real estate agent {location}",
        "homes for sale {location}",
        "{service} pricing {location}",
        "best {service} {location}",
    ],
}


def _provider_order():
    providers = [
        value.strip().lower()
        for value in (settings.SERP_DISCOVERY_PROVIDER or "").split(",")
        if value.strip()
    ]
    return providers or ["duckduckgo"]


def _provider_timeout(provider):
    if provider == "duckduckgo":
        return max(3, int(getattr(settings, "SERP_DUCKDUCKGO_TIMEOUT_SECONDS", 8)))
    return max(3, int(getattr(settings, "SERP_PROVIDER_TIMEOUT_SECONDS", 10)))


def _provider_cooldown_seconds(provider):
    if provider == "duckduckgo":
        return max(30, int(getattr(settings, "SERP_DUCKDUCKGO_COOLDOWN_SECONDS", 180)))
    return max(30, int(getattr(settings, "SERP_PROVIDER_COOLDOWN_SECONDS", 300)))


def _provider_cooldown_cache_key(provider):
    return f"seo:provider-cooldown:{provider}"


def _provider_cooldown_message(provider):
    seconds = _provider_cooldown_seconds(provider)
    return f"{provider} temporarily cooled down after repeated failures. Retry in about {seconds} seconds."


def _provider_is_cooled_down(provider):
    return bool(cache.get(_provider_cooldown_cache_key(provider)))


def _mark_provider_cooldown(provider):
    cache.set(_provider_cooldown_cache_key(provider), 1, _provider_cooldown_seconds(provider))


def _disable_provider(runtime_state, provider):
    if runtime_state is None:
        return
    runtime_state.setdefault("disabled_providers", set()).add(provider)


def _provider_is_disabled(runtime_state, provider):
    if runtime_state is None:
        return False
    return provider in runtime_state.setdefault("disabled_providers", set())


def _tokenize_terms(text):
    tokens = []
    for raw in (text or "").replace("/", " ").replace("-", " ").split():
        token = raw.strip(" ,.:;!?()[]{}\"'").lower()
        if len(token) < 3 or token in DISCOVERY_STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _audit_query_hints(project):
    audit_run = getattr(project, "latest_audit_run", None)
    if not audit_run:
        return []
    hints = []
    for page in audit_run.pages.order_by("-word_count", "url")[:6]:
        for source in (page.title, page.h1, page.meta_description):
            if not source:
                continue
            words = [token for token in _tokenize_terms(source) if token not in hints]
            if words:
                hints.append(" ".join(words[:4]))
            if len(hints) >= 4:
                return hints
    return hints


def _profile_service_terms(profile):
    terms = []
    raw_terms = [
        profile.primary_service or "",
        profile.business_type.replace("_", " ") if getattr(profile, "business_type", "") else "",
    ]
    raw_terms.extend(INDUSTRY_DISCOVERY_TERMS.get(getattr(profile, "business_type", ""), [])[:4])
    raw_terms.extend(INDUSTRY_MUST_HAVE_TERMS.get(getattr(profile, "business_type", ""), [])[:5])

    for raw in raw_terms:
        value = " ".join(str(raw or "").replace("/", " ").replace("-", " ").split()).strip().lower()
        if len(value) < 3 or value in terms:
            continue
        terms.append(value)
    return terms


def _has_foreign_geo_conflict(haystack, location):
    location_tokens = _tokenize_terms(location)
    if any(token in haystack for token in location_tokens):
        return False
    return any(token in haystack for token in FOREIGN_GEO_HINTS)


def build_discovery_queries(profile, project=None):
    service = (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()
    location = (profile.location or "").strip()
    audience = (profile.target_audience or "").strip()
    goal = (profile.target_goal or "").strip().lower()
    industry_terms = INDUSTRY_DISCOVERY_TERMS.get(profile.business_type, [])
    templates = DISCOVERY_QUERY_TEMPLATES.get(profile.business_type, DISCOVERY_QUERY_TEMPLATES["default"])
    queries = [
        template.format(
            service=service,
            location=location,
            audience=audience or "buyers",
        ).strip()
        for template in templates
    ]
    if audience:
        queries.append(f"{service} for {audience} {location}".strip())
    if "lead" in goal or "inquiry" in goal or "book" in goal or "sales" in goal:
        queries.append(f"{service} {location} contact".strip())
    for term in industry_terms[:2]:
        queries.append(f"{term} {location}".strip())
    for hint in _audit_query_hints(project)[:2]:
        queries.append(f"{hint} {location}".strip())

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
        timeout=_provider_timeout("serpapi"),
    )
    response.raise_for_status()
    return response.json()


def fetch_duckduckgo_results(query, location=""):
    search_query = " ".join(part for part in [query, location] if part).strip()
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": search_query},
        timeout=_provider_timeout("duckduckgo"),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        },
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results = []
    for index, block in enumerate(soup.select(".result"), start=1):
        link_tag = block.select_one(".result__a")
        snippet_tag = block.select_one(".result__snippet")
        link = link_tag.get("href", "").strip() if link_tag else ""
        title = link_tag.get_text(" ", strip=True) if link_tag else ""
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        if not link:
            continue
        results.append(
            {
                "position": index,
                "title": title,
                "link": link,
                "snippet": snippet,
            }
        )
        if len(results) >= settings.SERP_DISCOVERY_RESULTS_PER_QUERY:
            break
    return {"organic_results": results, "local_results": []}


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
    if any(domain == blocked or domain.endswith(f".{blocked}") for blocked in NON_COMPETITOR_DOMAIN_HINTS):
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
            "relevance_scores": [],
            "match_signals": [],
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
        if item.get("relevance_score") is not None:
            entry["relevance_scores"].append(item["relevance_score"])
        for signal in item.get("match_signals", []):
            if signal not in entry["match_signals"]:
                entry["match_signals"].append(signal)

    discovered = []
    for domain, item in aggregated.items():
        appearances = len(item["positions"])
        average_position = round(sum(item["positions"]) / max(appearances, 1), 1)
        best_position = min(item["positions"]) if item["positions"] else 99
        average_relevance = round(
            sum(item["relevance_scores"]) / max(len(item["relevance_scores"]), 1),
            1,
        ) if item["relevance_scores"] else 0
        discovery_score = appearances * 20 + max(0, 15 - best_position) + average_relevance
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
                "average_relevance": average_relevance,
                "match_signals": item["match_signals"][:8],
            }
        )

    discovered = [
        item
        for item in discovered
        if (
            item["average_relevance"] >= 7
            or (
                item["query_count"] >= 2
                and item["average_relevance"] >= 5
                and any(
                    signal.startswith("service:")
                    or signal.startswith("industry:")
                    or signal.startswith("location:")
                    for signal in item["match_signals"]
                )
            )
        )
    ]
    discovered.sort(key=lambda item: (-item["discovery_score"], item["average_position"]))
    return discovered


def _should_disable_provider(exc):
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def fetch_search_results(query, location="", runtime_state=None):
    providers = _provider_order()
    errors = []
    attempted_provider = False
    for provider in providers:
        if _provider_is_cooled_down(provider):
            errors.append({"provider": provider, "message": _provider_cooldown_message(provider)})
            _disable_provider(runtime_state, provider)
            continue
        if _provider_is_disabled(runtime_state, provider):
            continue
        if provider == "serpapi":
            if not settings.SERPAPI_API_KEY:
                errors.append({"provider": provider, "message": "SERPAPI_API_KEY is not configured."})
                _disable_provider(runtime_state, provider)
                continue
            try:
                attempted_provider = True
                payload = fetch_serpapi_results(query, location=location)
                return {"provider": provider, "payload": payload, "errors": errors}
            except requests.RequestException as exc:
                errors.append({"provider": provider, "message": str(exc)})
                if _should_disable_provider(exc):
                    _mark_provider_cooldown(provider)
                    _disable_provider(runtime_state, provider)
                continue
        if provider == "duckduckgo":
            try:
                attempted_provider = True
                payload = fetch_duckduckgo_results(query, location=location)
                return {"provider": provider, "payload": payload, "errors": errors}
            except requests.RequestException as exc:
                errors.append({"provider": provider, "message": str(exc)})
                if _should_disable_provider(exc):
                    _mark_provider_cooldown(provider)
                    _disable_provider(runtime_state, provider)
                continue
    return {
        "provider": "",
        "payload": {},
        "errors": errors,
        "providers_exhausted": not attempted_provider or all(
            _provider_is_disabled(runtime_state, provider) or _provider_is_cooled_down(provider)
            for provider in providers
        ),
    }


def _relevance_signals(result, profile):
    result_dict = result if isinstance(result, dict) else {}
    haystack = " ".join(
        [
            result_dict.get("title", ""),
            result_dict.get("snippet", ""),
            result_dict.get("description", ""),
            _candidate_link(result),
        ]
    ).lower()
    signals = []
    score = 0
    for term in _profile_service_terms(profile)[:8]:
        if term in haystack:
            score += 4 if " " in term else 2
            signals.append(f"service:{term}")
    for token in _tokenize_terms(profile.location):
        if token in haystack:
            score += 3
            signals.append(f"location:{token}")
    for token in _tokenize_terms(profile.target_audience)[:2]:
        if token in haystack:
            score += 1
            signals.append(f"audience:{token}")
    for token in INDUSTRY_MUST_HAVE_TERMS.get(profile.business_type, [])[:4]:
        if token.lower() in haystack:
            score += 2
            signals.append(f"industry:{token.lower()}")
    if any(hint in haystack for hint in GENERIC_RESULT_HINTS):
        score -= 4
        signals.append("generic_noise")
    if any(hint in haystack for hint in NON_COMPETITOR_RESULT_HINTS):
        score -= 7
        signals.append("non_competitor_pattern")
    if _has_foreign_geo_conflict(haystack, profile.location):
        score -= 8
        signals.append("foreign_location_conflict")
    if profile.business_type in INDUSTRY_MUST_HAVE_TERMS and not any(
        hint in haystack for hint in INDUSTRY_MUST_HAVE_TERMS[profile.business_type]
    ):
        score -= 5
        signals.append("missing_industry_match")
    if (
        (not result_dict.get("title") and not result_dict.get("snippet") and not result_dict.get("description"))
        and any(signal.startswith("service:") or signal.startswith("industry:") for signal in signals)
    ):
        score += 3
        signals.append("sparse_result_url_match")
    return score, signals


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
    queries = build_discovery_queries(profile, project=project)
    raw_candidates = []
    errors = []
    runtime_state = {"disabled_providers": set()}

    for query in queries:
        search_response = fetch_search_results(query, location=profile.location, runtime_state=runtime_state)
        payload = search_response.get("payload") or {}
        if search_response.get("errors"):
            for item in search_response["errors"]:
                errors.append(
                    {
                        "query": query,
                        "provider": item.get("provider", ""),
                        "message": item.get("message", ""),
                    }
                )
        if not payload:
            if search_response.get("providers_exhausted"):
                break
            continue
        try:
            for result in _result_items(payload, "organic_results"):
                parsed = _parse_result(result, query=query, own_domain=own_domain)
                if parsed:
                    relevance_score, match_signals = _relevance_signals(result, profile)
                    parsed["relevance_score"] = relevance_score
                    parsed["match_signals"] = match_signals
                    raw_candidates.append(parsed)
            for result in _result_items(payload, "local_results"):
                parsed = _parse_result(result, query=query, own_domain=own_domain)
                if parsed:
                    relevance_score, match_signals = _relevance_signals(result, profile)
                    parsed["relevance_score"] = relevance_score
                    parsed["match_signals"] = match_signals
                    raw_candidates.append(parsed)
        except Exception as exc:
            errors.append({"query": query, "message": f"SERP parsing error: {exc}"})
            continue

    competitors = _aggregate_candidates(raw_candidates)
    return {
        "provider": ",".join(_provider_order()),
        "enabled": True,
        "queries": queries,
        "competitors": competitors,
        "errors": errors,
    }
