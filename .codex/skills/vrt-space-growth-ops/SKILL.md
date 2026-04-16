---
name: vrt-space-growth-ops
description: Growth, lead-capture, quality, performance, security, and deployment guidance for VRT SPACE AGENCY. Use when building forms, audit tools, scoring flows, performance improvements, security hardening, test coverage, Docker and Nginx setup, or release workflows. Trigger for operational work, QA work, infrastructure work, and any change that must protect speed, safety, and zero-downtime delivery.
---

# VRT Space Growth and Ops

Use this skill to keep the platform fast, safe, testable, and conversion-oriented in production.

## Delivery Workflow

1. Read `references/08_LEAD_ENGINE.md` when building conversion flows or tools that collect leads.
2. Read `references/09_PERFORMANCE_ENGINE.md` before shipping templates, assets, or heavier queries.
3. Read `references/10_SECURITY_COMPLIANCE.md` for every form, public endpoint, and data-collection flow.
4. Read `references/11_TESTING_QA.md` before marking the change complete.
5. Read `references/12_DEPLOYMENT_DEVOPS.md` for runtime and deployment expectations.

## Hard Gates

- Every page must expose a meaningful lead path.
- Keep LCP under 2.5 seconds, CLS under 0.1, and TTFB under 500 ms.
- Enforce CSRF protection, rate limiting, input sanitization, and HTTPS-first assumptions.
- Do not collect unnecessary user data.
- Do not ship untested features.

## Release Checklist

- Confirm forms store, score, and notify correctly.
- Confirm caching, asset sizing, and query behavior meet performance targets.
- Confirm security middleware and validation are active.
- Confirm tests cover models, services, and integration paths.
- Confirm deployment changes preserve dev, staging, and production separation and support zero-downtime releases.

## References

- `references/08_LEAD_ENGINE.md`: capture, scoring, and notification intent
- `references/09_PERFORMANCE_ENGINE.md`: performance targets
- `references/10_SECURITY_COMPLIANCE.md`: security and data minimization rules
- `references/11_TESTING_QA.md`: test expectations
- `references/12_DEPLOYMENT_DEVOPS.md`: runtime stack and deployment model
