from collections import defaultdict
from urllib.parse import urlparse
import hashlib
import json

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
    "google.co.ke",
    "googleusercontent.com",
    "trivago.com",
    "kayak.com",
    "travelocity.com",
    "hotels.com",
    "agoda.com",
    "airbnb.com",
    "priceline.com",
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
    "trivago.com",
    "kayak.com",
    "travelocity.com",
    "hotels.com",
    "agoda.com",
    "airbnb.com",
    "priceline.com",
}

# FOREIGN_GEO_HINTS is intentionally removed.
# Geo-conflict detection is now dynamic via _parse_canonical_location() and
# _is_foreign_location() so it works correctly for ANY target location globally.

# Maps ISO country codes to their SerpApi gl parameter value
# and a representative language code for hl.
_COUNTRY_CODE_TO_GL = {
    # Africa
    "ke": ("ke", "en"),  # Kenya
    "ng": ("ng", "en"),  # Nigeria
    "gh": ("gh", "en"),  # Ghana
    "za": ("za", "en"),  # South Africa
    "tz": ("tz", "en"),  # Tanzania
    "ug": ("ug", "en"),  # Uganda
    "et": ("et", "en"),  # Ethiopia
    "eg": ("eg", "ar"),  # Egypt
    # Asia
    "in": ("in", "en"),  # India
    "pk": ("pk", "en"),  # Pakistan
    "bd": ("bd", "en"),  # Bangladesh
    "lk": ("lk", "en"),  # Sri Lanka
    "ph": ("ph", "en"),  # Philippines
    "sg": ("sg", "en"),  # Singapore
    "my": ("my", "en"),  # Malaysia
    "id": ("id", "id"),  # Indonesia
    "th": ("th", "th"),  # Thailand
    "vn": ("vn", "vi"),  # Vietnam
    "cn": ("cn", "zh-CN"),  # China
    "jp": ("jp", "ja"),  # Japan
    "kr": ("kr", "ko"),  # South Korea
    "ae": ("ae", "ar"),  # UAE
    "sa": ("sa", "ar"),  # Saudi Arabia
    # Europe
    "gb": ("gb", "en"),  # United Kingdom
    "ie": ("ie", "en"),  # Ireland
    "de": ("de", "de"),  # Germany
    "fr": ("fr", "fr"),  # France
    "es": ("es", "es"),  # Spain
    "it": ("it", "it"),  # Italy
    "nl": ("nl", "nl"),  # Netherlands
    "pt": ("pt", "pt"),  # Portugal
    "pl": ("pl", "pl"),  # Poland
    # Americas
    "us": ("us", "en"),  # United States
    "ca": ("ca", "en"),  # Canada
    "mx": ("mx", "es"),  # Mexico
    "br": ("br", "pt"),  # Brazil
    "ar": ("ar", "es"),  # Argentina
    "co": ("co", "es"),  # Colombia
    # Oceania
    "au": ("au", "en"),  # Australia
    "nz": ("nz", "en"),  # New Zealand
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

DISCOVERY_BUCKET_LABELS = {
    "benchmark_competitor": "Benchmark Competitor",
    "market_surface": "Market Surface",
    "citation_source": "Citation Source",
    "backlink_prospect": "Backlink Prospect",
    "discard": "Discard",
}

LOCAL_CITATION_HOST_HINTS = {
    "yellowpages.com",
    "mapquest.com",
    "yelp.com",
}

MARKET_SURFACE_HOST_HINTS = {
    "tripadvisor.com",
    "booking.com",
    "expedia.com",
    "trivago.com",
    "kayak.com",
    "travelocity.com",
    "hotels.com",
    "agoda.com",
    "airbnb.com",
    "priceline.com",
    "google.com",
    "google.co.ke",
    "googleusercontent.com",
}

DISCOVERY_SOURCE_FAMILY_LABELS = {
    "benchmark_competitors": "Benchmark Competitors",
    "market_surfaces": "Market Surfaces",
    "citation_sources": "Citation Sources",
    "backlink_prospects": "Backlink Prospects",
}

DISCOVERY_SOURCE_FAMILY_RULES = {
    "default": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "citation_sources", "target_bucket": "citation_source"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "local_service": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "citation_sources", "target_bucket": "citation_source"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "healthcare": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "citation_sources", "target_bucket": "citation_source"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "real_estate": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "citation_sources", "target_bucket": "citation_source"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "hotel": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "citation_sources", "target_bucket": "citation_source"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "ecommerce": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
    ],
    "saas": [
        {"key": "benchmark_competitors", "target_bucket": "benchmark_competitor"},
        {"key": "market_surfaces", "target_bucket": "market_surface"},
        {"key": "backlink_prospects", "target_bucket": "backlink_prospect"},
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
    return f"Intelligence provider ({provider}) is under heavy load. Resuming automated discovery in about {seconds // 60} minutes."


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


def _primary_service_tokens(profile):
    service = str(getattr(profile, "primary_service", "") or "")
    business_type = str(getattr(profile, "business_type", "") or "").replace("_", " ")
    business_tokens = set(_tokenize_terms(business_type))
    tokens = []
    for token in _tokenize_terms(service):
        if token in business_tokens:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:5]


def _is_hospitality_event_focus(profile):
    if getattr(profile, "business_type", "") != "hotel":
        return False
    service = str(getattr(profile, "primary_service", "") or "").lower()
    return any(token in service for token in ("event", "events", "garden", "venue", "wedding", "conference"))


def _has_foreign_geo_conflict(haystack, location):
    """Detect geo-conflict using dynamic location parsing instead of a hardcoded list."""
    location_parts = _parse_canonical_location(location)
    return _is_foreign_location(haystack, location_parts)


def _build_benchmark_queries(profile, project=None):
    service = (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()
    location = (profile.location or "").strip()
    audience = (profile.target_audience or "").strip()
    goal = (profile.target_goal or "").strip().lower()
    industry_terms = INDUSTRY_DISCOVERY_TERMS.get(profile.business_type, [])
    templates = DISCOVERY_QUERY_TEMPLATES.get(profile.business_type, DISCOVERY_QUERY_TEMPLATES["default"])
    
    # Extract city-only from canonical for tighter local queries
    loc_parts = _parse_canonical_location(location)
    city_only = loc_parts["city"] if loc_parts["city"] else location
    
    if _is_hospitality_event_focus(profile):
        templates = [
            "{service} {location}",
            "event venue {location}",
            "wedding venue {location}",
            "conference venue {location}",
            "{service} booking {location}",
            "{service} contact {location}",
        ]
    queries = [
        template.format(
            service=service,
            location=location,
            audience=audience or "buyers",
        ).strip()
        for template in templates
    ]
    # Add city-only variants for tighter local discovery
    if city_only and city_only.lower() != location.lower():
        queries.append(f"{service} in {city_only}".strip())
        queries.append(f"best {service} in {city_only}".strip())
    if audience:
        queries.append(f"{service} for {audience} {location}".strip())
    if "lead" in goal or "inquiry" in goal or "book" in goal or "sales" in goal:
        queries.append(f"{service} {location} contact".strip())
    for term in industry_terms[:2]:
        queries.append(f"{term} {location}".strip())
    for hint in _audit_query_hints(project)[:2]:
        queries.append(f"{hint} {location}".strip())
    return queries


def _family_query_templates(profile):
    service = (profile.primary_service or profile.business_type.replace("_", " ") or "service").strip()
    location = (profile.location or "").strip()
    benchmark_queries = _build_benchmark_queries(profile)
    families = {
        "benchmark_competitors": benchmark_queries,
        "citation_sources": [
            f"{service} {location} directory".strip(),
            f"{service} {location} reviews".strip(),
            f"{service} {location} listing".strip(),
        ],
        "market_surfaces": [
            f"best {service} {location}".strip(),
            f"{service} {location} reviews".strip(),
            f"{service} {location} comparison".strip(),
        ],
        "backlink_prospects": [
            f"{service} {location} guide".strip(),
            f"{service} {location} resources".strip(),
            f"{service} {location} association".strip(),
        ],
    }
    if profile.business_type == "ecommerce":
        families["market_surfaces"] = [
            f"{service} {location} shop".strip(),
            f"{service} {location} products".strip(),
            f"{service} {location} comparison".strip(),
        ]
    elif profile.business_type == "saas":
        families["market_surfaces"] = [
            f"{service} software reviews".strip(),
            f"{service} alternatives".strip(),
            f"{service} pricing comparison".strip(),
        ]
    elif profile.business_type == "hotel":
        families["market_surfaces"] = [
            f"{service} {location} reviews".strip(),
            f"{service} {location} booking".strip(),
            f"{service} {location} comparison".strip(),
        ]
        families["citation_sources"] = [
            f"{service} {location} reviews".strip(),
            f"{service} {location} listing".strip(),
            f"{service} {location} directions".strip(),
        ]
    return families


def _discovery_source_family_rules(profile):
    return DISCOVERY_SOURCE_FAMILY_RULES.get(getattr(profile, "business_type", ""), DISCOVERY_SOURCE_FAMILY_RULES["default"])


def build_discovery_routes(profile, project=None):
    families = _family_query_templates(profile)
    audit_hints = _audit_query_hints(project)
    routes = []
    for rule in _discovery_source_family_rules(profile):
        family_key = rule["key"]
        target_bucket = rule["target_bucket"]
        queries = list(families.get(family_key, []))
        if family_key == "benchmark_competitors":
            for hint in audit_hints[:2]:
                hint_query = f"{hint} {(profile.location or '').strip()}".strip()
                if hint_query and hint_query not in queries:
                    queries.append(hint_query)
        unique_queries = []
        for query in queries:
            query = " ".join(str(query or "").split())
            if query and query not in unique_queries:
                unique_queries.append(query)
        routes.append(
            {
                "family_key": family_key,
                "family_label": DISCOVERY_SOURCE_FAMILY_LABELS.get(
                    family_key,
                    family_key.replace("_", " ").title(),
                ),
                "target_bucket": target_bucket,
                "queries": unique_queries[: settings.SERP_DISCOVERY_QUERY_LIMIT],
            }
        )
    return routes


def build_discovery_queries(profile, project=None):
    for route in build_discovery_routes(profile, project=project):
        if route["family_key"] == "benchmark_competitors":
            return route["queries"]
    return []


def _parse_canonical_location(location_str):
    """Parse a Photon/canonical location string into usable parts.
    
    Input: "Nairobi, Nairobi County, Kenya" or "Austin, Texas, United States"
    Output: {city, region, country, country_code_lower}
    """
    if not location_str or location_str.strip().lower() == "worldwide":
        return {"city": "", "region": "", "country": "", "country_code": "", "tokens": []}
    
    parts = [p.strip() for p in location_str.split(",") if p.strip()]
    city = parts[0] if len(parts) > 0 else ""
    region = parts[1] if len(parts) > 1 else ""
    country = parts[-1] if len(parts) > 1 else ""
    
    # Build a token set for fast haystack matching (lowercase, 3+ chars)
    all_tokens = set()
    for part in parts:
        for word in part.replace("-", " ").split():
            token = word.strip(" ,.").lower()
            if len(token) >= 3:
                all_tokens.add(token)
    
    return {
        "city": city,
        "region": region,
        "country": country,
        "country_code": "",  # resolved separately via profile if available
        "tokens": list(all_tokens),
    }


def _infer_gl_hl(location_str, country_code=""):
    """Infer SerpApi gl (geo-location) and hl (language) from location string."""
    code = (country_code or "").strip().lower()
    if not code:
        # Derive from country name in canonical string
        loc = _parse_canonical_location(location_str)
        country_name = loc["country"].lower().strip()
        # Simple country-name to code mapping for most common cases
        _NAME_TO_CODE = {
            "kenya": "ke", "nigeria": "ng", "ghana": "gh", "south africa": "za",
            "tanzania": "tz", "uganda": "ug", "ethiopia": "et", "egypt": "eg",
            "india": "in", "pakistan": "pk", "bangladesh": "bd", "sri lanka": "lk",
            "philippines": "ph", "singapore": "sg", "malaysia": "my", "indonesia": "id",
            "thailand": "th", "vietnam": "vn", "china": "cn", "japan": "jp",
            "south korea": "kr", "united arab emirates": "ae", "uae": "ae",
            "saudi arabia": "sa", "united kingdom": "gb", "uk": "gb",
            "ireland": "ie", "germany": "de", "france": "fr", "spain": "es",
            "italy": "it", "netherlands": "nl", "portugal": "pt", "poland": "pl",
            "united states": "us", "usa": "us", "canada": "ca", "mexico": "mx",
            "brazil": "br", "argentina": "ar", "colombia": "co",
            "australia": "au", "new zealand": "nz",
        }
        code = _NAME_TO_CODE.get(country_name, "")
    gl, hl = _COUNTRY_CODE_TO_GL.get(code, ("", "en"))
    return gl, hl


def _is_foreign_location(haystack, location_parts):
    """Dynamic replacement for the old hardcoded FOREIGN_GEO_HINTS check.
    
    Returns True if the result haystack contains strong geo signals from a 
    DIFFERENT location than the target, indicating it's not locally relevant.
    """
    if not location_parts or not location_parts.get("tokens"):
        return False
    
    target_tokens = set(location_parts["tokens"])
    
    # If any of our own location tokens appear in the result, it's local — not foreign
    if any(token in haystack for token in target_tokens):
        return False
    
    # Check for clearly foreign geographic signals that wouldn't appear
    # in a locally relevant result. Only flag if we have enough context.
    # Common country/city tokens that signal a different geography.
    # We derive these dynamically from well-known global geo terms.
    STRONG_FOREIGN_SIGNALS = [
        # US-specific (would be foreign for non-US targets)
        "united states", "usa", " texas ", " california ", " florida ", " new york ",
        " chicago ", " houston ", " dallas ", " austin ", " miami ",
        # UK-specific
        "united kingdom", " london ", " manchester ", " birmingham ", " glasgow ",
        # Other major markets
        " toronto ", " sydney ", " melbourne ", " beijing ", " shanghai ",
        " tokyo ", " dubai ", " riyadh ", " singapore ", " mumbai ", " delhi ",
    ]
    
    # Only flag as foreign if the target is NOT in those regions
    target_country = (location_parts.get("country") or "").lower()
    for signal in STRONG_FOREIGN_SIGNALS:
        clean_signal = signal.strip()
        # Skip if signal overlaps with our target country
        if clean_signal in target_country or target_country in clean_signal:
            continue
        if clean_signal in haystack:
            return True
    
    return False


def _serpapi_params(query, location, country_code=""):
    """Build SerpApi params with geo-restriction via gl/hl."""
    params = {
        "engine": "google",
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
        "num": settings.SERP_DISCOVERY_RESULTS_PER_QUERY,
    }
    if location and location.strip().lower() != "worldwide":
        params["location"] = location
        gl, hl = _infer_gl_hl(location, country_code=country_code)
        if gl:
            params["gl"] = gl
        if hl:
            params["hl"] = hl
    return params


def fetch_serpapi_results(query, location="", country_code=""):
    params = _serpapi_params(query, location, country_code=country_code)
    
    # Generate a deterministic cache key (excluding the API tree/key safely)
    safe_params = {k: v for k, v in params.items() if k != "api_key"}
    param_hash = hashlib.md5(json.dumps(safe_params, sort_keys=True).encode("utf-8")).hexdigest()
    cache_key = f"seo:serpapi:discovery:{param_hash}"
    
    # Search cache before calling
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
        
    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=_provider_timeout("serpapi"),
    )
    response.raise_for_status()
    
    data = response.json()
    cache.set(cache_key, data, 604800)  # Cache duration: 7 days
    return data


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
    return False


def _matches_domain_hint(domain, hints):
    return any(domain == hint or domain.endswith(f".{hint}") for hint in hints)


def _classify_result_bucket(*, domain, haystack, profile):
    if not domain:
        return "discard", "no-domain"
    if _matches_domain_hint(domain, MARKET_SURFACE_HOST_HINTS):
        return "market_surface", "market-surface-host"
    if _matches_domain_hint(domain, LOCAL_CITATION_HOST_HINTS):
        return "citation_source", "citation-host"
    if _matches_domain_hint(domain, NON_COMPETITOR_DOMAIN_HINTS):
        if any(token in haystack for token in ("association", "resource", "guide", "news", "magazine", "journal")):
            return "backlink_prospect", "editorial-host"
        return "discard", "non-competitor-host"
    if any(hint in haystack for hint in ("directory", "directories", "listing", "listings", "profiles")):
        return "citation_source", "directory-surface"
    if any(hint in haystack for hint in ("review", "reviews", "compare", "comparison", "prices", "deals")):
        return "market_surface", "comparison-surface"
    if any(hint in haystack for hint in ("blog", "guide", "resource", "news", "magazine", "journal", "association")):
        return "backlink_prospect", "editorial-surface"
    if any(hint in haystack for hint in ("lead finder", "lead generation", "classifieds", "document", "pdf")):
        return "discard", "noise-surface"
    return "benchmark_competitor", "peer-site"


def _result_haystack(result, query=""):
    result_dict = result if isinstance(result, dict) else {}
    extra_bits = []
    for key in ("type", "category", "address", "phone", "website", "place_id"):
        value = result_dict.get(key)
        if value:
            extra_bits.append(str(value))
    for key in ("types", "extensions"):
        values = result_dict.get(key)
        if isinstance(values, list):
            extra_bits.extend(str(value) for value in values if value)
    return " ".join(
        [
            str(result_dict.get("title", "") or ""),
            str(result_dict.get("snippet", "") or result_dict.get("description", "") or ""),
            str(_candidate_link(result) or ""),
            str(query or ""),
            *extra_bits,
        ]
    ).replace("/", " ").replace("-", " ").replace("_", " ").lower()


def _domain_root_url(link):
    parsed = urlparse(link)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return normalize_url(f"{parsed.scheme}://{parsed.netloc}/")


def _parse_result(
    result,
    *,
    query,
    own_domain,
    source_family="",
    target_bucket="benchmark_competitor",
    result_kind="organic",
):
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
    result_dict = result if isinstance(result, dict) else {}
    haystack = _result_haystack(result, query=query if result_kind == "local" else "")
    bucket, bucket_reason = _classify_result_bucket(domain=domain, haystack=haystack, profile=None)
    if bucket == "benchmark_competitor" and target_bucket != "benchmark_competitor":
        bucket = target_bucket
        bucket_reason = f"{source_family or target_bucket}-route"
    return {
        "homepage_url": _domain_root_url(link) or normalize_url(link),
        "normalized_domain": domain,
        "position": position,
        "title": (result_dict.get("title") or "").strip(),
        "snippet": (result_dict.get("snippet") or result_dict.get("description") or "").strip(),
        "query": query,
        "result_url": link,
        "bucket": bucket,
        "bucket_reason": bucket_reason,
        "source_family": source_family or "benchmark_competitors",
        "result_kind": result_kind,
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
            "bucket": "benchmark_competitor",
            "bucket_reason": "",
            "source_families": [],
            "positions": [],
            "queries": [],
            "titles": [],
            "snippets": [],
            "result_urls": [],
            "relevance_scores": [],
            "match_signals": [],
            "result_kinds": [],
        }
    )
    for item in raw_candidates:
        entry = aggregated[(item["normalized_domain"], item.get("bucket", "benchmark_competitor"))]
        entry["homepage_url"] = item["homepage_url"]
        entry["normalized_domain"] = item["normalized_domain"]
        entry["bucket"] = item.get("bucket", "benchmark_competitor")
        entry["bucket_reason"] = item.get("bucket_reason", "")
        if item.get("source_family") and item["source_family"] not in entry["source_families"]:
            entry["source_families"].append(item["source_family"])
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
        if item.get("result_kind") and item["result_kind"] not in entry["result_kinds"]:
            entry["result_kinds"].append(item["result_kind"])
        for signal in item.get("match_signals", []):
            if signal not in entry["match_signals"]:
                entry["match_signals"].append(signal)

    discovered = []
    bucketed_items = defaultdict(list)
    for (_domain, _bucket), item in aggregated.items():
        appearances = len(item["positions"])
        average_position = round(sum(item["positions"]) / max(appearances, 1), 1)
        best_position = min(item["positions"]) if item["positions"] else 99
        average_relevance = round(
            sum(item["relevance_scores"]) / max(len(item["relevance_scores"]), 1),
            1,
        ) if item["relevance_scores"] else 0
        discovery_score = appearances * 20 + max(0, 15 - best_position) + average_relevance
        bucketed_items[item["bucket"]].append(
            {
                "homepage_url": item["homepage_url"],
                "normalized_domain": item["normalized_domain"],
                "label": item["normalized_domain"],
                "bucket": item["bucket"],
                "bucket_label": DISCOVERY_BUCKET_LABELS.get(item["bucket"], item["bucket"].replace("_", " ").title()),
                "bucket_reason": item["bucket_reason"],
                "source_families": item["source_families"][:4],
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
                "result_kinds": item["result_kinds"][:2],
            }
        )

    discovered = [
        item
        for item in bucketed_items["benchmark_competitor"]
        if (
            (
                item["average_relevance"] >= 7
                and "non_competitor_host" not in item["match_signals"]
                and "missing_primary_service_alignment" not in item["match_signals"]
            )
            or (
                item["query_count"] >= 2
                and item["average_relevance"] >= 5
                and "non_competitor_host" not in item["match_signals"]
                and "missing_primary_service_alignment" not in item["match_signals"]
                and any(
                    signal.startswith("service:")
                    or signal.startswith("industry:")
                    or signal.startswith("primary_service:")
                    or signal.startswith("location:")
                    for signal in item["match_signals"]
                )
            )
            or (
                "local" in item["result_kinds"]
                and item["average_relevance"] >= 3
                and "non_competitor_host" not in item["match_signals"]
                and "foreign_location_conflict" not in item["match_signals"]
                and any(
                    signal == "local_pack_presence"
                    or signal == "local_query_alignment"
                    or signal.startswith("service:")
                    or signal.startswith("industry:")
                    or signal.startswith("primary_service:")
                    for signal in item["match_signals"]
                )
            )
        )
    ]
    discovered.sort(key=lambda item: (-item["discovery_score"], item["average_position"]))
    for bucket_name in ("market_surface", "citation_source", "backlink_prospect"):
        bucketed_items[bucket_name].sort(key=lambda item: (-item["discovery_score"], item["average_position"]))
    return {
        "competitors": discovered,
        "market_surfaces": bucketed_items["market_surface"][:8],
        "citation_sources": bucketed_items["citation_source"][:8],
        "backlink_prospects": bucketed_items["backlink_prospect"][:8],
    }


def _should_disable_provider(exc):
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def _clean_error_message(exc, provider):
    if isinstance(exc, requests.Timeout):
        return f"The {provider} lookup timed out. This usually happens during peak global search traffic; system will retry automatically."
    if isinstance(exc, requests.ConnectionError):
        return f"Could not connect to {provider} intelligence feed. Please check your network or wait a few minutes."
    msg = str(exc)
    if "Max retries exceeded" in msg or "ConnectTimeoutError" in msg:
        return f"Connection to {provider} was interrupted or timed out. System is cooling down for a moment."
    return msg

def fetch_search_results(query, location="", runtime_state=None, country_code=""):
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
                errors.append({"provider": provider, "message": "Global search discovery is not configured (missing API key)."})
                _disable_provider(runtime_state, provider)
                continue
            try:
                attempted_provider = True
                payload = fetch_serpapi_results(query, location=location, country_code=country_code)
                return {"provider": provider, "payload": payload, "errors": errors}
            except requests.RequestException as exc:
                errors.append({"provider": provider, "message": _clean_error_message(exc, provider)})
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
                errors.append({"provider": provider, "message": _clean_error_message(exc, provider)})
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


def _relevance_signals(result, profile, *, query="", result_kind="organic"):
    result_dict = result if isinstance(result, dict) else {}
    haystack = _result_haystack(result, query=query if result_kind == "local" else "")
    signals = []
    score = 0
    local_pack = result_kind == "local"
    
    # Parse the canonical location for granular scoring
    loc_parts = _parse_canonical_location(getattr(profile, "location", "") or "")
    
    for term in _profile_service_terms(profile)[:8]:
        if term in haystack:
            score += 4 if " " in term else 2
            signals.append(f"service:{term}")
    
    # Granular location scoring: city match is highest signal
    city_token = loc_parts["city"].lower().strip() if loc_parts["city"] else ""
    country_token = loc_parts["country"].lower().strip() if loc_parts["country"] else ""
    region_token = loc_parts["region"].lower().strip() if loc_parts["region"] else ""
    
    if city_token and city_token in haystack:
        score += 6  # City-level match is the strongest local signal
        signals.append(f"location:city:{city_token}")
    elif region_token and region_token in haystack:
        score += 3  # Region/county match is a good secondary signal
        signals.append(f"location:region:{region_token}")
    
    if country_token and country_token in haystack:
        score += 2
        signals.append(f"location:country:{country_token}")
    
    # Also score individual tokenized terms from the full location string
    for token in _tokenize_terms(profile.location):
        if token in (city_token, region_token, country_token):
            continue  # Already scored above
        if token in haystack:
            score += 1
            signals.append(f"location:{token}")
    
    for token in _tokenize_terms(getattr(profile, "target_audience", "") or "")[:2]:
        if token in haystack:
            score += 1
            signals.append(f"audience:{token}")
    for token in INDUSTRY_MUST_HAVE_TERMS.get(getattr(profile, "business_type", ""), [])[:4]:
        if token.lower() in haystack:
            score += 2
            signals.append(f"industry:{token.lower()}")
    primary_matches = 0
    for token in _primary_service_tokens(profile):
        if token in haystack:
            primary_matches += 1
            score += 4
            signals.append(f"primary_service:{token}")
    if local_pack:
        score += 3
        signals.append("local_pack_presence")
        if any(token in haystack for token in _tokenize_terms(query)):
            score += 2
            signals.append("local_query_alignment")
    if any(hint in haystack for hint in GENERIC_RESULT_HINTS):
        score -= 4
        signals.append("generic_noise")
    if any(hint in haystack for hint in NON_COMPETITOR_RESULT_HINTS):
        score -= 7
        signals.append("non_competitor_pattern")
    if any(hint in haystack for hint in NON_COMPETITOR_DOMAIN_HINTS):
        score -= 8
        signals.append("non_competitor_host")
    # Dynamic foreign geo-conflict using parsed location parts
    if _is_foreign_location(haystack, loc_parts):
        score -= 10  # Stronger penalty than before (-8)
        signals.append("foreign_location_conflict")
    if getattr(profile, "business_type", "") in INDUSTRY_MUST_HAVE_TERMS and not any(
        hint in haystack for hint in INDUSTRY_MUST_HAVE_TERMS[profile.business_type]
    ):
        score -= 2 if local_pack else 5
        signals.append("missing_industry_match")
    if _primary_service_tokens(profile) and primary_matches == 0:
        score -= 2 if local_pack else 5
        signals.append("missing_primary_service_alignment")
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
    routes = build_discovery_routes(profile, project=project)
    queries = []
    raw_candidates = []
    errors = []
    runtime_state = {"disabled_providers": set(), "providers_exhausted": False}
    seen_error_keys = set()

    # Infer country code from canonical location for geo-restricted SerpApi queries
    location_str = getattr(profile, "location", "") or ""
    _gl, _hl = _infer_gl_hl(location_str)
    inferred_country_code = _gl  # e.g. "ke" for Kenya, "ng" for Nigeria

    for route in routes:
        if runtime_state.get("providers_exhausted"):
            break
        for query in route["queries"]:
            if query not in queries:
                queries.append(query)
            search_response = fetch_search_results(
                query,
                location=profile.location,
                runtime_state=runtime_state,
                country_code=inferred_country_code,
            )
            payload = search_response.get("payload") or {}
            if search_response.get("errors"):
                for item in search_response["errors"]:
                    error_key = (route["family_key"], item.get("provider", ""), item.get("message", ""))
                    if error_key not in seen_error_keys:
                        seen_error_keys.add(error_key)
                        errors.append(
                            {
                                "query": query,
                                "route_family": route["family_key"],
                                "provider": item.get("provider", ""),
                                "message": item.get("message", ""),
                            }
                        )
            if not payload:
                if search_response.get("providers_exhausted"):
                    runtime_state["providers_exhausted"] = True
                    break
                continue
            try:
                for result in _result_items(payload, "organic_results"):
                    parsed = _parse_result(
                        result,
                        query=query,
                        own_domain=own_domain,
                        source_family=route["family_key"],
                        target_bucket=route["target_bucket"],
                        result_kind="organic",
                    )
                    if parsed:
                        relevance_score, match_signals = _relevance_signals(
                            result,
                            profile,
                            query=query,
                            result_kind="organic",
                        )
                        parsed["relevance_score"] = relevance_score
                        parsed["match_signals"] = match_signals
                        raw_candidates.append(parsed)
                for result in _result_items(payload, "local_results"):
                    parsed = _parse_result(
                        result,
                        query=query,
                        own_domain=own_domain,
                        source_family=route["family_key"],
                        target_bucket=route["target_bucket"],
                        result_kind="local",
                    )
                    if parsed:
                        relevance_score, match_signals = _relevance_signals(
                            result,
                            profile,
                            query=query,
                            result_kind="local",
                        )
                        parsed["relevance_score"] = relevance_score
                        parsed["match_signals"] = match_signals
                        raw_candidates.append(parsed)
            except Exception as exc:
                errors.append(
                    {
                        "query": query,
                        "route_family": route["family_key"],
                        "message": f"SERP parsing error: {exc}",
                    }
                )
                continue

    # ── Vertical source queries (google_local, google_hotels, etc.) ──────────
    # Skip if serpapi is on cooldown (rate-limited) or all providers are exhausted,
    # since vertical queries also require a working SerpAPI key.
    _serpapi_available = (
        settings.SERPAPI_API_KEY
        and not _provider_is_cooled_down("serpapi")
        and not runtime_state.get("providers_exhausted")
        and "serpapi" not in runtime_state.get("disabled_providers", set())
    )
    if _serpapi_available:
        vertical_candidates, vertical_errors = _run_vertical_source_queries(
            profile,
            own_domain=own_domain,
            location=getattr(profile, "location", "") or "",
            country_code=inferred_country_code,
        )
        raw_candidates.extend(vertical_candidates)
        errors.extend(vertical_errors)

    aggregated = _aggregate_candidates(raw_candidates)
    competitors = aggregated.get("competitors", [])
    return {
        "provider": ",".join(_provider_order()),
        "enabled": True,
        "queries": queries,
        "competitors": competitors,
        "market_surfaces": aggregated.get("market_surfaces", []),
        "citation_sources": aggregated.get("citation_sources", []),
        "backlink_prospects": aggregated.get("backlink_prospects", []),
        "routing_policy": {
            "business_type": getattr(profile, "business_type", ""),
            "primary_service": getattr(profile, "primary_service", ""),
            "event_focused_hospitality": _is_hospitality_event_focus(profile),
            "source_families": [route["family_key"] for route in routes],
            "routes": routes,
        },
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Vertical source integration — provider-level routing per business type
# ---------------------------------------------------------------------------

# Maps each business type to the vertical SerpAPI engines that add real signal.
# These supplement the generic "google" engine rather than replacing it.
VERTICAL_SOURCE_ENGINES = {
    "local_service": [
        {"engine": "google_local", "target_bucket": "benchmark_competitor", "result_key": "local_results"},
        {"engine": "google_local_services", "target_bucket": "benchmark_competitor", "result_key": "ads"},
    ],
    "healthcare": [
        {"engine": "google_local", "target_bucket": "benchmark_competitor", "result_key": "local_results"},
        {"engine": "google_local_services", "target_bucket": "benchmark_competitor", "result_key": "ads"},
    ],
    "real_estate": [
        {"engine": "google_local", "target_bucket": "benchmark_competitor", "result_key": "local_results"},
    ],
    "automotive": [
        {"engine": "google_local", "target_bucket": "benchmark_competitor", "result_key": "local_results"},
    ],
    "hotel": [
        {"engine": "google_local", "target_bucket": "market_surface", "result_key": "local_results"},
        {"engine": "google_hotels", "target_bucket": "market_surface", "result_key": "properties"},
        {"engine": "google_events", "target_bucket": "citation_source", "result_key": "events_results"},
    ],
    "restaurant": [
        {"engine": "google_local", "target_bucket": "benchmark_competitor", "result_key": "local_results"},
    ],
    "ecommerce": [
        {"engine": "google_local", "target_bucket": "citation_source", "result_key": "local_results"},
    ],
}

# Query templates for vertical engines — simpler than benchmark queries.
# The engine itself handles location filtering.
_VERTICAL_QUERY_TEMPLATES = {
    "google_local": "{service} {location}",
    "google_local_services": "{service} near {location}",
    "google_hotels": "hotels {location}",
    "google_events": "events {location}",
}


def _serpapi_vertical_params(engine, query, location="", country_code=""):
    """Build SerpApi params for non-google vertical engines."""
    params = {
        "engine": engine,
        "api_key": settings.SERPAPI_API_KEY,
    }
    # google_local uses "q"; google_hotels/events use slightly different param names
    if engine in ("google_local", "google_local_services"):
        params["q"] = query
        if location and location.strip().lower() != "worldwide":
            params["location"] = location
        gl, hl = _infer_gl_hl(location, country_code=country_code)
        if gl:
            params["gl"] = gl
        if hl:
            params["hl"] = hl
    elif engine == "google_hotels":
        params["q"] = query
        if location and location.strip().lower() != "worldwide":
            params["location"] = location
        gl, hl = _infer_gl_hl(location, country_code=country_code)
        if gl:
            params["gl"] = gl
        if hl:
            params["hl"] = hl
        params["check_in_date"] = "2026-06-01"
        params["check_out_date"] = "2026-06-02"
    elif engine == "google_events":
        params["q"] = query
        if location and location.strip().lower() != "worldwide":
            params["location"] = location
        gl, hl = _infer_gl_hl(location, country_code=country_code)
        if gl:
            params["gl"] = gl
    return params


def fetch_vertical_serpapi_results(engine, query, location="", country_code=""):
    """
    Call a SerpAPI vertical engine and return the raw JSON payload.
    Uses a separate 7-day cache key so vertical results don't evict organic results.
    """
    params = _serpapi_vertical_params(engine, query, location=location, country_code=country_code)
    safe_params = {k: v for k, v in params.items() if k != "api_key"}
    param_hash = hashlib.md5(json.dumps(safe_params, sort_keys=True).encode("utf-8")).hexdigest()
    cache_key = f"seo:serpapi:vertical:{engine}:{param_hash}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=_provider_timeout("serpapi"),
    )
    response.raise_for_status()
    data = response.json()
    cache.set(cache_key, data, 604800)  # 7-day cache
    return data


def _parse_vertical_result(result, engine, *, query, own_domain, target_bucket, source_family="vertical"):
    """
    Extract a normalised candidate dict from a vertical engine result item.
    Each engine returns different structures; we normalise to the same shape
    used by _parse_result() so _aggregate_candidates() can process them uniformly.
    """
    if not isinstance(result, dict):
        return None

    # Extract the website URL — field name varies by engine
    link = (
        result.get("website")
        or result.get("link")
        or result.get("url")
        or result.get("thumbnail")  # fallback, will likely be filtered
        or ""
    ).strip()

    if not link or not link.startswith("http"):
        # For google_local results that have no website, skip them
        return None

    domain = extract_domain(link)
    if _is_blocked_domain(domain, own_domain):
        return None

    title = (result.get("title") or result.get("name") or "").strip()
    snippet = (
        result.get("snippet")
        or result.get("description")
        or result.get("type")
        or ""
    ).strip()

    # Determine bucket: vertical local results = competitor candidates for peer business types
    # market-surface engines (hotels, events) stay as market_surface
    bucket = target_bucket
    if engine in ("google_local", "google_local_services"):
        # Trust the caller's target_bucket (set by VERTICAL_SOURCE_ENGINES mapping)
        pass

    return {
        "homepage_url": _domain_root_url(link) or normalize_url(link),
        "normalized_domain": domain,
        "position": result.get("position", 99),
        "title": title,
        "snippet": snippet,
        "query": query,
        "result_url": link,
        "bucket": bucket,
        "bucket_reason": f"{engine}-vertical",
        "source_family": source_family,
        "result_kind": "local" if engine in ("google_local", "google_local_services") else "vertical",
        "vertical_engine": engine,
        # Preserve local-specific enrichment signals when present
        "local_metadata": {
            k: result.get(k)
            for k in ("rating", "reviews", "address", "hours", "type", "phone", "place_id")
            if result.get(k) is not None
        },
    }


def _run_vertical_source_queries(profile, *, own_domain, location, country_code):
    """
    Execute vertical-engine queries for the current business type.
    Returns (candidates_list, errors_list).
    Gracefully skips if no vertical engines are configured for this business type
    or if SerpAPI is unavailable/rate-limited.
    """
    business_type = getattr(profile, "business_type", "") or "default"
    engine_configs = VERTICAL_SOURCE_ENGINES.get(business_type, [])
    if not engine_configs:
        return [], []

    service = (getattr(profile, "primary_service", "") or business_type.replace("_", " ")).strip()
    location_label = location.strip() if location and location.strip().lower() != "worldwide" else ""

    candidates = []
    errors = []
    seen_domains = set()

    for config in engine_configs:
        engine = config["engine"]
        target_bucket = config["target_bucket"]
        result_key = config["result_key"]

        # Build the query string for this engine
        template = _VERTICAL_QUERY_TEMPLATES.get(engine, "{service} {location}")
        query = template.format(service=service, location=location_label).strip()

        try:
            payload = fetch_vertical_serpapi_results(
                engine,
                query,
                location=location_label,
                country_code=country_code,
            )
        except Exception as exc:
            # Only surface rate-limit and timeout errors as actionable errors;
            # auth errors (403) and other HTTP failures are silently skipped so
            # they don't pollute the error list when the API key is misconfigured.
            if _should_disable_provider(exc):
                errors.append({
                    "query": query,
                    "route_family": "vertical",
                    "provider": f"serpapi:{engine}",
                    "message": f"Vertical source ({engine}) error: {_clean_error_message(exc, 'serpapi')}",
                })
            continue

        raw_items = payload.get(result_key) or []
        if isinstance(raw_items, dict):
            # Some engines nest results differently
            raw_items = list(raw_items.values())

        for item in raw_items[:12]:
            parsed = _parse_vertical_result(
                item,
                engine,
                query=query,
                own_domain=own_domain,
                target_bucket=target_bucket,
                source_family="vertical",
            )
            if not parsed:
                continue
            domain = parsed["normalized_domain"]
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            candidates.append(parsed)

    return candidates, errors


# ---------------------------------------------------------------------------
# Competitor snapshot freshness — cache and reuse rules
# ---------------------------------------------------------------------------

COMPETITOR_SNAPSHOT_REUSE_DAYS = int(getattr(settings, "COMPETITOR_SNAPSHOT_REUSE_DAYS", 3))


def competitor_snapshot_is_fresh(snapshot, *, days=None):
    """
    Return True if a SEOCompetitorSnapshot is fresh enough to reuse without re-fetching.
    A snapshot is considered fresh when it was created within the reuse window and
    its output_json contains actual crawl data (non-empty).
    """
    if snapshot is None:
        return False
    if not snapshot.output_json:
        return False
    reuse_days = days if days is not None else COMPETITOR_SNAPSHOT_REUSE_DAYS
    from django.utils import timezone as _tz
    cutoff = _tz.now() - __import__("datetime").timedelta(days=reuse_days)
    return snapshot.created_at >= cutoff
