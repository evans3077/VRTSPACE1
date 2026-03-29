---
name: vrt-space-backend
description: Django backend implementation guidance for VRT SPACE AGENCY. Use when creating apps, models, services, views, forms, admin integrations, Celery tasks, or backend business logic inside the Django monolith. Trigger for backend feature work, refactors, data access changes, service-layer design, and any task that must preserve the project's CBV-plus-services pattern and query-performance rules.
---

# VRT Space Backend

Implement backend work with a thin-view, reusable-service approach.

## Backend Workflow

1. Read `references/01_SYSTEM_ARCHITECTURE.md` to confirm the target app and module boundaries.
2. Read `references/02_BACKEND_DJANGO_GUIDE.md` before implementing views or business logic.
3. Put business rules in service modules, not in templates or oversized views.
4. Keep data access explicit and optimized with `select_related`, `prefetch_related`, and focused queryset methods.
5. Write tests for models and services before treating the feature as done.

## Required Patterns

- Use Django apps that map to the planned domains: `core`, `seo`, `aeo`, `content`, `leads`, `case_studies`, `tools`, and `analytics`.
- Prefer class-based views for page and form handling.
- Keep direct DB access in views limited to simple orchestration.
- Use signals only when the coupling is justified and explicit.
- Design features to be reusable across service pages, tools, and editorial content.

## Delivery Checklist

- Place code in the correct app and module.
- Keep views thin and move branching logic into services.
- Validate inputs and handle failure paths explicitly.
- Check query count and relationship loading for list/detail pages.
- Add or update tests with each backend change.

## References

- `references/01_SYSTEM_ARCHITECTURE.md`: app layout and stack rules
- `references/02_BACKEND_DJANGO_GUIDE.md`: coding standards and view-service-model pattern
