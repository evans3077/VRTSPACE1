# VRT Space Agency — Codex Implementation Guide

This is the tactical build guide for restructuring the current project into a focused, conversion-driven SaaS product.

Use this together with the master instructions. The goal here is implementation discipline: what to change first, what to keep, and how to avoid creating unnecessary complexity.

---

## Implementation Priority Order

Codex should work in this order:

### Phase 1: Understand the current codebase

* Inspect the app structure.
* Identify the main routes, layouts, components, services, forms, and data flow.
* Find the current public-facing homepage and workspace flow.
* Identify any features that do not belong in the first version of the SaaS presentation.

### Phase 2: Simplify the public-facing experience

* Make the homepage focused on only:

  * Audit
  * SEO
  * AEO
* Remove or hide anything that makes the product feel busy, unfocused, or like a dashboard full of modules.
* Tighten the CTA structure.

### Phase 3: Strengthen the conversion flow

* Improve the hero section.
* Improve the explanation of each module.
* Make the 3–5 minute “wow” experience more obvious.
* Make the workspace feel like an active growth space.

### Phase 4: Improve reruns and retention

* Ensure rerun actions are clear and easy.
* Show progress over time.
* Make credit usage feel tied to improvement.

### Phase 5: Polish UI/UX

* Improve spacing, hierarchy, clarity, and responsiveness.
* Reduce visual noise.
* Make the product feel premium and credible.

---

## What to Inspect First

Codex should first inspect:

* app entry point
* routes or pages
* homepage structure
* workspace structure
* audit flow
* SEO flow
* AEO flow
* any shared components used across the app
* any global state or data storage related to projects/workspaces/credits

The purpose of inspection is to avoid breaking working parts while restructuring.

---

## Current Product Shape to Preserve

The existing product already has the right conceptual shape:

* Audit exists
* SEO exists
* AEO is planned
* Workspace exists
* Users can rerun analyses

Codex should preserve this core and improve it, not replace it with a new unrelated system.

---

## Public UI Rules

The public UI should show only the product story that matters.

### Must emphasize

* website analysis
* visibility improvement
* competitor gaps
* AI answer readiness
* progress tracking

### Must de-emphasize or hide

* extra modules that are not part of the core launch story
* technical clutter
* overly detailed internal mechanics
* any features that confuse the first-time visitor

---

## Homepage Restructure Instructions

The homepage should be organized into a simple conversion path.

### Section 1: Hero

The hero should answer, immediately:

* what the platform does
* who it is for
* why it is valuable
* what the next action is

It should contain:

* one strong headline
* one short subheadline
* one primary CTA
* one secondary CTA if useful
* one visual or concept that reinforces the promise

### Section 2: What the product does

Explain the three steps:

* Audit
* SEO
* AEO

Keep the language simple and outcome-focused.

### Section 3: Why it matters

Explain the value in plain language:

* find problems quickly
* compare with competitors
* see what is missing
* understand how to improve search and AI visibility

### Section 4: How it works

Use a simple sequence:

* enter website
* run audit
* review SEO gaps
* review AEO readiness
* save to workspace
* rerun after fixes

### Section 5: Workspace / progress

Show that this is an ongoing system, not a one-off report.

### Section 6: Final CTA

Reinforce the next action clearly.

---

## Audit Module Implementation Guidance

The audit should be fast and easy to understand.

### Audit input

* website URL
* optional workspace selection
* optional competitor URL if supported

### Audit data sources

* Google PageSpeed Insights API
* SerpAPI

### Audit should detect

* performance problems
* speed issues
* mobile issues
* visibility issues
* obvious technical blockers

### Audit output should include

* overall score
* critical issues
* quick wins
* next recommended step

### UX rule

Do not make the audit output feel like a raw dump of technical metrics.
It should feel like a diagnosis.

---

## SEO Module Implementation Guidance

The SEO module should expand the audit into strategy.

### SEO should analyze

* missing patterns
* competitor structures
* content gaps
* backlinks or authority signals
* keyword/theme opportunities

### SEO output should include

* what competitors are doing
* what the site is missing
* what pages or content should be added
* which issues matter most first

### UX rule

The SEO output should make the user think:

> “Now I understand what needs to be built or fixed.”

---

## AEO Module Implementation Guidance

The AEO module should be built on top of audit and SEO data.

### AEO should analyze

* answer-readiness
* entity coverage
* topic coverage
* structured data readiness
* AI visibility potential

### AEO output should include

* answer readiness score
* entity gaps
* content gaps for conversational search
* structured recommendations for AI visibility

### UX rule

AEO should feel like the premium layer that gives a modern edge.

---

## Workspace Implementation Guidance

The workspace must feel like a real project environment.

### Each workspace should store

* project name
* website URL
* main notes
* audit runs
* SEO runs
* AEO runs
* rerun history
* progress over time
* credit consumption

### Workspace behaviors

* create project
* open project
* rerun analyses
* compare runs
* view improvement over time

### UX rule

The workspace should feel like a growth log.
Users should see that their site is getting better.

---

## Credits and Usage Guidance

Credits should be linked to meaningful actions.

### Good credit actions

* run audit
* run SEO analysis
* run AEO analysis
* rerun after changes
* deeper comparison

### Credit experience rule

Do not make credits feel punitive.
Make them feel like unlocking more insight and more progress.

---

## Conversion UX Guidance

Codex should make conversion easier by using these patterns:

### 1. Clear single-purpose screens

Every screen should try to do one main thing.

### 2. Strong call to action

The CTA should be obvious and consistent.

### 3. Fast first value

The user should see something useful very quickly.

### 4. Controlled reveal

Show enough to demonstrate value, then allow deeper analysis via credits or upgrade.

### 5. Progress feedback

Always let the user know something is happening.

### 6. Visible next step

After each result, show the user exactly what to do next.

---

## UI/UX Design Rules

### Visual style

* clean
* modern
* premium
* uncluttered
* confident

### Layout

* avoid dense grids unless necessary
* use clear spacing and section separation
* keep the information hierarchy obvious

### Typography

* strong headings
* concise body copy
* readable sizes on all screens

### Components

Prefer components that help users understand quickly:

* score cards
* insight blocks
* comparison panels
* simple progress indicators
* compact CTAs

### Motion

Use motion to show progress or success, not just decoration.

### Mobile

Mobile must preserve:

* clarity
* fast scanning
* easy tap targets
* short sections

---

## Writing and Microcopy Rules

### Good copy should

* be direct
* feel human
* explain benefits clearly
* avoid jargon where possible

### Good examples of tone

* “See what is holding your site back.”
* “Compare your site with competitors.”
* “Find what to fix next.”
* “Track your progress after changes.”

### Avoid copy that sounds like

* a generic software manual
* a portfolio pitch
* a technical API dashboard

---

## Trust-Building Guidance

The product should build trust through:

* structured output
* clear logic
* consistency
* good presentation
* honest wording
* visible methodology

Do not overclaim.
Do not fake results.
Do not fill trust sections with empty marketing language.

---

## Recommended Experience Flow

### Homepage

* clear promise
* simple explanation
* direct CTA

### First analysis

* enter URL
* run audit
* show initial findings

### Next layer

* show SEO gaps
* show competitor comparison
* show backlinks or missing patterns

### Next layer

* show AEO readiness
* show answer gaps

### Workspace

* save project
* rerun after fixes
* compare before and after

### Repeat

* encourage returning to check progress

---

## Key Product Philosophy for Codex

Always remember:

* Audit creates the first wow.
* SEO gives the plan.
* AEO gives the modern edge.
* Workspace creates retention.
* Reruns create repeat usage.
* Clarity creates conversion.

---

## What Success Looks Like

The finished product should feel like:

* a focused SaaS tool
* a premium growth system
* a simple but powerful website intelligence platform
* something users can understand fast and trust enough to use repeatedly

The user should finish their first session feeling:

> “This is useful. I can see what is wrong. I know what to do next. I want to come back after I fix things.”

---

## Implementation Safety Rules

* Preserve working audit/SEO functionality.
* Refactor carefully.
* Avoid unnecessary rewrites.
* Do not create new complexity unless it directly helps conversion or usability.
* Keep the product aligned with the SaaS direction.

---

## Final Build Directive

Codex should rebuild the experience around this idea:

**A user enters a site, gets a fast and meaningful diagnosis, understands the SEO and AEO gaps, saves the work into a workspace, reruns after fixes, and sees progress over time.**

That is the product.
That is the loop.
That is the conversion system.
