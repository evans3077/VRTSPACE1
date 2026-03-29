# VRT SPACE Execution Plan

## Phase 1: Audit, Scoring, Recommendation Core

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

## Phase 2: Dashboard and Project Layer

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

## Phase 3: Billing and Plan Enforcement

Status: complete

- [x] Keep audit plan visibility live under a temporary free-pass mode until testing and core product development are complete
- [x] Add plans, subscriptions, and usage tracking
- [x] Gate audits, history, and premium recommendation features
- [x] Add webhook-driven payment verification
- [x] Finish live Stripe setup on Render with real `price_...` IDs for `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROWTH`, `STRIPE_PRICE_AUTHORITY`, and `STRIPE_PRICE_ENTERPRISE`

## Phase 4: Automation and Reporting

Status: complete

- [x] Add async audit reruns and recurring reports
- [x] Add notification and change-detection logic
- [x] Make automation plan-aware
- [x] Add a Render-friendly management command for recurring audit processing: `python manage.py process_workspace_schedules`

## Phase 5: AI Content Generation

Status: complete

- [x] Add generated-content models and service layer
- [x] Connect generator inputs to audit and SEO context
- [x] Support reusable page, article, and answer-block outputs

## Working Rule

When a phase step is completed, update this file before starting the next step.

## Deployment Rule

- Database changes must be migration-driven so the schema transfers cleanly to Render PostgreSQL for live testing.
- Geography reporting must use captured request headers and stored submission context, not inferred locations.

## Temporary Product Rule

- Audit tiers and package destinations stay visible during testing, but billing enforcement is deferred until the next product level so user-flow development can finish first.
