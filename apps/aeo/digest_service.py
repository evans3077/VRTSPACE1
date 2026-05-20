"""
Weekly AI Visibility digest builder.

For a given ClientProject, computes deltas over the trailing 7 days vs.
the prior 7 days and returns a context dict ready for the email template.

Pure function — no side effects. The actual email send happens via the
management command (process_weekly_digests).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.aeo.models import AEOAudit, PromptCheckRun, TrackedPrompt
from apps.aeo.simulator import ENGINE_PROFILES


def build_weekly_digest(project) -> dict:
    """
    Build a digest payload for a single project.

    Returns:
        {
            "project": <ClientProject>,
            "domain": str,
            "has_data": bool,
            "aeo_score": int,
            "aeo_score_delta": int,           # this week - last week
            "aeo_score_arrow": "up"/"down"/"flat",
            "checks_this_week": int,
            "checks_last_week": int,
            "citations_this_week": int,
            "citations_last_week": int,
            "citation_delta": int,
            "share_pct_this_week": int,       # % of checks where target was cited
            "share_pct_last_week": int,
            "share_pct_delta": int,
            "new_wins": [<prompt strings>],   # prompts cited THIS week but not LAST week
            "new_losses": [<prompt strings>], # prompts cited LAST week but not THIS week
            "top_prompts": [{"prompt", "share_pct", "engines"}],
            "biggest_opportunity": {"prompt", "score", "gap"} | None,
            "engine_breakdown": [{"engine", "label", "color", "cited_pct"}],
            "tracked_prompt_count": int,
            "tracked_competitor_count": int,
            "period_start": <date>,
            "period_end": <date>,
        }
    """
    now = timezone.now()
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    runs_this = PromptCheckRun.objects.filter(
        prompt__project=project,
        created_at__gte=this_week_start,
    )
    runs_last = PromptCheckRun.objects.filter(
        prompt__project=project,
        created_at__gte=last_week_start,
        created_at__lt=this_week_start,
    )

    checks_this = runs_this.count()
    checks_last = runs_last.count()
    cited_this = runs_this.filter(target_cited=True).count()
    cited_last = runs_last.filter(target_cited=True).count()
    citation_delta = cited_this - cited_last

    share_this = round(100 * cited_this / checks_this) if checks_this else 0
    share_last = round(100 * cited_last / checks_last) if checks_last else 0
    share_delta = share_this - share_last

    # AEO audit delta — compare latest audit's score to the one ~7 days older
    aeo_qs = AEOAudit.objects.filter(project=project).order_by("-created_at")
    latest_aeo = aeo_qs.first()
    aeo_score = latest_aeo.overall_score if latest_aeo else 0
    week_ago_aeo = aeo_qs.filter(created_at__lt=this_week_start).first()
    aeo_score_delta = (
        aeo_score - week_ago_aeo.overall_score if week_ago_aeo else 0
    )
    if aeo_score_delta > 0:
        aeo_arrow = "up"
    elif aeo_score_delta < 0:
        aeo_arrow = "down"
    else:
        aeo_arrow = "flat"

    # Per-prompt aggregation — what was cited this week vs last
    def _aggregate(runs_qs):
        per_prompt: dict[str, dict] = defaultdict(
            lambda: {"checks": 0, "cited": 0, "engines": set()}
        )
        for run in runs_qs.select_related("prompt"):
            key = run.prompt.prompt
            per_prompt[key]["checks"] += 1
            if run.target_cited:
                per_prompt[key]["cited"] += 1
                per_prompt[key]["engines"].add(run.engine)
        return per_prompt

    agg_this = _aggregate(runs_this)
    agg_last = _aggregate(runs_last)

    new_wins: list[str] = []
    new_losses: list[str] = []
    for prompt, data in agg_this.items():
        if data["cited"] > 0 and (
            prompt not in agg_last or agg_last[prompt]["cited"] == 0
        ):
            new_wins.append(prompt)
    for prompt, data in agg_last.items():
        if data["cited"] > 0 and (
            prompt not in agg_this or agg_this[prompt]["cited"] == 0
        ):
            new_losses.append(prompt)

    # Top 3 prompts by share-of-voice this week
    top_prompts = []
    for prompt_text, data in sorted(
        agg_this.items(),
        key=lambda pair: (
            -(pair[1]["cited"] / max(pair[1]["checks"], 1)),
            -pair[1]["cited"],
        ),
    )[:3]:
        share = (
            round(100 * data["cited"] / data["checks"]) if data["checks"] else 0
        )
        top_prompts.append({
            "prompt": prompt_text,
            "share_pct": share,
            "engines": [ENGINE_PROFILES.get(e, {}).get("label", e) for e in data["engines"]],
        })

    # Biggest opportunity — a prompt with a strong citation_score but not yet cited
    opportunity: Optional[dict] = None
    near_miss = runs_this.filter(target_cited=False).order_by("-citation_score").first()
    if near_miss and near_miss.citation_score >= 45:
        threshold = (near_miss.raw_signals or {}).get("threshold", 65)
        opportunity = {
            "prompt": near_miss.prompt.prompt,
            "score": near_miss.citation_score,
            "gap": max(0, threshold - near_miss.citation_score),
            "engine": ENGINE_PROFILES.get(near_miss.engine, {}).get("label", near_miss.engine),
        }

    # Per-engine cited percentage this week
    engine_breakdown = []
    for engine_key, profile in ENGINE_PROFILES.items():
        engine_runs = runs_this.filter(engine=engine_key)
        total = engine_runs.count()
        cited = engine_runs.filter(target_cited=True).count()
        engine_breakdown.append({
            "engine": engine_key,
            "label": profile["label"],
            "color": profile["color"],
            "cited_pct": round(100 * cited / total) if total else 0,
            "checks": total,
        })

    return {
        "project": project,
        "domain": project.normalized_domain or project.website or "your site",
        "brand_name": project.name or "your brand",
        "has_data": checks_this > 0,
        "aeo_score": aeo_score,
        "aeo_score_delta": aeo_score_delta,
        "aeo_score_arrow": aeo_arrow,
        "checks_this_week": checks_this,
        "checks_last_week": checks_last,
        "citations_this_week": cited_this,
        "citations_last_week": cited_last,
        "citation_delta": citation_delta,
        "share_pct_this_week": share_this,
        "share_pct_last_week": share_last,
        "share_pct_delta": share_delta,
        "new_wins": new_wins[:5],
        "new_losses": new_losses[:5],
        "top_prompts": top_prompts,
        "biggest_opportunity": opportunity,
        "engine_breakdown": engine_breakdown,
        "tracked_prompt_count": TrackedPrompt.objects.filter(project=project, is_active=True).count(),
        "tracked_competitor_count": project.tracked_competitors.filter(is_active=True).count() if hasattr(project, "tracked_competitors") else 0,
        "period_start": this_week_start.date(),
        "period_end": now.date(),
    }


def get_digest_recipients(project) -> list[str]:
    """Return email addresses that should receive this project's digest.

    Currently: just the project owner. Future: WorkspaceMembership opt-ins.
    """
    recipients: list[str] = []
    owner = getattr(project, "owner", None)
    if owner and owner.email:
        recipients.append(owner.email)
    return recipients
