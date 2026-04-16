---
name: vrt-space-data-api
description: Data-model, API, and analytics guidance for VRT SPACE AGENCY. Use when defining Django models, SEO fields, JSON endpoints, tool backends, calculators, audit request flows, serializers, event schemas, or reporting contracts. Trigger for schema changes, API implementation, analytics design, and any task that must keep SEO metadata and frontend-support APIs consistent.
---

# VRT Space Data and API

Use this skill to keep structured data, APIs, and analytics consistent across the platform.

## Modeling Workflow

1. Read `references/06_DATA_MODELS.md` before creating or changing persistent models.
2. Read `references/07_API_LAYER.md` before exposing JSON endpoints or powering tools.
3. Read `references/13_ANALYTICS_TRACKING.md` when adding events, dashboards, or reporting hooks.
4. Preserve SEO support fields on every content-like model.

## Required Data Rules

- Keep `Service`, `CaseStudy`, `Article`, `Lead`, `AuditRequest`, and `FAQ` as first-class concepts.
- Include `meta_title`, `meta_description`, and `schema_json` on models that render indexable pages.
- Validate all API inputs and apply rate limiting to public endpoints.
- Favor lightweight JSON views unless DRF provides clear leverage.

## Analytics Rules

- Track traffic, conversions, scroll depth, and CTA clicks.
- Keep event names and payloads stable enough for dashboards.
- Design APIs to support frontend interactions and internal tools without exposing unnecessary fields.

## References

- `references/06_DATA_MODELS.md`: core domain models and SEO fields
- `references/07_API_LAYER.md`: API-purpose and safety rules
- `references/13_ANALYTICS_TRACKING.md`: metrics and tooling expectations
