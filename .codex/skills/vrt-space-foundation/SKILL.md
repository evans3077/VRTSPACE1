---
name: vrt-space-foundation
description: Project foundation for VRT SPACE AGENCY. Use when planning features, reviewing architecture, naming or applying the proprietary method, validating work against project rules, or deciding how a new page or feature should fit the platform. Trigger for roadmap work, architecture decisions, project-wide reviews, and any task that must align with the Django monolith, performance-first standards, SEO/AEO requirements, and reusable/testable/scalable code.
---

# VRT Space Foundation

Use this skill to keep implementation aligned with the project brief before writing or reviewing code.

## Core Workflow

1. Read `references/00_PROJECT_OVERVIEW.md` to confirm the business goal: rank, generate inbound leads, and become a cited AI source.
2. Read `references/01_SYSTEM_ARCHITECTURE.md` before changing structure. Keep the Django monolith and modular app layout.
3. Read `references/17_CURRENT_BUILD_STATUS.md` to separate what is already implemented from what is still only planned.
4. Apply `references/15_AGENT_RULEBOOK.md` as a hard gate for every implementation and review.
5. Use `references/16_PROPRIETARY_METHOD.md` whenever service copy, lead magnets, or conversion sections need a named differentiator.
6. Use `references/overview.md` for deeper blueprint details such as site sections, pillar clusters, schema usage, and conversion patterns.

## Non-Negotiables

- Keep the stack strict: Django, PostgreSQL, Redis, Celery, and Cloudflare.
- Keep architecture stable. Do not add a separate frontend framework unless the project requirements change explicitly.
- Treat every page as a three-part system: it must load fast, rank, and convert.
- Reject shortcuts that introduce duplication, untested code, fat views, or weak SEO metadata.
- Preserve AI-citable content structure and the proprietary VRT method in user-facing materials.
- Treat files in `prompts/` as future-product direction unless the codebase already proves the feature exists.

## Current Build Lens

- The repo already has a marketing site, service architecture, lead capture, and a meaningful public audit engine.
- The repo does not yet have a finished billing layer, automation layer, customer dashboard, or AI content-generator product.
- Prefer strengthening the implemented core before spreading work across too many new systems at once.

## Review Checklist

- Confirm the change fits one of the planned app domains.
- Confirm the page or feature improves authority, lead capture, or AI visibility.
- Confirm SEO metadata, schema, and internal-link implications are handled.
- Confirm the change has a performance and testing path.
- Confirm naming and copy reinforce VRT SPACE AGENCY rather than generic agency language.

## References

- `references/00_PROJECT_OVERVIEW.md`: purpose, outcomes, differentiator
- `references/01_SYSTEM_ARCHITECTURE.md`: required stack and app layout
- `references/17_CURRENT_BUILD_STATUS.md`: implemented now vs planned next
- `references/15_AGENT_RULEBOOK.md`: hard delivery rules
- `references/16_PROPRIETARY_METHOD.md`: named methodology requirement
- `references/overview.md`: expanded website and content blueprint
- `references/structure.md`: original document map
