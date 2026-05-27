import concurrent.futures
import os
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests
import urllib3
from bs4 import BeautifulSoup
from django.utils import timezone
from requests.exceptions import SSLError

from .models import AuditIssue, AuditPage, AuditRun
from .recommendations import build_audit_summary
from .scoring import apply_audit_scores

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


REQUEST_TIMEOUT = 10
PAGE_LIMIT = 10
PAGESPEED_TIMEOUT = 60
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def get_pagespeed_api_key():
    for env_name in ("webspeed", "WEBSPEED", "PAGESPEED_API_KEY"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return ""


class ParsedPage:
    def __init__(self, url, status_code, response_time_ms, html, headers=None):
        self.url = url
        self.status_code = status_code
        self.response_time_ms = response_time_ms
        self.html = html
        self.headers = headers or {}
        self.soup = BeautifulSoup(html, "lxml") if html else BeautifulSoup("", "lxml")

        self.title = self._title()
        self.meta_description = self._meta("description")
        self.meta_robots = self._meta("robots")
        self.viewport = self._meta("viewport")
        self.og_title = self._meta(property_name="og:title")
        self.og_description = self._meta(property_name="og:description")
        self.canonical_url = self._canonical()
        self.html_lang = self.soup.html.get("lang", "").strip() if self.soup.html else ""
        self.h1s = [element.get_text(" ", strip=True) for element in self.soup.find_all("h1")]
        self.links = [anchor.get("href", "").strip() for anchor in self.soup.find_all("a", href=True)]
        self.images_missing_alt = len([img for img in self.soup.find_all("img") if not img.get("alt")])
        self.schema_blocks = self._schema_blocks()
        self.word_count = self._word_count()

    def _title(self):
        return self.soup.title.get_text(" ", strip=True) if self.soup.title else ""

    def _meta(self, name=None, property_name=None):
        if name:
            tag = self.soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
        else:
            tag = self.soup.find("meta", attrs={"property": re.compile(f"^{re.escape(property_name)}$", re.I)})
        return tag.get("content", "").strip() if tag else ""

    def _canonical(self):
        tag = self.soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
        return tag.get("href", "").strip() if tag else ""

    def _schema_blocks(self):
        blocks = []
        for tag in self.soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = tag.get_text(strip=True)
            if text:
                blocks.append(text)
        return blocks

    def _word_count(self):
        text = self.soup.get_text(" ", strip=True)
        return len(re.findall(r"\b[\w'-]+\b", text))

    @property
    def h1(self):
        return self.h1s[0] if self.h1s else ""

    @property
    def schema_count(self):
        return len(self.schema_blocks)

    @property
    def has_faq_schema(self):
        return any("faqpage" in block.lower() for block in self.schema_blocks)

    @property
    def has_noindex(self):
        return "noindex" in self.meta_robots.lower()


def normalize_url(value):
    value = (value or "").strip()
    if not value or value.startswith(("#", "mailto:", "tel:", "javascript:")):
        return ""
    if value.startswith("//"):
        value = f"https:{value}"

    parsed = urlparse(value)
    if not parsed.scheme:
        value = f"https://{value}"
        parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    path = parsed.path or "/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def extract_domain(url):
    return urlparse(url).netloc.lower()


def fetch_url(url, session=None, timeout=REQUEST_TIMEOUT, user_agent=None):
    session = session or requests.Session()
    ua = user_agent or "VRTSPACEAuditBot/1.0 (+https://vrtspace.agency)"
    started = time.perf_counter()
    response = session.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
        allow_redirects=True,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "final_url": response.url,
        "status_code": response.status_code,
        "body": response.text,
        "headers": dict(response.headers),
        "content_type": response.headers.get("Content-Type", ""),
        "response_time_ms": elapsed_ms,
    }


def safe_fetch(url, session=None, timeout=REQUEST_TIMEOUT):
    # Try with Bot UA first
    try:
        res = fetch_url(url, session=session, timeout=timeout)
        if res["status_code"] < 400:
            return res
        # If rejected (403, 401, 406), try with Browser UA fallback
        if res["status_code"] in {403, 401, 406}:
            browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            return fetch_url(url, session=session, timeout=timeout, user_agent=browser_ua)
        return res
    except SSLError:
        try:
            session = session or requests.Session()
            browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            response = session.get(
                url,
                timeout=timeout,
                headers={"User-Agent": browser_ua},
                allow_redirects=True,
                verify=False,
            )
            return {
                "final_url": response.url,
                "status_code": response.status_code,
                "body": response.text,
                "headers": dict(response.headers),
                "content_type": response.headers.get("Content-Type", ""),
                "response_time_ms": 0,
            }
        except requests.RequestException:
            return None
    except requests.RequestException as e:
        # Log or return basic error info
        return {"status_code": 999, "error": str(e), "content_type": ""}


def detect_tech_stack(parsed_page):
    stack = {"cms": None, "framework": None, "analytics": [], "marketing": []}
    html = parsed_page.html.lower()
    h_str = str(parsed_page.headers).lower()

    # CMS Detection (WordPress)
    if any(x in html for x in ["wp-content", "wp-includes", "wp-json", "wordpress"]) or "wp-json" in h_str:
        stack["cms"] = "WordPress"
    elif "shopify" in html or "cdn.shopify.com" in html:
        stack["cms"] = "Shopify"
    elif "webflow" in html:
        stack["cms"] = "Webflow"
    elif "squarespace" in html:
        stack["cms"] = "Squarespace"
    elif "wix" in html:
        stack["cms"] = "Wix"
    
    # Check for Meta Generator
    generator = parsed_page._meta("generator").lower()
    if "wordpress" in generator:
        stack["cms"] = "WordPress"
    elif "elementor" in generator:
        stack["framework"] = "Elementor"

    # Frameworks
    if "next/static" in html or "__next" in html:
        stack["framework"] = "Next.js"
    elif "react-dom" in html or "react" in html:
        stack["framework"] = "React"
    elif "vue" in html:
        stack["framework"] = "Vue"
    elif "svelte" in html:
        stack["framework"] = "Svelte"

    # Analytics & Marketing
    if "googletagmanager.com/gtm.js" in html or "gtag" in html:
        stack["analytics"].append("Google Tag Manager")
    if "google-analytics.com/analytics.js" in html or "ga4" in html:
        stack["analytics"].append("Google Analytics")
    if "facebook.net/en_us/fbevents.js" in html or "fbq" in html:
        stack["marketing"].append("Meta Pixel")
    if "hotjar.com" in html:
        stack["analytics"].append("Hotjar")

    return stack


def analyze_assets(parsed_page):
    assets = {"scripts": 0, "styles": 0, "images": 0, "webp_count": 0}
    assets["scripts"] = len(parsed_page.soup.find_all("script", src=True))
    assets["styles"] = len(parsed_page.soup.find_all("link", rel="stylesheet"))
    images = parsed_page.soup.find_all("img")
    assets["images"] = len(images)
    assets["webp_count"] = len([img for img in images if img.get("src", "").endswith(".webp")])
    return assets


def calculate_readability(text):
    if not text:
        return 0
    # Simple Flesch-Kincaid implementation
    sentences = len(re.split(r"[.!?]+", text)) or 1
    words = len(re.findall(r"\b\w+\b", text)) or 1
    # Very rough syllable estimate (vowel clusters)
    syllables = len(re.findall(r"[aeiouy]+", text.lower())) or 1

    # Formula: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
    score = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
    return max(0, min(100, round(score)))


def check_security_headers(headers):
    sec = {}
    sec["hsts"] = "strict-transport-security" in headers
    sec["csp"] = "content-security-policy" in headers
    sec["x_frame"] = "x-frame-options" in headers
    sec["x_content_type"] = "x-content-type-options" in headers
    return sec


def create_or_update_page_record(audit_run, parsed, raw_response):
    page = AuditPage.objects.create(
        audit_run=audit_run,
        url=parsed.url,
        status_code=parsed.status_code,
        title=parsed.title[:255],
        meta_description=parsed.meta_description,
        h1=parsed.h1[:255],
        canonical_url=parsed.canonical_url[:200] if parsed.canonical_url else "",
        robots=parsed.meta_robots[:255],
        word_count=parsed.word_count,
        internal_link_count=internal_link_total(parsed.url, parsed.links),
        images_missing_alt=parsed.images_missing_alt,
        schema_count=parsed.schema_count,
        has_faq_schema=parsed.has_faq_schema,
        response_time_ms=parsed.response_time_ms,
        tech_stack=detect_tech_stack(parsed),
        asset_stats=analyze_assets(parsed),
        readability_score=calculate_readability(parsed.soup.get_text(" ", strip=True)),
        security_headers=check_security_headers(raw_response.get("headers", {})),
    )
    return page


def fetch_pagespeed_insights(url, strategy="mobile"):
    # Using a list for 'category' ensures requests sends &category=performance&category=accessibility etc.
    categories = ["performance", "accessibility", "best-practices", "seo"]
    params = [
        ("url", url),
        ("strategy", strategy),
    ]
    for cat in categories:
        params.append(("category", cat))
    api_key = get_pagespeed_api_key()
    if api_key:
        params.append(("key", api_key))

    try:
        response = requests.get(PAGESPEED_API_URL, params=params, timeout=PAGESPEED_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    lighthouse = payload.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})

    def get_score(cat_key):
        cat = categories.get(cat_key)
        if cat is None:
            return None # Indicate category missing
        score = cat.get("score")
        return max(0, min(100, round(float(score) * 100))) if score is not None else 0

    audits = lighthouse.get("audits", {})
    failed_audits = []
    
    # Extract failed audits (score < 1)
    for audit_id, audit_data in audits.items():
        score = audit_data.get("score")
        if score is not None and score < 1:
            failed_audits.append({
                "id": audit_id,
                "title": audit_data.get("title"),
                "description": audit_data.get("description"),
                "displayValue": audit_data.get("displayValue"),
            })

    def metric_value(metric_key):
        value = audits.get(metric_key, {}).get("displayValue", "")
        return value.strip() if isinstance(value, str) else ""

    result = {
        "source": "Google PageSpeed Insights",
        "strategy": strategy,
        "performance_score": get_score("performance"),
        "accessibility_score": get_score("accessibility"),
        "best_practices_score": get_score("best-practices"),
        "seo_score": get_score("seo"),
        "analysis_timestamp": payload.get("analysisUTCTimestamp", ""),
        "failed_audits": failed_audits[:15],  # Limit to top 15 failures
        "metrics": {
            "first_contentful_paint": metric_value("first-contentful-paint"),
            "largest_contentful_paint": metric_value("largest-contentful-paint"),
            "cumulative_layout_shift": metric_value("cumulative-layout-shift"),
            "total_blocking_time": metric_value("total-blocking-time"),
            "speed_index": metric_value("speed-index"),
            "server_response_time": metric_value("server-response-time"),
        },
    }
    # For backward compatibility with the rest of the flow
    result["score"] = result["performance_score"]
    return result


def normalize_pagespeed_result(result):
    if not result:
        return None

    normalized = dict(result)
    if "performance_score" not in normalized and "score" in normalized:
        normalized["performance_score"] = normalized["score"]
    if "score" not in normalized and "performance_score" in normalized:
        normalized["score"] = normalized["performance_score"]

    normalized.setdefault("accessibility_score", None)
    normalized.setdefault("best_practices_score", None)
    normalized.setdefault("seo_score", None)
    normalized.setdefault("metrics", {})
    normalized.setdefault("failed_audits", [])
    return normalized


def fetch_pagespeed_many(urls):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(urls) or 1)) as executor:
        future_map = {executor.submit(fetch_pagespeed_insights, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = normalize_pagespeed_result(future.result())
            except Exception:
                results[url] = None
    return results


def parse_sitemap(xml_text):
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = []
    for loc in root.findall(f".//{namespace}loc"):
        if loc.text:
            urls.append(loc.text.strip())
    return urls


def choose_urls_to_crawl(start_url, homepage, sitemap_urls, limit=PAGE_LIMIT):
    domain = extract_domain(start_url)
    candidates = [start_url]

    for url in sitemap_urls:
        normalized = normalize_url(url)
        if normalized and extract_domain(normalized) == domain and normalized not in candidates:
            candidates.append(normalized)

    for href in homepage.links:
        normalized = normalize_url(urljoin(start_url, href))
        if normalized and extract_domain(normalized) == domain and normalized not in candidates:
            candidates.append(normalized)

    return candidates[:limit]


def normalize_competitor_urls(values, *, own_domain=""):
    urls = []
    for value in values or []:
        normalized = normalize_url(value)
        if not normalized:
            continue
        domain = extract_domain(normalized)
        if own_domain and domain == own_domain:
            continue
        if normalized not in urls:
            urls.append(normalized)
    return urls[:3]


def build_context_analysis(*, homepage, audit_request, session, own_domain):
    competitor_urls = normalize_competitor_urls(
        getattr(audit_request, "competitor_urls", []),
        own_domain=own_domain,
    ) if audit_request else []
    market_context = getattr(audit_request, "market_context", "") if audit_request else ""
    if not competitor_urls and not market_context:
        return {}

    competitor_snapshots = []
    for competitor_url in competitor_urls:
        response = safe_fetch(competitor_url, session=session, timeout=REQUEST_TIMEOUT)
        if not response or response.get("status_code", 0) >= 400 or "html" not in response.get("content_type", "").lower():
            competitor_snapshots.append(
                {
                    "url": competitor_url,
                    "status": "unavailable",
                }
            )
            continue
        parsed = parse_page(competitor_url, response)
        competitor_snapshots.append(
            {
                "url": competitor_url,
                "title": parsed.title,
                "h1": parsed.h1,
                "word_count": parsed.word_count,
                "schema_count": parsed.schema_count,
                "response_time_ms": parsed.response_time_ms,
                "meta_description": parsed.meta_description,
            }
        )

    insights = []
    available = [item for item in competitor_snapshots if item.get("status") != "unavailable"]
    if available:
        avg_competitor_words = sum(item.get("word_count", 0) for item in available) / max(len(available), 1)
        if homepage.word_count < avg_competitor_words:
            insights.append("Primary page copy is thinner than the average competitor homepage.")
        avg_competitor_speed = sum(item.get("response_time_ms", 0) for item in available) / max(len(available), 1)
        if homepage.response_time_ms > avg_competitor_speed:
            insights.append("Homepage response time is slower than the sampled competitor average.")
        competitor_with_schema = sum(1 for item in available if item.get("schema_count", 0) > 0)
        if homepage.schema_count == 0 and competitor_with_schema:
            insights.append("Competitors are using structured data where the audited site currently is not.")
        if not homepage.h1 and any(item.get("h1") for item in available):
            insights.append("Competitor pages have clear primary headings while the audited page does not.")

    if market_context:
        insights.insert(0, f"Submitted market context: {market_context}")

    return {
        "market_context": market_context,
        "competitors": competitor_snapshots,
        "insights": insights[:6],
    }


def create_issue(audit_run, page, code, category, severity, message, recommendation, details=None):
    AuditIssue.objects.create(
        audit_run=audit_run,
        page=page,
        code=code,
        category=category,
        severity=severity,
        message=message,
        recommendation=recommendation,
        details=details or {},
    )


def internal_link_total(page_url, links):
    domain = extract_domain(page_url)
    normalized = {
        normalize_url(urljoin(page_url, href))
        for href in links
        if normalize_url(urljoin(page_url, href))
    }
    return len({url for url in normalized if extract_domain(url) == domain})


def analyze_page(audit_run, page, parsed):
    title_length = len(parsed.title)
    if not parsed.title:
        create_issue(
            audit_run,
            page,
            "missing_title",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.HIGH,
            "Page is missing a title tag.",
            "Add a unique page title between 30 and 65 characters.",
        )
    elif title_length < 30 or title_length > 65:
        create_issue(
            audit_run,
            page,
            "title_length",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.MEDIUM,
            "Page title length is outside the recommended range.",
            "Keep titles concise and readable within the search snippet window.",
            {"length": title_length},
        )

    if not parsed.meta_description:
        create_issue(
            audit_run,
            page,
            "missing_meta_description",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.MEDIUM,
            "Page is missing a meta description.",
            "Add a compelling description that clarifies value and increases click intent.",
        )

    if not parsed.h1:
        create_issue(
            audit_run,
            page,
            "missing_h1",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.HIGH,
            "Page is missing an H1 heading.",
            "Add a single H1 that clearly describes the page topic.",
        )
    elif len(parsed.h1s) > 1:
        create_issue(
            audit_run,
            page,
            "multiple_h1",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.LOW,
            "Page contains multiple H1 headings.",
            "Keep a single dominant H1 and use lower heading levels for structure.",
            {"count": len(parsed.h1s)},
        )

    if not parsed.canonical_url:
        create_issue(
            audit_run,
            page,
            "missing_canonical",
            AuditIssue.Category.TECHNICAL,
            AuditIssue.Severity.MEDIUM,
            "Page is missing a canonical tag.",
            "Add canonical URLs to reduce duplication ambiguity.",
        )

    if parsed.has_noindex:
        create_issue(
            audit_run,
            page,
            "noindex_detected",
            AuditIssue.Category.TECHNICAL,
            AuditIssue.Severity.HIGH,
            "Page includes a noindex directive.",
            "Verify this page should really be blocked from indexing.",
        )

    if not parsed.viewport:
        create_issue(
            audit_run,
            page,
            "missing_viewport",
            AuditIssue.Category.TECHNICAL,
            AuditIssue.Severity.LOW,
            "Page is missing a viewport meta tag.",
            "Add a viewport declaration to improve mobile rendering.",
        )

    if not parsed.html_lang:
        create_issue(
            audit_run,
            page,
            "missing_html_lang",
            AuditIssue.Category.TECHNICAL,
            AuditIssue.Severity.LOW,
            "HTML lang attribute is missing.",
            "Set a language attribute on the html element to improve accessibility and parsing.",
        )

    # --- ENHANCED ON-PAGE / TECHNICAL DIAGNOSTICS ---
    
    # 1. H1 Integrity
    if len(parsed.h1s) > 1:
        create_issue(
            audit_run, page, "multiple_h1",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.MEDIUM,
            "Multiple H1 tags detected.",
            "Pages should have exactly one H1 to establish clear topical hierarchy. Current count: " + str(len(parsed.h1s)),
            {"h1_count": len(parsed.h1s)}
        )
    elif len(parsed.h1s) == 0:
        create_issue(
            audit_run, page, "missing_h1",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.HIGH,
            "No H1 tag detected.",
            "Add a single H1 that clearly describes the page topic for both users and search engines."
        )

    # 2. Title Optimization
    title_len = len(parsed.title)
    if title_len < 10 and title_len > 0:
        create_issue(
            audit_run, page, "title_too_short",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.LOW,
            "Page title is exceptionally short.",
            f"Your title ({title_len} chars) is too vague. Expand it to include primary keywords (Aim for 50-60 chars).",
            {"length": title_len}
        )
    elif title_len > 65:
        create_issue(
            audit_run, page, "title_too_long",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.LOW,
            "Page title is being truncated.",
            f"Your title ({title_len} chars) exceeds the 60-char limit for search results. Move core keywords to the front.",
            {"length": title_len}
        )

    # 3. Meta Description Depth
    meta_len = len(parsed.meta_description)
    if meta_len == 0:
        create_issue(
            audit_run, page, "missing_meta_description",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.MEDIUM,
            "Missing meta description.",
            "Add a unique meta description to improve click-through rates from search results."
        )
    elif meta_len < 50:
        create_issue(
            audit_run, page, "meta_too_short",
            AuditIssue.Category.ON_PAGE, AuditIssue.Severity.LOW,
            "Meta description is too thin.",
            f"Your description ({meta_len} chars) doesn't provide enough value. Aim for 120-160 characters to optimize for clicks.",
            {"length": meta_len}
        )

    # 4. Canonical / Duplicate Content Risk
    if not parsed.canonical_url:
        create_issue(
            audit_run, page, "missing_canonical",
            AuditIssue.Category.TECHNICAL, AuditIssue.Severity.MEDIUM,
            "Missing canonical tag.",
            "Specify a canonical URL to prevent duplicate content issues and consolidate ranking signals."
        )

    if parsed.word_count < 250:
        create_issue(
            audit_run,
            page,
            "thin_content",
            AuditIssue.Category.CONTENT,
            AuditIssue.Severity.MEDIUM,
            "Page looks thin for an indexable marketing page.",
            "Expand the page with clearer explanations, proof, and search-intent coverage.",
            {"word_count": parsed.word_count},
        )

    if page.internal_link_count < 2:
        create_issue(
            audit_run,
            page,
            "low_internal_links",
            AuditIssue.Category.INTERNAL_LINKING,
            AuditIssue.Severity.LOW,
            "Page exposes very few internal links.",
            "Add contextual internal links to services, tools, case studies, and related content.",
            {"internal_links": page.internal_link_count},
        )

    if parsed.images_missing_alt > 0:
        create_issue(
            audit_run,
            page,
            "missing_alt_text",
            AuditIssue.Category.CONTENT,
            AuditIssue.Severity.LOW,
            "Some images are missing alt text.",
            "Add descriptive alt text to support accessibility and reinforce topical context.",
            {"missing_alt": parsed.images_missing_alt},
        )

    if parsed.schema_count == 0:
        create_issue(
            audit_run,
            page,
            "missing_schema",
            AuditIssue.Category.AEO,
            AuditIssue.Severity.MEDIUM,
            "Page has no detectable structured data.",
            "Add schema markup that matches page intent, such as Organization, FAQ, or Article.",
        )

    if not parsed.og_title or not parsed.og_description:
        create_issue(
            audit_run,
            page,
            "weak_social_metadata",
            AuditIssue.Category.ON_PAGE,
            AuditIssue.Severity.LOW,
            "Page is missing Open Graph metadata.",
            "Add social metadata so pages share cleanly and preserve message clarity.",
        )

    if not parsed.has_faq_schema and parsed.word_count >= 400:
        create_issue(
            audit_run,
            page,
            "faq_schema_opportunity",
            AuditIssue.Category.AEO,
            AuditIssue.Severity.LOW,
            "Page could likely support FAQ-style answer blocks.",
            "Add concise question-and-answer sections and match them with FAQ schema where appropriate.",
        )

    if page.response_time_ms > 1800:
        create_issue(
            audit_run,
            page,
            "slow_response",
            AuditIssue.Category.PERFORMANCE,
            AuditIssue.Severity.MEDIUM,
            "Page response time appears slow.",
            "Review hosting, caching, and page weight to improve response speed.",
            {"response_time_ms": page.response_time_ms},
        )


def calculate_scores(audit_run):
    has_pagespeed = bool((audit_run.summary or {}).get("pagespeed"))
    return apply_audit_scores(audit_run, has_pagespeed=has_pagespeed)


def apply_pagespeed_score(audit_run):
    pagespeed = fetch_pagespeed_insights(audit_run.start_url)
    if not pagespeed:
        return None

    score = pagespeed["score"]
    severity = None
    if score < 50:
        severity = AuditIssue.Severity.HIGH
    elif score < 90:
        severity = AuditIssue.Severity.MEDIUM

    if severity:
        create_issue(
            audit_run,
            None,
            "pagespeed_performance",
            AuditIssue.Category.PERFORMANCE,
            severity,
            "Google PageSpeed Insights reports a suboptimal performance score.",
            "Reduce blocking scripts, heavy media, and layout shifts so mobile performance is competitive.",
            pagespeed,
        )

    return pagespeed
def parse_page(url, response):
    return ParsedPage(
        url=url,
        status_code=response["status_code"],
        response_time_ms=response["response_time_ms"],
        html=response["body"],
        headers=response.get("headers", {}),
    )




def fetch_many(urls, session):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(urls) or 1)) as executor:
        future_map = {executor.submit(safe_fetch, url, session, REQUEST_TIMEOUT): url for url in urls}
        for future in concurrent.futures.as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = None
    return results


def run_public_site_audit(*, audit_run, page_limit=PAGE_LIMIT):
    audit_run.status = AuditRun.Status.RUNNING
    audit_run.save(update_fields=["status", "updated_at"])

    start_url = normalize_url(audit_run.start_url)
    domain = extract_domain(start_url)
    audit_run.start_url = start_url
    audit_run.normalized_domain = domain
    audit_run.save(update_fields=["start_url", "normalized_domain", "updated_at"])

    with requests.Session() as session:
        homepage_response = safe_fetch(start_url, session=session)
        if not homepage_response or "html" not in homepage_response.get("content_type", "").lower() or homepage_response.get("status_code", 0) >= 400:
            audit_run.status = AuditRun.Status.FAILED
            status_info = homepage_response.get("status_code", "unknown") if homepage_response else "no response"
            error_details = homepage_response.get("error", "Not a valid HTML page") if homepage_response else "Connection failed"
            audit_run.error_message = f"Unable to fetch valid HTML. Status: {status_info}. Detail: {error_details}"
            audit_run.completed_at = timezone.now()
            audit_run.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            return audit_run

        homepage = parse_page(start_url, homepage_response)
        context_analysis = build_context_analysis(
            homepage=homepage,
            audit_request=audit_run.audit_request,
            session=session,
            own_domain=domain,
        )

        robots_response = safe_fetch(urljoin(start_url, "/robots.txt"), session=session)
        if not robots_response or robots_response["status_code"] >= 400:
            create_issue(
                audit_run,
                None,
                "missing_robots",
                AuditIssue.Category.TECHNICAL,
                AuditIssue.Severity.LOW,
                "robots.txt is missing or inaccessible.",
                "Publish a clear robots.txt file to control crawler guidance.",
            )

        sitemap_response = safe_fetch(urljoin(start_url, "/sitemap.xml"), session=session)
        sitemap_urls = []
        if sitemap_response and sitemap_response["status_code"] < 400 and "xml" in sitemap_response["content_type"].lower():
            sitemap_urls = parse_sitemap(sitemap_response["body"])
        else:
            create_issue(
                audit_run,
                None,
                "missing_sitemap",
                AuditIssue.Category.TECHNICAL,
                AuditIssue.Severity.MEDIUM,
                "sitemap.xml is missing or inaccessible.",
                "Publish an XML sitemap to improve crawl discovery and index coverage.",
            )

        urls_to_crawl = choose_urls_to_crawl(start_url, homepage, sitemap_urls, limit=page_limit)
        remaining_urls = [url for url in urls_to_crawl if url != start_url]
        fetched_pages = {start_url: homepage_response}
        fetched_pages.update(fetch_many(remaining_urls, session))

        pages = []
        successful_urls = []
        for url in urls_to_crawl:
            response = fetched_pages.get(url)
            if not response:
                continue

            if response["status_code"] >= 400 or "html" not in response["content_type"].lower():
                page = AuditPage.objects.create(
                    audit_run=audit_run,
                    url=url,
                    status_code=response["status_code"],
                    response_time_ms=response["response_time_ms"],
                )
                create_issue(
                    audit_run,
                    page,
                    "page_fetch_failed",
                    AuditIssue.Category.TECHNICAL,
                    AuditIssue.Severity.HIGH,
                    "Page could not be fetched as valid HTML.",
                    "Review the page response and ensure it is publicly crawlable.",
                    {"status_code": response["status_code"]},
                )
                pages.append(page)
                continue

            parsed = homepage if url == start_url else parse_page(url, response)
            page = create_or_update_page_record(audit_run, parsed, response)
            analyze_page(audit_run, page, parsed)
            pages.append(page)
            successful_urls.append(url)

    audit_run.pages_crawled = len(pages)
    
    # Run PageSpeed in parallel for all successful pages
    all_pagespeed = fetch_pagespeed_many(successful_urls)
    
    # Update Page records with PageSpeed data
    for page in pages:
        res = all_pagespeed.get(page.url)
        if res:
            page.pagespeed_score = res["performance_score"]
            page.accessibility_score = res["accessibility_score"]
            page.best_practices_score = res["best_practices_score"]
            page.seo_score = res["seo_score"]
            page.pagespeed_data = res
            page.save(update_fields=[
                "pagespeed_score", "accessibility_score", "best_practices_score", "seo_score", "pagespeed_data"
            ])
            
    # Set homepage pagespeed as the main run pagespeed for summary and run scores
    homepage_ps = all_pagespeed.get(start_url)
    if homepage_ps:
        audit_run.performance_score = homepage_ps["performance_score"]
        audit_run.accessibility_score = homepage_ps["accessibility_score"]
        audit_run.best_practices_score = homepage_ps["best_practices_score"]
        audit_run.seo_score = homepage_ps["seo_score"]
        audit_run.summary = {"pagespeed": homepage_ps}
        
    apply_audit_scores(audit_run, has_pagespeed=bool(homepage_ps))
        
    # Expert Intelligence Aggregation
    tech_summary = {"cms": [], "frameworks": [], "analytics": set(), "marketing": set(), "security": True}
    for page in pages:
        stack = page.tech_stack
        if stack.get("cms") and stack["cms"] not in tech_summary["cms"]:
            tech_summary["cms"].append(stack["cms"])
        if stack.get("framework") and stack["framework"] not in tech_summary["frameworks"]:
            tech_summary["frameworks"].append(stack["framework"])
        tech_summary["analytics"].update(stack.get("analytics", []))
        tech_summary["marketing"].update(stack.get("marketing", []))
        if not all(page.security_headers.values()):
            tech_summary["security"] = False

    tech_summary["analytics"] = list(tech_summary["analytics"])
    tech_summary["marketing"] = list(tech_summary["marketing"])
    audit_run.tech_summary = tech_summary

    audit_run.summary = build_audit_summary(audit_run)
    if context_analysis:
        audit_run.summary["context_analysis"] = context_analysis
    audit_run.status = AuditRun.Status.COMPLETED
    audit_run.completed_at = timezone.now()
    audit_run.save(update_fields=[
        "status", "completed_at", "pages_crawled", "summary", "tech_summary",
        "technical_score", "on_page_score", "content_score", "aeo_score", "internal_linking_score",
        "performance_score", "accessibility_score", "best_practices_score", "seo_score", "overall_score"
    ])
    return audit_run


# ---------------------------------------------------------------------------
# Cross-module decision summary — Phase 11 Track A
# ---------------------------------------------------------------------------

def build_cross_module_decision_summary(
    project,
    *,
    latest_audit=None,
    latest_seo_snapshot=None,
    latest_aeo_audit=None,
    seo_active_campaign_count=0,
    seo_execution_item_count=0,
    content_draft_count=0,
    audit_summary=None,
    change_report=None,
):
    """
    Produce a cross-module decision summary that tells the user:
    - primary_action: the single most impactful next step right now
    - supporting_signals: evidence from existing data that supports the decision
    - waiting_items: things that depend on the primary action being done first
    - module_health: per-module status dict (name, status, one-liner)
    - overall_narrative: a one-sentence state-of-the-workspace description

    This replaces the static numbered-list in the command center with data-driven guidance.
    """
    audit_summary = audit_summary or {}
    recommendations = audit_summary.get("featured_recommendations") or audit_summary.get("recommendations") or []
    issue_summary = audit_summary.get("issue_summary") or {}
    score_breakdown = audit_summary.get("score_breakdown") or {}

    # --- Module health signals ---
    audit_score = getattr(latest_audit, "overall_score", None)
    audit_date = getattr(latest_audit, "created_at", None)
    aeo_score = getattr(latest_aeo_audit, "overall_score", None)
    score_delta = None
    if change_report:
        score_delta = getattr(change_report, "overall_score_delta", None)

    has_audit = latest_audit is not None
    has_seo = latest_seo_snapshot is not None
    has_aeo = latest_aeo_audit is not None
    has_content = content_draft_count > 0

    # --- Determine primary action ---
    primary_action = {}
    supporting_signals = []
    waiting_items = []

    if not has_audit:
        primary_action = {
            "step": "Run your first audit",
            "reason": "The audit is the foundation — it creates the baseline score, issue queue, competitor context, and dependency chain for every other module.",
            "href": "#start-audit",
            "cta": "Start audit",
            "urgency": "required",
        }
        waiting_items = [
            {"label": "SEO intelligence", "reason": "Needs the audit's site structure and competitor hints as its base."},
            {"label": "AI Visibility (AEO)", "reason": "AEO analysis opens once the first audit run completes."},
            {"label": "Content workspace", "reason": "Content briefs and drafts are generated from SEO and AEO outputs."},
        ]

    elif not has_seo and not has_aeo:
        primary_action = {
            "step": "Run SEO intelligence",
            "reason": "Your audit is complete. The next highest-value move is mapping competitors and search gaps before optimising individual pages.",
            "href": "/workspace/seo/",
            "cta": "Open SEO workspace",
            "urgency": "high",
        }
        if audit_score is not None:
            supporting_signals.append({
                "label": "Audit score",
                "value": f"{audit_score}/100",
                "note": "Use SEO intelligence to turn this score into a prioritised page-level action queue.",
            })
        top_issue = recommendations[0] if recommendations else None
        if top_issue:
            supporting_signals.append({
                "label": "Top issue",
                "value": top_issue.get("title") or top_issue.get("category", ""),
                "note": "SEO context will confirm whether competitors have the same gap or if this is a differentiator.",
            })
        waiting_items = [
            {"label": "AI Visibility (AEO)", "reason": "Run AEO in parallel or after SEO to cover the AI citation gap."},
            {"label": "Content drafts", "reason": "Content briefs are strongest when built on SEO page-map evidence."},
        ]

    elif has_seo and not has_aeo:
        primary_action = {
            "step": "Run AEO analysis",
            "reason": "SEO is mapped. Close the gap on AI citations — AEO is the platform's primary differentiator and it runs independently of SEO.",
            "href": "/workspace/aeo/",
            "cta": "Open AI Visibility",
            "urgency": "high",
        }
        if seo_active_campaign_count:
            supporting_signals.append({
                "label": "SEO campaigns",
                "value": f"{seo_active_campaign_count} active",
                "note": "Campaigns are queued. Running AEO lets you compare AI visibility gaps against your existing SEO action plan.",
            })
        waiting_items = [
            {"label": "Content briefs", "reason": "Generate content once both SEO and AEO gaps are mapped so drafts address both signals."},
        ]

    elif has_audit and has_seo and has_aeo:
        # All modules have data — surface the most urgent signal
        urgency_items = []

        # Score drop is highest urgency
        if score_delta is not None and score_delta < -5:
            urgency_items.append(("score_drop", abs(score_delta)))

        # Low AEO score
        if aeo_score is not None and aeo_score < 50:
            urgency_items.append(("low_aeo", 100 - aeo_score))

        # Large SEO campaign backlog
        if seo_active_campaign_count >= 5:
            urgency_items.append(("seo_backlog", seo_active_campaign_count))

        # Pending content drafts
        if has_content:
            urgency_items.append(("content_drafts", content_draft_count))

        # Top issue queue
        if recommendations:
            urgency_items.append(("issue_queue", len(recommendations)))

        urgency_items.sort(key=lambda x: -x[1])
        top_urgency = urgency_items[0][0] if urgency_items else "issue_queue"

        if top_urgency == "score_drop":
            primary_action = {
                "step": f"Address the audit score drop ({score_delta:+d} points)",
                "reason": "A score drop signals a regression. Identify what changed and run a rerun after the fix to confirm recovery.",
                "href": f"/workspace/audit/{latest_audit.pk}/" if latest_audit else "#start-audit",
                "cta": "Open audit",
                "urgency": "critical",
            }
            supporting_signals.append({
                "label": "Score change",
                "value": f"{score_delta:+d} vs previous audit",
                "note": "Check the fix queue for newly flagged issues introduced since the last run.",
            })
        elif top_urgency == "low_aeo":
            primary_action = {
                "step": "Improve AI visibility",
                "reason": f"AEO score is {aeo_score}/100. Competitors with stronger entity clarity and answer-ready content are being cited instead.",
                "href": "/workspace/aeo/",
                "cta": "Open AI Visibility",
                "urgency": "high",
            }
            supporting_signals.append({
                "label": "AEO score",
                "value": f"{aeo_score}/100",
                "note": "Focus on entity schema, FAQ additions, and direct-answer content blocks.",
            })
        elif top_urgency == "seo_backlog":
            primary_action = {
                "step": "Work through the SEO campaign queue",
                "reason": f"{seo_active_campaign_count} SEO campaigns are queued and have not been started. Each carries a specific page-level action pack.",
                "href": "/workspace/seo/#seo-campaigns",
                "cta": "Open SEO campaigns",
                "urgency": "high",
            }
            supporting_signals.append({
                "label": "Active campaigns",
                "value": str(seo_active_campaign_count),
                "note": f"{seo_execution_item_count} execution items mapped across these campaigns.",
            })
        elif top_urgency == "content_drafts":
            primary_action = {
                "step": "Review and publish pending content drafts",
                "reason": f"{content_draft_count} draft{'s' if content_draft_count != 1 else ''} {'are' if content_draft_count != 1 else 'is'} ready for review. Publishing converts SEO briefs into indexed content.",
                "href": "/workspace/content/",
                "cta": "Open content workspace",
                "urgency": "medium",
            }
        else:
            # Default: point to the top recommendation
            top_issue = recommendations[0] if recommendations else None
            if top_issue:
                primary_action = {
                    "step": top_issue.get("title") or "Address the top audit issue",
                    "reason": top_issue.get("recommended_fix") or "This is the highest-priority issue identified across the current audit.",
                    "href": f"/workspace/audit/{latest_audit.pk}/" if latest_audit else "#start-audit",
                    "cta": "Open fix queue",
                    "urgency": "medium",
                }
            else:
                primary_action = {
                    "step": "Re-run the audit to validate recent changes",
                    "reason": "All modules have data and no critical gaps are detected. A fresh rerun confirms whether recent changes improved scores.",
                    "href": "#start-audit",
                    "cta": "Run rerun",
                    "urgency": "low",
                }

        # Add supporting signals from all modules
        if audit_score is not None:
            supporting_signals.append({
                "label": "Audit score",
                "value": f"{audit_score}/100",
                "note": f"{issue_summary.get('total', len(recommendations))} issues in queue.",
            })
        if seo_active_campaign_count and top_urgency != "seo_backlog":
            supporting_signals.append({
                "label": "SEO campaigns",
                "value": f"{seo_active_campaign_count} active",
                "note": f"{seo_execution_item_count} execution items mapped.",
            })
        if aeo_score is not None and top_urgency != "low_aeo":
            supporting_signals.append({
                "label": "AEO score",
                "value": f"{aeo_score}/100",
                "note": "AI visibility score from latest analysis.",
            })

    # --- Module health table ---
    module_health = []
    if has_audit:
        if audit_score is not None and audit_score >= 75:
            status = "good"
        elif audit_score is not None and audit_score >= 50:
            status = "warn"
        elif audit_score is not None:
            status = "critical"
        else:
            status = "none"
        module_health.append({"name": "Audit", "status": status, "score": audit_score, "date": audit_date})

    if has_seo:
        seo_status = "good" if seo_active_campaign_count < 5 else "warn"
        module_health.append({"name": "SEO", "status": seo_status, "score": None, "date": latest_seo_snapshot.created_at})

    if has_aeo:
        if aeo_score is not None and aeo_score >= 70:
            aeo_status = "good"
        elif aeo_score is not None and aeo_score >= 45:
            aeo_status = "warn"
        else:
            aeo_status = "critical"
        module_health.append({"name": "AEO", "status": aeo_status, "score": aeo_score, "date": latest_aeo_audit.created_at})

    if has_content:
        module_health.append({"name": "Content", "status": "active", "score": None, "date": None})

    # --- Overall narrative ---
    if not has_audit:
        narrative = "No audit has been run yet — start here to unlock the full workspace."
    elif not has_seo and not has_aeo:
        narrative = f"Audit complete ({audit_score}/100). SEO and AEO workspaces are ready to open."
    elif has_seo and not has_aeo:
        narrative = f"Audit and SEO are active. AEO analysis is the next open gap."
    elif score_delta is not None and score_delta < -5:
        narrative = f"Score dropped {abs(score_delta)} points since the last audit — recovery is the priority."
    elif aeo_score is not None and aeo_score < 50:
        narrative = f"All modules are active. AI visibility ({aeo_score}/100) is the weakest signal right now."
    elif seo_active_campaign_count >= 5:
        narrative = f"All modules active. {seo_active_campaign_count} SEO campaigns are queued and awaiting execution."
    else:
        narrative = "All core modules are active. Work through the fix queue and campaign actions."

    return {
        "primary_action": primary_action,
        "supporting_signals": supporting_signals[:4],
        "waiting_items": waiting_items,
        "module_health": module_health,
        "overall_narrative": narrative,
        "has_data": has_audit,
    }


# ---------------------------------------------------------------------------
# Executive outcome summary — Phase 11 Track D
# ---------------------------------------------------------------------------

def build_executive_outcome_summary(
    project,
    *,
    latest_audit=None,
    previous_audit=None,
    change_report=None,
    seo_campaigns=None,
    content_draft_count=0,
    backlink_prospect_count=0,
    credit_usage_pct=0,
):
    """
    Build a plain-language outcome summary suitable for a stakeholder overview panel.

    Returns a dict with:
      has_data          – bool; False when there is no audit to summarise
      headline          – one-sentence summary of the workspace state
      what_was_done     – audit scope metrics
      score_progress    – score delta and issue resolution stats
      assets_created    – SEO campaigns, edit items, content drafts
      links_pursued     – backlink prospect count
      validation        – campaign completion percentage
      credit_used_pct   – credit usage band (0-100 int)
    """
    has_data = bool(latest_audit and latest_audit.pk)
    if not has_data:
        return {"has_data": False}

    # --- What was done --------------------------------------------------
    pages_scanned = getattr(latest_audit, "pages_crawled", 0) or 0
    audit_summary_json = getattr(latest_audit, "summary", None) or {}
    issue_summary = audit_summary_json.get("issue_summary", {}) if isinstance(audit_summary_json, dict) else {}
    issues_found = issue_summary.get("total", 0)

    what_was_done = {
        "pages_scanned": pages_scanned,
        "issues_found": issues_found,
        "audit_date": latest_audit.created_at,
    }

    # --- Score progress -------------------------------------------------
    overall_delta = None
    from_score = None
    to_score = getattr(latest_audit, "overall_score", None)
    resolved_issues = 0
    new_issues = 0

    if change_report:
        overall_delta = getattr(change_report, "overall_score_delta", None)
        resolved_issues = getattr(change_report, "resolved_issue_count", 0) or 0
        new_issues = getattr(change_report, "new_issue_count", 0) or 0
        if overall_delta is not None and to_score is not None:
            from_score = to_score - overall_delta
    elif previous_audit:
        prev_score = getattr(previous_audit, "overall_score", None)
        if prev_score is not None and to_score is not None:
            overall_delta = to_score - prev_score
            from_score = prev_score

    score_progress = {
        "to_score": to_score,
        "from_score": from_score,
        "overall_delta": overall_delta,
        "resolved_issues": resolved_issues,
        "new_issues": new_issues,
        "improved": overall_delta > 0 if overall_delta is not None else None,
    }

    # --- Assets created -------------------------------------------------
    campaign_list = list(seo_campaigns) if seo_campaigns else []
    total_campaigns = len(campaign_list)
    completed_campaigns = sum(
        1 for c in campaign_list if getattr(c, "status", "") == "completed"
    )

    total_edit_items = 0
    completed_edit_items = 0
    for campaign in campaign_list:
        items = list(getattr(campaign, "edit_items", None) and campaign.edit_items.all() or [])
        total_edit_items += len(items)
        completed_edit_items += sum(1 for item in items if getattr(item, "status", "") == "completed")

    assets_created = {
        "seo_campaigns": total_campaigns,
        "seo_edit_items": total_edit_items,
        "seo_edit_items_completed": completed_edit_items,
        "content_drafts": content_draft_count,
    }

    # --- Links pursued --------------------------------------------------
    links_pursued = {"prospects_found": backlink_prospect_count}

    # --- Validation / completion ----------------------------------------
    completion_pct = 0
    if total_edit_items > 0:
        completion_pct = round(100 * completed_edit_items / total_edit_items)
    elif total_campaigns > 0:
        completion_pct = round(100 * completed_campaigns / total_campaigns)

    validation = {
        "campaigns_completed": completed_campaigns,
        "campaigns_total": total_campaigns,
        "completion_pct": completion_pct,
    }

    # --- Plain-language headline ----------------------------------------
    if overall_delta is not None and overall_delta > 0:
        score_note = f"Score up {overall_delta} points."
    elif overall_delta is not None and overall_delta < 0:
        score_note = f"Score down {abs(overall_delta)} points since last run."
    elif to_score is not None:
        score_note = f"Score holding at {to_score}."
    else:
        score_note = ""

    if total_edit_items > 0 and completed_edit_items > 0:
        action_note = f"{completed_edit_items} of {total_edit_items} page fixes done."
    elif total_campaigns > 0:
        action_note = f"{total_campaigns} campaign{'s' if total_campaigns != 1 else ''} queued."
    elif content_draft_count > 0:
        action_note = f"{content_draft_count} content draft{'s' if content_draft_count != 1 else ''} ready."
    else:
        action_note = f"{pages_scanned} pages scanned, {issues_found} issues found."

    headline_parts = [p for p in [score_note, action_note] if p]
    headline = " ".join(headline_parts) or f"Workspace active. {pages_scanned} pages scanned."

    return {
        "has_data": True,
        "headline": headline,
        "what_was_done": what_was_done,
        "score_progress": score_progress,
        "assets_created": assets_created,
        "links_pursued": links_pursued,
        "validation": validation,
        "credit_used_pct": int(credit_usage_pct or 0),
    }
