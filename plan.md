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

Antigravity's April 5 UI/UX review adds a fifth requirement that is now part of the same phase:

- make the visual shell, navigation, and conversion flow feel as production-grade as the backend already is

That is the bridge between the original build plan and the current strategy plan.

---

## Active Phase

### Phase 12: Clinical Precision & Advanced API Intelligence

Status: planned

Goal:

Integrate high-value third-party and Google Cloud APIs to provide clinical-grade precision that competitors cannot match, powering predictive insights and high-margin credit burn mechanics.

#### Track A: Clinical SEO Data & Authentication
- [ ] Implement Google OAuth for Search Console (GSC) workspace connection.
  Why:
  Move from estimated traffic to exact clicks, impressions, and CTR.
  Result:
  Generate an "Opportunity Finder" action pack to push high-impression Page 2 URLs to Page 1 based on ground truth data.
- [ ] Integrate DataForSEO API for Search Volume and Backlinks.
  Why:
  Enterprise-grade data at lower costs than Ahrefs/Semrush. Provide real "Market Gap Analysis" showing lost search volume.
- [ ] Integrate Google Indexing API.
  Why:
  Instant validation of the VRT SPACE content engine. Generate -> Publish -> Ping Indexing API.

#### Track B: AEO & GEO Verification
- [ ] Integrate Google Cloud Natural Language API.
  Why:
  Check if Google's AI actually recognizes the brand's primary entities.
  Result:
  Calculate a clinical "Entity Confidence Score". Low confidence triggers specific Schema/Content action packs.
- [ ] Integrate Perplexity API (Sonar Pro) for real-time testing.
  Why:
  AEO requires testing against real Answer Engines.
  Result:
  The "GEO Shootout" compares user vs competitors on Perplexity and generates an "Authority Gap Action Plan" if not cited.

#### Track C: Workspace Monetization & Credit Burns
- [ ] Implement high-value credit drain mechanisms for premium API checks.
  Result:
  Standard audits cost 1 credit. "Entity Confidence Scan" costs 25 credits. "GEO Shootout" costs 50 credits.
- [ ] Expose "Locked Potential" teasers in the UI.
  Result:
  Free/Starter users see the *opportunity* (e.g. "14 pages stuck on Page 2 missing 4,500 impressions") but must upgrade/burn credits to see the exact URLs and Action Packs.

---

### Phase 11: Product Precision, Packaging, and Decision Quality

Status: in progress

Goal:

Turn the current platform into a production-grade decision system that is clearly more actionable than traditional SEO tools, while making plan value, limits, and upgrade logic explicit before marketing or affiliate expansion begins.

#### Track A: Precision and runtime hardening

- [x] Add recommendation root-cause clustering across Audit, SEO, and AEO
  Why:
  Users still see advice that can feel too similar even when the evidence differs.
  Delivered result:
  Audit, SEO, and AEO now collapse repeated issue variants into root-cause groups with grouped evidence, affected URLs, confidence labels, and clearer implementation order.
- [x] Add stronger evidence scoring before any recommendation is shown
  Why:
  Weak competitor or crawl evidence should not leak into visible advice.
  Delivered result:
  Shared evidence scoring now decorates audit, SEO, and AEO recommendations and filters weak SEO/AEO advice before it reaches the visible roadmap.
  Refinement:
  Hospitality and venue-style profiles now block OTAs, metasearch travel sites, and generic search surfaces from entering the benchmark set when they match the search query but not the actual service being sold.
  Local competitor correction:
  Sparse local-pack results with real websites are now scored as valid peer evidence instead of being dropped for failing organic-style snippet thresholds. The benchmark set can now admit real local operators when they match the service, geography, and route intent.
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
- [x] Add the first source-routing and business-class discovery-policy slice
  Why:
  The platform serves many business types, so discovery cannot treat every query as a generic web-search problem.
  Delivered result:
  Discovery now classifies surfaced domains into benchmark competitors, market surfaces, citation sources, backlink prospects, or discard, and the SEO workspace shows those buckets explicitly so non-peer surfaces stop contaminating peer benchmarks.
  Current design:
  - `benchmark competitors`: true peer operators or product sites for the same business class
  - `market surfaces`: directories, marketplaces, metasearch, review surfaces, app stores, and answer surfaces that matter for visibility but are not true competitors
  - `citation sources`: local/business listing sources and profile ecosystems
  - `backlink prospects`: publishers, associations, partners, media, and niche resources
  - `discard`: irrelevant, foreign, low-fit, or noisy domains
- [x] Add the first source-family specialization slice
  Why:
  The bucket model is now in place, but discovery still needs business-type routing before peer qualification happens.
  Delivered result:
  Discovery now builds route families by business type, with benchmark, market-surface, citation, and backlink-oriented query tracks instead of one generic query set.
  Current source-family behavior:
  - generic web search remains the retrieval layer
  - route families now separate benchmark, market-surface, citation, and editorial/resource discovery
  - hospitality, local-service, ecommerce, SaaS, healthcare, and real-estate profiles no longer share the exact same discovery-family mix
  Value:
  This reduces vague results, improves crawl precision, and creates richer downstream data for page maps, action packs, backlink workflows, citations, and stakeholder reports.
- [x] Expand audit and workspace intake with structured niche and market fields
  Why:
  Precision starts at intake. Weak business context or flat location text makes the downstream discovery pipeline guess too much.
  Delivered result:
  Audit and workspace creation now capture business subtype, target audience, targeted-vs-worldwide market mode, and structured country plus validated area inputs. Those values are synced into the project layer so SEO and later modules inherit better context instead of rebuilding it from scratch.
- [x] Add provider-level vertical source integration
  Why:
  Route families are now separated, but they still retrieve primarily through generic web-search providers.
  Delivered result:
  VERTICAL_SOURCE_ENGINES mapping in discovery.py routes each business type to its appropriate SerpAPI vertical engines: google_local and google_local_services for local_service/healthcare/automotive; google_local + google_hotels + google_events for hotel; google_local for real_estate and restaurant. fetch_vertical_serpapi_results() calls each engine with a 7-day cache. _parse_vertical_result() normalises results across engine shapes. _run_vertical_source_queries() orchestrates per-business-type calls and appends enriched local candidates to the main candidate pool. Each vertical result carries local_metadata (rating, reviews, address, place_id) for downstream enrichment. Candidates from google_local/google_local_services land in benchmark_competitor bucket for peer business types; google_hotels and google_events land in market_surface and citation_source respectively. Gracefully skips when no vertical engines are configured for the business type.
- [x] Add cache and reuse rules for expensive benchmark artifacts
  Why:
  The system should not refetch or recompute everything on every refresh.
  Delivered result:
  competitor_snapshot_is_fresh() helper in discovery.py checks whether an existing SEOCompetitorSnapshot is within the reuse window (default 3 days, configurable via COMPETITOR_SNAPSHOT_REUSE_DAYS env var) and has non-empty output_json. get_or_build_competitor_snapshot() in services.py now follows a three-step hierarchy: (1) exact match for current audit run, (2) any fresh recent snapshot — reused by creating a lightweight copy with the same payload rather than re-crawling, (3) full re-fetch when no fresh snapshot exists. SerpAPI result caching (7-day per-query hash) was already in place; vertical engine results also use the same 7-day cache under a separate key prefix.

#### Track B: Decision explainability and action quality

- [x] Add competitor acceptance and rejection traceability
- [x] Add manual competitor controls
- [x] Extract repeatable competitor page patterns from accepted benchmarks
- [x] Build a page-to-page comparison layer
- [x] Add SERP evidence history
- [x] Add page-level action packs
  Why:
  Users need exact changes, not just diagnosis.
  Delivered result:
  SEOCampaignEditItem model persists each page-level edit target from the execution queue. A dedicated action pack detail view at /workspace/seo/campaigns/<pk>/action-pack/ renders the full implementation pack: page URL, change scope (new vs. existing), specific changes list, evidence card, competitor examples, and definition of done. Campaigns link to their action pack from the SEO workspace campaign pipeline.
- [x] Add recommendation evidence cards
  Why:
  Advice is more credible when the system shows why it believes the change is worth doing.
  Delivered result:
  Each execution queue item in the SEO workspace now shows competitor evidence inline (domain, page type, URL). The action pack detail page renders a full evidence card: evidence score bar, confidence label, evidence summary, and up to 6 competitor examples that justify the recommendation.
- [x] Add success-criteria contracts for execution items
  Why:
  A task should have a visible definition of success before it is considered complete.
  Delivered result:
  Each SEOCampaignEditItem carries a success_criteria JSON field generated from the edit target context: new-page live check, keyword alignment, Core Web Vitals pass, and SEO refresh revalidation. Criteria are shown as a "Definition of Done" block on the action pack page. Campaign-level validation status is also surfaced on the same page.

#### Track C: Credit system, packaging, and plan discipline

- [x] Add manual workspace creation and active-workspace switching
  Why:
  Users need to keep separate websites or client work independent without hacking around the audit flow.
  Delivered result:
  The dashboard can create independent workspaces, reopen an existing one by domain, and switch the active workspace cleanly from the shell.
- [x] Add audit-first onboarding for users who start from SEO, AEO, or content
  Why:
  Users should not get stranded in module screens when they actually need the first audit to create the working base.
  Delivered result:
  Zero states now point directly to a start-audit path that creates or attaches the workspace and continues into the audit result without extra detours.
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
- [x] Reframe credits as one visible workspace balance with weighted spend
  Why:
  The user should see one simple number on the dashboard, not a confusing pile of unrelated credit buckets.
  Needed result:
  Plans grant a single workspace credit pool, heavier work spends more based on complexity, and the dashboard shows where those credits went.
- [x] Prevent negative credit balances during testing mode
  Why:
  Free-pass testing should still log usage without making the product look broken or unpaid states look corrupt.
  Delivered result:
  Testing mode now records shadow usage, keeps the visible balance at zero or above, and shows estimated overage explicitly in the dashboard.
- [x] Define exact usage limits per plan
  Why:
  A SaaS plan is not complete until limits are explicit.
  Needed result:
  Set monthly credits, workflow access, historical depth, competitor depth, content-generation allowances, backlink prospecting allowances, and automation allowances per tier.
- [x] Add organized workspace navigation and credit visibility
  Why:
  The product menu and credit model were becoming hard to read in day-to-day use.
  Needed result:
  The global header stays simple, the workspace gets its own clear sub-navigation, and users can see plan and credit state without hunting through dense sections.
- [x] Add direct credit and billing shortcuts from the workspace shell
  Why:
  Buying or changing a plan should not require menu -> overview -> scroll -> select as a multi-step hunt.
  Delivered result:
  The header menu, workspace sub-navigation, and dashboard hero all expose direct links into credits and plans.
- [x] Separate account management from workspace operations
  Why:
  Personal profile, billing, and login management should not compete with project execution inside the workspace.
  Delivered result:
  A dedicated account dashboard now handles personal details, password changes, and billing access, while the workspace stays focused on projects and execution.
- [x] Declutter the workspace into an execution-only shell
  Why:
  The workspace had accumulated billing, export, plan, and context sections that distracted from the actual project flow and made the product feel heavier than it is.
  Delivered result:
  The workspace now centers on active project state, project switching, audit start/rerun, next-step modules, the fix queue, and audit history only. Account, billing, and deeper plan management stay outside the workspace shell.
- [x] Add direct checkout from blocked workflow states
  Why:
  If the product already knows which plan unlocks an action, sending the user through multiple intermediate screens reduces conversion and adds friction.
  Delivered result:
  Blocked export, sharing, and backlink states now offer direct checkout on the same screen with return routing back to the originating workflow.
- [x] Grant credits immediately on successful Stripe return
  Why:
  Users should not land back in the product with an active payment but no visible credits while waiting for webhook timing to catch up.
  Delivered result:
  The Stripe success return path now syncs the checkout session, activates the subscription, and writes the current-cycle credit grant immediately, while the webhook remains the durable background confirmation path.
- [x] Simplify the workspace flow around one audit base
  Why:
  The platform should feel like one path: audit first, then SEO or AEO, then content or exports only when needed.
  Needed result:
  The dashboard and module screens explain that the latest audit feeds the next layers and that a new audit is only required for validation or a fresh crawl.
- [x] Fix plan-direction language and project independence in the workspace
  Why:
  Higher-tier users should not be told to "upgrade" into lower tiers, and specialists need to see separate projects as distinct units of work.
  Needed result:
  Plan cards use correct movement language, and the dashboard shows independent projects with their own focus, state, and quick project switching.
- [x] Map every expensive workflow to a single plan-check path
  Why:
  Costly features should not be gated inconsistently.
  Needed result:
  Audits, competitor benchmarking, content generation, backlink prospecting, scheduled runs, share links, and exports all consult the same policy and credit layer.
- [x] Rework upgrade prompts around earned value
  Why:
  Upgrade prompts should follow visible work and visible limits, not generic sales language.
  Needed result:
  The UI explains what was used, what limit was reached, and what the next plan unlocks in operational terms.
- [x] Reshape the dashboard into a clearer user shell
  Why:
  Static cards and long sections make the product feel heavier than it needs to be.
  Delivered result:
  The user dashboard now has a direct start-audit entry, a separate create-workspace entry, and a clickable expandable workspace portfolio instead of forcing the user through long static sections.
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
  Progress:
  SERP discovery now uses provider cooldowns, shorter fallback timeouts, and per-refresh provider shutdown so one SerpApi 429 or DuckDuckGo timeout does not cascade into a long sequence of duplicate failures.
- [ ] Add executive-level outcome summaries
  Why:
  Stakeholders should not have to read the entire workspace to understand value.
  Needed result:
  Reports and dashboards summarize work completed, evidence gathered, pages improved, assets created, links pursued, and validation status in plain business terms.

#### Track E: UI shell, conversion flow, and module presentation

- [x] Fix shared UI foundation gaps
  Why:
  Antigravity found design-system gaps that weaken clarity even when the backend data is strong.
  Delivered result:
  The shared shell now loads the intended font, defines score-pill variants, includes a mobile drawer navigation, and has reusable command-card, evidence-card, progress-bar, metric-strip, and jump-nav primitives in the global CSS.
- [x] Rebuild the SEO workspace hierarchy
  Why:
  The SEO page is data-rich but too long and visually flat, which hides important sections and weakens the sense of progress.
  Delivered result:
  The SEO workspace now has section anchors, in-page jump navigation, stronger visual grouping, live refresh presentation, richer export/share states, and clearer placement of campaign and backlink sections.
- [x] Expand the AEO workspace to match product importance
  Why:
  AEO is part of the product wedge, but the current AEO surface is still too thin compared to SEO.
  Delivered result:
  The AEO workspace now includes scorecards, run states, entity context, audit-base context, recommendation cards, history, and cross-links into SEO and content execution.
- [x] Add a cross-module command center to the workspace
  Why:
  Users still need a single summary showing how audit, SEO, AEO, content, and backlinks connect.
  Delivered result:
  The workspace dashboard now includes a command center that surfaces module state, priority actions, and next-step routing across audit, SEO, AEO, and content.
- [x] Shorten the payment and conversion path
  Why:
  UI and flow changes to checkout should reduce friction, not leave users hunting through account and workspace surfaces.
  Delivered result:
  Billing now lives primarily in the account dashboard, plan cards can go directly to checkout, billing portal actions accept direct return paths, and checkout success synchronizes credits immediately on return.
- [x] Refine the account billing surface for readability and scan speed
  Why:
  The payment page was showing raw plan-limit objects, the visual treatment was too heavy, and long plan cards forced unnecessary scrolling.
  Delivered result:
  The account billing page now renders structured limit labels correctly, uses a lighter local surface, and collapses plan cards into a direct checkout accordion so users can compare plans without reading through one long static wall.
- [ ] Improve public homepage conversion flow
  Why:
  The audit form and mobile navigation still carry conversion risk when the page gets long.
  Needed result:
  Add progressive disclosure, cleaner mobile navigation behavior, and stronger CTA continuity without making the homepage heavier.

---

## Next Start Order

Start here, in this exact order:

1. Page-level action packs
   Reason:
   This strengthens the real wedge: exact, implementable actioning.

2. Source routing and business-class discovery policies
   Reason:
   Better results depend on knowing which APIs and domain classes belong to each business type before more crawl or recommendation work is added.

3. Runtime stage budgets and caching
   Reason:
   This reduces long wait times without weakening output quality.

4. Executive-level outcome summaries
   Reason:
   The internal command center exists now; the next gap is stakeholder-facing clarity.

5. Homepage conversion cleanup
   Reason:
   The mobile shell and progressive disclosure baseline are present, but the public entry flow still needs refinement.

6. Operational safeguards for heavy SEO work
   Reason:
   The UI is stronger now, so the next production risk is long-running or weak-data jobs under real usage.

---

## Next First Slice

The next work block should be:

### Antigravity UI/Flow Audit

Status: complete

Delivered:

- External Antigravity review captured the current frontend, module, and payment-flow gaps
- The main problems identified were design-system drift, overlong SEO layout, under-built AEO/content surfaces, and checkout friction
- The Antigravity priorities are now merged into this repo plan instead of living as a separate thread

### Block 4: UI Foundation and Payment-Flow Alignment

Status: complete

Delivered:

- Shared UI primitives were added for score pills, progress bars, evidence cards, metric strips, command cards, mobile navigation, and jump navigation
- The SEO workspace now has the long-page navigation and stronger hierarchy required for the current product depth
- The AEO workspace now has a fuller module surface instead of a thin placeholder
- Account and billing responsibilities are more clearly separated from workspace execution
- Checkout and billing portal entry paths are shorter and support cleaner return routing
- Stripe success now reflects credits immediately instead of waiting entirely on webhook timing
- The account billing page now renders plan details correctly, uses a lighter account-specific surface, and collapses plan cards to reduce scroll fatigue while keeping direct checkout on each card

### Block 5: Page-Level Action Packs and Success Criteria

Status: complete

Delivered:

- SEOCampaignEditItem model persists each page-level edit target (page URL, change scope, specific changes, evidence, success criteria, status, completed_at)
- Migration 0010_seocampaignedititem created and applied
- sync_campaign_edit_items() service: idempotent sync from campaign.metadata into edit item rows
- get_action_pack_for_campaign() helper: syncs on first access, returns ordered items
- SEOCampaignActionPackView: GET renders full implementation pack, POST toggles item status or campaign status
- URL: /workspace/seo/campaigns/<pk>/action-pack/
- Template: templates/seo/action_pack_detail.html — breadcrumb, campaign header with progress counter, evidence card with score bar and competitor examples, edit targets with change lists and "Definition of Done" blocks, execution order, rerun validation reminder
- SEO workspace campaign pipeline now shows "View Action Pack" button per campaign
- Execution queue items now surface competitor evidence inline
- plan.md updated with delivered results

### Block 2: Credit Policy Rollout and Upgrade Messaging

Status: complete

Delivered:

- Export, share, and stakeholder-report actions now spend through the same weighted credit policy as audit, SEO, AEO, and content work
- Repeated export/share requests reuse the same charge reference so the user is not charged twice for the same artifact in the same cycle
- SEO refresh now decides whether backlink intelligence should run based on plan access and remaining workspace credits, instead of treating backlink discovery as silently free
- Workspace and SEO screens now explain action cost, current plan fit, and the next plan unlock in operational terms rather than generic upgrade copy
- Project-level credit value is visible in the dashboard through current balance, recent spend, action costs, and per-project work context

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
- A visible workspace credit pool that is spent by weighted task complexity

### Growth

- Serious SMBs and lean teams
- Recurring audits
- Deeper competitor benchmarking
- Content briefs and editorial queue
- Stakeholder reporting and sharing
- More automation and historical depth
- A larger workspace credit pool that can support recurring audits, SEO, AEO, content, exports, and sharing

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
