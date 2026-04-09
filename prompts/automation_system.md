You are a senior Django product engineer and retention-systems architect.

Build an automation system for VRT SPACE AGENCY that turns one-time audits into recurring product value.

---

## OBJECTIVE

Create a system that can:

- rerun audits automatically
- detect important changes
- generate recurring reports
- notify users meaningfully
- support retention and upsell flows

---

## CURRENT PROJECT CONTEXT

The project already has:

- a public audit flow in `apps/tools/views.py`
- audit models and summaries in `apps/tools/`
- lead capture and qualification in `apps/leads/`
- marketing positioning around dashboards, reporting, and retention

The project does not yet have:

- a background job system in use
- notification models
- scheduled report logic
- plan-aware automation controls

Build this as an extension of the current Django monolith.

---

## REQUIRED CAPABILITIES

### 1. Scheduler Layer

Support:

- daily jobs
- weekly jobs
- monthly jobs
- on-demand reruns

Use Celery and Celery Beat or an equivalent async scheduler that fits the existing stack.

---

### 2. Audit Automation

The system should be able to:

- rerun website audits
- compare current and previous results
- store the run outcome
- surface trends over time

---

### 3. Alert Engine

Trigger alerts when:

- scores drop materially
- new critical issues appear
- a major performance or AI visibility regression is detected
- a strong opportunity appears

Each alert should include:

- what changed
- why it matters
- priority
- recommended next action

---

### 4. Notification System

Support channels such as:

- email
- in-app notifications
- future expandable delivery paths

Notifications must be useful and rate-limited.

---

### 5. Reporting System

Generate recurring summaries that include:

- score trends
- key wins
- critical issues
- recommended actions
- upsell or service-fit cues where appropriate

---

### 6. Plan-Aware Execution

Automation must respect subscription or account limits.

Design so that:

- free users can have limited automation
- paid users can have deeper or more frequent automation
- plan checks happen before expensive jobs run

---

### 7. Django Integration

Design models or equivalents for:

- automation logs
- notifications
- report snapshots
- job configuration or schedule settings

Keep scheduling, execution, comparison logic, and delivery separated.

---

### 8. Reliability

The automation layer must support:

- retries
- idempotency
- failure logging
- observability
- safe reprocessing

It must never block the main request cycle.

---

## RULES

- Do not spam users.
- Do not run expensive jobs without guardrails.
- Keep tasks asynchronous.
- Store enough data to explain what ran and what changed.
- Make alerts actionable, not vague.
- Build for extension into dashboard reporting later.

---

## DELIVERABLES

Provide:

1. Django model design
2. task and scheduler architecture
3. alert-threshold logic
4. reporting flow
5. notification flow
6. example service interfaces
7. integration plan with the existing audit engine

---

## PRODUCT THINKING

This system should turn VRT SPACE from:

- a one-time free audit experience

into:

- a retained monitoring product
- a relationship-deepening system
- an upsell and reporting engine

---

Now implement the system cleanly, asynchronously, and in a way that fits the current VRT SPACE codebase.
