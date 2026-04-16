---
name: vrt-space-product-strategy
description: Product-strategy guardrail for the VRT SPACE revamp. Use when changing homepage scope, navigation, pricing or positioning, public module visibility, product story, or any decision that must keep the platform focused on Audit, SEO, AEO, workspace value, credits, reruns, and the Audit to SEO to AEO to Workspace loop.
---

# VRT Space Product Strategy

Use this skill to keep revamp work aligned with the product story before changing code or copy.

## Workflow

1. Read `references/revamp-direction.md` for the intended SaaS direction from `prompts/new`.
2. Read `references/current-product-reality.md` to separate what already exists from what should only be presented selectively.
3. Use this skill first for scope decisions, then pair it with `vrt-space-frontend`, `vrt-space-ui-system`, `vrt-space-billing`, or `vrt-space-automation` for implementation.

## Core Guardrails

- Keep the public story centered on Audit, SEO, and AEO.
- Treat workspace, credits, reruns, and progress as retention mechanics, not as separate products.
- Preserve working implementation depth in SEO, AEO, content, billing, and automation, but do not expose every module equally in the public surface.
- Prefer simplification, sequencing, and hiding over deleting working systems.
- Reject changes that make the product feel like a portfolio site, an agency brochure, or a cluttered admin panel.

## Decision Tests

Before approving a change, answer all of these:

- Does it strengthen the Audit -> SEO -> AEO -> Workspace -> Rerun -> Progress loop?
- Does it help a first-time visitor understand the value faster?
- Does it improve conversion, retention, or credibility without adding avoidable complexity?
- Does it keep the public scope tighter than the internal system scope?
- Does it preserve the Django monolith and service-layer patterns already used in the repo?

## Use This Lens On

- `templates/base.html`
- `templates/core/*.html`
- `apps/core/views.py`
- `apps/core/site_content.py`
- pricing, CTA, and navigation changes
- any roadmap decision that changes what the product appears to be

## References

- `references/revamp-direction.md`: prompt-pack direction for the focused SaaS story
- `references/current-product-reality.md`: current implementation and revamp implications
- `../../../prompts/new/Vrt Space Agency Codex Master Instructions.md`
- `../../../prompts/new/Vrt Space Agency Codex Implementation Guide.md`
- `../../../prompts/new/Vrt Space Agency Codex Skills Pack.MD`
- `../../../plan.md`
