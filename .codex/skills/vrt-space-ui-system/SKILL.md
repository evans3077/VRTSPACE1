---
name: vrt-space-ui-system
description: Dashboard and product UI guidance for VRT SPACE AGENCY. Use when building audit result interfaces, client dashboards, scorecards, recommendation cards, upgrade prompts, or HTMX-driven product screens that present complex signals simply. Trigger for SaaS dashboard work, audit UI improvements, reusable product components, and conversion-aware interface decisions.
---

# VRT Space UI System

Use this skill when the work is shaping how users see audit intelligence, not just how the backend computes it.

## UI Workflow

1. Read `../../../03_FRONTEND_UI_UX_GUIDE.md` before designing a new product surface.
2. Read `../../../08_LEAD_ENGINE.md` so the interface keeps a clear conversion path.
3. Read `../../../09_PERFORMANCE_ENGINE.md` before adding heavier interactions.
4. Use `../../../prompts/ui_system.md` and `../../../prompts/dashboard_system.md` for the intended SaaS dashboard and component direction.
5. Preserve existing Django-template and HTMX-first patterns unless the task explicitly changes the stack.

## Current Repo Reality

- Public marketing pages exist in `templates/core/`.
- Audit result interfaces already exist in `templates/tools/audit_result.html` and `templates/tools/agency_audit.html`.
- There is no true customer dashboard yet, so dashboard work should extend the current design language without pretending the SaaS shell already exists.

## Hard Rules

- Keep interfaces fast and light on JavaScript.
- Prefer reusable score cards, recommendation cards, tables, and CTA blocks over page-specific one-offs.
- Make empty states, locked states, and error states explicit.
- Pair every complex data section with an obvious next action.
- Maintain mobile usability even for dense audit tables and score displays.

## Product Rules

- Show score context, not just the number.
- Use progressive disclosure for technical detail so the first screen stays clear.
- Make upgrade prompts and service CTAs feel like a natural continuation of the audit, not random ads.
- Use HTMX or small progressive enhancement where live updates improve the product meaningfully.

## Delivery Checklist

- Confirm the interface can handle no-data, partial-data, and failed-audit states.
- Confirm score and recommendation components are reusable across public and future authenticated views.
- Confirm layout decisions support both agency review and self-serve user comprehension.
- Confirm visual improvements do not damage load time.
- Confirm templates stay readable and maintainable as the dashboard grows.

## References

- `../../../03_FRONTEND_UI_UX_GUIDE.md`: layout and UX rules
- `../../../08_LEAD_ENGINE.md`: conversion and CTA guidance
- `../../../09_PERFORMANCE_ENGINE.md`: frontend performance constraints
- `../../../prompts/ui_system.md`: UI system direction
- `../../../prompts/dashboard_system.md`: dashboard structure direction
