"""
P5 — Public AEO Visibility Index.

A free, indexable lookup tool: "is your brand visible in ChatGPT?"

Strategy (per grill decision Q16, Q17):
- Cache-first: query AEOIndexEntry by normalised domain.
- Queue unknowns up to a daily ceiling of 50 fresh checks.
- Run the 3-engine, 3-query precision pass (smaller than the workspace pass
  to keep costs predictable).
- All entries are public + indexable so they generate organic SEO traffic.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .models import AEOIndexEntry, VisibilitySnapshot
from .precision import (
    ENGINE_CALLERS,
    detect_citations,
    is_precision_available,
)

logger = logging.getLogger(__name__)

# Rate limits
DAILY_QUEUE_CAP = 50
DAILY_QUEUE_CACHE_KEY = "aeo:index:daily-count"
DAILY_QUEUE_CACHE_TTL = 60 * 60 * 24  # 24 hours
STALE_AFTER_DAYS = 30  # re-check entries older than this if we have budget
QUERIES_PER_LOOKUP = 3


def normalise_domain(raw: str) -> str:
    """Same logic used elsewhere — lowercase, strip protocol + www + path."""
    if not raw:
        return ""
    value = raw.strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0].split("?", 1)[0]
    if value.startswith("www."):
        value = value[4:]
    return value.strip(".")


def _quota_remaining() -> int:
    used = cache.get(DAILY_QUEUE_CACHE_KEY, 0)
    return max(DAILY_QUEUE_CAP - used, 0)


def _consume_quota(n: int = 1) -> None:
    used = cache.get(DAILY_QUEUE_CACHE_KEY, 0)
    cache.set(DAILY_QUEUE_CACHE_KEY, used + n, DAILY_QUEUE_CACHE_TTL)


def _build_queries(domain: str, brand: str = "") -> list[str]:
    name = brand or domain
    return [
        f"Tell me about {name}.",
        f"Is {name} a reputable provider?",
        f"What does {name} do?",
    ][:QUERIES_PER_LOOKUP]


def lookup_or_queue(raw_domain: str, *, run_inline: bool = True) -> AEOIndexEntry:
    """
    Cache-first lookup for the public index.

    Returns the AEOIndexEntry (creating + populating if needed and quota allows).
    If quota is exhausted, returns a QUEUED entry without running.
    """
    domain = normalise_domain(raw_domain)
    if not domain:
        raise ValueError("Invalid domain.")

    entry, created = AEOIndexEntry.objects.get_or_create(
        domain=domain,
        defaults={"status": AEOIndexEntry.Status.QUEUED},
    )

    # Bump lookup counter (cheap demand signal)
    AEOIndexEntry.objects.filter(pk=entry.pk).update(
        lookup_count=entry.lookup_count + 1
    )
    entry.refresh_from_db()

    is_stale = (
        entry.last_checked_at is None
        or (timezone.now() - entry.last_checked_at) > timedelta(days=STALE_AFTER_DAYS)
    )

    if entry.status == AEOIndexEntry.Status.COMPLETED and not is_stale:
        return entry

    if not run_inline:
        return entry

    if _quota_remaining() <= 0:
        # Out of budget for today — leave as QUEUED so the page can show a
        # "checking soon" state.
        return entry

    _consume_quota()
    run_index_lookup(entry)
    return entry


def run_index_lookup(entry: AEOIndexEntry) -> AEOIndexEntry:
    """Execute the lightweight precision pass for a public index entry."""
    availability = is_precision_available()
    queries = _build_queries(entry.domain, entry.brand_name)
    queries_log: list[dict] = []
    cited_map: dict[str, int] = {"chatgpt": 0, "gemini": 0, "perplexity": 0}

    for engine, available in availability.items():
        if not available:
            queries_log.append({"engine": engine, "skipped": True})
            continue
        caller = ENGINE_CALLERS[engine]
        for query in queries:
            try:
                text, err = caller(query)
            except Exception as exc:  # pragma: no cover - defensive
                text, err = "", str(exc)[:160]
            result = detect_citations(
                text=text,
                brand_name=entry.brand_name or entry.domain,
                domain=entry.domain,
                competitors=(),
                engine=engine,
                query=query,
            )
            if result.brand_cited:
                cited_map[engine] = cited_map.get(engine, 0) + 1
            queries_log.append(
                {
                    "engine": engine,
                    "query": query,
                    "brand_cited": result.brand_cited,
                    "domain_cited": result.domain_cited,
                    "citation_count": result.citation_count,
                    "error": err,
                }
            )

    entry.chatgpt_cited = cited_map.get("chatgpt", 0) > 0
    entry.gemini_cited = cited_map.get("gemini", 0) > 0
    entry.perplexity_cited = cited_map.get("perplexity", 0) > 0
    entry.chatgpt_frequency = cited_map.get("chatgpt", 0)
    entry.gemini_frequency = cited_map.get("gemini", 0)
    entry.perplexity_frequency = cited_map.get("perplexity", 0)
    # Overall score: 0-100 from engine-cited count (0/1/2/3 engines)
    engines_cited = entry.engines_cited_count
    entry.overall_score = {0: 10, 1: 40, 2: 70, 3: 95}.get(engines_cited, 0)
    entry.queries_log = queries_log
    entry.last_checked_at = timezone.now()
    if any(v for v in cited_map.values()) or any(not q.get("skipped") for q in queries_log):
        entry.status = AEOIndexEntry.Status.COMPLETED
    else:
        entry.status = AEOIndexEntry.Status.FAILED
    entry.save()
    return entry
