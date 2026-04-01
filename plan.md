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
- Workspace structure is still too implicit for multi-site users
- Decision explainability and execution traceability are the next major gap

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

## Active Phase

### Phase 11: SEO Decision Engine and Campaign Execution

Status: in progress

Goal:

Turn the current SEO workspace from a strong analysis tool into a decision system that can explain why it chose a benchmark, compare pages directly, and carry a winning opportunity through execution.

#### Track A: Foundation fixes before more intelligence

- [x] Harden the dense product screens so audit, SEO, and content pages remain readable without dropping information, using responsive grid and contained-scroll layout patterns instead of long horizontal or vertical sprawl
- [x] Rebuild the audit intake step into a structured project-onboarding flow
  Why:
  The first step still captures too much context as free text.
  Needed result:
  Business type, location, target goal, and primary offer become first-class fields from the start.
- [x] Add audit-entry preflight and continuity rules
  Why:
  The intake still behaves like isolated submissions.
  Needed result:
  Normalize domains early, catch duplicate in-flight runs, show expected processing state clearly, and attach the run cleanly to a durable project path.
- [x] Harden audit-result rendering against incomplete or legacy score payloads
  Why:
  Public audit pages must not crash when live summaries contain `None` or partial score values.
  Needed result:
  The result view normalizes missing values safely and keeps public links stable across old and new audit records.
- [x] Add true multi-project workspace support
  Why:
  Most workspace flows still assume “latest project” instead of “selected project.”
  Needed result:
  Users can own multiple sites and switch the active project explicitly across Audits, SEO, AEO, Content, and Backlinks.

#### Track B: SEO decision explainability

- [x] Add competitor acceptance and rejection traceability
  Why:
  The engine now filters better, but users still cannot see why a competitor was accepted or rejected.
  Needed result:
  The SEO hub shows fit signals, penalty signals, source, and the reason each discovered site was kept, down-ranked, or filtered out.
- [x] Add manual competitor controls
  Why:
  Even a strong engine needs a correction path.
  Needed result:
  Users can approve, reject, pin, or suppress competitors without losing the automated pipeline.
- [x] Extract repeatable competitor page patterns from accepted benchmarks
  Why:
  We need more than counts and generic evidence.
  Needed result:
  The system identifies title formulas, H1 patterns, FAQ blocks, schema patterns, asset usage, local proof elements, and internal-link placement.
- [x] Build a page-to-page comparison layer
  Why:
  Recommendations become more credible when users can compare their page directly against winning competitors.
  Needed result:
  Show what the user page has, what accepted competitor pages include, what is missing, and the exact structural delta to close.
- [ ] Add SERP evidence history
  Why:
  A single snapshot is not enough for a recurring SEO product.
  Needed result:
  Track query evidence, competitor appearances, and ranking signals over time.

#### Track C: Execution and campaign continuity

- [ ] Turn execution items into campaign objects
  Why:
  The current execution queue is actionable, but not yet managed like an ongoing campaign.
  Needed result:
  Each execution item can have status, owner, due date, related pages, related keywords, and success criteria.
- [ ] Tie SEO execution, generated content, and backlink prospects together
  Why:
  The system should move one opportunity through the full chain.
  Needed result:
  A single accepted opportunity can flow:
  benchmark -> page brief -> draft -> publish target -> outreach target -> rerun validation
- [ ] Add clearer value reporting
  Why:
  Users should see where their time, credits, and money are going.
  Needed result:
  Report how many benchmarks ran, competitor pages were processed, briefs were generated, drafts were created, outreach targets were discovered, and campaigns advanced.
- [ ] Add SEO-specific stakeholder reporting
  Why:
  Audit PDF reporting exists, but SEO strategy still needs its own shareable layer.
  Needed result:
  Users can export or share competitor-backed SEO plans in a stakeholder-friendly format.
- [ ] Add operational safeguards for production
  Why:
  Heavy SEO work must stay durable under real usage.
  Needed result:
  Queue heavy jobs correctly, rate-limit discovery and crawl depth, and make fallback behavior explicit when providers return partial or weak data.

---

## Tomorrow Start Order

Start here, in this exact order:

1. Multi-project workspace selection
   Reason:
   Once onboarding improves, the system must stop assuming one implicit project.

2. Competitor traceability and manual controls
   Reason:
   This is the next trust layer for the SEO workspace.

3. Competitor pattern extraction and page-to-page comparison
   Reason:
   This is where the SEO engine becomes meaningfully harder to compete with.

4. Campaign objects and full-chain execution continuity
   Reason:
   This turns intelligence into managed work instead of static advice.

---

## Tomorrow First Slice

The next work block should be:

### Block 2: Project Selection Foundation

Target:

- Add explicit project selection in the workspace
- Make Audit, SEO, AEO, Content, and Backlinks use the selected project instead of the latest-updated project

Definition of done:

- A user with multiple projects can switch context safely
- Core workspace areas all resolve against the chosen project
- Tests cover the selection logic

---

## Follow-Through Rules

- Do not add more SEO surface area before the onboarding and project-selection foundation is corrected.
- Do not add more competitor intelligence before explainability exists.
- Do not add more campaigns or automation before execution items have a durable object model.
- Every heavy async workflow must have:
  - a visible status
  - a failure state
  - a retry path
  - a bounded scope

---

## Deployment Rules

- Database changes must be migration-driven so the schema transfers cleanly to Render PostgreSQL for live testing.
- Geography reporting must use captured request headers and stored submission context, not inferred locations.
- Any new long-running SEO or audit work must stay off the request thread in production.

---

## Temporary Product Rule

- Audit tiers and package destinations stay visible during testing, but billing enforcement is deferred until the next product level so user-flow development can finish first.
