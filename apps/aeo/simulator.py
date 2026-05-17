"""
Deterministic AI citation simulator.

Without API keys, we still want realistic, consistent citation results so
agencies can demo VRT SPACE and customers can pilot the prompt tracker.

The simulator is deterministic: same (prompt, engine, target_domain) always
produces the same result. When API keys are configured, swap _simulate_engine
for a real LLM call — the rest of the pipeline stays identical.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, asdict
from typing import Iterable

from apps.aeo.models import VisibilitySnapshot


# Engine personality weights. Each engine values different signals.
ENGINE_PROFILES = {
    VisibilitySnapshot.Engine.CHATGPT: {
        "label": "ChatGPT",
        "color": "#10a37f",
        "values": {"faq": 18, "freshness": 8, "schema": 10, "authority": 14, "depth": 6, "local": 4},
        "answer_style": "structured, FAQ-friendly",
    },
    VisibilitySnapshot.Engine.GEMINI: {
        "label": "Gemini",
        "color": "#4285f4",
        "values": {"faq": 6, "freshness": 6, "schema": 18, "authority": 8, "depth": 6, "local": 16},
        "answer_style": "knowledge-graph weighted, schema-heavy",
    },
    VisibilitySnapshot.Engine.PERPLEXITY: {
        "label": "Perplexity",
        "color": "#a855f7",
        "values": {"faq": 6, "freshness": 12, "schema": 6, "authority": 18, "depth": 16, "local": 4},
        "answer_style": "citation-driven, source-rich",
    },
}


@dataclass
class BrandFeatures:
    """The feature vector the simulator scores against."""
    domain: str
    label: str
    faq: int = 50            # 0..100 — FAQ schema strength
    freshness: int = 50      # 0..100 — recent content cadence
    schema: int = 50         # 0..100 — JSON-LD coverage
    authority: int = 50      # 0..100 — backlink/brand strength
    depth: int = 50          # 0..100 — average content depth
    local: int = 50          # 0..100 — local entity match
    is_target: bool = False


def _seed_for(prompt: str, engine: str, domain: str) -> int:
    raw = f"{prompt}::{engine}::{domain}".lower()
    return int(hashlib.sha256(raw.encode()).hexdigest()[:12], 16)


def _engine_score(features: BrandFeatures, engine: str, rng: random.Random) -> int:
    """Composite score 0..100 for one brand on one engine for one prompt."""
    weights = ENGINE_PROFILES[engine]["values"]
    raw = (
        features.faq * weights["faq"]
        + features.freshness * weights["freshness"]
        + features.schema * weights["schema"]
        + features.authority * weights["authority"]
        + features.depth * weights["depth"]
        + features.local * weights["local"]
    ) / sum(weights.values())
    # Add small noise so prompts vary against each other
    raw += rng.uniform(-6, 6)
    return max(0, min(100, round(raw)))


def _generate_snippet(prompt: str, brand_label: str, engine: str, rng: random.Random) -> str:
    """A plausible answer snippet that mentions the cited brand."""
    starters = [
        f"For {prompt.rstrip('?').lower()}, {brand_label} is frequently recommended as a leading option.",
        f"{brand_label} stands out when comparing solutions for {prompt.rstrip('?').lower()}.",
        f"When users ask about {prompt.rstrip('?').lower()}, {brand_label} appears across credible sources.",
        f"{brand_label} is cited as a reliable answer to '{prompt.rstrip('?')}'.",
    ]
    closers = {
        VisibilitySnapshot.Engine.CHATGPT: " It is most often surfaced when the question is phrased as a how-to or comparison.",
        VisibilitySnapshot.Engine.GEMINI: " The knowledge panel reinforces the recommendation with schema-backed entity data.",
        VisibilitySnapshot.Engine.PERPLEXITY: " Linked citations point to in-depth content with verifiable facts.",
    }
    return rng.choice(starters) + closers.get(engine, "")


def _generate_no_cite_reason(prompt: str, engine: str, rng: random.Random) -> str:
    options = {
        VisibilitySnapshot.Engine.CHATGPT: [
            "No FAQ schema match — answer was synthesised from competitors.",
            "Insufficient direct-answer paragraph found on the target domain.",
            "Competing brand owns the canonical answer surface for this prompt.",
        ],
        VisibilitySnapshot.Engine.GEMINI: [
            "Local entity signals favour another brand for this query.",
            "Knowledge panel sources another domain — schema gap on target.",
            "Insufficient JSON-LD structured data on the matching page.",
        ],
        VisibilitySnapshot.Engine.PERPLEXITY: [
            "Authority signals (citations + depth) favoured competitor sources.",
            "Pages under 600 words — Perplexity sourced from deeper competitors.",
            "Missing inline source citations on the target's content.",
        ],
    }
    return rng.choice(options.get(engine, ["Citation gap — competitor owns this answer."]))


def derive_target_features(audit_run=None, aeo_audit=None) -> BrandFeatures:
    """Build a BrandFeatures vector from the workspace's last audit + AEO score."""
    domain = ""
    label = "Your Site"
    if audit_run:
        domain = audit_run.normalized_domain or ""
        label = domain or label
    elif aeo_audit and getattr(aeo_audit, "project", None):
        domain = (aeo_audit.project.normalized_domain or "").lower()
        label = aeo_audit.project.name or domain or label

    feat = BrandFeatures(domain=domain, label=label, is_target=True)

    if audit_run:
        pages = list(audit_run.pages.all()[:15])
        has_faq = any(p.has_faq_schema for p in pages)
        has_schema = any((p.schema_count or 0) > 0 for p in pages)
        avg_wc = sum((p.word_count or 0) for p in pages) / max(len(pages), 1)
        feat.faq = 80 if has_faq else 35
        feat.schema = 75 if has_schema else 35
        feat.depth = min(100, round(avg_wc / 8))
        feat.authority = min(100, 35 + (audit_run.overall_score or 0) // 2)
        feat.freshness = 55
        feat.local = 60 if audit_run.summary.get("location") else 45

    if aeo_audit:
        # Bias by overall AEO score so simulator results reflect the real audit
        feat.authority = min(100, max(feat.authority, aeo_audit.overall_score or 0))
        feat.depth = min(100, max(feat.depth, aeo_audit.completeness_score or 0))
        feat.schema = max(feat.schema, aeo_audit.structure_score or 0)

    return feat


def build_competitor_features(competitor, rng: random.Random | None = None) -> BrandFeatures:
    """Generate a stable feature vector for a TrackedCompetitor."""
    rng = rng or random.Random(_seed_for("__features__", "competitor", competitor.brand_name))
    return BrandFeatures(
        domain=competitor.domain or "",
        label=competitor.brand_name,
        faq=rng.randint(30, 90),
        freshness=rng.randint(35, 85),
        schema=rng.randint(40, 90),
        authority=rng.randint(35, 95),
        depth=rng.randint(40, 90),
        local=rng.randint(20, 90),
        is_target=False,
    )


def simulate_prompt_check(
    *,
    prompt_text: str,
    engine: str,
    target: BrandFeatures,
    competitors: Iterable[BrandFeatures],
) -> dict:
    """
    Run a deterministic simulation for one (prompt, engine) pair.

    Returns a dict matching the shape PromptCheckRun expects.
    """
    rng = random.Random(_seed_for(prompt_text, engine, target.domain or target.label))
    competitors = list(competitors)

    all_brands = [target] + competitors
    scored = [(b, _engine_score(b, engine, rng)) for b in all_brands]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    # Citation threshold varies per engine
    threshold = {
        VisibilitySnapshot.Engine.CHATGPT: 60,
        VisibilitySnapshot.Engine.GEMINI: 62,
        VisibilitySnapshot.Engine.PERPLEXITY: 64,
    }.get(engine, 60)

    cited = [(b, s) for b, s in scored if s >= threshold][:5]

    target_cited = any(b.is_target for b, _ in cited)
    target_position = None
    target_score = next((s for b, s in scored if b.is_target), 0)
    if target_cited:
        for idx, (brand, _) in enumerate(cited, start=1):
            if brand.is_target:
                target_position = idx
                break

    cited_brands = [
        {"label": b.label, "domain": b.domain, "score": s, "is_target": b.is_target}
        for b, s in cited
    ]
    competitor_brands = [b.label for b, _ in cited if not b.is_target]

    if target_cited:
        winning_brand = next(b for b, _ in cited if b.is_target)
        snippet = _generate_snippet(prompt_text, winning_brand.label, engine, rng)
        sentiment = "positive"
    else:
        if cited:
            winning_brand = cited[0][0]
            snippet = _generate_snippet(prompt_text, winning_brand.label, engine, rng)
        else:
            snippet = _generate_no_cite_reason(prompt_text, engine, rng)
        sentiment = "neutral"

    return {
        "engine": engine,
        "target_cited": target_cited,
        "target_position": target_position,
        "citation_score": target_score,
        "answer_snippet": snippet,
        "cited_brands": cited_brands,
        "competitor_brands": competitor_brands,
        "sentiment": sentiment,
        "raw_signals": {
            "threshold": threshold,
            "engine_label": ENGINE_PROFILES[engine]["label"],
            "engine_color": ENGINE_PROFILES[engine]["color"],
        },
    }
