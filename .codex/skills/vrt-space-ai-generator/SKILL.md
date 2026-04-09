---
name: vrt-space-ai-generator
description: AI content generation guidance for VRT SPACE AGENCY. Use when building content generators, prompt templates, structured copy services, metadata generators, or workflows that turn business context plus SEO and AEO data into reusable page content. Trigger for generated service pages, landing pages, answer blocks, editorial scaffolds, and AI-assisted content operations.
---

# VRT Space AI Generator

Use this skill when the task is not just writing content manually, but building the system that generates or structures that content.

## Generator Workflow

1. Read `../../../04_SEO_AEO_ENGINE.md` and `../../../05_CONTENT_SYSTEM.md` to keep output rankable and citation-friendly.
2. Read `../../../14_AI_VISIBILITY_SYSTEM.md` when the output must be easy for AI systems to quote.
3. Read `../../../06_DATA_MODELS.md` and `../../../07_API_LAYER.md` before adding storage, APIs, or generation endpoints.
4. Use `../../../prompts/seo_context_engine.md` and `../../../prompts/aeo_engine.md` when generation needs industry, location, or AI-answer context.
5. Keep generation logic in services, templates in reusable modules, and publishing concerns separate from draft generation.

## Current Repo Reality

- There is no dedicated content-generator app yet.
- Most current marketing copy is assembled from `apps/core/site_content.py`.
- Search and audit intelligence already exists in the project, so generation should eventually consume structured audit and context data instead of freeform prompts alone.

## Required Output Shape

- Start from business context: industry, location, goal, offer.
- Produce answer-first structures, not generic long-form filler.
- Include title, meta description, headings, FAQ candidates, summary, and CTA when relevant.
- Keep output modular so sections can be edited, reordered, or reused in templates and dashboards.
- Validate keyword coverage, internal-link opportunities, and duplication risk before treating output as done.

## Build Rules

- Prefer deterministic templates plus controlled prompt inputs over open-ended generation.
- Persist generated drafts separately from published content.
- Keep SEO and AEO metadata explicit in the output contract.
- Avoid any generator that produces generic copy with no local or commercial context.
- If a generator consumes audit signals, store raw signals separately from generated recommendations.

## Delivery Checklist

- Confirm the generator has enough context to avoid generic output.
- Confirm the response contract includes structured fields, not just a blob of text.
- Confirm service code can support landing pages, service pages, blog articles, and short answer blocks.
- Confirm review and editing hooks exist before publication.
- Confirm generated copy still reinforces the VRT method and commercial positioning.

## References

- `../../../04_SEO_AEO_ENGINE.md`: SEO and AEO structure rules
- `../../../05_CONTENT_SYSTEM.md`: content-type requirements
- `../../../06_DATA_MODELS.md`: storage guidance for generated artifacts
- `../../../07_API_LAYER.md`: endpoint and JSON contract guidance
- `../../../14_AI_VISIBILITY_SYSTEM.md`: AI-citation goals
- `../../../16_PROPRIETARY_METHOD.md`: VRT naming and differentiation
- `../../../prompts/seo_context_engine.md`: context-aware recommendation direction
- `../../../prompts/aeo_engine.md`: AI visibility and answer-shape direction
