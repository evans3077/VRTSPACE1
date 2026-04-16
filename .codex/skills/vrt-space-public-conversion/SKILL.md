---
name: vrt-space-public-conversion
description: Public-site conversion guidance for the VRT SPACE revamp. Use when editing `templates/core/`, `templates/base.html`, hero copy, CTA structure, navigation, pricing presentation, public audit forms, trust sections, or any public UI that must stay simple, premium, and focused on Audit, SEO, and AEO.
---

# VRT Space Public Conversion

Use this skill when reshaping how first-time visitors understand and act on the product.

## Workflow

1. Read `references/public-revamp-brief.md` before changing homepage structure or messaging.
2. Read `references/current-public-surface.md` before editing templates so the simplification work stays grounded in the live implementation.
3. Edit public surfaces in this order: navigation, hero, module explanation, trust/proof, final CTA.

## Primary Hotspots

- `templates/base.html`
- `templates/core/home.html`
- `templates/core/services.html`
- `templates/core/service_detail.html`
- `templates/core/packages.html`
- `apps/core/views.py`
- `apps/core/site_content.py`

## Public Rules

- Keep only Audit, SEO, and AEO as first-class public modules.
- Use one dominant CTA family such as start audit, analyze website, or create workspace.
- Prefer outcome copy over system jargon.
- Make the audit form feel low-friction and progressively reveal extra context.
- Keep trust sections believable and concise.
- Keep custom work secondary to the product story.

## Layout Requirements

- Hero: one promise, one short support line, one primary CTA
- Explanation section: why website visibility problems matter
- Three-module section: Audit, SEO, AEO only
- Process section: simple path from scan to progress
- Trust or proof section: light, credible evidence
- Final CTA: repeat the same main action cleanly

## Review Checklist

- Is the page easier to scan in under 10 seconds?
- Are there fewer competing actions than before?
- Does the copy tell the user what they get, not just what the platform has?
- Does mobile keep the same clarity as desktop?
- Does the public surface avoid exposing internal complexity too early?

## References

- `references/public-revamp-brief.md`: target structure and messaging rules
- `references/current-public-surface.md`: current public implementation and blockers
- `../../../prompts/new/Vrt Space Agency Codex Master Instructions.md`
- `../../../prompts/new/Vrt Space Agency Codex Implementation Guide.md`
- `../../../new_plan2.md`
