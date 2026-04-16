# VRT SPACE Revamp Plan

This plan tracks the revamp work driven by the Markdown review, especially `prompts/new`, and separates what is already done from what still needs implementation.

## What I Reviewed

- Project structure and main Django entry points
- Public routes and templates, especially `templates/base.html` and `templates/core/home.html`
- Workspace and audit flow in `apps/tools/views.py`, `templates/tools/workspace_dashboard.html`, and `templates/tools/audit_result.html`
- Existing project docs including `plan.md`, `new_plan.md`, `new_plan2.md`, and `antigravity_plan.md`
- Prompt files in `prompts/`
- Revamp guidance in:
  - `prompts/new/Vrt Space Agency Codex Skills Pack.MD`
  - `prompts/new/Vrt Space Agency Codex Master Instructions.md`
  - `prompts/new/Vrt Space Agency Codex Implementation Guide.md`

## What Is Done

- Mapped the current product flow from homepage to audit result to workspace
- Confirmed the repo already has strong depth in Audit, SEO, AEO, workspace, billing, credits, reruns, exports, and automation
- Identified the main public-facing mismatch: the codebase is product-rich, but the public story is broader and more technical than the new revamp docs want
- Created three project-local revamp skills:
  - `.codex/skills/vrt-space-product-strategy`
  - `.codex/skills/vrt-space-public-conversion`
  - `.codex/skills/vrt-space-workspace-retention`
- Added focused reference files inside those skills so future work can reuse the prompt-pack direction without rereading every long Markdown file
- Simplified the shared public navigation in `templates/base.html` so the first-touch story centers on Audit, SEO, AEO, pricing, and the audit CTA
- Reworked `templates/core/home.html` around a clearer public journey with:
  - a tighter hero
  - a single services section
  - the existing audit form preserved
  - clearer workspace framing
  - simpler FAQs
  - custom work kept secondary
- Simplified `templates/core/services.html` so it supports the same public story instead of reintroducing heavier technical language
- Updated `apps/core/site_content.py` to support the simpler public messaging and homepage sections
- Updated `apps/core/views.py` so the main public routes now ship explicit canonical URLs, robots directives, and page schema instead of relying on generic fallback metadata
- Scoped a lighter public-shell theme to the main marketing routes so homepage, services, service-detail, and pricing pages use a white-led palette with stronger contrast while leaving workspace surfaces untouched
- Tightened the shared public navigation so it centers on Services, How It Works, Pricing, and the main audit CTA instead of carrying broader or duplicate actions
- Refactored the remaining public marketing templates so services, service detail, pricing, and auth entry pages follow the same homepage styling direction instead of older mixed card systems
- Reworked the public auth and pricing forms so they are clearer, more conversion-oriented, and visually consistent with the homepage
- Extended the light-shell handoff into the audit result view so post-audit user-facing pages stop dropping back into the older darker shell
- Refreshed the shared audit and shared SEO result/report pages so stakeholder-facing result surfaces also follow the newer light, readable result-page system
- Rebuilt the main audit result page into the newer light result-page system with clearer score hierarchy, recommendation cards, upgrade flow, and technical footprint layout
- Added a reusable white-card result-surface system inside `public/static/css/vrt-space-core.css` so authenticated SEO and AEO result pages can inherit the homepage-style clarity without forcing a full shell flip all at once
- Refactored the top result experience in `templates/seo/workspace_seo.html` so the input form, snapshot summary, refresh state, export/share actions, and discovery insight blocks are clearer, more readable, and more conversion-oriented
- Refactored the top result experience in `templates/aeo/workspace_aeo.html` so the run form, dimension-score summary, no-project / no-audit states, and citation-readiness block follow the same lighter, clearer result-page system
- Repriced the paid plans in `apps/core/plan_catalog.py` to `$59 / $149 / $349`, increased the free layer to 2 audits, added tracked-website capacity, and removed Enterprise from the public package list
- Reworked the audit policy layer in `apps/leads/billing.py` so plan capabilities, audit-run allowances, tracked-site limits, and result-depth profiles all use the current revamp rules
- Simplified the public audit intake in `templates/core/home.html` so it collects only the context needed for later SEO and AEO layers without surfacing the older noisy fields
- Updated public and workspace audit-start flows in `apps/tools/views.py` so they now check website capacity, audit limits, and credit access before creating new runs
- Added diagnosis, next-step, and captured-context objects to the audit summary in `apps/tools/recommendations.py` so the result page and later workspace layers share the same audit framing
- Rebuilt `templates/tools/audit_result.html` around a diagnosis-first, plan-aware audit experience with clearer borders, more deliberate upgrade pressure, and controlled reveal by plan
- Refined the audit result experience again so grouped issues now surface affected URLs, clearer human fix language, three-step action lists, value-aware metric colors, and a lightweight in-progress animation for the live audit state
- Updated `apps/tools/views.py` so older completed audits automatically refresh into the newer audit-summary contract when opened instead of rendering stale summary structures
- Updated account and workspace dashboard surfaces so they now show audit runs remaining and tracked-website capacity alongside credits
- Ran `python manage.py check` successfully after the changes

## Current Findings

### Public product story

- The public site should emphasize only Audit, SEO, and AEO.
- The current public shell still exposes extra modules and technical language too early.
- The public visual system was previously leaning too dark for the simplified product story, so the marketing shell now needs to stay bright, clear, and high-contrast by default.
- Uniformity matters most on the conversion path, so homepage, pricing, auth, and audit-result surfaces should feel like one connected journey rather than separate subsystems.
- Result pages are now a separate priority slice in the revamp, because post-run screens need clearer next actions, better contrast, and simpler stakeholder presentation.
- The main audit result route now aligns much better with the revamp direction than before, and the first-screen SEO and AEO result surfaces now follow that direction much more closely.
- The deeper SEO and AEO sections still contain older inline styling, so the first-screen experience is cleaner than the long-scroll detail sections for now.
- The homepage already has a workable audit CTA and a strong form base, so the revamp should simplify and tighten rather than rebuild from scratch.
- The audit now needs to act as a controlled SaaS diagnosis rather than a full technical dump: free results stay concise, Starter is meaningfully more detailed, and Growth / Authority expose the deeper layers.
- The audit result page now communicates value more clearly in the first diagnosis blocks, but the same clarity standard still needs to spread into the rest of the audit-related workspace surfaces.
- Plan policy now needs to stay consistent everywhere the user can feel it: homepage, public audit creation, workspace reruns, the result page, and the account dashboard.
- The audit intake only needs enough business context to make the next SEO and AEO layers smarter; competitor and market-detail prompts do not belong in the first public form anymore.

### Workspace product story

- The workspace already behaves much closer to the target SaaS product than the homepage does.
- Project switching, reruns, credit visibility, and command-center framing are strong foundations.
- The next retention gains should come from better cross-module summaries and clearer progress storytelling.

### Product strategy

- The revamp should hide or sequence complexity, not delete working systems.
- Custom work should remain a secondary exception path.
- Audit should stay the first wow moment and the entry point into the wider loop.

## What Is Left To Do

### Phase 1: Public simplification

- Keep refining public copy where technical language still appears on pricing and some secondary pages
- Continue reducing agency-style and platform-internals language across remaining public templates
- Review whether the homepage proof and case-study language should become even more grounded and less stylized
- Check the new light shell in-browser and tune any remaining low-contrast components or spacing mismatches in homepage cards, pricing, and service detail layouts
- Continue refactoring longer product surfaces like the full audit result detail and selected workspace-adjacent pages that still rely heavily on older inline styling
- Continue the same result-page cleanup for the remaining long-scroll detail sections in the richer SEO and AEO views where older inline styling still appears
- Return focus to the audit product surfaces and tighten the audit-specific journey now that the first-screen SEO and AEO result blocks are aligned
- Keep the audit form progressive and low-friction as future public edits continue
- Review whether anonymous public audits should later inherit a stronger account-linked limit beyond the current email/account matching behavior
- Continue tightening workspace audit, SEO, and AEO long-scroll sections so the deeper product shell matches the new audit result quality bar
- Carry the same issue grouping, recommendation clarity, and visible-progress language into the broader workspace audit surfaces after this public audit-result pass

### Phase 2: Public conversion polish

- Tighten CTA consistency across homepage, audit result, packages, and auth entry points
- Simplify `templates/core/packages.html` so pricing language matches the new public story
- Review `templates/core/service_detail.html` for the same tone and CTA consistency
- Rebalance trust, proof, and custom-work sections so they support the main product story instead of competing with it
- Make the public-to-workspace handoff clearer from audit results

### Phase 3: Workspace retention polish

- Add stronger cross-module decision summaries in the workspace
- Improve how progress, deltas, and rerun value are explained
- Keep credits and plan prompts tied to visible value and next steps

### Phase 4: Execution depth

- Build page-level action packs and more explicit evidence cards, which are still open in `plan.md`
- Continue the Phase 11 work already outlined in `plan.md` without breaking the new simplified public story

## Recommended Next Build Order

1. Use `vrt-space-product-strategy` before any revamp decisions that affect scope or story.
2. Apply `vrt-space-public-conversion` to `templates/base.html` and `templates/core/home.html`.
3. Apply `vrt-space-workspace-retention` to the audit-result-to-workspace handoff and the workspace dashboard.
4. After the public shell is cleaner, continue Phase 11 precision work from `plan.md`.
