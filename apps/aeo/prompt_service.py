"""
TrackedPrompt + share-of-voice service layer.

Public functions:
- run_prompt_check(prompt, engines=None) -> list[PromptCheckRun]
- run_all_active(project) -> dict summary
- compute_share_of_voice(project, days=30) -> dict for chart rendering
- get_prompt_trend(prompt, engine, days=30) -> list of points
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.aeo.models import (
    AEOAudit,
    PromptCheckRun,
    TrackedCompetitor,
    TrackedPrompt,
    VisibilitySnapshot,
)
from apps.aeo.simulator import (
    ENGINE_PROFILES,
    build_competitor_features,
    derive_target_features,
    simulate_prompt_check,
)


DEFAULT_ENGINES = (
    VisibilitySnapshot.Engine.CHATGPT,
    VisibilitySnapshot.Engine.GEMINI,
    VisibilitySnapshot.Engine.PERPLEXITY,
)


@transaction.atomic
def run_prompt_check(prompt: TrackedPrompt, engines: Iterable[str] | None = None) -> list[PromptCheckRun]:
    """Run one prompt across the requested engines, returning persisted PromptCheckRuns."""
    project = prompt.project
    engines = list(engines) if engines else list(DEFAULT_ENGINES)

    latest_audit = getattr(project, "latest_audit_run", None)
    latest_aeo = (
        AEOAudit.objects.filter(project=project).order_by("-created_at").first()
    )
    target_features = derive_target_features(audit_run=latest_audit, aeo_audit=latest_aeo)
    if not target_features.label or target_features.label == "Your Site":
        target_features.label = project.name or target_features.domain or "Your Site"

    competitors = list(
        TrackedCompetitor.objects.filter(project=project, is_active=True)
    )
    competitor_features = [build_competitor_features(c) for c in competitors]

    runs: list[PromptCheckRun] = []
    voice_tally = 0
    cited_engines = 0
    for engine in engines:
        result = simulate_prompt_check(
            prompt_text=prompt.prompt,
            engine=engine,
            target=target_features,
            competitors=competitor_features,
        )
        run = PromptCheckRun.objects.create(
            prompt=prompt,
            engine=engine,
            target_cited=result["target_cited"],
            target_position=result["target_position"],
            citation_score=result["citation_score"],
            answer_snippet=result["answer_snippet"],
            cited_brands=result["cited_brands"],
            competitor_brands=result["competitor_brands"],
            sentiment=result["sentiment"],
            raw_signals=result["raw_signals"],
        )
        runs.append(run)
        if result["target_cited"]:
            cited_engines += 1
            voice_tally += 100 - (result["target_position"] or 1) * 12

    prompt.last_checked_at = timezone.now()
    prompt.last_target_cited = cited_engines > 0
    prompt.last_share_of_voice = (
        round(voice_tally / max(cited_engines, 1)) if cited_engines else 0
    )
    prompt.save(update_fields=("last_checked_at", "last_target_cited", "last_share_of_voice", "updated_at"))
    return runs


def run_all_active(project) -> dict:
    """Run all active tracked prompts for a project."""
    prompts = list(TrackedPrompt.objects.filter(project=project, is_active=True))
    total_runs = 0
    cited_count = 0
    for prompt in prompts:
        runs = run_prompt_check(prompt)
        total_runs += len(runs)
        cited_count += sum(1 for r in runs if r.target_cited)
    return {
        "prompts": len(prompts),
        "runs_created": total_runs,
        "citations": cited_count,
    }


def compute_share_of_voice(project, days: int = 30) -> dict:
    """
    Aggregate share-of-voice across all tracked prompts and engines.

    Returns:
      {
        "window_days": 30,
        "total_checks": int,
        "target_label": str,
        "engines": [{"engine": "chatgpt", "label": "ChatGPT", "color": "...",
                     "target_cited_pct": int, "leaderboard": [...]}, ...],
        "leaderboard": [{"label": str, "is_target": bool, "share_pct": int,
                         "color": str, "appearances": int}],
        "weekly_trend": [{"week": "2026-W18", "target_pct": int, "competitor_pct": int}],
      }
    """
    since = timezone.now() - timedelta(days=days)
    runs = (
        PromptCheckRun.objects
        .filter(prompt__project=project, created_at__gte=since)
        .select_related("prompt")
    )

    target_label = project.name or (project.normalized_domain or "Your Site")

    competitor_records = {
        c.brand_name: c for c in TrackedCompetitor.objects.filter(project=project)
    }

    total_checks = runs.count()
    if total_checks == 0:
        return {
            "window_days": days,
            "total_checks": 0,
            "target_label": target_label,
            "engines": [],
            "leaderboard": [],
            "weekly_trend": [],
            "has_data": False,
        }

    # Tally appearances per brand globally and per engine
    engine_buckets: dict[str, dict] = {}
    global_tally: dict[str, dict] = defaultdict(lambda: {"appearances": 0, "is_target": False, "color": "#475569"})

    for run in runs:
        bucket = engine_buckets.setdefault(
            run.engine,
            {"total": 0, "target_hits": 0, "tally": defaultdict(lambda: {"appearances": 0, "is_target": False, "color": "#475569"})},
        )
        bucket["total"] += 1
        if run.target_cited:
            bucket["target_hits"] += 1

        for cited in run.cited_brands or []:
            label = cited.get("label") or "Unknown"
            is_target = bool(cited.get("is_target"))
            color = "#38bdf8" if is_target else competitor_records.get(label).color if competitor_records.get(label) else "#818cf8"
            bucket["tally"][label]["appearances"] += 1
            bucket["tally"][label]["is_target"] = is_target
            bucket["tally"][label]["color"] = color
            global_tally[label]["appearances"] += 1
            global_tally[label]["is_target"] = is_target
            global_tally[label]["color"] = color

    # Engine breakdowns
    engines_out = []
    for engine_key, bucket in engine_buckets.items():
        profile = ENGINE_PROFILES.get(engine_key, {})
        total_appearances = sum(v["appearances"] for v in bucket["tally"].values()) or 1
        leaderboard = sorted(
            bucket["tally"].items(),
            key=lambda pair: pair[1]["appearances"],
            reverse=True,
        )[:6]
        engines_out.append({
            "engine": engine_key,
            "label": profile.get("label", engine_key.title()),
            "color": profile.get("color", "#818cf8"),
            "total_checks": bucket["total"],
            "target_cited_pct": round(100 * bucket["target_hits"] / bucket["total"]) if bucket["total"] else 0,
            "leaderboard": [
                {
                    "label": label,
                    "appearances": data["appearances"],
                    "share_pct": round(100 * data["appearances"] / total_appearances),
                    "is_target": data["is_target"],
                    "color": data["color"],
                }
                for label, data in leaderboard
            ],
        })

    # Global leaderboard
    global_total = sum(v["appearances"] for v in global_tally.values()) or 1
    leaderboard_out = [
        {
            "label": label,
            "appearances": data["appearances"],
            "share_pct": round(100 * data["appearances"] / global_total),
            "is_target": data["is_target"],
            "color": data["color"],
        }
        for label, data in sorted(global_tally.items(), key=lambda p: -p[1]["appearances"])
    ][:8]

    # Weekly trend (target vs all-competitors)
    week_tally: dict[str, dict[str, int]] = defaultdict(lambda: {"target": 0, "competitor": 0, "total": 0})
    for run in runs:
        week_key = run.created_at.strftime("%Y-W%V")
        bucket = week_tally[week_key]
        bucket["total"] += 1
        if run.target_cited:
            bucket["target"] += 1
        else:
            bucket["competitor"] += 1
    weekly_trend = [
        {
            "week": week,
            "target_pct": round(100 * data["target"] / data["total"]) if data["total"] else 0,
            "competitor_pct": round(100 * data["competitor"] / data["total"]) if data["total"] else 0,
            "checks": data["total"],
        }
        for week, data in sorted(week_tally.items())
    ]

    return {
        "window_days": days,
        "total_checks": total_checks,
        "target_label": target_label,
        "engines": engines_out,
        "leaderboard": leaderboard_out,
        "weekly_trend": weekly_trend,
        "has_data": True,
    }


def get_prompt_trend(prompt: TrackedPrompt, days: int = 90) -> dict:
    """Return time-series citation data for one prompt across all engines."""
    since = timezone.now() - timedelta(days=days)
    runs = (
        PromptCheckRun.objects.filter(prompt=prompt, created_at__gte=since)
        .order_by("created_at")
    )
    engines: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        engines[run.engine].append({
            "at": run.created_at.isoformat(),
            "cited": run.target_cited,
            "position": run.target_position,
            "score": run.citation_score,
            "snippet": run.answer_snippet[:200],
        })

    series = []
    for engine_key, profile in ENGINE_PROFILES.items():
        points = engines.get(engine_key, [])
        if not points:
            continue
        latest = points[-1] if points else {}
        series.append({
            "engine": engine_key,
            "label": profile["label"],
            "color": profile["color"],
            "points": points,
            "latest_cited": latest.get("cited", False),
            "latest_position": latest.get("position"),
            "latest_score": latest.get("score", 0),
            "checks": len(points),
        })
    return {
        "prompt": prompt.prompt,
        "intent": prompt.get_intent_display(),
        "window_days": days,
        "series": series,
    }


def get_competitor_summary(project) -> list[dict]:
    """List active competitors with their last 30d appearance counts."""
    since = timezone.now() - timedelta(days=30)
    competitors = list(TrackedCompetitor.objects.filter(project=project, is_active=True))
    if not competitors:
        return []
    runs = PromptCheckRun.objects.filter(
        prompt__project=project, created_at__gte=since
    )
    counts: dict[str, int] = defaultdict(int)
    for run in runs:
        for label in run.competitor_brands or []:
            counts[label] += 1
    return [
        {
            "id": c.pk,
            "brand_name": c.brand_name,
            "domain": c.domain,
            "color": c.color,
            "appearances_30d": counts.get(c.brand_name, 0),
            "is_active": c.is_active,
        }
        for c in competitors
    ]
