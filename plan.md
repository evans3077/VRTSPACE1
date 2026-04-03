# VRT SPACE Execution Plan

This file is the working sequence for the product. It should answer three things at any point:

1. What is already complete
2. What is the next concrete thing to build
3. How to know a phase is actually finished

When a step is completed, update this file before starting the next one.

---

## Product State

Core product areas already in place:

- Public audit flow
- Workspace signup and login
- Google OAuth
- Billing and Stripe checkout/webhooks
- Audit reruns, reporting, PDF export, and email delivery
- Audit dashboard, SEO workspace, AEO workspace, content workspace
- Competitor-backed SEO discovery and benchmark flow
- Editorial queue and content brief generation
- Backlink prospecting and tracking

Current product reality:

- Audit is usable and strong
- SEO is promising and differentiated
- The product wedge is now visible:
  - direct recommendations
  - tighter page-level actioning
  - one flow across audits, SEO, AEO, content, backlinks, and reporting
  - stakeholder-ready outputs that do not force the user to interpret raw data
- The main risks are now:
  - noisy recommendations
  - long processing times
  - generic output
  - pricing that gets ahead of precision

---

## Completed Phases

### Phase 1: Audit, Scoring, Recommendation Core

Status: complete

- [x] Review the current audit engine, scoring flow, and recommendation output
- [x] Identify the first high-value correction and refactor target
- [x] Split scoring logic out of `apps/tools/services.py`
- [x] Split recommendation and summary shaping out of `apps/tools/services.py`
- [x] Fix score fallbacks so missing PageSpeed data does not zero out performance
- [x] Add tests for score calculation and ranked recommendations
- [x] Run Python test suite locally once a Python runtime is available in the environment
- [x] Move admin and view adapters onto the new `recommendations` and `score_breakdown` summary contract
- [x] Remove the remaining legacy summary helpers from `apps/tools/services.py`
- [x] Update templates to render `recommendations` and `score_breakdown` directly instead of legacy adapter shapes

### Phase 2: Dashboard and Project Layer

Status: complete

- [x] Define project/client entities on top of audit history
- [x] Build a real dashboard surface for score history and recommendations
- [x] Expose stable summary contracts for dashboard views
- [x] Add a staff-only operations dashboard for live inquiry, audit, project, and geography reporting
- [x] Replace public audit agency upsells with SaaS module recommendations and custom-work exceptions
- [x] Add a public workspace signup and user dashboard path from audit results
- [x] Rework the broader public marketing layer so public CTAs route into audit, workspace, plans, or custom-work exceptions
- [x] Add workspace sign-in and Google OAuth-ready authentication flow for user testing
- [x] Move live audit execution off the request thread so Render can return a status page instead of timing out

### Phase 3: Billing and Plan Enforcement

Status: complete

- [x] Keep audit plan visibility live under a temporary free-pass mode until testing and core product development are complete
- [x] Add plans, subscriptions, and usage tracking
- [x] Gate audits, history, and premium recommendation features
- [x] Add webhook-driven payment verification
- [x] Finish live Stripe setup on Render with real `price_...` IDs for `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROWTH`, `STRIPE_PRICE_AUTHORITY`, and `STRIPE_PRICE_ENTERPRISE`

### Phase 4: Automation and Reporting

Status: complete

- [x] Add async audit reruns and recurring reports
- [x] Add notification and change-detection logic
- [x] Make automation plan-aware
- [x] Add a Render-friendly management command for recurring audit processing: `python manage.py process_workspace_schedules`

### Phase 5: AI Content Generation

Status: complete

- [x] Add generated-content models and service layer
- [x] Connect generator inputs to audit and SEO context
- [x] Support reusable page, article, and answer-block outputs

### Phase 6: Editorial Workflow and API Contract

Status: complete

- [x] Add review and edit workflow for generated drafts before publication
- [x] Add a structured JSON endpoint for generated-content output
- [x] Add apply-to-library actions so drafts can create or update `Article` and `Service` content records

### Phase 7: Stakeholder PDF Reporting

Status: complete

- [x] Add a reusable audit PDF rendering service for completed audit runs
- [x] Add inline view and download routes for audit PDF reports
- [x] Expose PDF report actions from public audit results and the workspace dashboard

### Phase 8: Audit Hardening and Delivery

Status: complete

- [x] Add competitor and market-context inputs to audit requests
- [x] Add richer context-analysis output to completed audit summaries
- [x] Add stakeholder sharing controls with expiring share links and public shared-report routes
- [x] Add JSON and CSV export routes for completed audits
- [x] Add scheduled email delivery for audit reports and alerts with attached PDFs
- [x] Enforce report-sharing separately from email delivery so plans can allow one without the other
- [x] Add Celery-backed worker support for audit execution with the in-process queue kept only as a fallback
- [x] Strengthen completed-audit guards on export and shared-report routes
- [x] Re-run migrations and the relevant Django test suites after the hardening pass

### Phase 9: SEO Product Layer

Status: complete

- [x] Move from audit-system completion into the SEO product layer
- [x] Build the first SEO-specific workflow on top of the completed audit, billing, automation, export, and content foundations
- [x] Reshape the workspace so Audits, SEO, and AEO sit beside each other as separate product areas
- [x] Add visible usage and value reporting so users can see where workspace credits/activity are going
- [x] Add a stored SEO business profile per workspace
- [x] Add an industry and location-aware SEO context engine
- [x] Add a workspace SEO hub for keyword opportunities, priority pages, and context-aware recommendations
- [x] Add a workspace AEO hub for AI visibility, entity clarity, and answer-readiness analysis
- [x] Extend the SEO layer into deeper keyword planning, page mapping, and execution workflows
- [x] Turn real competitor benchmarks into a stored SEO opportunity snapshot with value reporting, keyword queue, page map, and execution queue
- [x] Add localized SERP-backed competitor discovery with persisted query/ranking evidence and merge it into the SEO benchmark flow
- [x] Connect SEO page-map and execution outputs directly into content generation so the content workspace can generate drafts from SEO-backed briefs instead of manual prompts alone
- [x] Turn SEO queue items into structured content briefs with title options, outlines, FAQ targets, internal-link targets, and competitor evidence stored on each generated draft
- [x] Turn SEO briefs into tracked editorial queue items so recurring SEO refreshes and audit completions can keep a live content operations queue in sync with the latest SEO opportunities
- [x] Make the SEO execution queue action-based by attaching page-level edit targets, exact change scopes, and ordered implementation steps instead of generic advice only
- [x] Add model-backed refinement adapters so briefs, titles, outlines, FAQs, and generated draft payloads can be upgraded by stronger models without losing the deterministic fallback path
- [x] Keep deterministic briefs and payload validation as the canonical guardrail so model output can only override allowed sections after structural checks pass
- [x] Move SEO refresh and first-time competitor profiling off the request thread so Render does not time out when benchmarking live competitor sites
- [x] Replace static queued text with an animated SEO refresh state so users can see the workspace is actively benchmarking competitors in the background
- [x] Tighten competitor discovery precision with richer audit-informed query generation, relevance scoring, and noise filtering so weak SERP matches do not dilute the benchmark set
- [x] Expand competitor profiling so fetched pages now carry asset and tech-stack signals that the SEO engine can use in page-map, execution, and future model reasoning
- [x] Auto-detect business category from the website and audit signals when the user does not explicitly set one in the SEO workflow
- [x] Add a production-grade secondary discovery provider fallback so competitor discovery can fall back from SerpApi to DuckDuckGo HTML search instead of depending on a single source
- [x] Tighten SEO refresh runtime and precision by capping competitor crawl scope, redirecting async form submissions cleanly, and filtering low-fit SERP competitors more aggressively
- [x] Rebuild SEO precision around cross-niche query families, stricter competitor qualification, and clustered recommendations so the roadmap stays specific without repeating itself

### Phase 10: Backlink Acquisition Engine

Status: complete

- [x] Turn competitor and page-gap intelligence into linkable-asset recommendations such as comparison pages, data pages, city pages, and FAQ assets that deserve outreach
- [x] Add a prospecting layer that finds likely backlink targets by topic, niche, location, citation source, and competitor-link patterns
- [x] Score backlink prospects by relevance, authority fit, local fit, and outreach likelihood instead of raw volume
- [x] Build outreach-ready packets from the content engine so users can generate asset summaries, subject lines, pitch angles, and proof snippets from live workspace data
- [x] Add backlink tracking so the workspace can show target status, acquired links, anchor patterns, and the pages each link is meant to support

---

## Strategic Continuity

The first ten phases were foundation-building phases. They were not separate products.

They built one connected system in this order:

1. Audit foundation
   Result:
   The platform can inspect a site, score it, explain it, and save the result.

2. Workspace and project foundation
   Result:
   The user can keep work inside the system instead of treating the audit as a one-off report.

3. Billing and plan foundation
   Result:
   The product can eventually enforce value and monetize workflows cleanly.

4. Automation and reporting foundation
   Result:
   The system can rerun, notify, export, and report instead of stopping at one scan.

5. Content and editorial foundation
   Result:
   SEO and audit intelligence can become briefs, drafts, edits, and publishable assets.

6. SEO and AEO intelligence foundation
   Result:
   The platform can benchmark competitors, reason over SERPs, understand niche and location context, and generate execution opportunities.

7. Backlink and campaign foundation
   Result:
   The system can carry an opportunity beyond diagnosis into authority-building and tracked execution.

Phase 11 is not a new direction. It is the refinement phase that makes the first ten phases work together as one production-grade decision system.

The purpose of Phase 11 is to do four things:

- make the existing outputs more precise
- make the existing workflows faster and more durable
- make the value of each paid tier explicit
- make the full chain easier to understand for both operators and stakeholders

That is the bridge between the original build plan and the current strategy plan.

---

## Active Phase

### Phase 11: Product Precision, Packaging, and Decision Quality

Status: in progress

Goal:

Turn the current platform into a production-grade decision system that is clearly more actionable than traditional SEO tools, while making plan value, limits, and upgrade logic explicit before marketing or affiliate expansion begins.

#### Track A: Precision and runtime hardening

- [ ] Add recommendation root-cause clustering across Audit, SEO, and AEO
  Why:
  Users still see advice that can feel too similar even when the evidence differs.
  Needed result:
  Repeated issue variants collapse into a smaller number of strategic actions with grouped evidence, affected URLs, and clear implementation order.
- [ ] Add stronger evidence scoring before any recommendation is shown
  Why:
  Weak competitor or crawl evidence should not leak into visible advice.
  Needed result:
  Every recommendation must pass fit, confidence, and page-target checks before entering the queue.
- [ ] Add cross-module decision summaries
  Why:
  Audit, SEO, AEO, content, and backlink work now exist, but the user still has to join the dots across separate screens.
  Needed result:
  The platform explains what to do first, what supports that decision, and what can wait.
- [ ] Reduce heavy-job runtime with explicit stage budgets
  Why:
  Long runs damage trust even when the output is good.
  Needed result:
  Discovery, crawl, pattern extraction, backlink prospecting, and report generation each run with bounded scope, visible stage state, and safe fallback behavior.
- [ ] Add cache and reuse rules for expensive benchmark artifacts
  Why:
  The system should not refetch or recompute everything on every refresh.
  Needed result:
  Competitor fetches, page-pattern extractions, and SERP evidence are reused when fresh enough, with explicit invalidation rules.

#### Track B: Decision explainability and action quality

- [x] Add competitor acceptance and rejection traceability
- [x] Add manual competitor controls
- [x] Extract repeatable competitor page patterns from accepted benchmarks
- [x] Build a page-to-page comparison layer
- [x] Add SERP evidence history
- [ ] Add page-level action packs
  Why:
  Users need exact changes, not just diagnosis.
  Needed result:
  For a chosen page, the system outputs title, H1, meta, heading structure, schema, internal-link targets, FAQ additions, proof blocks, and CTA improvements in one implementation pack.
- [ ] Add recommendation evidence cards
  Why:
  Advice is more credible when the system shows why it believes the change is worth doing.
  Needed result:
  Each major recommendation shows source evidence, accepted competitor examples, user-page gaps, and expected impact in one compact card.
- [ ] Add success-criteria contracts for execution items
  Why:
  A task should have a visible definition of success before it is considered complete.
  Needed result:
  Campaigns and action packs carry measurable validation checks tied to reruns or page-state verification.

#### Track C: Credit system, packaging, and plan discipline

- [x] Produce a plan-by-plan packaging sheet in code and plan docs
  Why:
  Pricing without exact feature ownership creates confusion and weak upgrade logic.
  Needed result:
  Define what stays free, what belongs to Starter, Growth, Authority, and what moves to Enterprise only.
- [x] Replace scattered hard caps with a credit-based plan contract
  Why:
  Credits are a better fit for recurring duties, usage tracking, and the future affiliate system than disconnected feature toggles and ad hoc counters.
  Needed result:
  Each plan has explicit monthly credits for audits, SEO, AEO, content, exports, shares, and later authority work, all tracked through one ledger.
- [x] Define exact usage limits per plan
  Why:
  A SaaS plan is not complete until limits are explicit.
  Needed result:
  Set monthly credits, workflow access, historical depth, competitor depth, content-generation allowances, backlink prospecting allowances, and automation allowances per tier.
- [ ] Map every expensive workflow to a single plan-check path
  Why:
  Costly features should not be gated inconsistently.
  Needed result:
  Audits, competitor benchmarking, content generation, backlink prospecting, scheduled runs, share links, and exports all consult the same policy and credit layer.
- [ ] Rework upgrade prompts around earned value
  Why:
  Upgrade prompts should follow visible work and visible limits, not generic sales language.
  Needed result:
  The UI explains what was used, what limit was reached, and what the next plan unlocks in operational terms.
- [x] Keep Enterprise reserved for true complexity
  Why:
  Enterprise should not become a dumping ground for ordinary paid features.
  Needed result:
  Enterprise is limited to multi-market, custom workflows, custom integrations, higher support, and bespoke implementation.

#### Track D: Execution continuity and reporting

- [x] Turn execution items into campaign objects
- [x] Tie SEO execution, generated content, and backlink prospects together
- [x] Add clearer value reporting
- [x] Add SEO-specific stakeholder reporting
- [ ] Add operational safeguards for production
  Why:
  Heavy SEO work must stay durable under real usage.
  Needed result:
  Queue heavy jobs correctly, rate-limit discovery and crawl depth, and make fallback behavior explicit when providers return partial or weak data.
- [ ] Add executive-level outcome summaries
  Why:
  Stakeholders should not have to read the entire workspace to understand value.
  Needed result:
  Reports and dashboards summarize work completed, evidence gathered, pages improved, assets created, links pursued, and validation status in plain business terms.

---

## Next Start Order

Start here, in this exact order:

1. Roll the credit policy through every expensive workflow
   Reason:
   The contract exists now, but exports, shares, backlink work, and remaining automation paths still need to spend and validate credits through one path.

2. Rework upgrade prompts around earned value
   Reason:
   Once credits are real, the UI should explain them clearly instead of only showing generic plan cards.

3. Recommendation clustering and evidence scoring
   Reason:
   This directly reduces noisy output and makes the system feel more deliberate.

4. Page-level action packs
   Reason:
   This strengthens the real wedge: exact, implementable actioning.

5. Runtime stage budgets and caching
   Reason:
   This reduces long wait times without weakening output quality.

6. Cross-module decision summaries
   Reason:
   This makes the combined value of audit, SEO, AEO, content, and backlinks easier to understand.

7. Executive-level outcome summaries
   Reason:
   Once the decision system is tighter internally, stakeholder reporting should summarize it in plain business language.

---

## Next First Slice

The next work block should be:

### Block 2: Credit Policy Rollout and Upgrade Messaging

Target:

- Route remaining expensive workflows through the credit policy layer
- Add earned-value upgrade prompts tied to depleted credits and locked workflows
- Make the workspace explain credits as the operating budget for recurring actions

Definition of done:

- Exports, shares, backlink work, and recurring duties all use the same credit/policy checks
- Upgrade prompts explain which credit bucket was used or exhausted
- The workspace explains current credits and the next unlock in operational terms

---

## Follow-Through Rules

- Do not add more market-facing feature copy before the packaging sheet and tier limits are explicit.
- Do not add new expensive recurring workflows without deciding which credit bucket pays for them.
- Do not let weak evidence create visible recommendations.
- Do not let heavy jobs run without bounded stage budgets, status, and fallback behavior.
- Do not price a feature above the current precision it can defend.
- Every heavy async workflow must have:
  - a visible status
  - a failure state
  - a retry path
  - a bounded scope

---

## Packaging Direction

This is the pricing, packaging, and credit direction to implement in code and UI next.

### Free

- Public audit entry layer
- Limited history
- Limited exports
- No deep recurring workflows
- Minimal or no recurring credits beyond the entry audit path
- Purpose:
  acquisition and proof of value

### Starter

- Solo operators and small local businesses
- Core audit workspace
- SEO and AEO basics
- Limited competitor-backed benchmarking
- Limited reports and action packs
- Small monthly credit bundle for audits, SEO, and AEO

### Growth

- Serious SMBs and lean teams
- Recurring audits
- Deeper competitor benchmarking
- Content briefs and editorial queue
- Stakeholder reporting and sharing
- More automation and historical depth
- Meaningful monthly credits for audit, SEO, AEO, content, export, and share workflows

### Authority

- Agencies, multi-location businesses, and execution-heavy teams
- Full audit, SEO, AEO, content, and backlink workflow
- Advanced reporting
- Larger limits
- Full campaign continuity and stronger collaboration paths
- Large monthly credit bundle including authority-building workflows

### Enterprise

- Multi-market and multi-site complexity
- Custom integrations
- Custom workflows
- Bespoke support and implementation
- Reserved for real complexity, not ordinary feature gating

---

## Implementation Logic

This is the order the product should continue to follow so the earlier plan and the newer precision work stay aligned.

### Layer 1: Foundation already built

- Audit
- Workspace
- Billing
- Automation
- Reporting
- SEO
- AEO
- Content
- Backlinks

Rule:
Do not rebuild these primitives. Extend them.

### Layer 2: Precision and packaging now

- Reduce noisy output
- Improve action specificity
- Bound runtime
- Make tier ownership explicit
- Align product value with pricing

Rule:
Every new improvement should either increase decision quality, reduce ambiguity, or clarify plan value.

### Layer 3: Growth systems later

- Marketing engine
- Affiliate system
- Broader distribution loops
- Go-to-market scaling

Rule:
Do not prioritize acquisition systems ahead of core precision and packaging discipline.

---

## Market Position Rule

- We are not trying to become Ahrefs by copying breadth first.
- We learn from the strongest tools in the market, study their movements, and capitalize on where they are weaker.
- The product advantage must come from decision quality, action quality, workflow continuity, and stakeholder clarity.
- Marketing and affiliate systems come after the core functionality, plan discipline, and product precision are strong enough to defend the pricing.

---

## Deployment Rules

- Database changes must be migration-driven so the schema transfers cleanly to Render PostgreSQL for live testing.
- Geography reporting must use captured request headers and stored submission context, not inferred locations.
- Any new long-running SEO or audit work must stay off the request thread in production.

---

## Temporary Product Rule

- Audit tiers and package destinations stay visible during testing, but billing enforcement is deferred until the next product level so user-flow development can finish first.
