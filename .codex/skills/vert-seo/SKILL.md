---
name: vert-seo
description: SEO and AEO implementation guidance for the VRT SPACE repo. Use when changing Django templates, views, page data, metadata, schema, internal links, robots or sitemap behavior, canonical tags, Open Graph or Twitter tags, indexation rules, or AI-citable content structure. Trigger for public marketing pages, report or share pages, auth pages that need crawl decisions, and any change that affects crawlability, ranking, answer-engine visibility, or snippet and social-share quality.
---

# vert_seo

Use this skill when a change can alter how a page is crawled, indexed, shared, summarized, or cited.

## Workflow

1. Read `references/change-plan.md`.
2. Classify the route before editing:
   - `indexable-marketing`: home, services, case studies, articles, landing pages.
   - `indexable-programmatic`: public pages that are intentionally meant to rank, be shared, or be cited.
   - `utility-or-private`: login, signup, workspace, exports, temporary states, gated pages.
3. Trace the full render path:
   - URL pattern
   - view or context builder
   - page data source
   - template
   - shared head tags in `../../../templates/base.html`
4. Set explicit SEO context in the view or page-data source. Do not rely on generic fallback metadata for public routes.
5. Match schema, heading structure, summary blocks, and internal links to the page intent.
6. Compare the result against the repo's own audit heuristics in `../../../apps/tools/services.py` before finishing.

## Repo Rules

- Every indexable page must ship with:
  - unique `page_title`
  - unique `meta_description`
  - canonical URL
  - explicit social metadata
  - matching schema
  - meaningful internal links
- Every utility or private page must ship with an explicit crawl decision.
  - Default to `noindex, nofollow` unless there is a real reason to expose it.
- Keep metadata close to the page source.
  - Static marketing pages: set it in the view or page-data object.
  - Model-backed or generated pages: store it in the model or service layer and pass it through consistently.
- Do not leave public routes on the fallback metadata in `../../../templates/base.html`.
- If visible content includes direct Q and A or FAQ blocks, consider `FAQPage` schema only when the page truly supports it.
- If a page is meant to be AI-citable, front-load the answer, use entity-rich phrasing, and keep headings scannable.

## Implementation Pattern

- Extend `../../../templates/base.html` instead of duplicating head markup in individual templates.
- Prefer these context keys when relevant:
  - `page_title`
  - `meta_description`
  - `canonical_url`
  - `meta_robots`
  - `og_title`
  - `og_description`
  - `og_type`
  - `twitter_card`
  - `schema_json`
- When adding a new public route, handle robots and sitemap implications in the same change if the page is indexable.
- When adding a new page type, preserve the metadata contract for existing pages instead of introducing one-off template logic.

## AEO Lens

Ask these questions before shipping:

- Can an AI system quote the opening answer cleanly?
- Does the heading stack match the real user intent?
- Does the schema reflect what is visibly on the page?
- Does the page have enough context to be summarized without guessing?

Strengthen pages with:

- direct answers near the top
- concise proof or supporting context
- FAQ or summary blocks when justified by the content
- internal links to adjacent authority pages

## Validation

Before finishing:

- Check the rendered page against the parser expectations in `../../../apps/tools/services.py`.
- Confirm title length and meta-description quality are reasonable.
- Confirm canonical, schema, OG data, `lang`, and viewport are present where expected.
- Confirm utility and private pages are intentionally non-indexable.
- Confirm new internal links reinforce the intended pillar and cluster structure.
- Run targeted tests if view logic, metadata assembly, or page data changed.

## References

- `references/change-plan.md`: execution plan and definition of done
- `../../../04_SEO_AEO_ENGINE.md`: repo SEO and AEO rule source
- `../../../15_AGENT_RULEBOOK.md`: hard gate for every page
- `../../../apps/tools/services.py`: audit heuristics already enforced by the product
