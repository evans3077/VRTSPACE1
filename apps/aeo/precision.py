"""
P1 AEO Precision Layer.

Runs real LLM API queries (ChatGPT + Perplexity + Gemini) against a curated set
of industry/location/intent queries derived from the project profile.  Detects
brand citations via domain URL matching + brand name string matching (passive
co-occurrence) and tracks competitor visibility delta.

When API keys are missing the engine gracefully returns "derived" results so
the existing UI keeps working without breakage.

Architecture:
    build_query_set(project, profile) -> list[str]
        5 queries derived from industry + location + primary service +
        target_keyword.

    run_precision_audit(aeo_audit, dry_run=False)
        For each engine, sends each query, parses responses, updates the
        AEOAudit + its VisibilitySnapshots.

    detect_citations(text, brand_name, domain, competitors)
        Brand-mention detection (case-insensitive, word-boundary) + domain URL
        match + competitor co-occurrence.

Credits are debited by the *caller* before invoking the audit (the AEO view
already calls spend_action_credits).  This module is API-cost-aware: each run
is exactly 15 outbound calls (3 engines × 5 queries) unless an engine is
unavailable.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse

import requests
from django.utils import timezone

from .models import AEOAudit, VisibilitySnapshot

logger = logging.getLogger(__name__)


# ─── Config ─────────────────────────────────────────────────────────────────

QUERIES_PER_ENGINE = 5
REQUEST_TIMEOUT_SECONDS = 45


def _openai_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def _perplexity_key() -> str:
    return (os.environ.get("PERPLEXITY_API_KEY") or "").strip()


def _gemini_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY") or "").strip()


# ─── Query Generation ───────────────────────────────────────────────────────

def build_query_set(*, project, profile, target_keyword: str = "") -> list[str]:
    """
    Produce up to 5 industry/intent queries derived from the project profile.

    The queries mimic the way a real user would ask an AI assistant — we want
    to discover whether the brand is mentioned passively in answers, not force
    the engine to talk about it.
    """
    service = (
        (getattr(profile, "primary_service", "") or "")
        or (getattr(profile, "business_type", "") or "")
        or "service"
    ).replace("_", " ").strip()
    location = (getattr(profile, "location", "") or "").strip()
    keyword = (target_keyword or "").strip()
    brand = (getattr(project, "name", "") or "").strip()

    queries: list[str] = []

    if keyword:
        queries.append(f"What is the best {keyword}?")
    if service and location:
        queries.append(f"Who offers the best {service} in {location}?")
    if service:
        queries.append(f"What should I look for when choosing a {service}?")
    if keyword and location:
        queries.append(f"Compare top {keyword} options in {location}.")
    elif service:
        queries.append(f"Which companies are highly rated for {service}?")
    if brand:
        queries.append(f"Tell me about {brand}.")
    else:
        queries.append(f"What are leading {service or keyword or 'providers'} doing differently?")

    # Pad / trim
    fallback = [
        f"Recommend a {service or 'provider'} for a small business.",
        f"What questions should I ask before hiring a {service or 'provider'}?",
        "What are the most trusted brands in this space right now?",
    ]
    while len(queries) < QUERIES_PER_ENGINE:
        queries.append(fallback[(len(queries) - 1) % len(fallback)])
    return queries[:QUERIES_PER_ENGINE]


# ─── Brand & Competitor Detection ───────────────────────────────────────────

@dataclass
class CitationResult:
    engine: str
    query: str
    response_text: str
    brand_cited: bool
    domain_cited: bool
    citation_count: int  # combined count of brand-name + domain mentions
    competitors_cited: dict[str, int] = field(default_factory=dict)
    error: str = ""


def _normalise_domain(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    if "://" in value:
        try:
            value = urlparse(value).netloc
        except Exception:
            pass
    return value.replace("www.", "")


def _name_pattern(name: str) -> re.Pattern[str]:
    # Word-boundary, case-insensitive match. Escapes regex metacharacters.
    return re.compile(rf"\b{re.escape(name.strip())}\b", re.IGNORECASE)


def detect_citations(
    *,
    text: str,
    brand_name: str,
    domain: str,
    competitors: Iterable[str] = (),
    engine: str = "",
    query: str = "",
) -> CitationResult:
    text = text or ""
    brand_cited = False
    domain_cited = False
    citation_count = 0

    norm_domain = _normalise_domain(domain)
    if norm_domain:
        # Match either bare domain or full URL
        domain_pattern = re.compile(
            rf"\b{re.escape(norm_domain)}\b", re.IGNORECASE
        )
        domain_hits = len(domain_pattern.findall(text))
        if domain_hits:
            domain_cited = True
            citation_count += domain_hits

    if brand_name and brand_name.strip():
        try:
            brand_pattern = _name_pattern(brand_name)
            brand_hits = len(brand_pattern.findall(text))
            if brand_hits:
                brand_cited = True
                citation_count += brand_hits
        except re.error:
            pass

    competitor_hits: dict[str, int] = {}
    for comp in competitors or ():
        comp = (comp or "").strip()
        if not comp:
            continue
        try:
            # Treat competitor as either a domain or a name
            norm_comp = _normalise_domain(comp)
            pattern_text = norm_comp or comp
            comp_pattern = re.compile(
                rf"\b{re.escape(pattern_text)}\b", re.IGNORECASE
            )
            hits = len(comp_pattern.findall(text))
            if hits:
                competitor_hits[comp] = hits
        except re.error:
            continue

    return CitationResult(
        engine=engine,
        query=query,
        response_text=text,
        brand_cited=brand_cited or domain_cited,
        domain_cited=domain_cited,
        citation_count=citation_count,
        competitors_cited=competitor_hits,
    )


# ─── Engine Callers ─────────────────────────────────────────────────────────

def _call_openai(query: str) -> tuple[str, str]:
    """Returns (response_text, error). Empty error means success."""
    key = _openai_key()
    if not key:
        return "", "OPENAI_API_KEY not configured"
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Answer briefly with relevant brand and product examples when applicable."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "") or "", ""
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("OpenAI call failed: %s", exc)
        return "", str(exc)[:160]


def _call_perplexity(query: str) -> tuple[str, str]:
    key = _perplexity_key()
    if not key:
        return "", "PERPLEXITY_API_KEY not configured"
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Cite specific brands or providers when answering."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        # Perplexity often returns citations in a separate field — append URLs to the response for matching
        citations = data.get("citations") or []
        if citations:
            content += "\n\nSources: " + " ".join(c if isinstance(c, str) else c.get("url", "") for c in citations)
        return content, ""
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("Perplexity call failed: %s", exc)
        return "", str(exc)[:160]


def _call_gemini(query: str) -> tuple[str, str]:
    key = _gemini_key()
    if not key:
        return "", "GEMINI_API_KEY not configured"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={key}"
    )
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": query}]}
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
    }
    try:
        r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return "", "gemini: no candidates"
        parts = candidates[0].get("content", {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts), ""
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("Gemini call failed: %s", exc)
        return "", str(exc)[:160]


ENGINE_CALLERS = {
    VisibilitySnapshot.Engine.CHATGPT: _call_openai,
    VisibilitySnapshot.Engine.PERPLEXITY: _call_perplexity,
    VisibilitySnapshot.Engine.GEMINI: _call_gemini,
}


def is_precision_available() -> dict[str, bool]:
    return {
        VisibilitySnapshot.Engine.CHATGPT: bool(_openai_key()),
        VisibilitySnapshot.Engine.PERPLEXITY: bool(_perplexity_key()),
        VisibilitySnapshot.Engine.GEMINI: bool(_gemini_key()),
    }


# ─── Main Runner ────────────────────────────────────────────────────────────

def run_precision_audit(aeo_audit: AEOAudit, *, dry_run: bool = False) -> AEOAudit:
    """
    Execute the precision layer for a given AEOAudit.

    On success, updates:
        - aeo_audit.status -> COMPLETED
        - aeo_audit.queries_sent, engines_used, queries_log
        - aeo_audit.competitor_visibility (per-competitor citation totals)
        - aeo_audit.precision_mode -> 'live' if any engine ran, else 'derived'
        - Replaces existing VisibilitySnapshots with per-engine aggregated rows

    Refuses to raise on engine failures — captures errors in queries_log so the
    UI can surface them cleanly.
    """
    project = aeo_audit.project
    profile = aeo_audit.seo_profile

    domain = ""
    if aeo_audit.source_audit_run and aeo_audit.source_audit_run.normalized_domain:
        domain = aeo_audit.source_audit_run.normalized_domain
    elif project and getattr(project, "normalized_domain", ""):
        domain = project.normalized_domain

    brand_name = (getattr(project, "name", "") or "").strip()
    # Competitor URLs live on the project's linked AuditRequest.
    competitors = []
    audit_request = getattr(project, "audit_request", None) if project else None
    if audit_request is not None:
        competitors = list(getattr(audit_request, "competitor_urls", None) or [])[:6]

    queries = build_query_set(
        project=project,
        profile=profile,
        target_keyword=aeo_audit.target_keyword or "",
    )

    aeo_audit.status = AEOAudit.Status.RUNNING
    aeo_audit.save(update_fields=["status"])

    availability = is_precision_available()
    queries_log: list[dict] = []
    engines_used: list[str] = []
    per_engine_results: dict[str, list[CitationResult]] = {}
    competitor_totals: dict[str, int] = {}

    for engine, available in availability.items():
        if not available:
            queries_log.append(
                {"engine": engine, "skipped": True, "reason": "no API key configured"}
            )
            continue
        engine_results: list[CitationResult] = []
        for query in queries:
            if dry_run:
                response_text, err = "(dry-run)", ""
            else:
                caller = ENGINE_CALLERS[engine]
                response_text, err = caller(query)
            result = detect_citations(
                text=response_text,
                brand_name=brand_name,
                domain=domain,
                competitors=competitors,
                engine=engine,
                query=query,
            )
            result.error = err
            engine_results.append(result)
            queries_log.append(
                {
                    "engine": engine,
                    "query": query,
                    "brand_cited": result.brand_cited,
                    "domain_cited": result.domain_cited,
                    "citation_count": result.citation_count,
                    "competitors": result.competitors_cited,
                    "error": err,
                }
            )
            for comp, hits in result.competitors_cited.items():
                competitor_totals[comp] = competitor_totals.get(comp, 0) + hits
        if engine_results:
            per_engine_results[engine] = engine_results
            engines_used.append(engine)

    # Aggregate per-engine to update VisibilitySnapshots with REAL data
    # Replace existing snapshots only if we actually ran live queries.
    if per_engine_results:
        VisibilitySnapshot.objects.filter(aeo_audit=aeo_audit).delete()
        snapshot_rows: list[VisibilitySnapshot] = []
        for engine, results in per_engine_results.items():
            total_queries = len(results)
            cited_queries = sum(1 for r in results if r.brand_cited)
            total_mentions = sum(r.citation_count for r in results)
            # citation_frequency: 0-5 scale, capped at queries-per-engine
            citation_freq = min(cited_queries, 5)
            sample_cited_url = ""
            if domain and any(r.domain_cited for r in results):
                sample_cited_url = f"https://{domain}"
            cited_ratio = cited_queries / max(total_queries, 1)
            notes_bits = [
                f"{cited_queries}/{total_queries} queries returned a brand citation",
                f"{total_mentions} total mention(s) across responses",
            ]
            errors = [r.error for r in results if r.error]
            if errors:
                notes_bits.append(f"Errors: {errors[0]}")
            snapshot_rows.append(
                VisibilitySnapshot(
                    aeo_audit=aeo_audit,
                    engine=engine,
                    prompt=results[0].query if results else "",
                    cited_url=sample_cited_url,
                    answer_present=cited_ratio > 0,
                    citation_frequency=citation_freq,
                    notes=" — ".join(notes_bits),
                )
            )
        VisibilitySnapshot.objects.bulk_create(snapshot_rows)
        aeo_audit.precision_mode = "live"
    else:
        aeo_audit.precision_mode = "derived"

    aeo_audit.queries_sent = sum(1 for entry in queries_log if not entry.get("skipped"))
    aeo_audit.engines_used = engines_used
    aeo_audit.queries_log = queries_log
    aeo_audit.competitor_visibility = {
        "totals": competitor_totals,
        "ranking": sorted(competitor_totals.items(), key=lambda kv: -kv[1])[:10],
    }
    aeo_audit.status = AEOAudit.Status.COMPLETED
    aeo_audit.save(
        update_fields=[
            "queries_sent",
            "engines_used",
            "queries_log",
            "competitor_visibility",
            "precision_mode",
            "status",
            "updated_at",
        ]
    )
    return aeo_audit


def mark_failed(aeo_audit: AEOAudit, message: str = "") -> None:
    aeo_audit.status = AEOAudit.Status.FAILED
    log = list(aeo_audit.queries_log or [])
    log.append({"error": message or "unknown failure", "at": timezone.now().isoformat()})
    aeo_audit.queries_log = log
    aeo_audit.save(update_fields=["status", "queries_log", "updated_at"])
