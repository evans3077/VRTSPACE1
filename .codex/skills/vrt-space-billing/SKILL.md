---
name: vrt-space-billing
description: Billing, subscription, and plan-enforcement guidance for VRT SPACE AGENCY. Use when adding plans, subscriptions, usage tracking, payment flows, or feature gating for the audit platform. Trigger for Stripe or Paystack work, webhook handling, upgrade flows, billing models, and access control tied to plans.
---

# VRT Space Billing

Use this skill when the work decides who can access what, how usage is measured, and how product revenue is enforced safely.

## Billing Workflow

1. Read `../../../01_SYSTEM_ARCHITECTURE.md` before introducing billing structure.
2. Read `../../../06_DATA_MODELS.md` and `../../../07_API_LAYER.md` before defining plan, subscription, usage, or webhook contracts.
3. Read `../../../08_LEAD_ENGINE.md` so billing upgrades and free-tool flows stay aligned with conversion intent.
4. Read `../../../10_SECURITY_COMPLIANCE.md` and `../../../12_DEPLOYMENT_DEVOPS.md` before handling payments or webhooks.
5. Use `../../../prompts/billing_system.md` and `../../../prompts/dashboard_system.md` for the intended SaaS feature-gating direction.

## Current Repo Reality

- There is no billing app or subscription model yet.
- Current access control is limited to public rate limiting and staff-only internal views.
- Use this skill when moving from a lead-gen website into a gated product experience.

## Hard Rules

- Keep billing logic separate from product feature logic, but require product features to consult billing state.
- Verify payments with signed webhooks, never frontend success messages.
- Track usage per billing period with explicit reset rules.
- Keep plan checks in services, decorators, or policy helpers, not scattered through templates.
- Treat payment failures, expired subscriptions, and abuse controls as first-class flows.

## Product Rules

- Model at least plans, subscriptions, and usage ledgers clearly.
- Support upgrade and downgrade behavior without losing customer history.
- Make free-tier limits visible in the UI so upgrade prompts feel earned, not confusing.
- Design for both global and Africa-friendly payment options if the business still wants Stripe plus Paystack.

## Delivery Checklist

- Confirm every protected feature has a single plan-check path.
- Confirm webhook handlers are authenticated and idempotent.
- Confirm usage caps are enforced before expensive audits run.
- Confirm plan state can be surfaced in dashboards and prompts cleanly.
- Confirm tests cover success, failure, downgrade, expiry, and limit exhaustion.

## References

- `../../../01_SYSTEM_ARCHITECTURE.md`: stack and app-boundary rules
- `../../../06_DATA_MODELS.md`: model and field conventions
- `../../../07_API_LAYER.md`: endpoint contracts
- `../../../08_LEAD_ENGINE.md`: conversion and upgrade flow alignment
- `../../../10_SECURITY_COMPLIANCE.md`: payment and webhook safety
- `../../../12_DEPLOYMENT_DEVOPS.md`: deployment expectations
- `../../../prompts/billing_system.md`: product billing direction
- `../../../prompts/dashboard_system.md`: dashboard and feature-lock context
