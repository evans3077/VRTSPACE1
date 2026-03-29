# VRT SPACE Execution Plan

## Phase 1: Audit, Scoring, Recommendation Core

Status: in progress

- [x] Review the current audit engine, scoring flow, and recommendation output
- [x] Identify the first high-value correction and refactor target
- [x] Split scoring logic out of `apps/tools/services.py`
- [x] Split recommendation and summary shaping out of `apps/tools/services.py`
- [x] Fix score fallbacks so missing PageSpeed data does not zero out performance
- [x] Add tests for score calculation and ranked recommendations
- [ ] Run Python test suite locally once a Python runtime is available in the environment

## Phase 2: Dashboard and Project Layer

Status: pending

- [ ] Define project/client entities on top of audit history
- [ ] Build a real dashboard surface for score history and recommendations
- [ ] Expose stable summary contracts for dashboard views

## Phase 3: Billing and Plan Enforcement

Status: pending

- [ ] Add plans, subscriptions, and usage tracking
- [ ] Gate audits, history, and premium recommendation features
- [ ] Add webhook-driven payment verification

## Phase 4: Automation and Reporting

Status: pending

- [ ] Add async audit reruns and recurring reports
- [ ] Add notification and change-detection logic
- [ ] Make automation plan-aware

## Phase 5: AI Content Generation

Status: pending

- [ ] Add generated-content models and service layer
- [ ] Connect generator inputs to audit and SEO context
- [ ] Support reusable page, article, and answer-block outputs

## Working Rule

When a phase step is completed, update this file before starting the next step.
