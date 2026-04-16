# Current Build Status

## Implemented Now

- Marketing-site content and service architecture live in `apps/core/views.py` and `apps/core/site_content.py`.
- Lead capture, lead scoring, and audit-request qualification live in `apps/leads/`.
- A public website audit engine already exists in `apps/tools/services.py` with models in `apps/tools/models.py`.
- Audit result presentation already exists in `templates/tools/audit_result.html` and `templates/tools/agency_audit.html`.

## Partially Implemented

- Scoring exists, but it is still embedded directly inside service-layer audit logic and should be treated as an evolving engine rather than a finished scoring platform.
- The site messaging already sells dashboards, automation, and retention systems, but the underlying product systems are not fully built yet.

## Planned Next

- Billing and subscription enforcement
- Scheduled automation, alerts, and recurring reports
- A fuller SaaS dashboard and project system
- AI content-generation workflows
- More explicit scoring, trend tracking, and recommendation explainability

## Prompt Folder Guidance

- Files in `prompts/` are product-direction documents, not proof that the feature already exists.
- When implementing from prompts, reconcile them against the current repo first.
- Prefer extending the existing Django monolith and current app boundaries over inventing a parallel architecture.
