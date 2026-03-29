---
name: vrt-space-automation
description: Automation and retention-system guidance for VRT SPACE AGENCY. Use when building scheduled audits, alerts, recurring reports, background jobs, follow-up workflows, or plan-aware automation around the audit platform. Trigger for Celery work, task orchestration, notifications, report generation, and retention loops.
---

# VRT Space Automation

Use this skill when work moves from one-off actions into scheduled, event-driven, or recurring product behavior.

## Automation Workflow

1. Read `../../../01_SYSTEM_ARCHITECTURE.md` before adding new background-processing structure.
2. Read `../../../08_LEAD_ENGINE.md`, `../../../13_ANALYTICS_TRACKING.md`, and `../../../14_AI_VISIBILITY_SYSTEM.md` to keep automation tied to lead value and reporting.
3. Read `../../../09_PERFORMANCE_ENGINE.md`, `../../../11_TESTING_QA.md`, and `../../../12_DEPLOYMENT_DEVOPS.md` before shipping recurring jobs.
4. Use `../../../prompts/dashboard_system.md` and `../../../prompts/live_intelligent_recommendation_systems.md` for the intended SaaS behavior and user-facing outputs.
5. Design each job to be idempotent, observable, and safe to retry.

## Current Repo Reality

- The public audit flow runs synchronously today from `apps/tools/views.py` into `apps/tools/services.py`.
- There is no notification model, report scheduler, or background job system implemented yet.
- Use this skill when turning the existing audit engine into retained-product behavior instead of a one-time scan.

## Hard Rules

- Run recurring work asynchronously.
- Respect subscription and usage limits before executing heavy work.
- Store enough run state to explain what happened, when it ran, and whether it failed.
- Send meaningful alerts only when change or severity crosses a real threshold.
- Avoid spammy notifications and duplicate task execution.

## Suggested System Boundaries

- Keep audit execution close to `apps/tools` unless a new domain clearly justifies its own app.
- Put user-facing alert history and report summaries where dashboards can query them cheaply.
- Separate task scheduling, execution, comparison logic, and notification delivery.
- Build diffing and threshold logic as reusable services rather than embedding it in tasks.

## Delivery Checklist

- Confirm each automation has a trigger, guardrail, retry policy, and stored result.
- Confirm failure paths do not block normal request handling.
- Confirm alerts map to concrete user action or agency follow-up.
- Confirm tests cover idempotency, retries, and threshold logic.
- Confirm the system can grow from weekly audits to richer monitoring without a rewrite.

## References

- `../../../01_SYSTEM_ARCHITECTURE.md`: stack and app-boundary rules
- `../../../08_LEAD_ENGINE.md`: lead and conversion intent
- `../../../09_PERFORMANCE_ENGINE.md`: runtime and performance targets
- `../../../11_TESTING_QA.md`: testing expectations
- `../../../12_DEPLOYMENT_DEVOPS.md`: deployment expectations for async work
- `../../../13_ANALYTICS_TRACKING.md`: tracking and reporting signals
- `../../../14_AI_VISIBILITY_SYSTEM.md`: monitoring direction
- `../../../prompts/dashboard_system.md`: future dashboard behavior
- `../../../prompts/live_intelligent_recommendation_systems.md`: live recommendation and progressive rendering direction
